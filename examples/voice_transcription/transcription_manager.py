"""
Basic Transcription Manager

This module implements Epic 1 User Story 1.5: Basic Transcription Manager
providing a high-level coordinator for transcription operations with automatic
state tracking, update processing, and concurrent request handling.

Features:
- Clean API for transcription operations
- Automatic request creation and state tracking
- Real-time update processing and state consistency
- Concurrent transcription support
- Comprehensive status queries and statistics
- Integrated error handling and recovery
"""

import asyncio
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import weakref

try:
    from .basic_request import BasicVoiceTranscriber, TranscriptionRequest
    from .state_manager import TranscriptionStateManager, TranscriptionState, TranscriptionStatus
    from .update_handler import VoiceTranscriptionUpdateHandler, UpdateEvent
    from .integration import TranscriptionCoordinator, IntegratedVoiceTranscriber
    from .validation import VoiceMessageValidator
    INTERNAL_IMPORTS = True
except ImportError:
    # Fallback for development
    INTERNAL_IMPORTS = False
    BasicVoiceTranscriber = Any
    TranscriptionRequest = Any
    TranscriptionStateManager = Any
    TranscriptionState = Any
    TranscriptionStatus = Any
    VoiceTranscriptionUpdateHandler = Any
    UpdateEvent = Any
    TranscriptionCoordinator = Any
    IntegratedVoiceTranscriber = Any
    VoiceMessageValidator = Any

try:
    from telethon import TelegramClient
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TelegramClient = Any


logger = logging.getLogger(__name__)


@dataclass
class TranscriptionManagerConfig:
    """Configuration for TranscriptionManager"""
    auto_cleanup_enabled: bool = True
    cleanup_interval: int = 3600  # 1 hour
    max_completed_age: int = 86400  # 24 hours
    concurrent_limit: int = 50  # Max concurrent transcriptions
    default_timeout: float = 30.0  # Default timeout for operations
    retry_attempts: int = 3  # Default retry attempts
    validate_messages: bool = True  # Validate messages before transcription
    enable_statistics: bool = True  # Enable statistics tracking
    log_level: str = "INFO"  # Logging level


@dataclass
class TranscriptionResult:
    """Result of a transcription operation"""
    success: bool
    request: Optional['TranscriptionRequest'] = None
    state: Optional[TranscriptionState] = None
    error: Optional[str] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def transcription_id(self) -> Optional[int]:
        """Get transcription ID from request or state"""
        if self.request and self.request.transcription_id:
            return self.request.transcription_id
        elif self.state and self.state.transcription_id:
            return self.state.transcription_id
        return None
        
    @property
    def text(self) -> str:
        """Get transcribed text"""
        if self.request and self.request.result:
            return self.request.result.text
        elif self.state:
            return self.state.text
        return ""
        
    @property
    def is_completed(self) -> bool:
        """Check if transcription is completed"""
        if self.request:
            return self.request.completed
        elif self.state:
            return self.state.is_completed
        return False


class TranscriptionManager:
    """
    High-level manager for voice transcription operations.
    
    This manager provides a clean, unified API for handling voice transcriptions
    with automatic state tracking, update processing, and concurrent request
    management. It coordinates between all the lower-level components to provide
    a seamless transcription experience.
    """
    
    def __init__(
        self,
        client: 'TelegramClient',
        config: Optional[TranscriptionManagerConfig] = None
    ):
        """
        Initialize the transcription manager.
        
        Args:
            client: Authenticated TelegramClient instance
            config: Optional configuration object
        """
        if not TELETHON_AVAILABLE:
            raise ImportError("Telethon is required for transcription management")
            
        if not INTERNAL_IMPORTS:
            raise ImportError("Required voice transcription modules not available")
            
        self.client = client
        self.config = config or TranscriptionManagerConfig()
        
        # Initialize core components
        self.transcriber = BasicVoiceTranscriber(client)
        self.state_manager = TranscriptionStateManager(
            cleanup_interval=self.config.cleanup_interval,
            max_completed_age=self.config.max_completed_age,
            auto_cleanup=self.config.auto_cleanup_enabled
        )
        self.update_handler = VoiceTranscriptionUpdateHandler(client)
        self.validator = VoiceMessageValidator(client)
        
        # Initialize integration layer
        self.coordinator = TranscriptionCoordinator(self.transcriber, self.update_handler)
        
        # Manager state
        self._active_requests: Dict[str, weakref.ref] = {}
        self._completion_callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._initialized = False
        
        # Statistics
        self.stats = {
            'requests_created': 0,
            'requests_completed': 0,
            'requests_failed': 0,
            'total_processing_time': 0.0,
            'peak_concurrent': 0,
            'start_time': datetime.now(timezone.utc)
        }
        
        # Configure logging
        if self.config.log_level:
            logging.getLogger(__name__).setLevel(getattr(logging, self.config.log_level.upper()))
            
    async def initialize(self):
        """Initialize the manager and start all components"""
        if self._initialized:
            logger.warning("Manager already initialized")
            return
            
        try:
            # Start update handling
            self.update_handler.start()
            
            # Register manager-level update handler
            self.update_handler.register_handler(
                "transcription_manager",
                self._handle_transcription_update,
                priority=50  # Medium priority
            )
            
            # Add state change observer
            self.state_manager.add_observer(self._handle_state_change)
            
            self._initialized = True
            logger.info("Transcription manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize transcription manager: {e}")
            raise
            
    async def shutdown(self):
        """Shutdown the manager and clean up resources"""
        if not self._initialized:
            return
            
        try:
            # Stop update handling
            self.update_handler.stop()
            
            # Clean up active requests
            with self._lock:
                self._active_requests.clear()
                self._completion_callbacks.clear()
                
            # Final cleanup
            if self.config.auto_cleanup_enabled:
                self.state_manager.cleanup_old_transcriptions()
                
            self._initialized = False
            logger.info("Transcription manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during manager shutdown: {e}")
            
    async def transcribe(
        self,
        chat: Any,
        msg_id: int,
        wait_for_completion: bool = False,
        timeout: Optional[float] = None,
        completion_callback: Optional[Callable] = None,
        validate: Optional[bool] = None,
        retry_attempts: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TranscriptionResult:
        """
        Transcribe a voice message with comprehensive management.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID of the voice message
            wait_for_completion: Whether to wait for completion
            timeout: Timeout for waiting (uses config default if None)
            completion_callback: Callback for completion notifications
            validate: Whether to validate message (uses config default if None)
            retry_attempts: Number of retry attempts (uses config default if None)
            metadata: Additional metadata to store with transcription
            
        Returns:
            TranscriptionResult object with operation details
        """
        if not self._initialized:
            await self.initialize()
            
        start_time = asyncio.get_event_loop().time()
        
        # Use config defaults
        if timeout is None:
            timeout = self.config.default_timeout
        if validate is None:
            validate = self.config.validate_messages
        if retry_attempts is None:
            retry_attempts = self.config.retry_attempts
            
        try:
            # Check concurrent limit
            await self._check_concurrent_limit()
            
            # Get peer information
            peer_id = await self._get_peer_id(chat)
            state_key = f"{peer_id}:{msg_id}"
            
            # Check for existing transcription
            existing_state = self.state_manager.get_transcription(peer_id, msg_id)
            if existing_state and existing_state.is_active:
                logger.info(f"Found existing active transcription: {state_key}")
                return TranscriptionResult(
                    success=True,
                    state=existing_state,
                    metadata={'reused_existing': True}
                )
                
            # Create state first
            state = self.state_manager.create_transcription(
                peer_id=peer_id,
                msg_id=msg_id,
                metadata=metadata or {}
            )
            
            # Create transcription request
            request = await self.transcriber.transcribe(
                chat=chat,
                msg_id=msg_id,
                validate=validate,
                wait_for_completion=False,  # We handle waiting ourselves
                timeout=timeout
            )
            
            # Link request with state
            await self._link_request_and_state(request, state)
            
            # Register for coordination
            self.coordinator.register_request(request, completion_callback)
            
            # Track active request
            with self._lock:
                self._active_requests[state_key] = weakref.ref(request)
                if completion_callback:
                    if state_key not in self._completion_callbacks:
                        self._completion_callbacks[state_key] = []
                    self._completion_callbacks[state_key].append(completion_callback)
                    
                # Update statistics
                self.stats['requests_created'] += 1
                current_active = len(self._active_requests)
                if current_active > self.stats['peak_concurrent']:
                    self.stats['peak_concurrent'] = current_active
                    
            logger.info(f"Created transcription request: {state_key}")
            
            # Wait for completion if requested
            if wait_for_completion:
                await self._wait_for_completion(request, state, timeout, retry_attempts)
                
            # Calculate duration
            duration = asyncio.get_event_loop().time() - start_time
            
            return TranscriptionResult(
                success=True,
                request=request,
                state=state,
                duration=duration,
                metadata={'created_new': True}
            )
            
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            self.stats['requests_failed'] += 1
            
            logger.error(f"Transcription failed for {chat}:{msg_id}: {e}")
            return TranscriptionResult(
                success=False,
                error=str(e),
                duration=duration
            )
            
    async def get_transcription_status(
        self,
        chat: Any,
        msg_id: int
    ) -> Optional[TranscriptionState]:
        """
        Get the current status of a transcription.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID
            
        Returns:
            TranscriptionState if found, None otherwise
        """
        try:
            peer_id = await self._get_peer_id(chat)
            return self.state_manager.get_transcription(peer_id, msg_id)
        except Exception as e:
            logger.error(f"Failed to get transcription status: {e}")
            return None
            
    async def cancel_transcription(
        self,
        chat: Any,
        msg_id: int
    ) -> bool:
        """
        Cancel an active transcription.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID
            
        Returns:
            True if cancelled successfully
        """
        try:
            peer_id = await self._get_peer_id(chat)
            state_key = f"{peer_id}:{msg_id}"
            
            # Mark state as failed
            state = self.state_manager.mark_transcription_failed(
                peer_id, msg_id, "Cancelled by user"
            )
            
            # Clean up active request
            with self._lock:
                if state_key in self._active_requests:
                    del self._active_requests[state_key]
                if state_key in self._completion_callbacks:
                    del self._completion_callbacks[state_key]
                    
            logger.info(f"Cancelled transcription: {state_key}")
            return state is not None
            
        except Exception as e:
            logger.error(f"Failed to cancel transcription: {e}")
            return False
            
    def get_active_transcriptions(self) -> List[TranscriptionState]:
        """Get all active transcriptions"""
        return self.state_manager.get_active_transcriptions()
        
    def get_transcriptions_by_chat(self, chat: Any) -> List[TranscriptionState]:
        """Get all transcriptions for a specific chat"""
        try:
            # Note: This is a simplified implementation
            # In reality, we'd need to resolve chat to peer_id
            # For now, assume chat is peer_id
            peer_id = int(chat) if isinstance(chat, (str, int)) else chat
            return self.state_manager.get_transcriptions_by_peer(peer_id)
        except Exception as e:
            logger.error(f"Failed to get transcriptions by chat: {e}")
            return []
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive manager statistics"""
        with self._lock:
            active_count = len([
                ref for ref in self._active_requests.values()
                if ref() is not None
            ])
            
        uptime = datetime.now(timezone.utc) - self.stats['start_time']
        
        manager_stats = {
            **self.stats,
            'active_requests': active_count,
            'uptime_seconds': uptime.total_seconds(),
            'average_processing_time': (
                self.stats['total_processing_time'] / max(1, self.stats['requests_completed'])
            ),
            'success_rate': (
                self.stats['requests_completed'] / 
                max(1, self.stats['requests_completed'] + self.stats['requests_failed']) * 100
            )
        }
        
        return {
            'manager': manager_stats,
            'state_manager': self.state_manager.get_transcription_statistics(),
            'update_handler': self.update_handler.get_comprehensive_stats(),
            'coordinator': self.coordinator.get_coordination_stats()
        }
        
    async def cleanup_completed(self, max_age: Optional[int] = None) -> int:
        """Clean up completed transcriptions"""
        count = self.state_manager.cleanup_old_transcriptions(max_age)
        
        # Clean up dead weak references
        with self._lock:
            dead_keys = [
                key for key, ref in self._active_requests.items()
                if ref() is None
            ]
            for key in dead_keys:
                del self._active_requests[key]
                
        logger.info(f"Cleaned up {count} transcriptions and {len(dead_keys)} dead references")
        return count
        
    def add_global_completion_callback(
        self,
        callback: Callable[[TranscriptionState, str], None]
    ):
        """Add a global callback for all transcription completions"""
        self.state_manager.add_observer(callback)
        
    def remove_global_completion_callback(
        self,
        callback: Callable[[TranscriptionState, str], None]
    ):
        """Remove a global completion callback"""
        self.state_manager.remove_observer(callback)
        
    async def _check_concurrent_limit(self):
        """Check if we're within the concurrent transcription limit"""
        with self._lock:
            active_count = len([
                ref for ref in self._active_requests.values()
                if ref() is not None
            ])
            
        if active_count >= self.config.concurrent_limit:
            raise RuntimeError(
                f"Concurrent transcription limit reached ({self.config.concurrent_limit}). "
                f"Please wait for some transcriptions to complete."
            )
            
    async def _get_peer_id(self, chat: Any) -> int:
        """Get peer ID from chat identifier"""
        # Simplified implementation - in reality would use Telethon's get_input_entity
        if isinstance(chat, int):
            return chat
        elif isinstance(chat, str) and chat.isdigit():
            return int(chat)
        else:
            # For now, just hash the string representation
            return abs(hash(str(chat))) % (10**10)
            
    async def _link_request_and_state(
        self,
        request: 'TranscriptionRequest',
        state: TranscriptionState
    ):
        """Link a request object with its corresponding state"""
        # Update state with request information
        if hasattr(request, 'transcription_id') and request.transcription_id:
            state.transcription_id = request.transcription_id
            
        # Store reference in request for easier access
        if hasattr(request, '_state'):
            request._state = state
            
    async def _wait_for_completion(
        self,
        request: 'TranscriptionRequest',
        state: TranscriptionState,
        timeout: float,
        retry_attempts: int
    ):
        """Wait for transcription completion with retry logic"""
        start_time = asyncio.get_event_loop().time()
        
        for attempt in range(retry_attempts + 1):
            try:
                # Wait for completion
                while not (request.completed or state.is_completed):
                    current_time = asyncio.get_event_loop().time()
                    if current_time - start_time > timeout:
                        if attempt < retry_attempts:
                            logger.warning(f"Transcription timeout, retrying... (attempt {attempt + 1})")
                            break
                        else:
                            raise TimeoutError(f"Transcription timeout after {timeout}s")
                            
                    await asyncio.sleep(0.1)
                    
                # Check if completed successfully
                if request.completed or state.is_completed:
                    duration = asyncio.get_event_loop().time() - start_time
                    self.stats['requests_completed'] += 1
                    self.stats['total_processing_time'] += duration
                    return
                    
            except Exception as e:
                if attempt < retry_attempts:
                    logger.warning(f"Transcription attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1.0)  # Wait before retry
                else:
                    raise
                    
    async def _handle_transcription_update(self, update_event: UpdateEvent):
        """Handle transcription updates at the manager level"""
        try:
            state_key = f"{update_event.peer_id}:{update_event.msg_id}"
            
            # Update our tracking
            with self._lock:
                if state_key in self._active_requests:
                    request_ref = self._active_requests[state_key]
                    request = request_ref()
                    
                    if request is not None:
                        # Update request object if needed
                        if not request.transcription_id:
                            request.transcription_id = update_event.transcription_id
                            
                        # If completed, clean up
                        if update_event.is_completion:
                            self._cleanup_completed_request(state_key)
                            
        except Exception as e:
            logger.error(f"Error handling transcription update: {e}")
            
    def _handle_state_change(self, state: TranscriptionState, event_type: str):
        """Handle state changes from the state manager"""
        try:
            if 'completed' in event_type.lower() or 'failed' in event_type.lower():
                self._cleanup_completed_request(state.state_key)
                
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
            
    def _cleanup_completed_request(self, state_key: str):
        """Clean up a completed request"""
        with self._lock:
            # Call completion callbacks
            if state_key in self._completion_callbacks:
                callbacks = self._completion_callbacks[state_key]
                for callback in callbacks:
                    try:
                        # Get current state
                        peer_id, msg_id = state_key.split(':')
                        state = self.state_manager.get_transcription(int(peer_id), int(msg_id))
                        
                        if asyncio.iscoroutinefunction(callback):
                            asyncio.create_task(callback(state, 'completed'))
                        else:
                            callback(state, 'completed')
                    except Exception as e:
                        logger.error(f"Error in completion callback: {e}")
                        
                del self._completion_callbacks[state_key]
                
            # Remove from active requests
            if state_key in self._active_requests:
                del self._active_requests[state_key]
                
        logger.debug(f"Cleaned up completed request: {state_key}")


# Example usage
async def example_transcription_manager():
    """Example of how to use the TranscriptionManager"""
    
    client = None  # Placeholder - would be real TelegramClient
    
    # Create manager with custom config
    config = TranscriptionManagerConfig(
        concurrent_limit=10,
        default_timeout=45.0,
        validate_messages=True
    )
    
    manager = TranscriptionManager(client, config)
    await manager.initialize()
    
    try:
        # Simple transcription
        result = await manager.transcribe(
            chat='me',
            msg_id=12345,
            wait_for_completion=True
        )
        
        if result.success:
            print(f"Transcription: {result.text}")
        else:
            print(f"Failed: {result.error}")
            
        # Check status
        status = await manager.get_transcription_status('me', 12345)
        if status:
            print(f"Status: {status.status.value}")
            
        # Get statistics
        stats = manager.get_statistics()
        print(f"Manager stats: {stats['manager']}")
        
        # Cleanup
        cleaned = await manager.cleanup_completed()
        print(f"Cleaned up {cleaned} transcriptions")
        
    finally:
        await manager.shutdown()


if __name__ == "__main__":
    print("Voice Transcription Manager")
    print("See example_transcription_manager() function for usage patterns")
    asyncio.run(example_transcription_manager())