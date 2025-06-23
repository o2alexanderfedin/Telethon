"""
Tests for Voice Transcription Update Handling System

Comprehensive tests for update validation, processing, handler registration,
and integration components.
"""

import asyncio
import pytest
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import threading
import time
import sys
import os

# Add the implementation directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from update_handler import (
    UpdateEvent, HandlerRegistration, UpdateValidator, UpdateProcessor,
    VoiceTranscriptionUpdateHandler, create_completion_filter, create_peer_filter
)
from integration import TranscriptionCoordinator, IntegratedVoiceTranscriber


class MockUpdateTranscribedAudio:
    """Mock UpdateTranscribedAudio object"""
    
    def __init__(
        self,
        transcription_id=12345,
        peer_id=67890,
        msg_id=111,
        text="Test transcription",
        pending=False
    ):
        self.transcription_id = transcription_id
        self.msg_id = msg_id
        self.text = text
        self.pending = pending
        
        # Create mock peer
        self.peer = Mock()
        self.peer.user_id = peer_id


class MockTelegramClient:
    """Mock Telethon client for testing"""
    
    def __init__(self):
        self.add_event_handler = Mock()
        self.remove_event_handler = Mock()
        self.handlers = []


class TestUpdateEvent(unittest.TestCase):
    """Test UpdateEvent data class"""
    
    def test_update_event_creation(self):
        """Test creating UpdateEvent"""
        event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Hello world",
            pending=False,
            received_at=datetime.now(timezone.utc)
        )
        
        self.assertEqual(event.transcription_id, 12345)
        self.assertEqual(event.peer_id, 67890)
        self.assertEqual(event.msg_id, 111)
        self.assertEqual(event.text, "Hello world")
        self.assertFalse(event.pending)
        self.assertTrue(event.is_completion)
        
    def test_update_key_generation(self):
        """Test update key generation"""
        event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Test",
            pending=False,
            received_at=datetime.now(timezone.utc)
        )
        
        expected_key = "67890:111:12345"
        self.assertEqual(event.update_key, expected_key)
        
    def test_completion_detection(self):
        """Test completion detection"""
        # Pending update
        pending_event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="",
            pending=True,
            received_at=datetime.now(timezone.utc)
        )
        self.assertFalse(pending_event.is_completion)
        
        # Completed update
        completed_event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Completed text",
            pending=False,
            received_at=datetime.now(timezone.utc)
        )
        self.assertTrue(completed_event.is_completion)
        
    def test_to_dict_serialization(self):
        """Test dictionary serialization"""
        event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Test",
            pending=False,
            received_at=datetime.now(timezone.utc)
        )
        
        data = event.to_dict()
        
        self.assertEqual(data['transcription_id'], 12345)
        self.assertEqual(data['peer_id'], 67890)
        self.assertEqual(data['msg_id'], 111)
        self.assertEqual(data['text'], "Test")
        self.assertFalse(data['pending'])
        self.assertTrue(data['is_completion'])
        self.assertIn('received_at', data)


class TestHandlerRegistration(unittest.TestCase):
    """Test HandlerRegistration data class"""
    
    def test_handler_registration_creation(self):
        """Test creating HandlerRegistration"""
        callback = lambda x: None
        filter_func = lambda x: True
        
        registration = HandlerRegistration(
            handler_id="test_handler",
            callback=callback,
            filter_func=filter_func,
            priority=5
        )
        
        self.assertEqual(registration.handler_id, "test_handler")
        self.assertEqual(registration.callback, callback)
        self.assertEqual(registration.filter_func, filter_func)
        self.assertEqual(registration.priority, 5)
        self.assertTrue(registration.active)
        self.assertEqual(registration.call_count, 0)
        self.assertEqual(registration.error_count, 0)
        
    def test_handler_matching(self):
        """Test handler matching logic"""
        # Handler with no filter (matches all)
        registration = HandlerRegistration(
            handler_id="all_handler",
            callback=lambda x: None
        )
        
        event = UpdateEvent(12345, 67890, 111, "Test", False, datetime.now(timezone.utc))
        self.assertTrue(registration.matches(event))
        
        # Handler with filter
        completion_registration = HandlerRegistration(
            handler_id="completion_handler",
            callback=lambda x: None,
            filter_func=lambda x: x.is_completion
        )
        
        pending_event = UpdateEvent(12345, 67890, 111, "", True, datetime.now(timezone.utc))
        completed_event = UpdateEvent(12345, 67890, 111, "Done", False, datetime.now(timezone.utc))
        
        self.assertFalse(completion_registration.matches(pending_event))
        self.assertTrue(completion_registration.matches(completed_event))
        
        # Inactive handler
        registration.active = False
        self.assertFalse(registration.matches(event))


class TestUpdateValidator(unittest.TestCase):
    """Test UpdateValidator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.validator = UpdateValidator()
        
    def test_valid_update_validation(self):
        """Test validation of valid update"""
        mock_update = MockUpdateTranscribedAudio(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Hello world",
            pending=False
        )
        
        result = self.validator.validate_update(mock_update)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, UpdateEvent)
        self.assertEqual(result.transcription_id, 12345)
        self.assertEqual(result.peer_id, 67890)
        self.assertEqual(result.msg_id, 111)
        self.assertEqual(result.text, "Hello world")
        self.assertFalse(result.pending)
        
    def test_duplicate_update_detection(self):
        """Test duplicate update detection"""
        mock_update = MockUpdateTranscribedAudio(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Hello world",
            pending=False
        )
        
        # First validation should succeed
        result1 = self.validator.validate_update(mock_update)
        self.assertIsNotNone(result1)
        
        # Second validation should fail (duplicate)
        result2 = self.validator.validate_update(mock_update)
        self.assertIsNone(result2)
        
        # Check statistics
        stats = self.validator.get_statistics()
        self.assertEqual(stats['total_received'], 2)
        self.assertEqual(stats['valid_updates'], 1)
        self.assertEqual(stats['duplicates'], 1)
        
    def test_invalid_update_validation(self):
        """Test validation of invalid updates"""
        # Update without transcription_id
        invalid_update = Mock()
        invalid_update.peer = Mock()
        invalid_update.peer.user_id = 67890
        invalid_update.msg_id = 111
        # Missing transcription_id
        
        result = self.validator.validate_update(invalid_update)
        self.assertIsNone(result)
        
        # Check error statistics
        stats = self.validator.get_statistics()
        self.assertEqual(stats['missing_fields'], 1)
        
    def test_cache_cleanup(self):
        """Test seen updates cache cleanup"""
        # Add many updates to exceed max size
        for i in range(15):
            mock_update = MockUpdateTranscribedAudio(
                transcription_id=i,
                peer_id=67890,
                msg_id=111,
                text=f"Update {i}",
                pending=False
            )
            self.validator.validate_update(mock_update)
            
        # Trigger cleanup
        self.validator.cleanup_seen_updates(max_size=10)
        
        # Cache should be reduced
        stats = self.validator.get_statistics()
        self.assertLessEqual(stats['cache_size'], 5)  # Half of max_size


class TestUpdateProcessor(unittest.TestCase):
    """Test UpdateProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = UpdateProcessor()
        
    def test_handler_registration(self):
        """Test handler registration and unregistration"""
        callback = Mock()
        
        # Register handler
        success = self.processor.register_handler(
            "test_handler",
            callback,
            priority=5
        )
        self.assertTrue(success)
        
        # Check handler is registered
        self.assertIn("test_handler", self.processor.handlers)
        handler = self.processor.handlers["test_handler"]
        self.assertEqual(handler.callback, callback)
        self.assertEqual(handler.priority, 5)
        
        # Unregister handler
        success = self.processor.unregister_handler("test_handler")
        self.assertTrue(success)
        self.assertNotIn("test_handler", self.processor.handlers)
        
    def test_handler_enable_disable(self):
        """Test enabling and disabling handlers"""
        callback = Mock()
        
        self.processor.register_handler("test_handler", callback)
        
        # Disable handler
        success = self.processor.disable_handler("test_handler")
        self.assertTrue(success)
        self.assertFalse(self.processor.handlers["test_handler"].active)
        
        # Enable handler
        success = self.processor.enable_handler("test_handler")
        self.assertTrue(success)
        self.assertTrue(self.processor.handlers["test_handler"].active)
        
    async def test_update_processing(self):
        """Test update processing through handlers"""
        callback1 = Mock()
        callback2 = Mock()
        
        # Register handlers with different priorities
        self.processor.register_handler("high_priority", callback1, priority=10)
        self.processor.register_handler("low_priority", callback2, priority=1)
        
        # Create update event
        update_event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Test",
            pending=False,
            received_at=datetime.now(timezone.utc)
        )
        
        # Process update
        results = await self.processor.process_update(update_event)
        
        # Check results
        self.assertEqual(results['handlers_called'], 2)
        self.assertEqual(results['handlers_succeeded'], 2)
        self.assertEqual(results['handlers_failed'], 0)
        
        # Check handlers were called
        callback1.assert_called_once_with(update_event)
        callback2.assert_called_once_with(update_event)
        
        # Check sequence number was assigned
        self.assertIsNotNone(update_event.sequence_number)
        
    async def test_handler_error_handling(self):
        """Test error handling in processors"""
        def error_callback(update_event):
            raise Exception("Test error")
            
        success_callback = Mock()
        
        self.processor.register_handler("error_handler", error_callback)
        self.processor.register_handler("success_handler", success_callback)
        
        update_event = UpdateEvent(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Test",
            pending=False,
            received_at=datetime.now(timezone.utc)
        )
        
        results = await self.processor.process_update(update_event)
        
        # Check error was handled
        self.assertEqual(results['handlers_called'], 2)
        self.assertEqual(results['handlers_succeeded'], 1)
        self.assertEqual(results['handlers_failed'], 1)
        self.assertEqual(len(results['errors']), 1)
        
        # Success handler should still have been called
        success_callback.assert_called_once()
        
    def test_handler_filtering(self):
        """Test handler filtering"""
        completion_callback = Mock()
        all_callback = Mock()
        
        # Register filtered handler
        self.processor.register_handler(
            "completion_only",
            completion_callback,
            filter_func=lambda x: x.is_completion
        )
        
        # Register unfiltered handler
        self.processor.register_handler(
            "all_updates",
            all_callback
        )
        
        # Test with pending update
        pending_event = UpdateEvent(12345, 67890, 111, "", True, datetime.now(timezone.utc))
        
        # Get matching handlers
        matching = [h for h in self.processor.handlers.values() if h.matches(pending_event)]
        
        # Only unfiltered handler should match
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].handler_id, "all_updates")
        
        # Test with completed update
        completed_event = UpdateEvent(12345, 67890, 111, "Done", False, datetime.now(timezone.utc))
        
        matching = [h for h in self.processor.handlers.values() if h.matches(completed_event)]
        
        # Both handlers should match
        self.assertEqual(len(matching), 2)
        
    def test_statistics_tracking(self):
        """Test statistics tracking"""
        initial_stats = self.processor.get_processing_stats()
        
        # Register handler and process update
        callback = Mock()
        self.processor.register_handler("test", callback)
        
        update_event = UpdateEvent(12345, 67890, 111, "Test", False, datetime.now(timezone.utc))
        
        # Process update (need to run async)
        async def run_test():
            await self.processor.process_update(update_event)
            
        asyncio.run(run_test())
        
        # Check statistics
        stats = self.processor.get_processing_stats()
        self.assertEqual(stats['updates_processed'], initial_stats['updates_processed'] + 1)
        self.assertEqual(stats['handlers_called'], initial_stats['handlers_called'] + 1)
        self.assertEqual(stats['handler_count'], 1)
        self.assertEqual(stats['active_handlers'], 1)


class TestVoiceTranscriptionUpdateHandler(unittest.TestCase):
    """Test VoiceTranscriptionUpdateHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MockTelegramClient()
        self.handler = VoiceTranscriptionUpdateHandler(self.client)
        
    def test_handler_initialization(self):
        """Test handler initialization"""
        self.assertEqual(self.handler.client, self.client)
        self.assertIsNotNone(self.handler.validator)
        self.assertIsNotNone(self.handler.processor)
        self.assertFalse(self.handler._registered_with_client)
        
    def test_start_stop_cycle(self):
        """Test starting and stopping the handler"""
        # Start handler
        self.handler.start()
        self.assertTrue(self.handler._registered_with_client)
        self.client.add_event_handler.assert_called_once()
        
        # Stop handler
        self.handler.stop()
        self.assertFalse(self.handler._registered_with_client)
        self.client.remove_event_handler.assert_called_once()
        
    def test_handler_registration_delegation(self):
        """Test that handler registration delegates to processor"""
        callback = Mock()
        
        success = self.handler.register_handler(
            "test_handler",
            callback,
            priority=5
        )
        
        self.assertTrue(success)
        # Should be registered in the processor
        self.assertIn("test_handler", self.handler.processor.handlers)
        
    async def test_raw_update_handling(self):
        """Test processing of raw Telethon updates"""
        # Create mock event
        mock_event = Mock()
        mock_event.update = MockUpdateTranscribedAudio(
            transcription_id=12345,
            peer_id=67890,
            msg_id=111,
            text="Test transcription",
            pending=False
        )
        
        # Register a test handler
        callback = Mock()
        self.handler.register_handler("test", callback)
        
        # Process the raw update
        await self.handler._handle_raw_update(mock_event)
        
        # Check that callback was called
        callback.assert_called_once()
        
        # Check that the callback received an UpdateEvent
        call_args = callback.call_args[0]
        self.assertEqual(len(call_args), 1)
        update_event = call_args[0]
        self.assertIsInstance(update_event, UpdateEvent)
        self.assertEqual(update_event.transcription_id, 12345)
        
    def test_comprehensive_statistics(self):
        """Test comprehensive statistics"""
        stats = self.handler.get_comprehensive_stats()
        
        self.assertIn('uptime_seconds', stats)
        self.assertIn('validation', stats)
        self.assertIn('processing', stats)
        self.assertIn('handlers', stats)
        self.assertIn('system', stats)
        
        # Check system stats
        self.assertEqual(stats['system']['registered_with_client'], False)
        self.assertIn('start_time', stats['system'])


class TestFilterFunctions(unittest.TestCase):
    """Test convenience filter functions"""
    
    def test_completion_filter(self):
        """Test completion filter function"""
        filter_func = create_completion_filter()
        
        pending_event = UpdateEvent(12345, 67890, 111, "", True, datetime.now(timezone.utc))
        completed_event = UpdateEvent(12345, 67890, 111, "Done", False, datetime.now(timezone.utc))
        
        self.assertFalse(filter_func(pending_event))
        self.assertTrue(filter_func(completed_event))
        
    def test_peer_filter(self):
        """Test peer filter function"""
        filter_func = create_peer_filter(67890)
        
        matching_event = UpdateEvent(12345, 67890, 111, "Test", False, datetime.now(timezone.utc))
        non_matching_event = UpdateEvent(12345, 99999, 111, "Test", False, datetime.now(timezone.utc))
        
        self.assertTrue(filter_func(matching_event))
        self.assertFalse(filter_func(non_matching_event))


class TestIntegrationComponents(unittest.TestCase):
    """Test integration components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MockTelegramClient()
        
        # Mock the required classes
        self.mock_transcriber = Mock()
        self.mock_transcriber.get_active_count.return_value = 2
        self.mock_transcriber.get_completed_count.return_value = 5
        
        self.mock_update_handler = Mock()
        self.mock_update_handler.register_handler.return_value = True
        
    @patch('integration.BasicVoiceTranscriber')
    @patch('integration.VoiceTranscriptionUpdateHandler')
    def test_transcription_coordinator(self, mock_handler_class, mock_transcriber_class):
        """Test TranscriptionCoordinator"""
        mock_transcriber_class.return_value = self.mock_transcriber
        mock_handler_class.return_value = self.mock_update_handler
        
        coordinator = TranscriptionCoordinator(
            self.mock_transcriber,
            self.mock_update_handler
        )
        
        # Check that coordination handler was registered
        self.mock_update_handler.register_handler.assert_called_once()
        call_args = self.mock_update_handler.register_handler.call_args
        self.assertEqual(call_args[0][0], "transcription_coordinator")  # handler_id
        self.assertEqual(call_args[1]['priority'], 100)  # High priority
        
    def test_coordinator_statistics(self):
        """Test coordinator statistics"""
        coordinator = TranscriptionCoordinator(
            self.mock_transcriber,
            self.mock_update_handler
        )
        
        stats = coordinator.get_coordination_stats()
        
        self.assertIn('updates_matched', stats)
        self.assertIn('updates_orphaned', stats)
        self.assertIn('requests_completed', stats)
        self.assertIn('coordination_errors', stats)
        self.assertIn('pending_requests', stats)
        self.assertIn('pending_callbacks', stats)


# Test runner for async tests
class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases"""
    
    def run_async(self, coro):
        """Helper to run async functions in tests"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# Performance tests
class TestUpdateHandlerPerformance(unittest.TestCase):
    """Performance tests for update handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MockTelegramClient()
        self.handler = VoiceTranscriptionUpdateHandler(self.client)
        
    def test_high_volume_updates(self):
        """Test handling high volume of updates"""
        # Register a simple handler
        processed_count = 0
        
        def counting_handler(update_event):
            nonlocal processed_count
            processed_count += 1
            
        self.handler.register_handler("counter", counting_handler)
        
        # Process many updates
        async def process_many_updates():
            for i in range(100):
                mock_event = Mock()
                mock_event.update = MockUpdateTranscribedAudio(
                    transcription_id=i,
                    peer_id=67890,
                    msg_id=111 + i,
                    text=f"Update {i}",
                    pending=False
                )
                await self.handler._handle_raw_update(mock_event)
                
        # Time the processing
        start_time = time.time()
        asyncio.run(process_many_updates())
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Check results
        self.assertEqual(processed_count, 100)
        self.assertLess(processing_time, 5.0)  # Should complete in under 5 seconds
        
        # Check statistics
        stats = self.handler.get_comprehensive_stats()
        self.assertEqual(stats['validation']['valid_updates'], 100)
        self.assertEqual(stats['processing']['updates_processed'], 100)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)