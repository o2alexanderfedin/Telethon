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
from typing import Optional, Union, Callable, Dict, Any
from datetime import datetime, timedelta

from .. import functions, types, utils, hints
from ..tl.custom import Message

logger = logging.getLogger(__name__)


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
        
        # Register update handler for transcription updates
        if hasattr(self, 'add_event_handler'):
            self.add_event_handler(self._handle_transcription_update)
    
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
            ValueError: If message doesn't contain audio
            TimeoutError: If transcription times out
            RuntimeError: If transcription fails
        """
        # Resolve entity to input peer
        peer = await self.get_input_entity(entity)
        
        # Extract message ID and validate audio content
        if isinstance(message, int):
            msg_id = message
            # We'll validate the message contains audio during the request
        elif isinstance(message, Message):
            msg_id = message.id
            if not self._is_voice_message(message):
                raise ValueError(
                    "Message does not contain voice or audio content. "
                    "Only voice messages and audio files can be transcribed."
                )
        else:
            raise TypeError("message must be an int (message ID) or Message object")
        
        # Create unique key for tracking
        state_key = f"{utils.get_peer_id(peer)}:{msg_id}"
        
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
                            existing_state, timeout
                        )
                    return existing_state
            
            # Create new transcription state
            state = TranscriptionState(
                peer_id=utils.get_peer_id(peer),
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
                
            logger.info(
                f"Transcription initiated: {state_key}, "
                f"ID: {state.transcription_id}, "
                f"Pending: {state.pending}"
            )
            
            # Wait for completion if requested
            if wait_for_result:
                return await self._wait_for_transcription(state, timeout)
            
            return state
            
        except Exception as e:
            # Mark state as failed
            async with self._transcription_lock:
                state.mark_failed(str(e))
                
            logger.error(f"Transcription request failed for {state_key}: {e}")
            raise RuntimeError(f"Failed to request transcription: {e}") from e
    
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
        try:
            peer = await self.get_input_entity(entity)
            msg_id = message.id if isinstance(message, Message) else message
            state_key = f"{utils.get_peer_id(peer)}:{msg_id}"
            
            async with self._transcription_lock:
                return self._transcription_states.get(state_key)
                
        except Exception as e:
            logger.error(f"Failed to get transcription status: {e}")
            return None
    
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
        try:
            peer = await self.get_input_entity(entity)
            msg_id = message.id if isinstance(message, Message) else message
            
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
            
        except Exception as e:
            logger.error(f"Failed to rate transcription: {e}")
            return False
    
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
        timeout: float
    ) -> str:
        """Wait for transcription completion and return the text."""
        start_time = asyncio.get_event_loop().time()
        
        while state.is_active:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(
                    f"Transcription timed out after {timeout} seconds"
                )
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
        
        if state.failed:
            raise RuntimeError(f"Transcription failed: {state.error}")
        
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
        
        # Keep the state for a while for status queries
        # TODO: Implement automatic cleanup after some time


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
    
    def mark_failed(self, error: str):
        """Mark transcription as failed."""
        self.failed = True
        self.pending = False
        self.error = error
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