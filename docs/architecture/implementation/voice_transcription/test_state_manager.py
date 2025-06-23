"""
Comprehensive Test Suite for Transcription State Management

Tests Epic 1 User Story 1.4: Transcription State Management implementation
including thread safety, state lifecycle management, and cleanup operations.
"""

import asyncio
import pytest
import threading
import time
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from .state_manager import (
    TranscriptionState,
    TranscriptionStatus,
    StateStorage,
    TranscriptionStateManager
)


class TestTranscriptionState:
    """Test the TranscriptionState data class"""
    
    def test_state_creation(self):
        """Test basic state creation"""
        state = TranscriptionState(peer_id=123, msg_id=456)
        
        assert state.peer_id == 123
        assert state.msg_id == 456
        assert state.status == TranscriptionStatus.PENDING
        assert state.text == ""
        assert state.transcription_id is None
        assert state.created_at is not None
        assert state.last_update is not None
        
    def test_state_key_generation(self):
        """Test unique state key generation"""
        state1 = TranscriptionState(peer_id=123, msg_id=456)
        state2 = TranscriptionState(peer_id=123, msg_id=789)
        state3 = TranscriptionState(peer_id=456, msg_id=456)
        
        assert state1.state_key == "123:456"
        assert state2.state_key == "123:789"
        assert state3.state_key == "456:456"
        assert state1.state_key != state2.state_key
        assert state1.state_key != state3.state_key
        
    def test_status_properties(self):
        """Test status checking properties"""
        state = TranscriptionState(peer_id=123, msg_id=456)
        
        # Test pending state
        assert state.is_pending
        assert state.is_active
        assert not state.is_processing
        assert not state.is_completed
        assert not state.is_failed
        
        # Test processing state
        state.status = TranscriptionStatus.PROCESSING
        assert not state.is_pending
        assert state.is_active
        assert state.is_processing
        assert not state.is_completed
        assert not state.is_failed
        
        # Test completed state
        state.status = TranscriptionStatus.COMPLETED
        assert not state.is_pending
        assert not state.is_active
        assert not state.is_processing
        assert state.is_completed
        assert not state.is_failed
        
        # Test failed state
        state.status = TranscriptionStatus.FAILED
        assert not state.is_pending
        assert not state.is_active
        assert not state.is_processing
        assert not state.is_completed
        assert state.is_failed
        
    def test_status_updates(self):
        """Test status update functionality"""
        state = TranscriptionState(peer_id=123, msg_id=456)
        original_time = state.last_update
        
        # Wait a bit to ensure time difference
        time.sleep(0.01)
        
        # Update status
        state.update_status(TranscriptionStatus.PROCESSING, text="partial text")
        
        assert state.status == TranscriptionStatus.PROCESSING
        assert state.text == "partial text"
        assert state.last_update > original_time
        assert state.completed_at is None
        
        # Complete transcription
        time.sleep(0.01)
        state.update_status(TranscriptionStatus.COMPLETED, text="final text")
        
        assert state.status == TranscriptionStatus.COMPLETED
        assert state.text == "final text"
        assert state.completed_at is not None
        
    def test_api_response_updates(self):
        """Test updates from API responses"""
        state = TranscriptionState(peer_id=123, msg_id=456)
        
        # Test pending response
        state.update_from_api_response(
            transcription_id=789,
            text="processing...",
            pending=True
        )
        
        assert state.transcription_id == 789
        assert state.text == "processing..."
        assert state.status == TranscriptionStatus.PROCESSING
        
        # Test completion response
        state.update_from_api_response(
            transcription_id=789,
            text="Hello world",
            pending=False
        )
        
        assert state.text == "Hello world"
        assert state.status == TranscriptionStatus.COMPLETED
        assert state.completed_at is not None
        
    def test_update_event_processing(self):
        """Test updates from update events"""
        state = TranscriptionState(peer_id=123, msg_id=456)
        state.transcription_id = 789
        
        # Test matching transcription ID
        state.update_from_update_event(
            transcription_id=789,
            text="updated text",
            pending=True
        )
        
        assert state.text == "updated text"
        assert state.status == TranscriptionStatus.PROCESSING
        
        # Test mismatched transcription ID (should still work but log warning)
        with patch('logging.getLogger') as mock_logger:
            logger_mock = Mock()
            mock_logger.return_value = logger_mock
            
            state.update_from_update_event(
                transcription_id=999,
                text="different id",
                pending=False
            )
            
            # Should still update despite warning
            assert state.text == "different id"
            assert state.status == TranscriptionStatus.COMPLETED
            
    def test_failure_handling(self):
        """Test failure marking and retry logic"""
        state = TranscriptionState(peer_id=123, msg_id=456)
        
        # Mark as failed
        state.mark_failed("Network error", increment_retry=True)
        
        assert state.is_failed
        assert state.error_message == "Network error"
        assert state.retry_count == 1
        
        # Test retry logic
        assert not state.can_retry()  # Too recent
        
        # Simulate older failure
        state.last_update = datetime.now(timezone.utc) - timedelta(minutes=2)
        assert state.can_retry()
        
        # Test max retries
        state.retry_count = 5
        assert not state.can_retry(max_retries=3)
        
    def test_duration_calculation(self):
        """Test duration and time calculations"""
        # Create state with known creation time
        created_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = TranscriptionState(peer_id=123, msg_id=456)
        state.created_at = created_time
        
        # Test duration
        duration = state.duration
        assert duration.total_seconds() >= 300  # At least 5 minutes
        
        # Test time since update
        state.last_update = datetime.now(timezone.utc) - timedelta(seconds=30)
        time_since = state.time_since_update
        assert time_since.total_seconds() >= 30
        
    def test_serialization(self):
        """Test dictionary conversion for serialization"""
        state = TranscriptionState(
            peer_id=123,
            msg_id=456,
            transcription_id=789,
            text="test text",
            status=TranscriptionStatus.COMPLETED,
            metadata={"test": "value"}
        )
        
        # Test to_dict
        data = state.to_dict()
        
        assert data['peer_id'] == 123
        assert data['msg_id'] == 456
        assert data['transcription_id'] == 789
        assert data['text'] == "test text"
        assert data['status'] == "completed"
        assert data['state_key'] == "123:456"
        assert 'duration_seconds' in data
        assert 'time_since_update_seconds' in data
        
        # Test from_dict
        restored_state = TranscriptionState.from_dict(data)
        
        assert restored_state.peer_id == state.peer_id
        assert restored_state.msg_id == state.msg_id
        assert restored_state.transcription_id == state.transcription_id
        assert restored_state.text == state.text
        assert restored_state.status == state.status
        assert restored_state.metadata == state.metadata


class TestStateStorage:
    """Test the StateStorage class"""
    
    def test_storage_creation(self):
        """Test basic storage creation"""
        storage = StateStorage()
        
        assert storage.get_state_count() == 0
        assert storage.get_state_counts_by_status() == {}
        
    def test_state_creation_and_retrieval(self):
        """Test creating and retrieving states"""
        storage = StateStorage()
        
        # Create state
        state = storage.create_state(peer_id=123, msg_id=456)
        
        assert state.peer_id == 123
        assert state.msg_id == 456
        assert storage.get_state_count() == 1
        
        # Retrieve state
        retrieved = storage.get_state(peer_id=123, msg_id=456)
        assert retrieved is state
        
        # Test by key
        retrieved_by_key = storage.get_state_by_key("123:456")
        assert retrieved_by_key is state
        
        # Test non-existent state
        assert storage.get_state(peer_id=999, msg_id=999) is None
        
    def test_duplicate_state_handling(self):
        """Test handling of duplicate state creation"""
        storage = StateStorage()
        
        # Create initial state
        state1 = storage.create_state(peer_id=123, msg_id=456)
        
        # Try to create duplicate while active (should raise error)
        with pytest.raises(ValueError, match="Active transcription state already exists"):
            storage.create_state(peer_id=123, msg_id=456)
            
        # Complete the state
        state1.status = TranscriptionStatus.COMPLETED
        
        # Now should be able to create new state (old one gets replaced)
        state2 = storage.create_state(peer_id=123, msg_id=456)
        assert state2 is not state1
        assert storage.get_state_count() == 1
        
    def test_state_updates(self):
        """Test state update functionality"""
        storage = StateStorage()
        state = storage.create_state(peer_id=123, msg_id=456)
        
        # Update state
        updated = storage.update_state(
            peer_id=123,
            msg_id=456,
            text="updated text",
            transcription_id=789
        )
        
        assert updated is state
        assert updated.text == "updated text"
        assert updated.transcription_id == 789
        
        # Update non-existent state
        result = storage.update_state(peer_id=999, msg_id=999, text="nope")
        assert result is None
        
    def test_state_removal(self):
        """Test state removal"""
        storage = StateStorage()
        state = storage.create_state(peer_id=123, msg_id=456)
        
        assert storage.get_state_count() == 1
        
        # Remove state
        result = storage.remove_state(peer_id=123, msg_id=456)
        assert result is True
        assert storage.get_state_count() == 0
        
        # Remove non-existent state
        result = storage.remove_state(peer_id=999, msg_id=999)
        assert result is False
        
    def test_state_filtering(self):
        """Test state filtering and retrieval"""
        storage = StateStorage()
        
        # Create multiple states
        state1 = storage.create_state(peer_id=123, msg_id=456)
        state2 = storage.create_state(peer_id=123, msg_id=789)
        state3 = storage.create_state(peer_id=456, msg_id=123)
        
        # Update statuses
        state1.status = TranscriptionStatus.COMPLETED
        state2.status = TranscriptionStatus.PROCESSING
        state3.status = TranscriptionStatus.PENDING
        
        # Test get all states
        all_states = storage.get_all_states()
        assert len(all_states) == 3
        
        # Test filter by status
        completed = storage.get_all_states(TranscriptionStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0] is state1
        
        processing = storage.get_all_states(TranscriptionStatus.PROCESSING)
        assert len(processing) == 1
        assert processing[0] is state2
        
        # Test get by peer
        peer_states = storage.get_states_by_peer(123)
        assert len(peer_states) == 2
        assert state1 in peer_states
        assert state2 in peer_states
        
        # Test get active states
        active = storage.get_active_states()
        assert len(active) == 2  # processing and pending
        assert state2 in active
        assert state3 in active
        
    def test_state_counts(self):
        """Test state counting functionality"""
        storage = StateStorage()
        
        # Create states with different statuses
        state1 = storage.create_state(peer_id=123, msg_id=456)
        state2 = storage.create_state(peer_id=123, msg_id=789)
        state3 = storage.create_state(peer_id=456, msg_id=123)
        
        state1.status = TranscriptionStatus.COMPLETED
        state2.status = TranscriptionStatus.PROCESSING
        state3.status = TranscriptionStatus.FAILED
        
        # Test total count
        assert storage.get_state_count() == 3
        
        # Test counts by status
        counts = storage.get_state_counts_by_status()
        assert counts['completed'] == 1
        assert counts['processing'] == 1
        assert counts['failed'] == 1
        
    def test_cleanup_operations(self):
        """Test cleanup of old states"""
        storage = StateStorage()
        
        # Create old completed states
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        
        state1 = storage.create_state(peer_id=123, msg_id=456)
        state1.status = TranscriptionStatus.COMPLETED
        state1.last_update = old_time
        
        state2 = storage.create_state(peer_id=123, msg_id=789)
        state2.status = TranscriptionStatus.FAILED
        state2.last_update = old_time
        
        # Create recent active state
        state3 = storage.create_state(peer_id=456, msg_id=123)
        # Leave as pending (active)
        
        assert storage.get_state_count() == 3
        
        # Clean up old states (older than 1 hour)
        cleaned = storage.cleanup_old_states(max_age=3600)
        
        assert cleaned == 2  # Two old states cleaned
        assert storage.get_state_count() == 1  # Only active state remains
        
        remaining = storage.get_all_states()
        assert remaining[0] is state3
        
    def test_auto_cleanup(self):
        """Test automatic cleanup functionality"""
        storage = StateStorage(cleanup_interval=1)  # 1 second interval
        
        # Create old state
        state = storage.create_state(peer_id=123, msg_id=456)
        state.status = TranscriptionStatus.COMPLETED
        state.last_update = datetime.now(timezone.utc) - timedelta(hours=2)
        
        # Auto cleanup should not run yet (interval not passed)
        cleaned = storage.auto_cleanup()
        assert cleaned == 0
        
        # Simulate time passing
        storage._last_cleanup = datetime.now(timezone.utc) - timedelta(seconds=2)
        
        # Now auto cleanup should run
        cleaned = storage.auto_cleanup()
        assert cleaned == 1
        assert storage.get_state_count() == 0
        
    def test_statistics(self):
        """Test statistics gathering"""
        storage = StateStorage()
        
        # Create and manipulate states
        storage.create_state(peer_id=123, msg_id=456)
        storage.create_state(peer_id=123, msg_id=789)
        
        stats = storage.get_statistics()
        
        assert stats['total_created'] == 2
        assert stats['current_total'] == 2
        assert stats['peak_concurrent'] == 2
        assert 'cleanup_interval_seconds' in stats
        assert 'max_completed_age_seconds' in stats
        
    def test_import_export(self):
        """Test state import/export functionality"""
        storage = StateStorage()
        
        # Create states
        state1 = storage.create_state(peer_id=123, msg_id=456, text="test1")
        state2 = storage.create_state(peer_id=123, msg_id=789, text="test2")
        
        # Export states
        exported = storage.export_states()
        assert len(exported) == 2
        
        # Clear storage
        cleared = storage.clear_all_states()
        assert cleared == 2
        assert storage.get_state_count() == 0
        
        # Import states
        imported = storage.import_states(exported)
        assert imported == 2
        assert storage.get_state_count() == 2
        
        # Verify imported states
        restored1 = storage.get_state(peer_id=123, msg_id=456)
        restored2 = storage.get_state(peer_id=123, msg_id=789)
        
        assert restored1.text == "test1"
        assert restored2.text == "test2"
        
    def test_thread_safety(self):
        """Test thread-safe operations"""
        storage = StateStorage()
        results = []
        errors = []
        
        def create_states(start_id: int, count: int):
            """Create states in a thread"""
            try:
                for i in range(count):
                    peer_id = start_id + i
                    state = storage.create_state(peer_id=peer_id, msg_id=123)
                    results.append(state.state_key)
            except Exception as e:
                errors.append(str(e))
                
        def update_states(peer_ids: List[int]):
            """Update states in a thread"""
            try:
                for peer_id in peer_ids:
                    storage.update_state(
                        peer_id=peer_id,
                        msg_id=123,
                        text=f"updated_{peer_id}"
                    )
            except Exception as e:
                errors.append(str(e))
                
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            # Create states concurrently
            futures.append(executor.submit(create_states, 1000, 10))
            futures.append(executor.submit(create_states, 2000, 10))
            
            # Wait for creation to complete
            for future in as_completed(futures[:2]):
                future.result()
                
            # Update states concurrently
            futures.append(executor.submit(update_states, list(range(1000, 1010))))
            futures.append(executor.submit(update_states, list(range(2000, 2010))))
            
            # Wait for all operations
            for future in as_completed(futures[2:]):
                future.result()
                
        # Verify results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 20  # 10 + 10 states created
        assert storage.get_state_count() == 20
        
        # Verify updates
        state = storage.get_state(peer_id=1005, msg_id=123)
        assert state.text == "updated_1005"


class TestTranscriptionStateManager:
    """Test the TranscriptionStateManager class"""
    
    def test_manager_creation(self):
        """Test basic manager creation"""
        manager = TranscriptionStateManager()
        
        assert manager.storage is not None
        assert manager.auto_cleanup is True
        
    def test_transcription_lifecycle(self):
        """Test complete transcription lifecycle"""
        manager = TranscriptionStateManager()
        observer_calls = []
        
        # Add observer
        def test_observer(state, event_type):
            observer_calls.append((state.state_key, event_type))
            
        manager.add_observer(test_observer)
        
        # Create transcription
        state = manager.create_transcription(peer_id=123, msg_id=456)
        
        assert state.peer_id == 123
        assert state.msg_id == 456
        assert state.is_pending
        
        # Update from API response
        updated = manager.update_transcription_from_response(
            peer_id=123,
            msg_id=456,
            transcription_id=789,
            text="processing...",
            pending=True
        )
        
        assert updated is state
        assert updated.transcription_id == 789
        assert updated.is_processing
        
        # Complete via update event
        completed = manager.update_transcription_from_update(
            peer_id=123,
            msg_id=456,
            transcription_id=789,
            text="Hello world",
            pending=False
        )
        
        assert completed is state
        assert completed.is_completed
        assert completed.text == "Hello world"
        
        # Verify observer calls
        assert len(observer_calls) == 3
        assert observer_calls[0] == ("123:456", "created")
        assert "updated_from_response" in observer_calls[1][1]
        assert "updated_from_update" in observer_calls[2][1]
        
    def test_transcription_failure(self):
        """Test transcription failure handling"""
        manager = TranscriptionStateManager()
        
        # Create transcription
        state = manager.create_transcription(peer_id=123, msg_id=456)
        
        # Mark as failed
        failed = manager.mark_transcription_failed(
            peer_id=123,
            msg_id=456,
            error_message="Network timeout"
        )
        
        assert failed is state
        assert failed.is_failed
        assert failed.error_message == "Network timeout"
        
    def test_active_transcriptions(self):
        """Test active transcription tracking"""
        manager = TranscriptionStateManager()
        
        # Create multiple transcriptions
        state1 = manager.create_transcription(peer_id=123, msg_id=456)
        state2 = manager.create_transcription(peer_id=123, msg_id=789)
        state3 = manager.create_transcription(peer_id=456, msg_id=123)
        
        # Complete one
        state2.status = TranscriptionStatus.COMPLETED
        
        # Get active transcriptions
        active = manager.get_active_transcriptions()
        assert len(active) == 2
        assert state1 in active
        assert state3 in active
        assert state2 not in active
        
    def test_peer_transcriptions(self):
        """Test peer-specific transcription retrieval"""
        manager = TranscriptionStateManager()
        
        # Create transcriptions for different peers
        state1 = manager.create_transcription(peer_id=123, msg_id=456)
        state2 = manager.create_transcription(peer_id=123, msg_id=789)
        state3 = manager.create_transcription(peer_id=456, msg_id=123)
        
        # Get transcriptions for peer 123
        peer_transcriptions = manager.get_transcriptions_by_peer(123)
        assert len(peer_transcriptions) == 2
        assert state1 in peer_transcriptions
        assert state2 in peer_transcriptions
        assert state3 not in peer_transcriptions
        
    def test_statistics(self):
        """Test comprehensive statistics"""
        manager = TranscriptionStateManager(auto_cleanup=False)
        
        # Create transcriptions
        manager.create_transcription(peer_id=123, msg_id=456)
        manager.create_transcription(peer_id=123, msg_id=789)
        
        stats = manager.get_transcription_statistics()
        
        assert stats['total_created'] == 2
        assert stats['current_total'] == 2
        assert stats['auto_cleanup_enabled'] is False
        assert stats['observers_count'] == 0
        
    def test_observer_management(self):
        """Test observer add/remove functionality"""
        manager = TranscriptionStateManager()
        
        def observer1(state, event_type):
            pass
            
        def observer2(state, event_type):
            pass
            
        # Add observers
        manager.add_observer(observer1)
        manager.add_observer(observer2)
        
        stats = manager.get_transcription_statistics()
        assert stats['observers_count'] == 2
        
        # Remove observer
        manager.remove_observer(observer1)
        
        stats = manager.get_transcription_statistics()
        assert stats['observers_count'] == 1
        
        # Remove non-existent observer (should not error)
        manager.remove_observer(observer1)
        
        stats = manager.get_transcription_statistics()
        assert stats['observers_count'] == 1
        
    def test_observer_error_handling(self):
        """Test observer error handling"""
        manager = TranscriptionStateManager()
        
        def failing_observer(state, event_type):
            raise Exception("Observer error")
            
        def working_observer(state, event_type):
            working_observer.called = True
            
        working_observer.called = False
        
        # Add both observers
        manager.add_observer(failing_observer)
        manager.add_observer(working_observer)
        
        # Create transcription (should not fail despite observer error)
        with patch('logging.getLogger') as mock_logger:
            logger_mock = Mock()
            mock_logger.return_value = logger_mock
            
            state = manager.create_transcription(peer_id=123, msg_id=456)
            
            # Working observer should still be called
            assert working_observer.called
            assert state is not None
            
    def test_auto_cleanup_integration(self):
        """Test auto cleanup integration"""
        manager = TranscriptionStateManager(
            cleanup_interval=1,
            max_completed_age=1,
            auto_cleanup=True
        )
        
        # Create and complete transcription
        state = manager.create_transcription(peer_id=123, msg_id=456)
        state.status = TranscriptionStatus.COMPLETED
        state.last_update = datetime.now(timezone.utc) - timedelta(seconds=2)
        
        # Force last cleanup to be old
        manager.storage._last_cleanup = datetime.now(timezone.utc) - timedelta(seconds=2)
        
        # Create new transcription (should trigger auto cleanup)
        new_state = manager.create_transcription(peer_id=456, msg_id=789)
        
        # Old state should be cleaned up
        assert manager.storage.get_state_count() == 1
        assert manager.get_transcription(peer_id=123, msg_id=456) is None
        assert manager.get_transcription(peer_id=456, msg_id=789) is new_state


@pytest.mark.asyncio
async def test_example_usage():
    """Test the example usage pattern"""
    from .state_manager import example_state_management
    
    # This should run without errors
    await example_state_management()


def test_performance_concurrent_operations():
    """Test performance with many concurrent operations"""
    manager = TranscriptionStateManager()
    
    def create_and_update_states(start_id: int, count: int):
        """Create and update states in a thread"""
        for i in range(count):
            peer_id = start_id + i
            msg_id = 123
            
            # Create state
            state = manager.create_transcription(peer_id=peer_id, msg_id=msg_id)
            
            # Update with response
            manager.update_transcription_from_response(
                peer_id=peer_id,
                msg_id=msg_id,
                transcription_id=i * 1000,
                text=f"text_{i}",
                pending=True
            )
            
            # Complete with update
            manager.update_transcription_from_update(
                peer_id=peer_id,
                msg_id=msg_id,
                transcription_id=i * 1000,
                text=f"final_text_{i}",
                pending=False
            )
            
    start_time = time.time()
    
    # Run concurrent operations
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(create_and_update_states, i * 100, 25)
            for i in range(4)
        ]
        
        for future in as_completed(futures):
            future.result()
            
    end_time = time.time()
    duration = end_time - start_time
    
    # Verify results
    stats = manager.get_transcription_statistics()
    assert stats['total_created'] == 100
    assert stats['total_completed'] >= 90  # Most should be completed
    
    # Performance check (should handle 100 operations in reasonable time)
    assert duration < 5.0, f"Performance test took too long: {duration}s"
    
    print(f"Performance test: {100} transcriptions in {duration:.2f}s")
    print(f"Final statistics: {stats}")


if __name__ == "__main__":
    # Run specific tests
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "performance":
        test_performance_concurrent_operations()
    else:
        # Run all tests with pytest
        pytest.main([__file__, "-v"])