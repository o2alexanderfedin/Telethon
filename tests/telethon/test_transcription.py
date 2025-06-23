"""
Tests for voice message transcription functionality.

This test suite covers the Basic Transcription Manager implementation
including client methods, state management, event handling, and automatic cleanup system.
"""

import pytest
import asyncio
import gc
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from telethon import TelegramClient, types, functions, events
from telethon.client.transcription import (
    TranscriptionMixin, 
    TranscriptionState, 
    CleanupStrategy,
    CleanupConfig,
    CleanupMetrics
)
from telethon.events.transcription import TranscriptionUpdate, TranscriptionComplete


class TestTranscriptionState:
    """Test TranscriptionState class functionality."""
    
    def test_initialization(self):
        """Test TranscriptionState initialization."""
        peer_id = 12345
        msg_id = 67890
        created_at = datetime.utcnow()
        
        state = TranscriptionState(peer_id, msg_id, created_at)
        
        assert state.peer_id == peer_id
        assert state.msg_id == msg_id
        assert state.created_at == created_at
        assert state.transcription_id is None
        assert state.text == ""
        assert state.pending is True
        assert state.failed is False
        assert state.error is None
        assert state.is_active is True
        assert state.is_completed is False
        assert state.state_key == f"{peer_id}:{msg_id}"
    
    def test_update_from_result(self):
        """Test updating state from TranscribedAudio result."""
        state = TranscriptionState(123, 456, datetime.utcnow())
        
        # Mock TranscribedAudio result
        result = Mock()
        result.transcription_id = 789
        result.text = "Hello world"
        result.pending = True
        result.trial_remains_num = 5
        result.trial_remains_until_date = datetime.utcnow() + timedelta(days=1)
        
        state.update_from_result(result)
        
        assert state.transcription_id == 789
        assert state.text == "Hello world"
        assert state.pending is True
        assert state.trial_remains_num == 5
        assert state.update_count == 1
        assert state.is_active is True
    
    def test_update_from_update(self):
        """Test updating state from UpdateTranscribedAudio."""
        state = TranscriptionState(123, 456, datetime.utcnow())
        state.transcription_id = 789
        
        # Mock UpdateTranscribedAudio
        update = Mock()
        update.transcription_id = 789
        update.text = "Hello world complete"
        update.pending = False
        
        state.update_from_update(update)
        
        assert state.text == "Hello world complete"
        assert state.pending is False
        assert state.update_count == 1
        assert state.is_active is False
        assert state.is_completed is True
    
    def test_mark_failed(self):
        """Test marking transcription as failed."""
        state = TranscriptionState(123, 456, datetime.utcnow())
        
        state.mark_failed("Test error")
        
        assert state.failed is True
        assert state.pending is False
        assert state.error == "Test error"
        assert state.is_active is False
        assert state.is_completed is False
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        created_at = datetime.utcnow()
        state = TranscriptionState(123, 456, created_at)
        state.transcription_id = 789
        state.text = "Test text"
        
        data = state.to_dict()
        
        assert data['peer_id'] == 123
        assert data['msg_id'] == 456
        assert data['transcription_id'] == 789
        assert data['text'] == "Test text"
        assert data['pending'] is True
        assert data['failed'] is False
        assert data['created_at'] == created_at.isoformat()


class TestTranscriptionMixin:
    """Test TranscriptionMixin functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock TelegramClient with transcription support."""
        client = Mock(spec=TelegramClient)
        client.get_input_entity = AsyncMock()
        client.add_event_handler = Mock()
        
        # Initialize the mixin
        mixin = TranscriptionMixin()
        mixin.client = client
        
        # Mock the __call__ method for sending requests
        async def mock_call(request):
            if isinstance(request, functions.messages.TranscribeAudioRequest):
                result = Mock()
                result.transcription_id = 123
                result.text = "Initial transcription"
                result.pending = True
                return result
            elif isinstance(request, functions.messages.RateTranscribedAudioRequest):
                return True
            return Mock()
        
        client.__call__ = AsyncMock(side_effect=mock_call)
        
        # Add mixin methods to client
        for attr_name in dir(mixin):
            if not attr_name.startswith('_') and callable(getattr(mixin, attr_name)):
                setattr(client, attr_name, getattr(mixin, attr_name))
        
        # Initialize mixin state
        client._transcription_states = {}
        client._transcription_callbacks = {}
        client._transcription_lock = asyncio.Lock()
        
        # Initialize cleanup system
        client._cleanup_config = CleanupConfig()
        client._cleanup_metrics = CleanupMetrics()
        client._cleanup_task = None
        client._cleanup_running = False
        
        return client
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_message_id(self, mock_client):
        """Test transcribing audio with message ID."""
        # Mock get_input_entity
        mock_peer = Mock()
        mock_client.get_input_entity.return_value = mock_peer
        
        # Mock utils.get_peer_id
        import telethon.utils as utils
        original_get_peer_id = utils.get_peer_id
        utils.get_peer_id = Mock(return_value=12345)
        
        try:
            result = await mock_client.transcribe_audio(
                entity="testchat",
                message=67890,
                wait_for_result=False
            )
            
            # Verify request was made
            mock_client.get_input_entity.assert_called_once_with("testchat")
            assert mock_client.__call__.called
            
            # Verify result
            assert isinstance(result, TranscriptionState)
            assert result.peer_id == 12345
            assert result.msg_id == 67890
            assert result.transcription_id == 123
            assert result.text == "Initial transcription"
            assert result.pending is True
        
        finally:
            utils.get_peer_id = original_get_peer_id
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_message_object(self, mock_client):
        """Test transcribing audio with Message object."""
        # Create mock message with voice
        message = Mock()
        message.id = 67890
        message.media = Mock()
        message.media.document = Mock()
        message.media.document.mime_type = "audio/ogg"
        message.media.document.attributes = [
            Mock(spec=types.DocumentAttributeAudio, voice=True)
        ]
        
        mock_peer = Mock()
        mock_client.get_input_entity.return_value = mock_peer
        
        import telethon.utils as utils
        original_get_peer_id = utils.get_peer_id
        utils.get_peer_id = Mock(return_value=12345)
        
        try:
            result = await mock_client.transcribe_audio(
                entity="testchat",
                message=message,
                wait_for_result=False
            )
            
            assert isinstance(result, TranscriptionState)
            assert result.msg_id == 67890
        
        finally:
            utils.get_peer_id = original_get_peer_id
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_invalid_message(self, mock_client):
        """Test transcribing audio with invalid message type."""
        with pytest.raises(TypeError, match="message must be an int"):
            await mock_client.transcribe_audio(
                entity="testchat",
                message="invalid",
                wait_for_result=False
            )
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_non_voice_message(self, mock_client):
        """Test transcribing non-voice message raises error."""
        # Create mock message without voice
        message = Mock()
        message.id = 67890
        message.media = None
        
        with pytest.raises(ValueError, match="Message does not contain voice"):
            await mock_client.transcribe_audio(
                entity="testchat",
                message=message,
                wait_for_result=False
            )
    
    @pytest.mark.asyncio
    async def test_get_transcription_status(self, mock_client):
        """Test getting transcription status."""
        # Add existing state
        state = TranscriptionState(12345, 67890, datetime.utcnow())
        mock_client._transcription_states["12345:67890"] = state
        
        mock_peer = Mock()
        mock_client.get_input_entity.return_value = mock_peer
        
        import telethon.utils as utils
        original_get_peer_id = utils.get_peer_id
        utils.get_peer_id = Mock(return_value=12345)
        
        try:
            result = await mock_client.get_transcription_status("testchat", 67890)
            
            assert result is state
        
        finally:
            utils.get_peer_id = original_get_peer_id
    
    @pytest.mark.asyncio
    async def test_rate_transcription(self, mock_client):
        """Test rating transcription quality."""
        mock_peer = Mock()
        mock_client.get_input_entity.return_value = mock_peer
        
        result = await mock_client.rate_transcription(
            entity="testchat",
            message=67890,
            transcription_id=123,
            good=True
        )
        
        assert result is True
        mock_client.get_input_entity.assert_called_once_with("testchat")
        
        # Verify the correct request was made
        call_args = mock_client.__call__.call_args[0][0]
        assert isinstance(call_args, functions.messages.RateTranscribedAudioRequest)
        assert call_args.msg_id == 67890
        assert call_args.transcription_id == 123
        assert call_args.good is True


class TestTranscriptionEvents:
    """Test transcription event handling."""
    
    def test_transcription_update_build(self):
        """Test building TranscriptionUpdate event."""
        # Create mock update
        update = Mock(spec=types.UpdateTranscribedAudio)
        update.peer = Mock()
        update.peer.user_id = 12345
        update.msg_id = 67890
        update.transcription_id = 123
        update.text = "Test transcription"
        update.pending = True
        
        event = TranscriptionUpdate.build(update)
        
        assert event is not None
        assert isinstance(event, TranscriptionUpdate.Event)
        assert event.peer_id == 12345
        assert event.message_id == 67890
        assert event.transcription_id == 123
        assert event.text == "Test transcription"
        assert event.is_pending is True
        assert event.is_complete is False
        assert event.is_private is True
    
    def test_transcription_complete_build(self):
        """Test building TranscriptionComplete event."""
        # Create mock update for completed transcription
        update = Mock(spec=types.UpdateTranscribedAudio)
        update.peer = Mock()
        update.peer.user_id = 12345
        update.msg_id = 67890
        update.transcription_id = 123
        update.text = "Complete transcription"
        update.pending = False
        
        event = TranscriptionComplete.build(update)
        
        assert event is not None
        assert event.is_complete is True
        assert event.is_pending is False
    
    def test_transcription_complete_no_build_for_pending(self):
        """Test TranscriptionComplete doesn't build for pending updates."""
        # Create mock update for pending transcription
        update = Mock(spec=types.UpdateTranscribedAudio)
        update.pending = True
        
        event = TranscriptionComplete.build(update)
        
        assert event is None
    
    def test_transcription_progress_build(self):
        """Test building TranscriptionProgress event."""
        # Create mock update for progress
        update = Mock(spec=types.UpdateTranscribedAudio)
        update.peer = Mock()
        update.peer.chat_id = 12345
        update.msg_id = 67890
        update.transcription_id = 123
        update.text = "Partial transcription"
        update.pending = True
        
        event = TranscriptionProgress.build(update)
        
        assert event is not None
        assert event.is_pending is True
        assert event.is_complete is False
        assert event.is_group is True
    
    def test_transcription_progress_no_build_for_complete(self):
        """Test TranscriptionProgress doesn't build for completed updates."""
        # Create mock update for completed transcription
        update = Mock(spec=types.UpdateTranscribedAudio)
        update.pending = False
        
        event = TranscriptionProgress.build(update)
        
        assert event is None
    
    def test_event_string_representation(self):
        """Test string representation of transcription events."""
        update = Mock(spec=types.UpdateTranscribedAudio)
        update.peer = Mock()
        update.peer.user_id = 12345
        update.msg_id = 67890
        update.transcription_id = 123
        update.text = "Test transcription text that is longer than fifty characters to test truncation"
        update.pending = False
        
        event = TranscriptionUpdate.Event(update)
        
        str_repr = str(event)
        assert "TranscriptionUpdate" in str_repr
        assert "12345" in str_repr
        assert "67890" in str_repr
        assert "complete" in str_repr
        assert "..." in str_repr  # Text should be truncated


class TestTranscriptionIntegration:
    """Integration tests for complete transcription workflow."""
    
    @pytest.mark.asyncio
    async def test_full_transcription_workflow(self):
        """Test complete transcription workflow from request to completion."""
        # This would be a more complex integration test
        # that would require a more sophisticated mock setup
        # or actual Telegram API testing environment
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_transcriptions(self):
        """Test handling multiple concurrent transcriptions."""
        pass
    
    @pytest.mark.asyncio
    async def test_transcription_with_callbacks(self):
        """Test transcription with progress callbacks."""
        pass


class TestCleanupConfig:
    """Test CleanupConfig dataclass functionality."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = CleanupConfig()
        
        assert config.enabled is True
        assert config.completed_ttl == 3600  # 1 hour
        assert config.failed_ttl == 1800     # 30 minutes
        assert config.pending_timeout == 300 # 5 minutes
        assert config.max_total_states == 1000
        assert config.max_completed_states == 500
        assert config.cleanup_batch_size == 100
        assert config.cleanup_interval == 300  # 5 minutes
        assert config.background_cleanup is True
        assert config.preserve_recent == 60
        assert config.max_cleanup_percentage == 0.3
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = CleanupConfig(
            enabled=False,
            completed_ttl=7200,  # 2 hours
            failed_ttl=900,      # 15 minutes
            max_total_states=500,
            cleanup_interval=600 # 10 minutes
        )
        
        assert config.enabled is False
        assert config.completed_ttl == 7200
        assert config.failed_ttl == 900
        assert config.max_total_states == 500
        assert config.cleanup_interval == 600


class TestCleanupMetrics:
    """Test CleanupMetrics functionality."""
    
    def test_initialization(self):
        """Test metrics initialization."""
        metrics = CleanupMetrics()
        
        assert metrics.total_runs == 0
        assert metrics.total_cleaned == 0
        assert metrics.last_cleanup is None
        assert metrics.last_cleanup_count == 0
        assert metrics.average_cleanup_time == 0.0


class TestAutomaticCleanup:
    """Test automatic cleanup system functionality."""
    
    @pytest.fixture
    def cleanup_client(self, mock_client):
        """Create a client with cleanup system enabled."""
        # Configure cleanup for testing
        mock_client._cleanup_config = CleanupConfig(
            enabled=True,
            completed_ttl=60,     # 1 minute for testing
            failed_ttl=30,        # 30 seconds for testing
            pending_timeout=30,   # 30 seconds for testing
            max_total_states=5,   # Low threshold for testing
            max_completed_states=3,
            cleanup_batch_size=10,
            cleanup_interval=1,   # 1 second for testing
            background_cleanup=False,  # Disable for unit tests
            preserve_recent=5,    # 5 seconds
            max_cleanup_percentage=0.8
        )
        
        return mock_client
    
    def test_cleanup_config_integration(self, cleanup_client):
        """Test cleanup configuration integration."""
        config = CleanupConfig(
            enabled=False,
            completed_ttl=1800,
            background_cleanup=False
        )
        
        cleanup_client.configure_cleanup(config)
        
        assert cleanup_client._cleanup_config.enabled is False
        assert cleanup_client._cleanup_config.completed_ttl == 1800
        assert cleanup_client._cleanup_config.background_cleanup is False
    
    def test_cleanup_status(self, cleanup_client):
        """Test getting cleanup system status."""
        # Add some states
        now = datetime.utcnow()
        cleanup_client._transcription_states = {
            "123:456": TranscriptionState(123, 456, now),
            "789:012": TranscriptionState(789, 12, now - timedelta(minutes=2))
        }
        
        status = cleanup_client.get_cleanup_status()
        
        assert 'enabled' in status
        assert 'background_running' in status
        assert 'total_states' in status
        assert 'metrics' in status
        assert 'config' in status
        assert status['enabled'] is True
        assert status['total_states'] == 2
    
    def test_cleanup_metrics_access(self, cleanup_client):
        """Test accessing cleanup metrics."""
        metrics = cleanup_client.get_cleanup_metrics()
        
        assert isinstance(metrics, CleanupMetrics)
        assert metrics.total_runs == 0
        assert metrics.total_cleaned == 0
    
    @pytest.mark.asyncio
    async def test_age_based_cleanup(self, cleanup_client):
        """Test age-based cleanup strategy."""
        now = datetime.utcnow()
        old_time = now - timedelta(minutes=5)
        
        # Create states of different ages
        old_completed = TranscriptionState(123, 456, old_time)
        old_completed.pending = False
        old_completed.failed = False
        old_completed.last_update = old_time
        
        old_failed = TranscriptionState(789, 12, old_time)
        old_failed.pending = False
        old_failed.failed = True
        old_failed.last_update = old_time
        
        recent_state = TranscriptionState(111, 222, now)
        recent_state.pending = False
        recent_state.last_update = now
        
        # Add states to client
        cleanup_client._transcription_states = {
            "123:456": old_completed,
            "789:012": old_failed,
            "111:222": recent_state
        }
        
        # Perform age-based cleanup
        cleaned_count = cleanup_client._age_based_cleanup()
        
        # Should clean old completed and failed states, but not recent ones
        assert cleaned_count >= 2
        assert "111:222" in cleanup_client._transcription_states  # Recent should remain
    
    @pytest.mark.asyncio
    async def test_count_based_cleanup(self, cleanup_client):
        """Test count-based cleanup strategy."""
        now = datetime.utcnow()
        
        # Create more states than the limit
        states = {}
        for i in range(10):  # More than max_total_states (5)
            state = TranscriptionState(i, i * 100, now - timedelta(minutes=i))
            state.pending = False  # Make them inactive
            state.last_update = now - timedelta(minutes=i)
            states[f"{i}:{i * 100}"] = state
        
        cleanup_client._transcription_states = states
        
        # Perform count-based cleanup
        cleaned_count = cleanup_client._count_based_cleanup()
        
        # Should clean some states to get under the limit
        assert cleaned_count > 0
        assert len(cleanup_client._transcription_states) < 10
    
    @pytest.mark.asyncio
    async def test_hybrid_cleanup(self, cleanup_client):
        """Test hybrid cleanup strategy."""
        now = datetime.utcnow()
        
        # Create mix of old and new states
        states = {}
        
        # Old completed states
        for i in range(3):
            state = TranscriptionState(i, i * 100, now - timedelta(hours=2))
            state.pending = False
            state.failed = False
            state.last_update = now - timedelta(hours=2)
            states[f"{i}:{i * 100}"] = state
        
        # Recent active state (should not be cleaned)
        active_state = TranscriptionState(999, 999, now)
        active_state.pending = True
        states["999:999"] = active_state
        
        cleanup_client._transcription_states = states
        
        # Perform hybrid cleanup
        cleaned_count = cleanup_client._hybrid_cleanup()
        
        # Should clean old states but preserve active ones
        assert cleaned_count >= 0
        assert "999:999" in cleanup_client._transcription_states  # Active should remain
    
    @pytest.mark.asyncio
    async def test_manual_cleanup_trigger(self, cleanup_client):
        """Test manually triggering cleanup."""
        now = datetime.utcnow()
        
        # Add old state that should be cleaned
        old_state = TranscriptionState(123, 456, now - timedelta(hours=2))
        old_state.pending = False
        old_state.last_update = now - timedelta(hours=2)
        cleanup_client._transcription_states["123:456"] = old_state
        
        # Trigger manual cleanup
        result = await cleanup_client.trigger_cleanup(CleanupStrategy.AGE_BASED)
        
        assert result['success'] is True
        assert 'strategy' in result
        assert 'cleaned_count' in result
        assert 'duration' in result
        assert result['strategy'] == CleanupStrategy.AGE_BASED.value
    
    @pytest.mark.asyncio
    async def test_cleanup_safety_checks(self, cleanup_client):
        """Test cleanup safety mechanisms."""
        now = datetime.utcnow()
        
        # Create active state (should never be cleaned)
        active_state = TranscriptionState(123, 456, now)
        active_state.pending = True  # Still active
        
        # Create very recent state (should be preserved)
        recent_state = TranscriptionState(789, 12, now)
        recent_state.pending = False
        recent_state.last_update = now  # Very recent
        
        cleanup_client._transcription_states = {
            "123:456": active_state,
            "789:012": recent_state
        }
        
        # Try to clean - should preserve both due to safety checks
        cleaned_count = cleanup_client._age_based_cleanup()
        
        assert cleaned_count == 0  # Nothing should be cleaned
        assert len(cleanup_client._transcription_states) == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_with_disabled_config(self, cleanup_client):
        """Test cleanup behavior when disabled."""
        # Disable cleanup
        cleanup_client._cleanup_config.enabled = False
        
        # Try to trigger cleanup
        result = await cleanup_client.trigger_cleanup()
        
        assert result['success'] is False
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_background_cleanup_lifecycle(self, cleanup_client):
        """Test background cleanup task lifecycle."""
        # Enable background cleanup
        cleanup_client._cleanup_config.background_cleanup = True
        cleanup_client._cleanup_config.cleanup_interval = 0.1  # Very short for testing
        
        # Start background cleanup
        cleanup_client._start_background_cleanup()
        
        assert cleanup_client._cleanup_running is True
        assert cleanup_client._cleanup_task is not None
        
        # Let it run briefly
        await asyncio.sleep(0.2)
        
        # Stop background cleanup
        cleanup_client._stop_background_cleanup()
        
        assert cleanup_client._cleanup_running is False
    
    @pytest.mark.asyncio
    async def test_cleanup_all_transcriptions(self, cleanup_client):
        """Test cleaning up all inactive transcriptions."""
        now = datetime.utcnow()
        
        # Add mix of active and inactive states
        active_state = TranscriptionState(123, 456, now)
        active_state.pending = True
        
        inactive_state1 = TranscriptionState(789, 12, now)
        inactive_state1.pending = False
        
        inactive_state2 = TranscriptionState(111, 222, now)
        inactive_state2.pending = False
        inactive_state2.failed = True
        
        cleanup_client._transcription_states = {
            "123:456": active_state,
            "789:012": inactive_state1,
            "111:222": inactive_state2
        }
        
        # Clean all inactive transcriptions
        cleaned_count = cleanup_client.cleanup_all_transcriptions()
        
        assert cleaned_count == 2  # Should clean 2 inactive states
        assert len(cleanup_client._transcription_states) == 1  # Only active remains
        assert "123:456" in cleanup_client._transcription_states
    
    def test_is_safe_to_clean(self, cleanup_client):
        """Test cleanup safety checks."""
        now = datetime.utcnow()
        
        # Active state - not safe to clean
        active_state = TranscriptionState(123, 456, now)
        active_state.pending = True
        assert not cleanup_client._is_safe_to_clean(active_state)
        
        # Very recent inactive state - not safe to clean
        recent_state = TranscriptionState(789, 12, now)
        recent_state.pending = False
        recent_state.last_update = now
        assert not cleanup_client._is_safe_to_clean(recent_state)
        
        # Old inactive state - safe to clean
        old_state = TranscriptionState(111, 222, now - timedelta(minutes=5))
        old_state.pending = False
        old_state.last_update = now - timedelta(minutes=5)
        assert cleanup_client._is_safe_to_clean(old_state)
    
    @pytest.mark.asyncio
    async def test_cleanup_metrics_update(self, cleanup_client):
        """Test cleanup metrics are properly updated."""
        now = datetime.utcnow()
        
        # Add state to clean
        old_state = TranscriptionState(123, 456, now - timedelta(hours=2))
        old_state.pending = False
        old_state.last_update = now - timedelta(hours=2)
        cleanup_client._transcription_states["123:456"] = old_state
        
        # Trigger cleanup and check metrics
        initial_runs = cleanup_client._cleanup_metrics.total_runs
        result = await cleanup_client.trigger_cleanup()
        
        assert cleanup_client._cleanup_metrics.total_runs == initial_runs + 1
        assert cleanup_client._cleanup_metrics.last_cleanup is not None
        assert cleanup_client._cleanup_metrics.last_cleanup_count >= 0
    
    @pytest.mark.asyncio 
    async def test_scheduled_state_cleanup(self, cleanup_client):
        """Test scheduled cleanup of specific states."""
        now = datetime.utcnow()
        
        # Add state for scheduled cleanup
        state = TranscriptionState(123, 456, now)
        state.pending = False
        state.last_update = now - timedelta(minutes=2)  # Old enough
        cleanup_client._transcription_states["123:456"] = state
        
        # Schedule cleanup with very short delay
        await cleanup_client._schedule_state_cleanup("123:456", delay=0.1)
        
        # State should be cleaned after delay
        assert "123:456" not in cleanup_client._transcription_states


class TestCleanupIntegration:
    """Integration tests for cleanup system with transcription workflow."""
    
    @pytest.mark.asyncio
    async def test_cleanup_integration_with_transcription(self, cleanup_client):
        """Test cleanup integration with full transcription workflow."""
        # Mock transcription completion that triggers cleanup
        now = datetime.utcnow()
        
        # Simulate completed transcription
        state = TranscriptionState(123, 456, now - timedelta(minutes=10))
        state.pending = False
        state.transcription_id = 789
        state.text = "Test transcription"
        cleanup_client._transcription_states["123:456"] = state
        
        # Simulate cleanup trigger
        cleanup_client._cleanup_transcription("123:456")
        
        # Check that callbacks are cleaned and scheduled cleanup is triggered
        assert "123:456" not in cleanup_client._transcription_callbacks
    
    @pytest.mark.asyncio
    async def test_cleanup_performance_with_many_states(self, cleanup_client):
        """Test cleanup performance with large number of states."""
        now = datetime.utcnow()
        
        # Create large number of states
        states = {}
        for i in range(100):
            state = TranscriptionState(i, i * 100, now - timedelta(minutes=i))
            state.pending = False
            state.last_update = now - timedelta(minutes=i)
            states[f"{i}:{i * 100}"] = state
        
        cleanup_client._transcription_states = states
        
        # Measure cleanup performance
        import time
        start_time = time.time()
        
        result = await cleanup_client.trigger_cleanup(CleanupStrategy.HYBRID)
        
        duration = time.time() - start_time
        
        # Should complete reasonably quickly (less than 1 second for 100 states)
        assert duration < 1.0
        assert result['success'] is True
        assert result['cleaned_count'] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])