"""
Integration Tests for Voice Transcription

This module provides integration tests for Epic 1 User Story 1.8: Basic Testing Infrastructure
testing the complete API request/response flow, update handling, and component integration.

Features:
- Complete transcription workflow testing
- Mock Telegram API server
- Real-time update simulation
- Component integration validation
- End-to-end flow verification
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import json
import uuid

# Mock Telegram API structures
class MockTelegramClient:
    """Mock TelegramClient for integration testing"""
    
    def __init__(self):
        self.user_id = 123456789
        self.session_id = str(uuid.uuid4())
        self.connected = True
        self._event_handlers = []
        self._api_responses = {}
        self._update_queue = asyncio.Queue()
        
    async def get_input_entity(self, entity):
        """Mock entity resolution"""
        if isinstance(entity, int):
            return MockInputPeer(entity, "user")
        elif isinstance(entity, str):
            if entity.startswith("@"):
                return MockInputPeer(abs(hash(entity)) % 10**9, "username")
            else:
                return MockInputPeer(int(entity), "user")
        return MockInputPeer(entity, "chat")
        
    async def __call__(self, request):
        """Mock API call handling"""
        request_type = type(request).__name__
        
        if request_type == "TranscribeAudioRequest":
            return await self._handle_transcribe_request(request)
        elif request_type == "RateTranscribedAudioRequest":
            return await self._handle_rate_request(request)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
            
    async def _handle_transcribe_request(self, request):
        """Handle transcription requests"""
        # Simulate API delay
        await asyncio.sleep(0.1)
        
        transcription_id = abs(hash(f"{request.peer.peer_id}:{request.msg_id}")) % 10**9
        
        # Simulate different response scenarios
        if request.msg_id % 10 == 0:
            # Immediate completion
            return MockTranscribedAudio(
                transcription_id=transcription_id,
                text="Hello world",
                pending=False
            )
        elif request.msg_id % 10 == 1:
            # Error case - no audio
            raise MockPeerIdInvalidError("Message contains no audio")
        else:
            # Pending case - schedule update
            response = MockTranscribedAudio(
                transcription_id=transcription_id,
                text="",
                pending=True
            )
            
            # Schedule completion update
            asyncio.create_task(self._send_completion_update(
                request.peer.peer_id,
                request.msg_id,
                transcription_id
            ))
            
            return response
            
    async def _send_completion_update(self, peer_id, msg_id, transcription_id):
        """Send completion update after delay"""
        await asyncio.sleep(0.5)  # Simulate processing time
        
        update = MockUpdateTranscribedAudio(
            peer=MockPeer(peer_id),
            msg_id=msg_id,
            transcription_id=transcription_id,
            text=f"Transcribed text for message {msg_id}",
            pending=False
        )
        
        # Send to all registered handlers
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(MockUpdateEvent(update))
                else:
                    handler(MockUpdateEvent(update))
            except Exception as e:
                print(f"Handler error: {e}")
                
    async def _handle_rate_request(self, request):
        """Handle rating requests"""
        await asyncio.sleep(0.05)
        return True
        
    def add_event_handler(self, handler, event_type):
        """Add event handler"""
        self._event_handlers.append(handler)
        
    def remove_event_handler(self, handler, event_type):
        """Remove event handler"""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)


class MockInputPeer:
    """Mock InputPeer"""
    def __init__(self, peer_id, peer_type):
        self.peer_id = peer_id
        self.peer_type = peer_type


class MockPeer:
    """Mock Peer"""
    def __init__(self, peer_id):
        self.user_id = peer_id if peer_id > 0 else None
        self.chat_id = abs(peer_id) if peer_id < 0 else None
        self.channel_id = None


class MockTranscribedAudio:
    """Mock TranscribedAudio response"""
    def __init__(self, transcription_id, text, pending, trial_remains=None):
        self.transcription_id = transcription_id
        self.text = text
        self.pending = pending
        self.trial_remains_num = trial_remains
        self.trial_remains_until_date = None


class MockUpdateTranscribedAudio:
    """Mock UpdateTranscribedAudio"""
    def __init__(self, peer, msg_id, transcription_id, text, pending):
        self.peer = peer
        self.msg_id = msg_id
        self.transcription_id = transcription_id
        self.text = text
        self.pending = pending


class MockUpdateEvent:
    """Mock update event"""
    def __init__(self, update):
        self.update = update


class MockTranscribeAudioRequest:
    """Mock TranscribeAudioRequest"""
    def __init__(self, peer, msg_id):
        self.peer = peer
        self.msg_id = msg_id


class MockRateTranscribedAudioRequest:
    """Mock RateTranscribedAudioRequest"""
    def __init__(self, peer, msg_id, transcription_id, good):
        self.peer = peer
        self.msg_id = msg_id
        self.transcription_id = transcription_id
        self.good = good


class MockPeerIdInvalidError(Exception):
    """Mock PeerIdInvalidError"""
    pass


@pytest.fixture
async def mock_client():
    """Create mock Telegram client"""
    return MockTelegramClient()


@pytest.fixture
async def integrated_system(mock_client):
    """Create integrated voice transcription system"""
    # Import after mocking
    with patch.multiple(
        'voice_transcription.basic_request',
        TelegramClient=lambda: mock_client,
        TranscribeAudioRequest=MockTranscribeAudioRequest,
        RateTranscribedAudioRequest=MockRateTranscribedAudioRequest
    ):
        with patch.multiple(
            'voice_transcription.update_handler',
            TelegramClient=lambda: mock_client,
            UpdateTranscribedAudio=MockUpdateTranscribedAudio,
            TELETHON_AVAILABLE=True
        ):
            with patch.multiple(
                'voice_transcription.transcription_manager',
                TelegramClient=lambda: mock_client,
                TELETHON_AVAILABLE=True,
                INTERNAL_IMPORTS=True
            ):
                # Import components after patching
                from .transcription_manager import TranscriptionManager, TranscriptionManagerConfig
                from .state_manager import TranscriptionStateManager
                from .update_handler import VoiceTranscriptionUpdateHandler
                from .automatic_cleanup import AutomaticCleanupSystem, CleanupConfig
                
                # Create integrated system
                config = TranscriptionManagerConfig(
                    concurrent_limit=10,
                    default_timeout=5.0,
                    validate_messages=False  # Skip validation in tests
                )
                
                manager = TranscriptionManager(mock_client, config)
                await manager.initialize()
                
                yield {
                    'client': mock_client,
                    'manager': manager,
                    'state_manager': manager.state_manager,
                    'update_handler': manager.update_handler,
                    'cleanup_system': AutomaticCleanupSystem(manager.state_manager, CleanupConfig())
                }
                
                await manager.shutdown()


@pytest.mark.asyncio
class TestCompleteTranscriptionFlow:
    """Test complete transcription workflow"""
    
    async def test_immediate_completion_flow(self, integrated_system):
        """Test transcription that completes immediately"""
        manager = integrated_system['manager']
        
        # Use message ID that triggers immediate completion (ends with 0)
        result = await manager.transcribe(
            chat=123456,
            msg_id=1000,  # Ends with 0 - immediate completion
            wait_for_completion=True,
            timeout=2.0
        )
        
        assert result.success is True
        assert result.is_completed is True
        assert result.text == "Hello world"
        assert result.transcription_id is not None
        
    async def test_pending_completion_flow(self, integrated_system):
        """Test transcription that completes via update"""
        manager = integrated_system['manager']
        
        # Use message ID that triggers pending response (doesn't end with 0 or 1)
        result = await manager.transcribe(
            chat=123456,
            msg_id=1002,  # Pending case
            wait_for_completion=True,
            timeout=2.0
        )
        
        assert result.success is True
        assert result.is_completed is True
        assert "Transcribed text for message 1002" in result.text
        assert result.transcription_id is not None
        
    async def test_error_handling_flow(self, integrated_system):
        """Test error handling in transcription flow"""
        manager = integrated_system['manager']
        
        # Use message ID that triggers error (ends with 1)
        result = await manager.transcribe(
            chat=123456,
            msg_id=1001,  # Error case
            wait_for_completion=False
        )
        
        assert result.success is False
        assert "no audio" in result.error.lower()
        
    async def test_concurrent_transcriptions(self, integrated_system):
        """Test multiple concurrent transcriptions"""
        manager = integrated_system['manager']
        
        # Start multiple transcriptions concurrently
        tasks = []
        for i in range(5):
            task = manager.transcribe(
                chat=123456 + i,
                msg_id=2000 + i,
                wait_for_completion=True,
                timeout=3.0
            )
            tasks.append(task)
            
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_results = [r for r in results if hasattr(r, 'success') and r.success]
        assert len(successful_results) >= 4  # Allow for some variability
        
        for result in successful_results:
            assert result.is_completed
            assert result.transcription_id is not None


@pytest.mark.asyncio
class TestStateManagementIntegration:
    """Test state management integration"""
    
    async def test_state_lifecycle_tracking(self, integrated_system):
        """Test complete state lifecycle tracking"""
        manager = integrated_system['manager']
        state_manager = integrated_system['state_manager']
        
        peer_id = 123456
        msg_id = 3000
        
        # Start transcription
        result = await manager.transcribe(
            chat=peer_id,
            msg_id=msg_id,
            wait_for_completion=False
        )
        
        # Check initial state
        state = state_manager.get_transcription(peer_id, msg_id)
        assert state is not None
        assert state.peer_id == peer_id
        assert state.msg_id == msg_id
        
        # Wait for completion
        for _ in range(20):  # Wait up to 2 seconds
            await asyncio.sleep(0.1)
            state = state_manager.get_transcription(peer_id, msg_id)
            if state and state.is_completed:
                break
                
        # Verify final state
        assert state.is_completed
        assert len(state.text) > 0
        assert state.transcription_id is not None
        
    async def test_state_cleanup_integration(self, integrated_system):
        """Test state cleanup integration"""
        manager = integrated_system['manager']
        cleanup_system = integrated_system['cleanup_system']
        
        # Create multiple completed transcriptions
        for i in range(5):
            await manager.transcribe(
                chat=123456,
                msg_id=4000 + i,
                wait_for_completion=True,
                timeout=2.0
            )
            
        # Verify states exist
        initial_count = manager.state_manager.storage.get_state_count()
        assert initial_count == 5
        
        # Trigger cleanup
        await cleanup_system.start()
        result = await cleanup_system.trigger_cleanup(force=True)
        await cleanup_system.stop()
        
        # Cleanup may or may not remove states depending on age
        assert result['success'] is True


@pytest.mark.asyncio 
class TestUpdateHandlingIntegration:
    """Test update handling integration"""
    
    async def test_update_processing_flow(self, integrated_system):
        """Test complete update processing flow"""
        update_handler = integrated_system['update_handler']
        
        # Register test handler
        received_updates = []
        
        def test_handler(update_event):
            received_updates.append(update_event)
            
        update_handler.register_handler("test_handler", test_handler)
        
        # Start transcription that will generate update
        manager = integrated_system['manager']
        result = await manager.transcribe(
            chat=123456,
            msg_id=5000,
            wait_for_completion=True,
            timeout=2.0
        )
        
        # Verify update was received
        assert len(received_updates) > 0
        
        update_event = received_updates[0]
        assert update_event.peer_id == 123456
        assert update_event.msg_id == 5000
        assert update_event.is_completion
        
    async def test_update_validation_integration(self, integrated_system):
        """Test update validation integration"""
        update_handler = integrated_system['update_handler']
        
        # Get validation statistics before
        initial_stats = update_handler.validator.get_statistics()
        
        # Trigger transcription with updates
        manager = integrated_system['manager']
        await manager.transcribe(
            chat=123456,
            msg_id=6000,
            wait_for_completion=True,
            timeout=2.0
        )
        
        # Check validation statistics
        final_stats = update_handler.validator.get_statistics()
        assert final_stats['valid_updates'] > initial_stats['valid_updates']


@pytest.mark.asyncio
class TestErrorHandlingIntegration:
    """Test error handling integration"""
    
    async def test_classification_and_recovery(self, integrated_system):
        """Test error classification and recovery"""
        manager = integrated_system['manager']
        
        # Trigger various error scenarios
        error_results = []
        
        # Invalid message (triggers error)
        result = await manager.transcribe(
            chat=123456,
            msg_id=7001,  # Error case
            wait_for_completion=False
        )
        error_results.append(result)
        
        # Verify error handling
        assert not result.success
        assert result.error is not None
        
    async def test_timeout_handling(self, integrated_system):
        """Test timeout handling"""
        manager = integrated_system['manager']
        
        # Use very short timeout
        result = await manager.transcribe(
            chat=123456,
            msg_id=8000,
            wait_for_completion=True,
            timeout=0.01  # Very short timeout
        )
        
        # Should timeout and still return result
        assert result.success is True  # Request created successfully
        # But may not be completed due to timeout


@pytest.mark.asyncio
class TestPerformanceIntegration:
    """Test performance characteristics"""
    
    async def test_throughput_performance(self, integrated_system):
        """Test system throughput"""
        manager = integrated_system['manager']
        
        start_time = time.time()
        
        # Process multiple transcriptions
        tasks = []
        for i in range(10):
            task = manager.transcribe(
                chat=123456,
                msg_id=9000 + i,
                wait_for_completion=True,
                timeout=3.0
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        
        # Verify performance
        successful_results = [r for r in results if hasattr(r, 'success') and r.success]
        throughput = len(successful_results) / duration
        
        assert throughput > 2.0  # At least 2 transcriptions per second
        assert duration < 5.0    # Complete within 5 seconds
        
    async def test_memory_usage_stability(self, integrated_system):
        """Test memory usage stability"""
        manager = integrated_system['manager']
        
        # Process many transcriptions
        for batch in range(3):
            tasks = []
            for i in range(5):
                task = manager.transcribe(
                    chat=123456,
                    msg_id=10000 + batch * 5 + i,
                    wait_for_completion=True,
                    timeout=2.0
                )
                tasks.append(task)
                
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check state count doesn't grow indefinitely
            state_count = manager.state_manager.storage.get_state_count()
            assert state_count < 50  # Reasonable limit


@pytest.mark.asyncio
async def test_complete_system_integration():
    """Test complete system integration"""
    mock_client = MockTelegramClient()
    
    with patch.multiple(
        'voice_transcription',
        TelegramClient=lambda: mock_client,
        TELETHON_AVAILABLE=True,
        INTERNAL_IMPORTS=True
    ):
        # Import and create full system
        from .transcription_manager import TranscriptionManager, TranscriptionManagerConfig
        from .automatic_cleanup import AutomaticCleanupSystem, CleanupConfig
        
        # Create manager
        config = TranscriptionManagerConfig(
            concurrent_limit=5,
            default_timeout=3.0,
            auto_cleanup_enabled=True
        )
        
        manager = TranscriptionManager(mock_client, config)
        await manager.initialize()
        
        try:
            # Test complete workflow
            result = await manager.transcribe(
                chat="@testuser",
                msg_id=20000,
                wait_for_completion=True,
                timeout=3.0
            )
            
            # Verify integration
            assert result.success is True
            
            # Test statistics
            stats = manager.get_statistics()
            assert stats['manager']['requests_created'] > 0
            
        finally:
            await manager.shutdown()


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short"])