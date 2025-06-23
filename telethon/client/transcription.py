"""
Voice Message Transcription Methods for Telethon

This module implements the Basic Transcription Manager functionality
as part of Epic 1: Core Infrastructure & Raw API Support.

Features:
- High-level transcription methods for TelegramClient
- Automatic state management and update handling
- Progress tracking and completion callbacks
- Error handling and retry logic
- Integration with existing Telethon patterns
"""

import asyncio
import logging
import weakref
import gc
from typing import Optional, Union, Callable, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .. import functions, types, utils, hints
from ..tl.custom import Message
from .voice_errors import (
    VoiceTranscriptionError,
    InvalidMessageError,
    InvalidPeerError,
    TranscriptionTimeoutError,
    TranscriptionQuotaExceededError,
    TranscriptionNotAvailableError,
    TranscriptionRequestError,
    StateManagementError,
    TranscriptionMemoryError,
    ErrorHandler,
    ErrorContext,
    create_error_context,
    handle_transcription_errors,
    attempt_recovery
)

logger = logging.getLogger(__name__)


class CleanupStrategy(Enum):
    """Cleanup strategy types for transcription states"""
    AGE_BASED = "age_based"          # Clean by age (TTL)
    COUNT_BASED = "count_based"      # Clean oldest when count exceeded
    MEMORY_BASED = "memory_based"    # Clean when memory pressure detected
    HYBRID = "hybrid"                # Combination of strategies


@dataclass
class CleanupConfig:
    """Configuration for automatic transcription cleanup"""
    
    # Enable/disable cleanup
    enabled: bool = True
    
    # Age-based cleanup (in seconds)
    completed_ttl: int = 3600        # 1 hour for completed transcriptions
    failed_ttl: int = 1800           # 30 minutes for failed transcriptions
    pending_timeout: int = 300       # 5 minutes for stuck pending transcriptions
    
    # Count-based cleanup
    max_total_states: int = 1000     # Maximum total transcription states
    max_completed_states: int = 500  # Maximum completed states to keep
    cleanup_batch_size: int = 100    # Max states to clean per operation
    
    # Cleanup intervals
    cleanup_interval: int = 300      # Background cleanup every 5 minutes
    background_cleanup: bool = True  # Enable background cleanup task
    
    # Safety settings
    preserve_recent: int = 60        # Never clean states newer than this (seconds)
    max_cleanup_percentage: float = 0.3  # Max percentage of states to clean per run


@dataclass
class CleanupMetrics:
    """Metrics for cleanup operations"""
    total_runs: int = 0
    total_cleaned: int = 0
    last_cleanup: Optional[datetime] = None
    last_cleanup_count: int = 0
    average_cleanup_time: float = 0.0


class TranscriptionMixin:
    """
    Mixin to add voice transcription functionality to TelegramClient.
    
    This mixin provides high-level methods for requesting and managing
    voice message transcriptions using Telegram's Speech-to-Text API.
    """
    
    def __init__(self):
        # Initialize transcription state tracking
        self._transcription_states: Dict[str, 'TranscriptionState'] = {}
        self._transcription_callbacks: Dict[str, list] = {}
        self._transcription_lock = asyncio.Lock()
        
        # Initialize automatic cleanup system
        self._cleanup_config = CleanupConfig()
        self._cleanup_metrics = CleanupMetrics()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False
        
        # Initialize error handler
        self._error_handler = ErrorHandler(logger_name=f"{__name__}.TranscriptionMixin")
        
        # Register update handler for transcription updates
        if hasattr(self, 'add_event_handler'):
            self.add_event_handler(self._handle_transcription_update)
            
        # Start background cleanup if enabled
        if self._cleanup_config.background_cleanup:
            self._start_background_cleanup()
    
    @handle_transcription_errors("transcribe_audio", "TranscriptionMixin")
    async def transcribe_audio(
        self,
        entity: 'hints.EntityLike',
        message: Union[int, Message],
        *,
        wait_for_result: bool = True,
        timeout: float = 30.0,
        callback: Optional[Callable] = None
    ) -> Union[str, 'TranscriptionState']:
        """
        Request transcription of a voice message.
        
        Args:
            entity: The chat containing the message
            message: Message ID or Message object with voice/audio
            wait_for_result: Whether to wait for complete transcription
            timeout: Maximum time to wait for completion (seconds)
            callback: Optional callback for progress updates
            
        Returns:
            Transcribed text if wait_for_result=True, 
            TranscriptionState object otherwise
            
        Raises:
            InvalidMessageError: If message doesn't contain audio
            InvalidPeerError: If peer is invalid
            TranscriptionTimeoutError: If transcription times out
            TranscriptionQuotaExceededError: If quota is exceeded
            TranscriptionRequestError: If transcription request fails
            VoiceTranscriptionError: For other transcription-related errors
        """
        # Create error context
        context = create_error_context(
            operation="transcribe_audio",
            component="TranscriptionMixin",
            msg_id=message.id if hasattr(message, 'id') else message
        )
        
        try:
            # Resolve entity to input peer
            peer = await self.get_input_entity(entity)
            context.peer_id = utils.get_peer_id(peer)
        except Exception as e:
            raise InvalidPeerError(
                peer_id=entity,
                context=context,
                original_error=e
            )
        
        # Extract message ID and validate audio content
        if isinstance(message, int):
            msg_id = message
            # We'll validate the message contains audio during the request
        elif isinstance(message, Message):
            msg_id = message.id
            if not self._is_voice_message(message):
                raise InvalidMessageError(
                    "Message does not contain voice or audio content. "
                    "Only voice messages and audio files can be transcribed.",
                    context=context
                )
        else:
            raise InvalidMessageError(
                "message must be an int (message ID) or Message object",
                context=context
            )
        
        context.msg_id = msg_id
        
        # Create unique key for tracking
        state_key = f"{context.peer_id}:{msg_id}"
        
        async with self._transcription_lock:
            # Check for existing transcription
            if state_key in self._transcription_states:
                existing_state = self._transcription_states[state_key]
                if existing_state.is_active:
                    logger.info(f"Reusing existing transcription: {state_key}")
                    if callback:
                        self._add_callback(state_key, callback)
                    
                    if wait_for_result:
                        return await self._wait_for_transcription(
                            existing_state, timeout, context
                        )
                    return existing_state
            
            # Create new transcription state
            state = TranscriptionState(
                peer_id=context.peer_id,
                msg_id=msg_id,
                created_at=datetime.utcnow()
            )
            
            # Store state and callback
            self._transcription_states[state_key] = state
            if callback:
                self._add_callback(state_key, callback)
        
        try:
            # Send transcription request
            logger.info(f"Requesting transcription for {state_key}")
            result = await self(functions.messages.TranscribeAudioRequest(
                peer=peer,
                msg_id=msg_id
            ))
            
            # Update state with initial response
            async with self._transcription_lock:
                state.update_from_result(result)
                context.transcription_id = state.transcription_id
                
                # Check for quota issues
                if hasattr(result, 'trial_remains_num') and result.trial_remains_num == 0:
                    raise TranscriptionQuotaExceededError(
                        trial_remains=result.trial_remains_num,
                        trial_expires=result.trial_remains_until_date,
                        context=context
                    )
                
            logger.info(
                f"Transcription initiated: {state_key}, "
                f"ID: {state.transcription_id}, "
                f"Pending: {state.pending}"
            )
            
            # Wait for completion if requested
            if wait_for_result:
                return await self._wait_for_transcription(state, timeout, context)
            
            return state
            
        except VoiceTranscriptionError:
            # Already classified, just reraise
            raise
        except Exception as e:
            # Mark state as failed
            async with self._transcription_lock:
                if state_key in self._transcription_states:
                    self._transcription_states[state_key].mark_failed(str(e))
                
            # Let the decorator handle the error classification
            raise
    
    @handle_transcription_errors("get_transcription_status", "TranscriptionMixin", reraise=False, default_return=None)
    async def get_transcription_status(
        self,
        entity: 'hints.EntityLike',
        message: Union[int, Message]
    ) -> Optional['TranscriptionState']:
        """
        Get the current status of a transcription.
        
        Args:
            entity: The chat containing the message
            message: Message ID or Message object
            
        Returns:
            TranscriptionState if found, None otherwise
        """
        context = create_error_context(
            operation="get_transcription_status",
            component="TranscriptionMixin",
            msg_id=message.id if hasattr(message, 'id') else message
        )
        
        peer = await self.get_input_entity(entity)
        msg_id = message.id if isinstance(message, Message) else message
        context.peer_id = utils.get_peer_id(peer)
        context.msg_id = msg_id
        
        state_key = f"{context.peer_id}:{msg_id}"
        
        async with self._transcription_lock:
            return self._transcription_states.get(state_key)
    
    @handle_transcription_errors("rate_transcription", "TranscriptionMixin", reraise=False, default_return=False)
    async def rate_transcription(
        self,
        entity: 'hints.EntityLike',
        message: Union[int, Message],
        transcription_id: int,
        good: bool
    ) -> bool:
        """
        Rate the quality of a transcription.
        
        Args:
            entity: The chat containing the message
            message: Message ID or Message object
            transcription_id: ID of the transcription to rate
            good: True if transcription was accurate, False otherwise
            
        Returns:
            True if rating was submitted successfully
        """
        context = create_error_context(
            operation="rate_transcription",
            component="TranscriptionMixin",
            msg_id=message.id if hasattr(message, 'id') else message,
            transcription_id=transcription_id
        )
        
        peer = await self.get_input_entity(entity)
        msg_id = message.id if isinstance(message, Message) else message
        context.peer_id = utils.get_peer_id(peer)
        context.msg_id = msg_id
        
        result = await self(functions.messages.RateTranscribedAudioRequest(
            peer=peer,
            msg_id=msg_id,
            transcription_id=transcription_id,
            good=good
        ))
        
        logger.info(
            f"Rated transcription {transcription_id} as "
            f"{'good' if good else 'bad'}: {result}"
        )
        return bool(result)
    
    def _is_voice_message(self, message: Message) -> bool:
        """Check if message contains voice or audio content."""
        if not message.media:
            return False
            
        if isinstance(message.media, types.MessageMediaDocument):
            document = message.media.document
            if hasattr(document, 'mime_type'):
                # Check for voice notes and audio files
                return (
                    document.mime_type.startswith('audio/') or
                    any(isinstance(attr, types.DocumentAttributeAudio) 
                        and getattr(attr, 'voice', False) 
                        for attr in document.attributes)
                )
        
        return False
    
    def _add_callback(self, state_key: str, callback: Callable):
        """Add a callback for transcription updates."""
        if state_key not in self._transcription_callbacks:
            self._transcription_callbacks[state_key] = []
        self._transcription_callbacks[state_key].append(callback)
    
    async def _wait_for_transcription(
        self, 
        state: 'TranscriptionState', 
        timeout: float,
        context: Optional[ErrorContext] = None
    ) -> str:
        """Wait for transcription completion and return the text."""
        start_time = asyncio.get_event_loop().time()
        
        while state.is_active:
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TranscriptionTimeoutError(
                    operation="wait_for_transcription",
                    timeout_seconds=timeout,
                    context=context
                )
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
        
        if state.failed:
            raise TranscriptionRequestError(
                f"Transcription failed: {state.error}",
                context=context
            )
        
        return state.text
    
    async def _handle_transcription_update(self, update):
        """Handle incoming transcription updates."""
        if not isinstance(update, types.UpdateTranscribedAudio):
            return
        
        state_key = f"{update.peer.user_id if hasattr(update.peer, 'user_id') else utils.get_peer_id(update.peer)}:{update.msg_id}"
        
        async with self._transcription_lock:
            if state_key not in self._transcription_states:
                logger.warning(f"Received update for unknown transcription: {state_key}")
                return
            
            state = self._transcription_states[state_key]
            
            # Update state
            old_text = state.text
            state.update_from_update(update)
            
            logger.debug(
                f"Transcription update: {state_key}, "
                f"pending: {state.pending}, "
                f"text_length: {len(state.text)}"
            )
            
            # Call progress callbacks
            callbacks = self._transcription_callbacks.get(state_key, [])
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(state, old_text)
                    else:
                        callback(state, old_text)
                except Exception as e:
                    logger.error(f"Error in transcription callback: {e}")
            
            # Clean up completed transcriptions
            if not state.is_active:
                self._cleanup_transcription(state_key)
    
    def _cleanup_transcription(self, state_key: str):
        """Clean up a completed transcription."""
        # Remove callbacks
        self._transcription_callbacks.pop(state_key, None)
        
        # Schedule automatic cleanup if not active
        if state_key in self._transcription_states:
            state = self._transcription_states[state_key]
            if not state.is_active:
                # Trigger cleanup after delay to allow status queries
                asyncio.create_task(self._schedule_state_cleanup(state_key, delay=self._cleanup_config.preserve_recent))
    
    # ========================================================================
    # AUTOMATIC CLEANUP SYSTEM
    # ========================================================================
    
    def configure_cleanup(self, config: CleanupConfig):
        """Configure the automatic cleanup system."""
        self._cleanup_config = config
        
        # Restart background cleanup if config changed
        if config.background_cleanup and not self._cleanup_running:
            self._start_background_cleanup()
        elif not config.background_cleanup and self._cleanup_running:
            self._stop_background_cleanup()
    
    def get_cleanup_metrics(self) -> CleanupMetrics:
        """Get cleanup metrics."""
        return self._cleanup_metrics
    
    def get_cleanup_status(self) -> Dict[str, Any]:
        """Get current cleanup system status."""
        return {
            'enabled': self._cleanup_config.enabled,
            'background_running': self._cleanup_running,
            'total_states': len(self._transcription_states),
            'metrics': {
                'total_runs': self._cleanup_metrics.total_runs,
                'total_cleaned': self._cleanup_metrics.total_cleaned,
                'last_cleanup': self._cleanup_metrics.last_cleanup.isoformat() if self._cleanup_metrics.last_cleanup else None,
                'last_cleanup_count': self._cleanup_metrics.last_cleanup_count,
                'average_cleanup_time': self._cleanup_metrics.average_cleanup_time
            },
            'config': {
                'completed_ttl': self._cleanup_config.completed_ttl,
                'failed_ttl': self._cleanup_config.failed_ttl,
                'max_total_states': self._cleanup_config.max_total_states,
                'cleanup_interval': self._cleanup_config.cleanup_interval
            }
        }
    
    async def trigger_cleanup(self, strategy: CleanupStrategy = CleanupStrategy.HYBRID) -> Dict[str, Any]:
        """Manually trigger cleanup operation."""
        if not self._cleanup_config.enabled:
            return {'success': False, 'error': 'Cleanup disabled'}
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            cleaned_count = await self._perform_cleanup(strategy)
            
            duration = asyncio.get_event_loop().time() - start_time
            
            # Update metrics
            self._cleanup_metrics.total_runs += 1
            self._cleanup_metrics.total_cleaned += cleaned_count
            self._cleanup_metrics.last_cleanup = datetime.utcnow()
            self._cleanup_metrics.last_cleanup_count = cleaned_count
            
            # Update average cleanup time
            if self._cleanup_metrics.total_runs > 1:
                self._cleanup_metrics.average_cleanup_time = (
                    (self._cleanup_metrics.average_cleanup_time * (self._cleanup_metrics.total_runs - 1) + duration) 
                    / self._cleanup_metrics.total_runs
                )
            else:
                self._cleanup_metrics.average_cleanup_time = duration
            
            logger.info(f"Manual cleanup completed: {cleaned_count} states cleaned in {duration:.2f}s")
            
            return {
                'success': True,
                'strategy': strategy.value,
                'cleaned_count': cleaned_count,
                'duration': duration,
                'total_states_remaining': len(self._transcription_states)
            }
            
        except Exception as e:
            logger.error(f"Manual cleanup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _start_background_cleanup(self):
        """Start background cleanup task."""
        if self._cleanup_running:
            return
            
        self._cleanup_running = True
        self._cleanup_task = asyncio.create_task(self._background_cleanup_loop())
        logger.info("Background transcription cleanup started")
    
    def _stop_background_cleanup(self):
        """Stop background cleanup task."""
        if not self._cleanup_running:
            return
            
        self._cleanup_running = False
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        logger.info("Background transcription cleanup stopped")
    
    async def _background_cleanup_loop(self):
        """Background cleanup loop."""
        try:
            while self._cleanup_running:
                try:
                    # Wait for cleanup interval
                    await asyncio.sleep(self._cleanup_config.cleanup_interval)
                    
                    if not self._cleanup_running or not self._cleanup_config.enabled:
                        continue
                    
                    # Perform automatic cleanup
                    if await self._should_perform_cleanup():
                        cleaned_count = await self._perform_cleanup(CleanupStrategy.HYBRID)
                        
                        if cleaned_count > 0:
                            logger.debug(f"Background cleanup: {cleaned_count} states cleaned")
                            
                            # Update metrics
                            self._cleanup_metrics.total_runs += 1
                            self._cleanup_metrics.total_cleaned += cleaned_count
                            self._cleanup_metrics.last_cleanup = datetime.utcnow()
                            self._cleanup_metrics.last_cleanup_count = cleaned_count
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in background cleanup: {e}")
                    # Continue running despite errors
                    
        except asyncio.CancelledError:
            logger.debug("Background cleanup cancelled")
        finally:
            self._cleanup_running = False
    
    async def _should_perform_cleanup(self) -> bool:
        """Check if cleanup should be performed."""
        total_states = len(self._transcription_states)
        
        # Check total state limit
        if total_states > self._cleanup_config.max_total_states:
            return True
        
        # Check completed state limit
        completed_states = sum(
            1 for state in self._transcription_states.values() 
            if not state.is_active
        )
        
        if completed_states > self._cleanup_config.max_completed_states:
            return True
        
        # Always perform some cleanup periodically
        return total_states > 10  # Only if we have some states to potentially clean
    
    async def _perform_cleanup(self, strategy: CleanupStrategy) -> int:
        """Perform cleanup operation."""
        async with self._transcription_lock:
            if strategy == CleanupStrategy.AGE_BASED:
                return self._age_based_cleanup()
            elif strategy == CleanupStrategy.COUNT_BASED:
                return self._count_based_cleanup()
            elif strategy == CleanupStrategy.MEMORY_BASED:
                return self._memory_based_cleanup()
            elif strategy == CleanupStrategy.HYBRID:
                return self._hybrid_cleanup()
            else:
                return 0
    
    def _age_based_cleanup(self) -> int:
        """Clean up transcriptions based on age."""
        current_time = datetime.utcnow()
        cleaned_count = 0
        
        states_to_remove = []
        
        for state_key, state in self._transcription_states.items():
            age = (current_time - state.created_at).total_seconds()
            
            # Skip recent states
            if age < self._cleanup_config.preserve_recent:
                continue
            
            should_clean = False
            
            # Clean completed states
            if state.is_completed and age > self._cleanup_config.completed_ttl:
                should_clean = True
            
            # Clean failed states
            elif state.failed and age > self._cleanup_config.failed_ttl:
                should_clean = True
            
            # Clean stuck pending states
            elif state.pending and age > self._cleanup_config.pending_timeout:
                should_clean = True
                logger.warning(f"Cleaning stuck pending transcription: {state_key}")
            
            if should_clean:
                states_to_remove.append(state_key)
        
        # Remove the states
        for state_key in states_to_remove:
            self._remove_transcription_state(state_key)
            cleaned_count += 1
            
            # Respect batch size limit
            if cleaned_count >= self._cleanup_config.cleanup_batch_size:
                break
        
        return cleaned_count
    
    def _count_based_cleanup(self) -> int:
        """Clean up transcriptions based on count limits."""
        total_states = len(self._transcription_states)
        
        if total_states <= self._cleanup_config.max_total_states:
            return 0
        
        # Calculate how many to clean
        target_count = int(self._cleanup_config.max_total_states * 0.8)
        to_clean = min(
            total_states - target_count,
            self._cleanup_config.cleanup_batch_size,
            int(total_states * self._cleanup_config.max_cleanup_percentage)
        )
        
        if to_clean <= 0:
            return 0
        
        # Get oldest non-active states
        inactive_states = [
            (key, state) for key, state in self._transcription_states.items()
            if not state.is_active and self._is_safe_to_clean(state)
        ]
        
        # Sort by creation time (oldest first)
        inactive_states.sort(key=lambda x: x[1].created_at)
        
        # Remove oldest states
        cleaned_count = 0
        for state_key, state in inactive_states[:to_clean]:
            self._remove_transcription_state(state_key)
            cleaned_count += 1
        
        return cleaned_count
    
    def _memory_based_cleanup(self) -> int:
        """Clean up transcriptions based on memory pressure."""
        # Simplified memory-based cleanup
        # In a real implementation, this would check actual memory usage
        total_states = len(self._transcription_states)
        
        if total_states < 100:  # Arbitrary threshold
            return 0
        
        # Clean a portion of completed states
        max_to_clean = max(1, int(total_states * 0.1))  # Clean up to 10%
        
        completed_states = [
            (key, state) for key, state in self._transcription_states.items()
            if state.is_completed and self._is_safe_to_clean(state)
        ]
        
        # Sort by last update (oldest first)
        completed_states.sort(key=lambda x: x[1].last_update)
        
        cleaned_count = 0
        for state_key, state in completed_states[:max_to_clean]:
            self._remove_transcription_state(state_key)
            cleaned_count += 1
        
        return cleaned_count
    
    def _hybrid_cleanup(self) -> int:
        """Perform hybrid cleanup combining strategies."""
        total_cleaned = 0
        
        # First, age-based cleanup for very old states
        total_cleaned += self._age_based_cleanup()
        
        # Then count-based if we still have too many
        if len(self._transcription_states) > self._cleanup_config.max_total_states:
            total_cleaned += self._count_based_cleanup()
        
        # Finally, memory-based if still needed
        if len(self._transcription_states) > self._cleanup_config.max_total_states * 1.2:
            total_cleaned += self._memory_based_cleanup()
        
        return total_cleaned
    
    def _is_safe_to_clean(self, state: 'TranscriptionState') -> bool:
        """Check if a transcription state is safe to clean."""
        # Never clean active states
        if state.is_active:
            return False
        
        # Never clean very recent states
        age = (datetime.utcnow() - state.created_at).total_seconds()
        if age < self._cleanup_config.preserve_recent:
            return False
        
        return True
    
    def _remove_transcription_state(self, state_key: str):
        """Remove a transcription state and associated data."""
        # Remove the state
        if state_key in self._transcription_states:
            del self._transcription_states[state_key]
        
        # Remove callbacks
        if state_key in self._transcription_callbacks:
            del self._transcription_callbacks[state_key]
    
    async def _schedule_state_cleanup(self, state_key: str, delay: int):
        """Schedule cleanup of a specific state after delay."""
        try:
            await asyncio.sleep(delay)
            
            # Check if state still exists and is safe to clean
            if state_key in self._transcription_states:
                state = self._transcription_states[state_key]
                if self._is_safe_to_clean(state):
                    async with self._transcription_lock:
                        self._remove_transcription_state(state_key)
                        logger.debug(f"Scheduled cleanup completed for: {state_key}")
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in scheduled cleanup for {state_key}: {e}")
    
    def cleanup_all_transcriptions(self) -> int:
        """Clean up all non-active transcriptions immediately."""
        cleaned_count = 0
        
        states_to_remove = [
            key for key, state in self._transcription_states.items()
            if not state.is_active
        ]
        
        for state_key in states_to_remove:
            self._remove_transcription_state(state_key)
            cleaned_count += 1
        
        # Force garbage collection
        gc.collect()
        
        logger.info(f"Cleaned up all inactive transcriptions: {cleaned_count} states removed")
        return cleaned_count
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for transcription operations.
        
        Returns:
            Dictionary containing error counts and statistics
        """
        return self._error_handler.get_error_statistics()


class TranscriptionState:
    """
    Represents the state of an active transcription.
    
    This class tracks the progress and status of a voice message
    transcription request throughout its lifecycle.
    """
    
    def __init__(
        self,
        peer_id: int,
        msg_id: int,
        created_at: datetime
    ):
        self.peer_id = peer_id
        self.msg_id = msg_id
        self.created_at = created_at
        
        # Transcription details
        self.transcription_id: Optional[int] = None
        self.text: str = ""
        self.pending: bool = True
        self.failed: bool = False
        self.error: Optional[str] = None
        self.error_type: Optional[str] = None
        
        # Trial information for non-premium users
        self.trial_remains_num: Optional[int] = None
        self.trial_remains_until_date: Optional[datetime] = None
        
        # Progress tracking
        self.last_update: datetime = created_at
        self.update_count: int = 0
    
    @property
    def is_active(self) -> bool:
        """Check if transcription is still active (pending and not failed)."""
        return self.pending and not self.failed
    
    @property
    def is_completed(self) -> bool:
        """Check if transcription is completed successfully."""
        return not self.pending and not self.failed
    
    @property
    def duration(self) -> timedelta:
        """Get the duration since transcription started."""
        return datetime.utcnow() - self.created_at
    
    @property
    def state_key(self) -> str:
        """Get the unique key for this transcription."""
        return f"{self.peer_id}:{self.msg_id}"
    
    def update_from_result(self, result: types.messages.TranscribedAudio):
        """Update state from initial TranscribeAudio response."""
        self.transcription_id = result.transcription_id
        self.text = result.text
        self.pending = getattr(result, 'pending', False)
        
        # Update trial information if present
        if hasattr(result, 'trial_remains_num'):
            self.trial_remains_num = result.trial_remains_num
        if hasattr(result, 'trial_remains_until_date'):
            self.trial_remains_until_date = result.trial_remains_until_date
        
        self.last_update = datetime.utcnow()
        self.update_count += 1
    
    def update_from_update(self, update: types.UpdateTranscribedAudio):
        """Update state from UpdateTranscribedAudio."""
        if update.transcription_id != self.transcription_id:
            logger.warning(
                f"Transcription ID mismatch: expected {self.transcription_id}, "
                f"got {update.transcription_id}"
            )
        
        self.text = update.text
        self.pending = getattr(update, 'pending', False)
        
        self.last_update = datetime.utcnow()
        self.update_count += 1
    
    def mark_failed(self, error: Union[str, Exception]):
        """Mark transcription as failed."""
        self.failed = True
        self.pending = False
        if isinstance(error, Exception):
            self.error = str(error)
            self.error_type = type(error).__name__
        else:
            self.error = error
            self.error_type = None
        self.last_update = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            'peer_id': self.peer_id,
            'msg_id': self.msg_id,
            'transcription_id': self.transcription_id,
            'text': self.text,
            'pending': self.pending,
            'failed': self.failed,
            'error': self.error,
            'error_type': self.error_type,
            'trial_remains_num': self.trial_remains_num,
            'trial_remains_until_date': self.trial_remains_until_date.isoformat() if self.trial_remains_until_date else None,
            'created_at': self.created_at.isoformat(),
            'last_update': self.last_update.isoformat(),
            'update_count': self.update_count
        }
    
    def __repr__(self) -> str:
        status = "pending" if self.pending else ("failed" if self.failed else "completed")
        return (
            f"TranscriptionState({self.peer_id}:{self.msg_id}, "
            f"id={self.transcription_id}, status={status}, "
            f"text_length={len(self.text)})"
        )