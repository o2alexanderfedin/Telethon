"""
Integration Layer for Voice Transcription Update Handling

This module integrates the update handling system with the basic request implementation,
providing seamless coordination between transcription requests and update processing.
"""

import asyncio
import logging
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime, timezone, timedelta
import weakref

try:
    from .basic_request import BasicVoiceTranscriber, TranscriptionRequest
    from .update_handler import VoiceTranscriptionUpdateHandler, UpdateEvent
    from .response_parser import ResponseParser, TranscriptionResult
    INTERNAL_IMPORTS = True
except ImportError:
    # Fallback for development
    INTERNAL_IMPORTS = False
    BasicVoiceTranscriber = Any
    TranscriptionRequest = Any
    VoiceTranscriptionUpdateHandler = Any
    UpdateEvent = Any
    ResponseParser = Any
    TranscriptionResult = Any


logger = logging.getLogger(__name__)


class TranscriptionCoordinator:
    """
    Coordinates transcription requests with update handling.
    
    This class bridges the gap between the BasicVoiceTranscriber (which handles
    requests) and the VoiceTranscriptionUpdateHandler (which processes updates),
    providing automatic state synchronization and completion tracking.
    """
    
    def __init__(
        self,
        transcriber: 'BasicVoiceTranscriber',
        update_handler: 'VoiceTranscriptionUpdateHandler'
    ):
        """
        Initialize the coordinator.
        
        Args:
            transcriber: BasicVoiceTranscriber instance
            update_handler: VoiceTranscriptionUpdateHandler instance
        """
        self.transcriber = transcriber
        self.update_handler = update_handler
        self.parser = ResponseParser()
        
        # Weak references to avoid circular references
        self._pending_requests: Dict[str, weakref.ref] = {}
        self._completion_callbacks: Dict[str, List[Callable]] = {}
        
        # Statistics
        self.coordination_stats = {
            'updates_matched': 0,
            'updates_orphaned': 0,
            'requests_completed': 0,
            'coordination_errors': 0
        }
        
        # Register our update handler
        self._register_coordination_handler()
        
    def _register_coordination_handler(self):
        """Register the coordination handler with the update system"""
        self.update_handler.register_handler(
            "transcription_coordinator",
            self._handle_update_coordination,
            priority=100  # High priority to handle before user handlers
        )
        logger.info("Transcription coordinator registered with update handler")
        
    async def _handle_update_coordination(self, update_event: UpdateEvent):
        """Handle update coordination with pending requests"""
        try:
            # Find matching request
            request_key = f"{update_event.peer_id}:{update_event.msg_id}"
            
            # Check if we have a pending request for this update
            if request_key in self._pending_requests:
                request_ref = self._pending_requests[request_key]
                request = request_ref()  # Get the actual object from weak reference
                
                if request is not None:
                    # Update the request with the new information
                    await self._update_request_from_event(request, update_event)
                    self.coordination_stats['updates_matched'] += 1
                    
                    # If transcription is complete, clean up
                    if update_event.is_completion:
                        self._cleanup_completed_request(request_key, request, update_event)
                        
                else:
                    # Request was garbage collected, clean up
                    del self._pending_requests[request_key]
                    
            else:
                # No matching request found
                self.coordination_stats['updates_orphaned'] += 1
                logger.debug(f"Received update for unknown request: {request_key}")
                
        except Exception as e:
            self.coordination_stats['coordination_errors'] += 1
            logger.error(f"Error in update coordination: {e}")
            
    async def _update_request_from_event(
        self,
        request: 'TranscriptionRequest',
        update_event: UpdateEvent
    ):
        """Update a transcription request with information from an update event"""
        
        # Update transcription ID if not set
        if not request.transcription_id:
            request.transcription_id = update_event.transcription_id
            
        # Create or update the result
        if update_event.is_completion:
            # Final result
            request.result = TranscriptionResult(
                transcription_id=update_event.transcription_id,
                text=update_event.text,
                pending=False,
                parsed_at=update_event.processed_at
            )
            request.completed = True
            logger.info(f"Request {request.key} completed via update: {len(update_event.text)} chars")
            
        else:
            # Intermediate update
            request.result = TranscriptionResult(
                transcription_id=update_event.transcription_id,
                text=update_event.text,
                pending=True,
                parsed_at=update_event.processed_at
            )
            logger.debug(f"Request {request.key} updated via update: pending")
            
    def _cleanup_completed_request(
        self,
        request_key: str,
        request: 'TranscriptionRequest',
        update_event: UpdateEvent
    ):
        """Clean up a completed request and call completion callbacks"""
        
        # Call completion callbacks
        if request_key in self._completion_callbacks:
            callbacks = self._completion_callbacks[request_key]
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(request, update_event))
                    else:
                        callback(request, update_event)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")
                    
            # Clean up callbacks
            del self._completion_callbacks[request_key]
            
        # Remove from pending requests
        if request_key in self._pending_requests:
            del self._pending_requests[request_key]
            
        self.coordination_stats['requests_completed'] += 1
        logger.debug(f"Cleaned up completed request: {request_key}")
        
    def register_request(
        self,
        request: 'TranscriptionRequest',
        completion_callback: Optional[Callable] = None
    ):
        """
        Register a request for update coordination.
        
        Args:
            request: TranscriptionRequest to track
            completion_callback: Optional callback for completion
        """
        request_key = request.key
        
        # Store weak reference to avoid keeping requests alive
        self._pending_requests[request_key] = weakref.ref(request)
        
        # Store completion callback if provided
        if completion_callback:
            if request_key not in self._completion_callbacks:
                self._completion_callbacks[request_key] = []
            self._completion_callbacks[request_key].append(completion_callback)
            
        logger.debug(f"Registered request for coordination: {request_key}")
        
    def unregister_request(self, request: 'TranscriptionRequest'):
        """
        Unregister a request from coordination.
        
        Args:
            request: TranscriptionRequest to unregister
        """
        request_key = request.key
        
        if request_key in self._pending_requests:
            del self._pending_requests[request_key]
            
        if request_key in self._completion_callbacks:
            del self._completion_callbacks[request_key]
            
        logger.debug(f"Unregistered request from coordination: {request_key}")
        
    def get_pending_count(self) -> int:
        """Get the number of pending requests"""
        # Clean up dead weak references while counting
        active_count = 0
        dead_keys = []
        
        for key, ref in self._pending_requests.items():
            if ref() is not None:
                active_count += 1
            else:
                dead_keys.append(key)
                
        # Clean up dead references
        for key in dead_keys:
            del self._pending_requests[key]
            
        return active_count
        
    def get_coordination_stats(self) -> Dict[str, Any]:
        """Get coordination statistics"""
        return {
            **self.coordination_stats,
            'pending_requests': self.get_pending_count(),
            'pending_callbacks': len(self._completion_callbacks)
        }


class IntegratedVoiceTranscriber:
    """
    Integrated voice transcriber that combines request handling and update processing.
    
    This is the main class users should interact with for voice transcription,
    providing a unified interface that handles both requests and updates automatically.
    """
    
    def __init__(self, client: 'TelegramClient'):
        """
        Initialize the integrated transcriber.
        
        Args:
            client: Authenticated TelegramClient instance
        """
        if not INTERNAL_IMPORTS:
            raise ImportError("Required voice transcription modules not available")
            
        self.client = client
        self.transcriber = BasicVoiceTranscriber(client)
        self.update_handler = VoiceTranscriptionUpdateHandler(client)
        self.coordinator = TranscriptionCoordinator(self.transcriber, self.update_handler)
        
        # Start update handling
        self.update_handler.start()
        
        logger.info("Integrated voice transcriber initialized")
        
    async def transcribe(
        self,
        chat: Any,
        msg_id: int,
        wait_for_completion: bool = False,
        timeout: Optional[float] = 30.0,
        completion_callback: Optional[Callable] = None,
        **kwargs
    ) -> 'TranscriptionRequest':
        """
        Transcribe a voice message with integrated update handling.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID of the voice message
            wait_for_completion: Whether to wait for completion
            timeout: Timeout for waiting
            completion_callback: Callback for completion notifications
            **kwargs: Additional arguments passed to transcriber
            
        Returns:
            TranscriptionRequest object that will be automatically updated
        """
        
        # Create the transcription request
        request = await self.transcriber.transcribe(
            chat=chat,
            msg_id=msg_id,
            wait_for_completion=False,  # We handle waiting ourselves
            **kwargs
        )
        
        # Register for update coordination
        self.coordinator.register_request(request, completion_callback)
        
        # Wait for completion if requested
        if wait_for_completion:
            await self._wait_for_completion(request, timeout)
            
        return request
        
    async def _wait_for_completion(
        self,
        request: 'TranscriptionRequest',
        timeout: Optional[float]
    ):
        """Wait for a request to complete via updates"""
        if timeout is None:
            timeout = 30.0
            
        start_time = asyncio.get_event_loop().time()
        
        while not request.completed:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning(f"Transcription timeout for {request.key}")
                break
                
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
            
    def register_update_handler(
        self,
        handler_id: str,
        callback: Callable[[UpdateEvent], Any],
        filter_func: Optional[Callable[[UpdateEvent], bool]] = None,
        priority: int = 0
    ) -> bool:
        """
        Register a custom update handler.
        
        Args:
            handler_id: Unique identifier for the handler
            callback: Function to call with UpdateEvent
            filter_func: Optional filter function
            priority: Handler priority
            
        Returns:
            True if registered successfully
        """
        return self.update_handler.register_handler(
            handler_id, callback, filter_func, priority
        )
        
    def unregister_update_handler(self, handler_id: str) -> bool:
        """Unregister a custom update handler"""
        return self.update_handler.unregister_handler(handler_id)
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all components"""
        return {
            'transcriber': {
                'active_requests': self.transcriber.get_active_count(),
                'completed_requests': self.transcriber.get_completed_count()
            },
            'update_handler': self.update_handler.get_comprehensive_stats(),
            'coordinator': self.coordinator.get_coordination_stats()
        }
        
    def cleanup(self):
        """Clean up resources"""
        self.update_handler.stop()
        self.transcriber.cleanup_completed()
        logger.info("Integrated voice transcriber cleaned up")


# Example usage
async def example_integrated_usage():
    """Example of how to use the integrated transcriber"""
    
    client = None  # Placeholder - would be real TelegramClient
    transcriber = IntegratedVoiceTranscriber(client)
    
    # Simple transcription with automatic updates
    request = await transcriber.transcribe(
        chat='me',
        msg_id=12345,
        wait_for_completion=True
    )
    
    if request.completed:
        print(f"Transcription: {request.result.text}")
        
    # Transcription with completion callback
    async def on_completion(request, update_event):
        print(f"Completed: {request.result.text}")
        
    request2 = await transcriber.transcribe(
        chat='@channel',
        msg_id=54321,
        completion_callback=on_completion
    )
    
    # Register custom update handler
    def log_all_updates(update_event):
        print(f"Update: {update_event.update_key} - {update_event.text}")
        
    transcriber.register_update_handler(
        "logger",
        log_all_updates,
        priority=1
    )
    
    # Get statistics
    stats = transcriber.get_comprehensive_stats()
    print(f"Total requests: {stats['transcriber']['active_requests']}")
    
    # Cleanup when done
    transcriber.cleanup()


if __name__ == "__main__":
    print("Voice Transcription Integration Layer")
    print("See example_integrated_usage() function for usage patterns")