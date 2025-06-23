"""
Transcription State Management System

This module implements Epic 1 User Story 1.4: Transcription State Management
for tracking active transcription states and managing concurrent transcriptions efficiently.

Features:
- Thread-safe state storage and retrieval
- Unique identification using peer_id and msg_id combination
- State lifecycle management (creation, updates, completion)
- Memory-efficient concurrent transcription tracking
- Automatic cleanup and garbage collection
- State validation and consistency checks
"""

import asyncio
import logging
import threading
import weakref
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum
import json

logger = logging.getLogger(__name__)


class TranscriptionStatus(Enum):
    """Enumeration of transcription states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class TranscriptionState:
    """
    Represents the state of a voice transcription.
    
    This class tracks all necessary information for a transcription request
    from initiation through completion, providing thread-safe access and
    efficient memory usage.
    """
    peer_id: int
    msg_id: int
    transcription_id: Optional[int] = None
    text: str = ""
    status: TranscriptionStatus = TranscriptionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    trial_remains: Optional[int] = None
    trial_expires: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation and setup"""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.last_update is None:
            self.last_update = datetime.now(timezone.utc)
            
    @property
    def state_key(self) -> str:
        """Unique key for this transcription state"""
        return f"{self.peer_id}:{self.msg_id}"
        
    @property
    def is_pending(self) -> bool:
        """True if transcription is still pending"""
        return self.status == TranscriptionStatus.PENDING
        
    @property
    def is_processing(self) -> bool:
        """True if transcription is being processed"""
        return self.status == TranscriptionStatus.PROCESSING
        
    @property
    def is_completed(self) -> bool:
        """True if transcription is completed successfully"""
        return self.status == TranscriptionStatus.COMPLETED
        
    @property
    def is_failed(self) -> bool:
        """True if transcription failed"""
        return self.status == TranscriptionStatus.FAILED
        
    @property
    def is_active(self) -> bool:
        """True if transcription is still active (pending or processing)"""
        return self.status in (TranscriptionStatus.PENDING, TranscriptionStatus.PROCESSING)
        
    @property
    def duration(self) -> timedelta:
        """Duration since creation"""
        end_time = self.completed_at or datetime.now(timezone.utc)
        return end_time - self.created_at
        
    @property
    def time_since_update(self) -> timedelta:
        """Time since last update"""
        return datetime.now(timezone.utc) - self.last_update
        
    def update_status(self, status: TranscriptionStatus, text: str = None, error: str = None):
        """
        Update the transcription status.
        
        Args:
            status: New status
            text: Transcribed text (if available)
            error: Error message (if failed)
        """
        old_status = self.status
        self.status = status
        self.last_update = datetime.now(timezone.utc)
        
        if text is not None:
            self.text = text
            
        if error is not None:
            self.error_message = error
            
        if status == TranscriptionStatus.COMPLETED:
            self.completed_at = self.last_update
            
        logger.debug(f"State {self.state_key}: {old_status.value} -> {status.value}")
        
    def update_from_api_response(self, transcription_id: int, text: str, pending: bool):
        """
        Update state from API response.
        
        Args:
            transcription_id: Transcription ID from API
            text: Transcribed text
            pending: Whether transcription is still pending
        """
        self.transcription_id = transcription_id
        self.text = text
        
        if pending:
            self.update_status(TranscriptionStatus.PROCESSING, text)
        else:
            self.update_status(TranscriptionStatus.COMPLETED, text)
            
    def update_from_update_event(self, transcription_id: int, text: str, pending: bool):
        """
        Update state from update event.
        
        Args:
            transcription_id: Transcription ID from update
            text: Transcribed text
            pending: Whether transcription is still pending
        """
        # Verify transcription ID matches
        if self.transcription_id and self.transcription_id != transcription_id:
            logger.warning(f"Transcription ID mismatch for {self.state_key}: "
                          f"expected {self.transcription_id}, got {transcription_id}")
            
        self.update_from_api_response(transcription_id, text, pending)
        
    def mark_failed(self, error_message: str, increment_retry: bool = True):
        """
        Mark transcription as failed.
        
        Args:
            error_message: Reason for failure
            increment_retry: Whether to increment retry count
        """
        self.update_status(TranscriptionStatus.FAILED, error=error_message)
        if increment_retry:
            self.retry_count += 1
            
    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if transcription can be retried"""
        return (self.is_failed and 
                self.retry_count < max_retries and
                self.time_since_update.total_seconds() > 60)  # Wait at least 1 minute
                
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat() if value else None
            elif isinstance(value, TranscriptionStatus):
                data[key] = value.value
                
        # Add computed properties
        data.update({
            'state_key': self.state_key,
            'is_pending': self.is_pending,
            'is_processing': self.is_processing,
            'is_completed': self.is_completed,
            'is_failed': self.is_failed,
            'is_active': self.is_active,
            'duration_seconds': self.duration.total_seconds(),
            'time_since_update_seconds': self.time_since_update.total_seconds()
        })
        
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranscriptionState':
        """Create instance from dictionary"""
        # Convert ISO strings back to datetime objects
        for key in ['created_at', 'last_update', 'completed_at', 'trial_expires']:
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key])
                
        # Convert status string to enum
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = TranscriptionStatus(data['status'])
            
        # Remove computed properties
        computed_keys = [
            'state_key', 'is_pending', 'is_processing', 'is_completed',
            'is_failed', 'is_active', 'duration_seconds', 'time_since_update_seconds'
        ]
        for key in computed_keys:
            data.pop(key, None)
            
        return cls(**data)
        
    def __repr__(self):
        return (f"TranscriptionState(key={self.state_key}, "
                f"status={self.status.value}, "
                f"transcription_id={self.transcription_id})")


class StateStorage:
    """
    Thread-safe storage for transcription states.
    
    Provides efficient storage, retrieval, and management of transcription states
    with support for concurrent access and automatic cleanup.
    """
    
    def __init__(self, cleanup_interval: int = 3600, max_completed_age: int = 86400):
        """
        Initialize state storage.
        
        Args:
            cleanup_interval: Interval in seconds between cleanup runs
            max_completed_age: Maximum age in seconds for completed states
        """
        self._states: Dict[str, TranscriptionState] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = cleanup_interval
        self._max_completed_age = max_completed_age
        self._last_cleanup = datetime.now(timezone.utc)
        
        # Statistics
        self._stats = {
            'total_created': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cleaned': 0,
            'peak_concurrent': 0
        }
        
    def create_state(
        self,
        peer_id: int,
        msg_id: int,
        **kwargs
    ) -> TranscriptionState:
        """
        Create a new transcription state.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            **kwargs: Additional state parameters
            
        Returns:
            Created TranscriptionState
            
        Raises:
            ValueError: If state already exists
        """
        state_key = f"{peer_id}:{msg_id}"
        
        with self._lock:
            if state_key in self._states:
                existing_state = self._states[state_key]
                if existing_state.is_active:
                    raise ValueError(f"Active transcription state already exists: {state_key}")
                else:
                    # Remove old completed/failed state
                    del self._states[state_key]
                    
            state = TranscriptionState(peer_id=peer_id, msg_id=msg_id, **kwargs)
            self._states[state_key] = state
            
            # Update statistics
            self._stats['total_created'] += 1
            current_count = len(self._states)
            if current_count > self._stats['peak_concurrent']:
                self._stats['peak_concurrent'] = current_count
                
            logger.debug(f"Created state: {state_key}")
            return state
            
    def get_state(self, peer_id: int, msg_id: int) -> Optional[TranscriptionState]:
        """
        Get transcription state by peer and message ID.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            
        Returns:
            TranscriptionState if found, None otherwise
        """
        state_key = f"{peer_id}:{msg_id}"
        
        with self._lock:
            return self._states.get(state_key)
            
    def get_state_by_key(self, state_key: str) -> Optional[TranscriptionState]:
        """Get transcription state by key"""
        with self._lock:
            return self._states.get(state_key)
            
    def update_state(
        self,
        peer_id: int,
        msg_id: int,
        **updates
    ) -> Optional[TranscriptionState]:
        """
        Update transcription state.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            **updates: State updates
            
        Returns:
            Updated TranscriptionState if found, None otherwise
        """
        state = self.get_state(peer_id, msg_id)
        if state:
            with self._lock:
                for key, value in updates.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                state.last_update = datetime.now(timezone.utc)
                
                # Update statistics
                if state.is_completed and 'status' in updates:
                    self._stats['total_completed'] += 1
                elif state.is_failed and 'status' in updates:
                    self._stats['total_failed'] += 1
                    
        return state
        
    def remove_state(self, peer_id: int, msg_id: int) -> bool:
        """
        Remove transcription state.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            
        Returns:
            True if state was removed, False if not found
        """
        state_key = f"{peer_id}:{msg_id}"
        
        with self._lock:
            if state_key in self._states:
                del self._states[state_key]
                logger.debug(f"Removed state: {state_key}")
                return True
            return False
            
    def get_all_states(self, status_filter: Optional[TranscriptionStatus] = None) -> List[TranscriptionState]:
        """
        Get all states, optionally filtered by status.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of TranscriptionState objects
        """
        with self._lock:
            states = list(self._states.values())
            
        if status_filter:
            states = [state for state in states if state.status == status_filter]
            
        return states
        
    def get_states_by_peer(self, peer_id: int) -> List[TranscriptionState]:
        """Get all states for a specific peer"""
        with self._lock:
            return [state for state in self._states.values() if state.peer_id == peer_id]
            
    def get_active_states(self) -> List[TranscriptionState]:
        """Get all active (pending or processing) states"""
        with self._lock:
            return [state for state in self._states.values() if state.is_active]
            
    def get_state_count(self) -> int:
        """Get total number of states"""
        with self._lock:
            return len(self._states)
            
    def get_state_counts_by_status(self) -> Dict[str, int]:
        """Get count of states by status"""
        counts = defaultdict(int)
        
        with self._lock:
            for state in self._states.values():
                counts[state.status.value] += 1
                
        return dict(counts)
        
    def cleanup_old_states(self, max_age: Optional[int] = None) -> int:
        """
        Clean up old completed/failed states.
        
        Args:
            max_age: Maximum age in seconds (uses default if None)
            
        Returns:
            Number of states cleaned up
        """
        if max_age is None:
            max_age = self._max_completed_age
            
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=max_age)
        states_to_remove = []
        
        with self._lock:
            for state_key, state in self._states.items():
                if (not state.is_active and 
                    state.last_update < cutoff_time):
                    states_to_remove.append(state_key)
                    
            # Remove old states
            for state_key in states_to_remove:
                del self._states[state_key]
                
            self._stats['total_cleaned'] += len(states_to_remove)
            self._last_cleanup = datetime.now(timezone.utc)
            
        if states_to_remove:
            logger.info(f"Cleaned up {len(states_to_remove)} old transcription states")
            
        return len(states_to_remove)
        
    def auto_cleanup(self) -> int:
        """
        Perform automatic cleanup if interval has passed.
        
        Returns:
            Number of states cleaned up, or 0 if no cleanup performed
        """
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup).total_seconds() >= self._cleanup_interval:
            return self.cleanup_old_states()
        return 0
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self._lock:
            current_counts = self.get_state_counts_by_status()
            
            return {
                **self._stats,
                'current_total': len(self._states),
                'current_by_status': current_counts,
                'last_cleanup': self._last_cleanup.isoformat(),
                'cleanup_interval_seconds': self._cleanup_interval,
                'max_completed_age_seconds': self._max_completed_age
            }
            
    def export_states(self) -> List[Dict[str, Any]]:
        """Export all states as dictionaries"""
        with self._lock:
            return [state.to_dict() for state in self._states.values()]
            
    def import_states(self, states_data: List[Dict[str, Any]]) -> int:
        """
        Import states from dictionaries.
        
        Args:
            states_data: List of state dictionaries
            
        Returns:
            Number of states imported
        """
        imported_count = 0
        
        with self._lock:
            for state_data in states_data:
                try:
                    state = TranscriptionState.from_dict(state_data)
                    self._states[state.state_key] = state
                    imported_count += 1
                except Exception as e:
                    logger.error(f"Failed to import state: {e}")
                    
        logger.info(f"Imported {imported_count} transcription states")
        return imported_count
        
    def clear_all_states(self) -> int:
        """
        Clear all states.
        
        Returns:
            Number of states cleared
        """
        with self._lock:
            count = len(self._states)
            self._states.clear()
            logger.warning(f"Cleared all {count} transcription states")
            return count


class TranscriptionStateManager:
    """
    High-level manager for transcription states.
    
    Provides a clean API for managing transcription states with automatic
    cleanup, state validation, and consistency checks.
    """
    
    def __init__(
        self,
        cleanup_interval: int = 3600,
        max_completed_age: int = 86400,
        auto_cleanup: bool = True
    ):
        """
        Initialize state manager.
        
        Args:
            cleanup_interval: Automatic cleanup interval in seconds
            max_completed_age: Maximum age for completed states in seconds
            auto_cleanup: Whether to perform automatic cleanup
        """
        self.storage = StateStorage(cleanup_interval, max_completed_age)
        self.auto_cleanup = auto_cleanup
        self._observers: List[Callable[[TranscriptionState, str], None]] = []
        
    def create_transcription(
        self,
        peer_id: int,
        msg_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TranscriptionState:
        """
        Create a new transcription state.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            metadata: Optional metadata
            
        Returns:
            Created TranscriptionState
        """
        state = self.storage.create_state(
            peer_id=peer_id,
            msg_id=msg_id,
            metadata=metadata or {}
        )
        
        self._notify_observers(state, 'created')
        
        # Perform auto cleanup if enabled
        if self.auto_cleanup:
            self.storage.auto_cleanup()
            
        return state
        
    def get_transcription(self, peer_id: int, msg_id: int) -> Optional[TranscriptionState]:
        """Get transcription state"""
        return self.storage.get_state(peer_id, msg_id)
        
    def update_transcription_from_response(
        self,
        peer_id: int,
        msg_id: int,
        transcription_id: int,
        text: str,
        pending: bool,
        trial_remains: Optional[int] = None,
        trial_expires: Optional[datetime] = None
    ) -> Optional[TranscriptionState]:
        """
        Update transcription from API response.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            transcription_id: Transcription ID
            text: Transcribed text
            pending: Whether still pending
            trial_remains: Trial transcriptions remaining
            trial_expires: When trial expires
            
        Returns:
            Updated state or None if not found
        """
        state = self.storage.get_state(peer_id, msg_id)
        if state:
            old_status = state.status
            state.update_from_api_response(transcription_id, text, pending)
            
            if trial_remains is not None:
                state.trial_remains = trial_remains
            if trial_expires is not None:
                state.trial_expires = trial_expires
                
            self._notify_observers(state, f'updated_from_response_{old_status.value}_to_{state.status.value}')
            
        return state
        
    def update_transcription_from_update(
        self,
        peer_id: int,
        msg_id: int,
        transcription_id: int,
        text: str,
        pending: bool
    ) -> Optional[TranscriptionState]:
        """
        Update transcription from update event.
        
        Args:
            peer_id: Peer ID
            msg_id: Message ID
            transcription_id: Transcription ID
            text: Transcribed text
            pending: Whether still pending
            
        Returns:
            Updated state or None if not found
        """
        state = self.storage.get_state(peer_id, msg_id)
        if state:
            old_status = state.status
            state.update_from_update_event(transcription_id, text, pending)
            self._notify_observers(state, f'updated_from_update_{old_status.value}_to_{state.status.value}')
            
        return state
        
    def mark_transcription_failed(
        self,
        peer_id: int,
        msg_id: int,
        error_message: str
    ) -> Optional[TranscriptionState]:
        """Mark transcription as failed"""
        state = self.storage.get_state(peer_id, msg_id)
        if state:
            state.mark_failed(error_message)
            self._notify_observers(state, 'failed')
            
        return state
        
    def get_active_transcriptions(self) -> List[TranscriptionState]:
        """Get all active transcriptions"""
        return self.storage.get_active_states()
        
    def get_transcriptions_by_peer(self, peer_id: int) -> List[TranscriptionState]:
        """Get all transcriptions for a peer"""
        return self.storage.get_states_by_peer(peer_id)
        
    def get_transcription_statistics(self) -> Dict[str, Any]:
        """Get comprehensive transcription statistics"""
        storage_stats = self.storage.get_statistics()
        
        # Add manager-specific stats
        manager_stats = {
            'auto_cleanup_enabled': self.auto_cleanup,
            'observers_count': len(self._observers)
        }
        
        return {**storage_stats, **manager_stats}
        
    def cleanup_old_transcriptions(self, max_age: Optional[int] = None) -> int:
        """Clean up old completed transcriptions"""
        return self.storage.cleanup_old_states(max_age)
        
    def add_observer(self, observer: Callable[[TranscriptionState, str], None]):
        """
        Add state change observer.
        
        Args:
            observer: Function called with (state, event_type)
        """
        self._observers.append(observer)
        
    def remove_observer(self, observer: Callable[[TranscriptionState, str], None]):
        """Remove state change observer"""
        if observer in self._observers:
            self._observers.remove(observer)
            
    def _notify_observers(self, state: TranscriptionState, event_type: str):
        """Notify all observers of state changes"""
        for observer in self._observers:
            try:
                observer(state, event_type)
            except Exception as e:
                logger.error(f"Observer error: {e}")


# Example usage
async def example_state_management():
    """Example of how to use the state management system"""
    
    # Create state manager
    manager = TranscriptionStateManager()
    
    # Add observer for state changes
    def log_state_changes(state, event_type):
        print(f"State {state.state_key} event: {event_type} -> {state.status.value}")
        
    manager.add_observer(log_state_changes)
    
    # Create transcription
    state = manager.create_transcription(peer_id=123456, msg_id=789)
    print(f"Created: {state}")
    
    # Update from API response
    manager.update_transcription_from_response(
        peer_id=123456,
        msg_id=789,
        transcription_id=987654321,
        text="",
        pending=True
    )
    
    # Update from completion event
    manager.update_transcription_from_update(
        peer_id=123456,
        msg_id=789,
        transcription_id=987654321,
        text="Hello world",
        pending=False
    )
    
    # Get statistics
    stats = manager.get_transcription_statistics()
    print(f"Statistics: {stats}")


if __name__ == "__main__":
    print("Voice Transcription State Management System")
    print("See example_state_management() function for usage patterns")
    asyncio.run(example_state_management())