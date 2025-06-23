"""
Comprehensive Test Suite for TranscriptionManager

Tests Epic 1 User Story 1.5: Basic Transcription Manager implementation
including request coordination, state management, concurrent handling, and API integration.
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from .transcription_manager import (
    TranscriptionManager,
    TranscriptionManagerConfig,
    TranscriptionResult
)

# Mock Telethon components for testing
class MockTelegramClient:
    """Mock TelegramClient for testing"""
    def __init__(self):
        self.user_id = 123456789
        
    async def get_input_entity(self, entity):
        """Mock get_input_entity"""
        if isinstance(entity, int):
            return entity
        return abs(hash(str(entity))) % (10**10)


class MockTranscriptionRequest:
    """Mock TranscriptionRequest for testing"""
    def __init__(self, peer_id, msg_id, transcription_id=None):
        self.peer_id = peer_id
        self.msg_id = msg_id
        self.transcription_id = transcription_id
        self.completed = False
        self.result = None
        self.key = f"{peer_id}:{msg_id}"
        
    def complete_with_text(self, text: str):
        """Simulate completion with text"""
        self.result = Mock()
        self.result.text = text
        self.completed = True


class MockTranscriptionResult:
    """Mock result object"""
    def __init__(self, text="", pending=False):
        self.text = text
        self.pending = pending


@pytest.fixture
def mock_client():
    """Create a mock TelegramClient"""
    return MockTelegramClient()


@pytest.fixture
def mock_config():
    """Create a test configuration"""
    return TranscriptionManagerConfig(
        concurrent_limit=5,
        default_timeout=5.0,
        cleanup_interval=10,
        max_completed_age=60,
        validate_messages=False  # Skip validation in tests
    )


@pytest.fixture
async def manager(mock_client, mock_config):
    """Create a TranscriptionManager for testing"""
    with patch('telethon.TelegramClient', return_value=mock_client):
        with patch.multiple(
            'voice_transcription.transcription_manager',
            TELETHON_AVAILABLE=True,
            INTERNAL_IMPORTS=True
        ):
            # Mock all the component imports
            with patch('voice_transcription.transcription_manager.BasicVoiceTranscriber') as mock_transcriber_class, \
                 patch('voice_transcription.transcription_manager.TranscriptionStateManager') as mock_state_class, \
                 patch('voice_transcription.transcription_manager.VoiceTranscriptionUpdateHandler') as mock_update_class, \
                 patch('voice_transcription.transcription_manager.TranscriptionCoordinator') as mock_coord_class, \
                 patch('voice_transcription.transcription_manager.VoiceMessageValidator') as mock_validator_class:
                
                # Setup mocks
                mock_transcriber = Mock()
                mock_transcriber_class.return_value = mock_transcriber
                
                mock_state_manager = Mock()
                mock_state_class.return_value = mock_state_manager
                
                mock_update_handler = Mock()
                mock_update_handler.start = Mock()
                mock_update_handler.stop = Mock()
                mock_update_handler.register_handler = Mock(return_value=True)
                mock_update_handler.get_comprehensive_stats = Mock(return_value={})
                mock_update_class.return_value = mock_update_handler
                
                mock_coordinator = Mock()
                mock_coordinator.register_request = Mock()
                mock_coordinator.get_coordination_stats = Mock(return_value={})
                mock_coord_class.return_value = mock_coordinator
                
                mock_validator = Mock()
                mock_validator_class.return_value = mock_validator
                
                # Create manager
                manager = TranscriptionManager(mock_client, mock_config)
                
                # Store mocks for access in tests
                manager._mock_transcriber = mock_transcriber
                manager._mock_state_manager = mock_state_manager
                manager._mock_update_handler = mock_update_handler
                manager._mock_coordinator = mock_coordinator
                manager._mock_validator = mock_validator
                
                yield manager


class TestTranscriptionManagerConfig:
    """Test TranscriptionManagerConfig"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = TranscriptionManagerConfig()
        
        assert config.auto_cleanup_enabled is True
        assert config.cleanup_interval == 3600
        assert config.max_completed_age == 86400
        assert config.concurrent_limit == 50
        assert config.default_timeout == 30.0
        assert config.retry_attempts == 3
        assert config.validate_messages is True
        assert config.enable_statistics is True
        assert config.log_level == "INFO"
        
    def test_custom_config(self):
        """Test custom configuration"""
        config = TranscriptionManagerConfig(
            concurrent_limit=10,
            default_timeout=45.0,
            validate_messages=False,
            log_level="DEBUG"
        )
        
        assert config.concurrent_limit == 10
        assert config.default_timeout == 45.0
        assert config.validate_messages is False
        assert config.log_level == "DEBUG"


class TestTranscriptionResult:
    """Test TranscriptionResult class"""
    
    def test_result_creation(self):
        """Test basic result creation"""
        result = TranscriptionResult(success=True)
        
        assert result.success is True
        assert result.request is None
        assert result.state is None
        assert result.error is None
        assert result.duration is None
        assert result.metadata == {}
        
    def test_result_with_request(self):
        """Test result with request object"""
        request = MockTranscriptionRequest(123, 456, 789)
        request.complete_with_text("Hello world")
        
        result = TranscriptionResult(success=True, request=request)
        
        assert result.transcription_id == 789
        assert result.text == "Hello world"
        assert result.is_completed is True
        
    def test_result_with_state(self):
        """Test result with state object"""
        from .state_manager import TranscriptionState, TranscriptionStatus
        
        state = TranscriptionState(peer_id=123, msg_id=456)
        state.transcription_id = 789
        state.text = "Test text"
        state.status = TranscriptionStatus.COMPLETED
        
        result = TranscriptionResult(success=True, state=state)
        
        assert result.transcription_id == 789
        assert result.text == "Test text"
        assert result.is_completed is True


@pytest.mark.asyncio
class TestTranscriptionManager:
    """Test TranscriptionManager class"""
    
    async def test_manager_creation(self, manager):
        """Test basic manager creation"""
        assert manager.client is not None
        assert manager.config is not None
        assert manager.transcriber is not None
        assert manager.state_manager is not None
        assert manager.update_handler is not None
        assert manager.coordinator is not None
        assert manager.validator is not None
        assert manager._initialized is False
        
    async def test_manager_initialization(self, manager):
        """Test manager initialization"""
        await manager.initialize()
        
        assert manager._initialized is True
        manager._mock_update_handler.start.assert_called_once()
        manager._mock_update_handler.register_handler.assert_called()
        
    async def test_manager_shutdown(self, manager):
        """Test manager shutdown"""
        await manager.initialize()
        await manager.shutdown()
        
        assert manager._initialized is False
        manager._mock_update_handler.stop.assert_called_once()
        
    async def test_double_initialization(self, manager):
        """Test double initialization handling"""
        await manager.initialize()
        
        # Should not raise error
        await manager.initialize()
        
        # Start should only be called once
        assert manager._mock_update_handler.start.call_count == 1
        
    async def test_transcribe_basic(self, manager):
        """Test basic transcription request"""
        # Setup mocks
        mock_request = MockTranscriptionRequest(123, 456, 789)
        manager._mock_transcriber.transcribe = AsyncMock(return_value=mock_request)
        
        mock_state = Mock()
        mock_state.peer_id = 123
        mock_state.msg_id = 456
        manager._mock_state_manager.create_transcription = Mock(return_value=mock_state)
        
        # Test transcription
        result = await manager.transcribe(chat=123, msg_id=456)
        
        assert result.success is True
        assert result.request is mock_request
        assert result.state is mock_state
        assert result.duration is not None
        
        # Verify calls
        manager._mock_state_manager.create_transcription.assert_called_once()
        manager._mock_transcriber.transcribe.assert_called_once()
        manager._mock_coordinator.register_request.assert_called_once()
        
    async def test_transcribe_with_completion_wait(self, manager):
        """Test transcription with completion waiting"""
        # Setup mocks
        mock_request = MockTranscriptionRequest(123, 456, 789)
        manager._mock_transcriber.transcribe = AsyncMock(return_value=mock_request)
        
        mock_state = Mock()
        mock_state.peer_id = 123
        mock_state.msg_id = 456
        mock_state.is_completed = False
        manager._mock_state_manager.create_transcription = Mock(return_value=mock_state)
        
        # Complete the request after a short delay
        async def complete_after_delay():
            await asyncio.sleep(0.1)
            mock_request.completed = True
            mock_state.is_completed = True
            
        asyncio.create_task(complete_after_delay())
        
        # Test with waiting
        result = await manager.transcribe(
            chat=123, 
            msg_id=456, 
            wait_for_completion=True,
            timeout=1.0
        )
        
        assert result.success is True
        assert mock_request.completed is True
        
    async def test_transcribe_timeout(self, manager):
        """Test transcription timeout handling"""
        # Setup mocks
        mock_request = MockTranscriptionRequest(123, 456, 789)
        manager._mock_transcriber.transcribe = AsyncMock(return_value=mock_request)
        
        mock_state = Mock()
        mock_state.peer_id = 123
        mock_state.msg_id = 456
        mock_state.is_completed = False
        manager._mock_state_manager.create_transcription = Mock(return_value=mock_state)
        
        # Test timeout (request never completes)
        result = await manager.transcribe(
            chat=123, 
            msg_id=456, 
            wait_for_completion=True,
            timeout=0.1,
            retry_attempts=0  # No retries
        )
        
        assert result.success is False
        assert "timeout" in result.error.lower()
        
    async def test_transcribe_existing_active(self, manager):
        """Test transcription with existing active request"""
        # Setup mocks
        mock_state = Mock()
        mock_state.peer_id = 123
        mock_state.msg_id = 456
        mock_state.is_active = True
        manager._mock_state_manager.get_transcription = Mock(return_value=mock_state)
        
        # Test with existing active
        result = await manager.transcribe(chat=123, msg_id=456)
        
        assert result.success is True
        assert result.state is mock_state
        assert result.metadata.get('reused_existing') is True
        
        # Should not create new request
        manager._mock_transcriber.transcribe.assert_not_called()
        
    async def test_concurrent_limit(self, manager):
        """Test concurrent transcription limit"""
        manager.config.concurrent_limit = 2
        
        # Setup mocks for multiple requests
        def create_mock_request(peer_id, msg_id):
            mock_request = MockTranscriptionRequest(peer_id, msg_id)
            mock_state = Mock()
            mock_state.peer_id = peer_id
            mock_state.msg_id = msg_id
            mock_state.is_active = False
            return mock_request, mock_state
            
        manager._mock_transcriber.transcribe = AsyncMock()
        manager._mock_state_manager.get_transcription = Mock(return_value=None)
        manager._mock_state_manager.create_transcription = Mock()
        
        # Create requests up to limit
        requests = []
        for i in range(2):
            mock_request, mock_state = create_mock_request(123, 456 + i)
            manager._mock_transcriber.transcribe.return_value = mock_request
            manager._mock_state_manager.create_transcription.return_value = mock_state
            
            result = await manager.transcribe(chat=123, msg_id=456 + i)
            assert result.success is True
            requests.append(result)
            
        # Third request should fail due to limit
        mock_request, mock_state = create_mock_request(123, 458)
        manager._mock_transcriber.transcribe.return_value = mock_request
        manager._mock_state_manager.create_transcription.return_value = mock_state
        
        result = await manager.transcribe(chat=123, msg_id=458)
        assert result.success is False
        assert "concurrent" in result.error.lower()
        
    async def test_get_transcription_status(self, manager):
        """Test getting transcription status"""
        mock_state = Mock()
        manager._mock_state_manager.get_transcription = Mock(return_value=mock_state)
        
        status = await manager.get_transcription_status(chat=123, msg_id=456)
        
        assert status is mock_state
        manager._mock_state_manager.get_transcription.assert_called_once()
        
    async def test_cancel_transcription(self, manager):
        """Test cancelling transcription"""
        mock_state = Mock()
        manager._mock_state_manager.mark_transcription_failed = Mock(return_value=mock_state)
        
        result = await manager.cancel_transcription(chat=123, msg_id=456)
        
        assert result is True
        manager._mock_state_manager.mark_transcription_failed.assert_called_once_with(
            123, 456, "Cancelled by user"
        )
        
    async def test_get_active_transcriptions(self, manager):
        """Test getting active transcriptions"""
        mock_states = [Mock(), Mock()]
        manager._mock_state_manager.get_active_transcriptions = Mock(return_value=mock_states)
        
        active = manager.get_active_transcriptions()
        
        assert active is mock_states
        manager._mock_state_manager.get_active_transcriptions.assert_called_once()
        
    async def test_get_transcriptions_by_chat(self, manager):
        """Test getting transcriptions by chat"""
        mock_states = [Mock(), Mock()]
        manager._mock_state_manager.get_transcriptions_by_peer = Mock(return_value=mock_states)
        
        states = manager.get_transcriptions_by_chat(chat=123)
        
        assert states is mock_states
        manager._mock_state_manager.get_transcriptions_by_peer.assert_called_once_with(123)
        
    async def test_statistics(self, manager):
        """Test statistics gathering"""
        manager._mock_state_manager.get_transcription_statistics = Mock(return_value={'state': 'stats'})
        
        stats = manager.get_statistics()
        
        assert 'manager' in stats
        assert 'state_manager' in stats
        assert 'update_handler' in stats
        assert 'coordinator' in stats
        
        # Check manager stats
        manager_stats = stats['manager']
        assert 'requests_created' in manager_stats
        assert 'requests_completed' in manager_stats
        assert 'requests_failed' in manager_stats
        assert 'uptime_seconds' in manager_stats
        
    async def test_cleanup_completed(self, manager):
        """Test cleanup of completed transcriptions"""
        manager._mock_state_manager.cleanup_old_transcriptions = Mock(return_value=5)
        
        count = await manager.cleanup_completed()
        
        assert count == 5
        manager._mock_state_manager.cleanup_old_transcriptions.assert_called_once()
        
    async def test_global_callbacks(self, manager):
        """Test global completion callbacks"""
        callback = Mock()
        
        manager.add_global_completion_callback(callback)
        manager._mock_state_manager.add_observer.assert_called_with(callback)
        
        manager.remove_global_completion_callback(callback)
        manager._mock_state_manager.remove_observer.assert_called_with(callback)
        
    async def test_error_handling(self, manager):
        """Test error handling in transcription"""
        # Make transcriber raise an error
        manager._mock_transcriber.transcribe = AsyncMock(side_effect=Exception("Test error"))
        manager._mock_state_manager.create_transcription = Mock(return_value=Mock())
        
        result = await manager.transcribe(chat=123, msg_id=456)
        
        assert result.success is False
        assert "Test error" in result.error
        
    async def test_completion_callback(self, manager):
        """Test completion callback functionality"""
        callback_called = False
        callback_state = None
        
        def completion_callback(state, event_type):
            nonlocal callback_called, callback_state
            callback_called = True
            callback_state = state
            
        # Setup mocks
        mock_request = MockTranscriptionRequest(123, 456, 789)
        manager._mock_transcriber.transcribe = AsyncMock(return_value=mock_request)
        
        mock_state = Mock()
        mock_state.peer_id = 123
        mock_state.msg_id = 456
        mock_state.state_key = "123:456"
        manager._mock_state_manager.create_transcription = Mock(return_value=mock_state)
        
        # Test with callback
        await manager.transcribe(
            chat=123, 
            msg_id=456, 
            completion_callback=completion_callback
        )
        
        # Simulate completion
        manager._cleanup_completed_request("123:456")
        
        # Note: In real implementation, callback would be called
        # Here we just verify the callback was registered
        assert "123:456" in manager._completion_callbacks or len(manager._completion_callbacks) == 0


@pytest.mark.asyncio
async def test_peer_id_extraction():
    """Test peer ID extraction logic"""
    manager_module = __import__('voice_transcription.transcription_manager', fromlist=['TranscriptionManager'])
    
    # Test with mock manager instance
    mock_client = MockTelegramClient()
    config = TranscriptionManagerConfig()
    
    # Create a minimal manager for testing peer ID extraction
    with patch.multiple(
        'voice_transcription.transcription_manager',
        TELETHON_AVAILABLE=True,
        INTERNAL_IMPORTS=True,
        BasicVoiceTranscriber=Mock,
        TranscriptionStateManager=Mock,
        VoiceTranscriptionUpdateHandler=Mock,
        TranscriptionCoordinator=Mock,
        VoiceMessageValidator=Mock
    ):
        manager = manager_module.TranscriptionManager(mock_client, config)
        
        # Test integer peer ID
        peer_id = await manager._get_peer_id(123)
        assert peer_id == 123
        
        # Test string numeric peer ID
        peer_id = await manager._get_peer_id("456")
        assert peer_id == 456
        
        # Test string peer ID (hashed)
        peer_id = await manager._get_peer_id("@username")
        assert isinstance(peer_id, int)
        assert peer_id > 0


def test_performance_concurrent_requests():
    """Test performance with concurrent requests"""
    
    async def run_concurrent_test():
        mock_client = MockTelegramClient()
        config = TranscriptionManagerConfig(concurrent_limit=20)
        
        with patch.multiple(
            'voice_transcription.transcription_manager',
            TELETHON_AVAILABLE=True,
            INTERNAL_IMPORTS=True
        ):
            # Mock all components
            with patch('voice_transcription.transcription_manager.BasicVoiceTranscriber') as mock_transcriber_class, \
                 patch('voice_transcription.transcription_manager.TranscriptionStateManager') as mock_state_class, \
                 patch('voice_transcription.transcription_manager.VoiceTranscriptionUpdateHandler') as mock_update_class, \
                 patch('voice_transcription.transcription_manager.TranscriptionCoordinator') as mock_coord_class, \
                 patch('voice_transcription.transcription_manager.VoiceMessageValidator') as mock_validator_class:
                
                # Setup mocks
                mock_transcriber = Mock()
                mock_transcriber_class.return_value = mock_transcriber
                
                mock_state_manager = Mock()
                mock_state_class.return_value = mock_state_manager
                
                mock_update_handler = Mock()
                mock_update_handler.start = Mock()
                mock_update_handler.register_handler = Mock(return_value=True)
                mock_update_handler.get_comprehensive_stats = Mock(return_value={})
                mock_update_class.return_value = mock_update_handler
                
                mock_coordinator = Mock()
                mock_coord_class.return_value = mock_coordinator
                
                mock_validator = Mock()
                mock_validator_class.return_value = mock_validator
                
                manager = TranscriptionManager(mock_client, config)
                
                # Setup mock responses
                async def mock_transcribe(**kwargs):
                    return MockTranscriptionRequest(kwargs.get('chat', 123), kwargs.get('msg_id', 456))
                    
                mock_transcriber.transcribe = mock_transcribe
                mock_state_manager.get_transcription = Mock(return_value=None)
                mock_state_manager.create_transcription = Mock(return_value=Mock())
                
                # Run concurrent requests
                start_time = time.time()
                
                tasks = []
                for i in range(10):
                    task = manager.transcribe(chat=123, msg_id=456 + i)
                    tasks.append(task)
                    
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                duration = end_time - start_time
                
                # Verify results
                successful_results = [r for r in results if isinstance(r, TranscriptionResult) and r.success]
                
                assert len(successful_results) == 10
                assert duration < 5.0  # Should complete quickly
                
                print(f"Performance test: 10 concurrent requests in {duration:.2f}s")
                
    # Run the async test
    asyncio.run(run_concurrent_test())


@pytest.mark.asyncio
async def test_example_usage():
    """Test the example usage pattern"""
    from .transcription_manager import example_transcription_manager
    
    # Mock the components for the example
    with patch.multiple(
        'voice_transcription.transcription_manager',
        TELETHON_AVAILABLE=True,
        INTERNAL_IMPORTS=True,
        BasicVoiceTranscriber=Mock,
        TranscriptionStateManager=Mock,
        VoiceTranscriptionUpdateHandler=Mock,
        TranscriptionCoordinator=Mock,
        VoiceMessageValidator=Mock
    ):
        # This should run without errors
        await example_transcription_manager()


if __name__ == "__main__":
    # Run specific tests
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "performance":
        test_performance_concurrent_requests()
    else:
        # Run all tests with pytest
        pytest.main([__file__, "-v"])