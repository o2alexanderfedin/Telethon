"""
Update Handling System for Voice Transcription

This module implements Epic 1 User Story 1.3: Update Handling System for processing
real-time transcription updates from UpdateTranscribedAudio events.

Features:
- Real-time update processing
- Handler registration and management
- Update validation and ordering
- Event integration with Telethon
- State synchronization
- Duplicate detection
"""

import asyncio
import logging
from typing import Dict, List, Callable, Optional, Any, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import UpdateTranscribedAudio, Peer
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TelegramClient = Any
    UpdateTranscribedAudio = Any
    Peer = Any


logger = logging.getLogger(__name__)


@dataclass
class UpdateEvent:
    """
    Represents a processed transcription update event.
    """
    transcription_id: int
    peer_id: int
    msg_id: int
    text: str
    pending: bool
    received_at: datetime
    processed_at: Optional[datetime] = None
    sequence_number: Optional[int] = None
    raw_update: Optional[Any] = None
    
    def __post_init__(self):
        if self.received_at is None:
            self.received_at = datetime.now(timezone.utc)
            
    @property
    def update_key(self) -> str:
        """Unique key for this update"""
        return f"{self.peer_id}:{self.msg_id}:{self.transcription_id}"
        
    @property
    def is_completion(self) -> bool:
        """True if this update indicates completion"""
        return not self.pending
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'transcription_id': self.transcription_id,
            'peer_id': self.peer_id,
            'msg_id': self.msg_id,
            'text': self.text,
            'pending': self.pending,
            'received_at': self.received_at.isoformat(),
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'sequence_number': self.sequence_number,
            'update_key': self.update_key,
            'is_completion': self.is_completion
        }


@dataclass
class HandlerRegistration:
    """
    Represents a registered update handler.
    """
    handler_id: str
    callback: Callable[[UpdateEvent], Any]
    filter_func: Optional[Callable[[UpdateEvent], bool]] = None
    priority: int = 0  # Higher numbers = higher priority
    active: bool = True
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    call_count: int = 0
    error_count: int = 0
    last_called: Optional[datetime] = None
    last_error: Optional[str] = None
    
    def matches(self, update_event: UpdateEvent) -> bool:
        """Check if this handler should process the update"""
        if not self.active:
            return False
        return self.filter_func(update_event) if self.filter_func else True


class UpdateValidator:
    """
    Validates and filters transcription updates.
    """
    
    def __init__(self):
        self.seen_updates: Set[str] = set()
        self.validation_stats = {
            'total_received': 0,
            'valid_updates': 0,
            'duplicates': 0,
            'invalid_format': 0,
            'missing_fields': 0
        }
        
    def validate_update(self, raw_update: UpdateTranscribedAudio) -> Optional[UpdateEvent]:
        """
        Validate and convert raw update to UpdateEvent.
        
        Args:
            raw_update: Raw UpdateTranscribedAudio from Telethon
            
        Returns:
            UpdateEvent if valid, None if invalid
        """
        self.validation_stats['total_received'] += 1
        
        try:
            # Extract peer ID
            peer_id = self._extract_peer_id(raw_update.peer)
            if peer_id == 0:
                logger.warning(f"Invalid peer in update: {raw_update.peer}")
                self.validation_stats['invalid_format'] += 1
                return None
                
            # Check required fields
            if not hasattr(raw_update, 'transcription_id') or not raw_update.transcription_id:
                logger.warning("Update missing transcription_id")
                self.validation_stats['missing_fields'] += 1
                return None
                
            if not hasattr(raw_update, 'msg_id') or not raw_update.msg_id:
                logger.warning("Update missing msg_id")
                self.validation_stats['missing_fields'] += 1
                return None
                
            # Create update event
            update_event = UpdateEvent(
                transcription_id=raw_update.transcription_id,
                peer_id=peer_id,
                msg_id=raw_update.msg_id,
                text=getattr(raw_update, 'text', ''),
                pending=getattr(raw_update, 'pending', False),
                received_at=datetime.now(timezone.utc),
                raw_update=raw_update
            )
            
            # Check for duplicates
            if update_event.update_key in self.seen_updates:
                logger.debug(f"Duplicate update detected: {update_event.update_key}")
                self.validation_stats['duplicates'] += 1
                return None
                
            # Mark as seen
            self.seen_updates.add(update_event.update_key)
            self.validation_stats['valid_updates'] += 1
            
            logger.debug(f"Validated update: {update_event.update_key}")
            return update_event
            
        except Exception as e:
            logger.error(f"Update validation error: {e}")
            self.validation_stats['invalid_format'] += 1
            return None
            
    def _extract_peer_id(self, peer: Peer) -> int:
        """Extract peer ID from peer object"""
        if hasattr(peer, 'user_id'):
            return peer.user_id
        elif hasattr(peer, 'chat_id'):
            return peer.chat_id
        elif hasattr(peer, 'channel_id'):
            return peer.channel_id
        else:
            return 0
            
    def cleanup_seen_updates(self, max_size: int = 10000):
        """Clean up seen updates cache if it gets too large"""
        if len(self.seen_updates) > max_size:
            # Keep only the most recent half
            to_keep = max_size // 2
            self.seen_updates = set(list(self.seen_updates)[-to_keep:])
            logger.info(f"Cleaned up seen updates cache, kept {to_keep} entries")
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics"""
        total = self.validation_stats['total_received']
        if total > 0:
            success_rate = (self.validation_stats['valid_updates'] / total) * 100
            duplicate_rate = (self.validation_stats['duplicates'] / total) * 100
        else:
            success_rate = 0
            duplicate_rate = 0
            
        return {
            **self.validation_stats,
            'success_rate_percent': round(success_rate, 2),
            'duplicate_rate_percent': round(duplicate_rate, 2),
            'cache_size': len(self.seen_updates)
        }


class UpdateProcessor:
    """
    Processes validated updates through registered handlers.
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self.handlers: Dict[str, HandlerRegistration] = {}
        self.update_queue: deque = deque(maxlen=max_queue_size)
        self.processing_stats = {
            'updates_processed': 0,
            'handlers_called': 0,
            'handler_errors': 0,
            'queue_overflows': 0
        }
        self._lock = threading.RLock()
        self._sequence_counter = 0
        
    def register_handler(
        self,
        handler_id: str,
        callback: Callable[[UpdateEvent], Any],
        filter_func: Optional[Callable[[UpdateEvent], bool]] = None,
        priority: int = 0
    ) -> bool:
        """
        Register an update handler.
        
        Args:
            handler_id: Unique identifier for the handler
            callback: Function to call with UpdateEvent
            filter_func: Optional filter function
            priority: Handler priority (higher = called first)
            
        Returns:
            True if registered successfully
        """
        try:
            with self._lock:
                if handler_id in self.handlers:
                    logger.warning(f"Handler {handler_id} already registered, updating")
                    
                registration = HandlerRegistration(
                    handler_id=handler_id,
                    callback=callback,
                    filter_func=filter_func,
                    priority=priority
                )
                
                self.handlers[handler_id] = registration
                logger.info(f"Registered update handler: {handler_id} (priority: {priority})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register handler {handler_id}: {e}")
            return False
            
    def unregister_handler(self, handler_id: str) -> bool:
        """
        Unregister an update handler.
        
        Args:
            handler_id: Handler to remove
            
        Returns:
            True if unregistered successfully
        """
        try:
            with self._lock:
                if handler_id in self.handlers:
                    del self.handlers[handler_id]
                    logger.info(f"Unregistered update handler: {handler_id}")
                    return True
                else:
                    logger.warning(f"Handler {handler_id} not found for unregistration")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to unregister handler {handler_id}: {e}")
            return False
            
    def disable_handler(self, handler_id: str) -> bool:
        """Temporarily disable a handler"""
        with self._lock:
            if handler_id in self.handlers:
                self.handlers[handler_id].active = False
                logger.info(f"Disabled handler: {handler_id}")
                return True
            return False
            
    def enable_handler(self, handler_id: str) -> bool:
        """Re-enable a disabled handler"""
        with self._lock:
            if handler_id in self.handlers:
                self.handlers[handler_id].active = True
                logger.info(f"Enabled handler: {handler_id}")
                return True
            return False
            
    async def process_update(self, update_event: UpdateEvent) -> Dict[str, Any]:
        """
        Process an update through all matching handlers.
        
        Args:
            update_event: Validated update event
            
        Returns:
            Processing results
        """
        with self._lock:
            # Assign sequence number
            self._sequence_counter += 1
            update_event.sequence_number = self._sequence_counter
            
            # Add to queue
            if len(self.update_queue) >= self.update_queue.maxlen:
                self.processing_stats['queue_overflows'] += 1
                logger.warning("Update queue overflow, dropping oldest update")
                
            self.update_queue.append(update_event)
            
            # Get matching handlers sorted by priority
            matching_handlers = [
                h for h in self.handlers.values() 
                if h.matches(update_event)
            ]
            matching_handlers.sort(key=lambda h: h.priority, reverse=True)
            
        self.processing_stats['updates_processed'] += 1
        update_event.processed_at = datetime.now(timezone.utc)
        
        results = {
            'update_key': update_event.update_key,
            'sequence_number': update_event.sequence_number,
            'handlers_called': 0,
            'handlers_succeeded': 0,
            'handlers_failed': 0,
            'errors': []
        }
        
        # Call handlers
        for handler in matching_handlers:
            try:
                # Update handler stats
                handler.call_count += 1
                handler.last_called = datetime.now(timezone.utc)
                
                # Call the handler
                if asyncio.iscoroutinefunction(handler.callback):
                    await handler.callback(update_event)
                else:
                    handler.callback(update_event)
                    
                results['handlers_succeeded'] += 1
                self.processing_stats['handlers_called'] += 1
                
                logger.debug(f"Handler {handler.handler_id} processed update {update_event.update_key}")
                
            except Exception as e:
                handler.error_count += 1
                handler.last_error = str(e)
                results['handlers_failed'] += 1
                results['errors'].append(f"{handler.handler_id}: {e}")
                self.processing_stats['handler_errors'] += 1
                
                logger.error(f"Handler {handler.handler_id} failed on update {update_event.update_key}: {e}")
                
            finally:
                results['handlers_called'] += 1
                
        logger.debug(f"Processed update {update_event.update_key}: {results['handlers_succeeded']}/{results['handlers_called']} handlers succeeded")
        return results
        
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get statistics for all handlers"""
        with self._lock:
            stats = {}
            for handler_id, handler in self.handlers.items():
                stats[handler_id] = {
                    'priority': handler.priority,
                    'active': handler.active,
                    'call_count': handler.call_count,
                    'error_count': handler.error_count,
                    'success_rate': (handler.call_count - handler.error_count) / max(1, handler.call_count) * 100,
                    'last_called': handler.last_called.isoformat() if handler.last_called else None,
                    'last_error': handler.last_error,
                    'registered_at': handler.registered_at.isoformat()
                }
            return stats
            
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.processing_stats,
            'queue_size': len(self.update_queue),
            'queue_max_size': self.update_queue.maxlen,
            'handler_count': len(self.handlers),
            'active_handlers': sum(1 for h in self.handlers.values() if h.active),
            'sequence_counter': self._sequence_counter
        }


class VoiceTranscriptionUpdateHandler:
    """
    Main update handling system for voice transcription.
    
    Integrates with Telethon's event system to process UpdateTranscribedAudio events
    and dispatch them to registered handlers.
    """
    
    def __init__(self, client: 'TelegramClient'):
        """
        Initialize the update handler.
        
        Args:
            client: Authenticated TelegramClient instance
        """
        if not TELETHON_AVAILABLE:
            raise ImportError("Telethon is required for update handling")
            
        self.client = client
        self.validator = UpdateValidator()
        self.processor = UpdateProcessor()
        self._registered_with_client = False
        self._stats_start_time = datetime.now(timezone.utc)
        
    def start(self):
        """Start the update handling system"""
        if not self._registered_with_client:
            self.client.add_event_handler(
                self._handle_raw_update,
                events.Raw(UpdateTranscribedAudio)
            )
            self._registered_with_client = True
            logger.info("Voice transcription update handler started")
        else:
            logger.warning("Update handler already started")
            
    def stop(self):
        """Stop the update handling system"""
        if self._registered_with_client:
            self.client.remove_event_handler(
                self._handle_raw_update,
                events.Raw(UpdateTranscribedAudio)
            )
            self._registered_with_client = False
            logger.info("Voice transcription update handler stopped")
        else:
            logger.warning("Update handler not started")
            
    async def _handle_raw_update(self, event):
        """Internal handler for raw Telethon update events"""
        try:
            raw_update = event.update
            logger.debug(f"Received raw update: transcription_id={getattr(raw_update, 'transcription_id', 'unknown')}")
            
            # Validate the update
            update_event = self.validator.validate_update(raw_update)
            if not update_event:
                return  # Invalid or duplicate update
                
            # Process through handlers
            results = await self.processor.process_update(update_event)
            
            logger.info(f"Update processed: {update_event.update_key}, "
                       f"{results['handlers_succeeded']}/{results['handlers_called']} handlers succeeded")
                       
        except Exception as e:
            logger.error(f"Error in update handler: {e}")
            
    def register_handler(
        self,
        handler_id: str,
        callback: Callable[[UpdateEvent], Any],
        filter_func: Optional[Callable[[UpdateEvent], bool]] = None,
        priority: int = 0
    ) -> bool:
        """
        Register a handler for transcription updates.
        
        Args:
            handler_id: Unique identifier for the handler
            callback: Function to call with UpdateEvent (can be async)
            filter_func: Optional filter function
            priority: Handler priority (higher = called first)
            
        Returns:
            True if registered successfully
        """
        return self.processor.register_handler(handler_id, callback, filter_func, priority)
        
    def unregister_handler(self, handler_id: str) -> bool:
        """Unregister a handler"""
        return self.processor.unregister_handler(handler_id)
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        uptime = datetime.now(timezone.utc) - self._stats_start_time
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'validation': self.validator.get_statistics(),
            'processing': self.processor.get_processing_stats(),
            'handlers': self.processor.get_handler_stats(),
            'system': {
                'registered_with_client': self._registered_with_client,
                'start_time': self._stats_start_time.isoformat()
            }
        }


# Convenience functions for common use cases

def create_completion_filter() -> Callable[[UpdateEvent], bool]:
    """Create a filter that only passes completion updates"""
    return lambda update: update.is_completion


def create_peer_filter(peer_id: int) -> Callable[[UpdateEvent], bool]:
    """Create a filter for updates from a specific peer"""
    return lambda update: update.peer_id == peer_id


def create_transcription_filter(transcription_id: int) -> Callable[[UpdateEvent], bool]:
    """Create a filter for updates from a specific transcription"""
    return lambda update: update.transcription_id == transcription_id


# Example usage
async def example_update_handling():
    """Example of how to use the update handling system"""
    
    client = None  # Placeholder - would be real TelegramClient
    handler = VoiceTranscriptionUpdateHandler(client)
    
    # Example handler for completion updates
    async def on_completion(update_event: UpdateEvent):
        print(f"Transcription completed: {update_event.text}")
        
    # Example handler for all updates from a specific chat
    def on_chat_updates(update_event: UpdateEvent):
        print(f"Update from chat {update_event.peer_id}: {update_event.text}")
        
    # Register handlers
    handler.register_handler(
        "completion_handler",
        on_completion,
        filter_func=create_completion_filter(),
        priority=10
    )
    
    handler.register_handler(
        "chat_monitor",
        on_chat_updates,
        filter_func=create_peer_filter(123456),
        priority=5
    )
    
    # Start handling updates
    handler.start()
    
    # Get statistics
    stats = handler.get_comprehensive_stats()
    print(f"Processing stats: {stats['processing']}")
    
    # Stop when done
    handler.stop()


if __name__ == "__main__":
    print("Voice Transcription Update Handling System")
    print("See example_update_handling() function for usage patterns")