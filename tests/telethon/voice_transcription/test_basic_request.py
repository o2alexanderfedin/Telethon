"""
Integration tests for Basic Request Implementation

These tests verify the complete flow of voice transcription requests,
including validation, request creation, response handling, and error cases.
"""

import asyncio
import pytest
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

# Add the implementation directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from basic_request import (
    BasicVoiceTranscriber, TranscriptionRequest, VoiceTranscriptionError,
    InvalidMessageError, TranscriptionRateLimitError
)
from validation import VoiceMessageValidator, ValidationError, MessageValidationError
from response_parser import ResponseParser, TranscriptionResult, TextProcessor


class MockTelegramClient:
    """Mock Telethon client for testing"""
    
    def __init__(self):
        self.get_entity = AsyncMock()
        self.get_input_entity = AsyncMock()
        self.get_messages = AsyncMock()
        self.get_me = AsyncMock()
        self.add_event_handler = Mock()
        self._call_mock = AsyncMock()
        
    async def __call__(self, request):
        """Mock client call"""
        return await self._call_mock(request)


class MockMessage:
    """Mock message object"""
    
    def __init__(self, msg_id=12345, is_voice=True, duration=30):
        self.id = msg_id
        self.date = datetime.now()
        self.voice = is_voice
        self.from_id = Mock()
        self.from_id.user_id = 123456
        
        if is_voice:
            self.media = Mock()
            self.media.document = Mock()
            self.media.document.size = 1024 * 50  # 50KB
            self.media.document.mime_type = "audio/ogg"
            self.media.document.attributes = [Mock()]
            self.media.document.attributes[0].voice = True
            self.media.document.attributes[0].duration = duration
        else:
            self.media = None


class MockTranscribedAudio:
    """Mock TranscribedAudio response"""
    
    def __init__(self, transcription_id=987654321, text="Test transcription", pending=False):
        self.transcription_id = transcription_id
        self.text = text
        self.pending = pending
        self.trial_remains_num = 5
        self.trial_remains_until_date = int((datetime.now() + timedelta(days=1)).timestamp())


class TestBasicVoiceTranscriber(unittest.TestCase):
    """Test the BasicVoiceTranscriber class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MockTelegramClient()
        self.transcriber = BasicVoiceTranscriber(self.client)
        
        # Setup default mocks
        self.client.get_input_entity.return_value = Mock()
        self.client.get_input_entity.return_value.user_id = 123456
        
    def test_initialization(self):
        """Test transcriber initialization"""
        self.assertEqual(self.transcriber.client, self.client)
        self.assertEqual(len(self.transcriber.active_requests), 0)
        self.assertFalse(self.transcriber._update_handler_registered)
        
    def test_transcription_request_creation(self):
        """Test TranscriptionRequest creation and properties"""
        peer = Mock()
        peer.user_id = 123456
        
        request = TranscriptionRequest(peer, 12345, self.client)
        
        self.assertEqual(request.peer, peer)
        self.assertEqual(request.msg_id, 12345)
        self.assertEqual(request.client, self.client)
        self.assertEqual(request.key, "123456:12345")
        self.assertFalse(request.completed)
        self.assertIsNone(request.result)
        
    @patch('basic_request.TELETHON_AVAILABLE', True)
    async def test_validate_message_success(self):
        """Test successful message validation"""
        # Setup mock message
        mock_message = MockMessage(is_voice=True)
        self.client.get_messages.return_value = mock_message
        
        # Test validation
        result = await self.transcriber.validate_message('test_chat', 12345)
        
        self.assertEqual(result, mock_message)
        self.client.get_messages.assert_called_once_with('test_chat', ids=12345)
        
    async def test_validate_message_not_voice(self):
        """Test validation failure for non-voice message"""
        # Setup mock non-voice message
        mock_message = MockMessage(is_voice=False)
        self.client.get_messages.return_value = mock_message
        
        # Test validation failure
        with self.assertRaises(InvalidMessageError) as context:
            await self.transcriber.validate_message('test_chat', 12345)
            
        self.assertIn("not a voice message", str(context.exception))
        
    async def test_validate_message_not_found(self):
        """Test validation failure for missing message"""
        self.client.get_messages.return_value = None
        
        with self.assertRaises(MessageNotFoundError):
            await self.transcriber.validate_message('test_chat', 12345)
            
    @patch('basic_request.TranscribeAudioRequest')
    async def test_transcribe_immediate_completion(self, mock_request_class):
        """Test transcription with immediate completion"""
        # Setup mocks
        mock_response = MockTranscribedAudio(pending=False, text="Hello world")
        self.client._call_mock.return_value = mock_response
        
        mock_message = MockMessage(is_voice=True)
        self.client.get_messages.return_value = mock_message
        
        # Perform transcription
        request = await self.transcriber.transcribe(
            'test_chat', 12345, validate=True, wait_for_completion=False
        )
        
        # Verify results
        self.assertTrue(request.completed)
        self.assertEqual(request.result.text, "Hello world")
        self.assertEqual(request.transcription_id, mock_response.transcription_id)
        
        # Verify request was stored
        self.assertIn(request.key, self.transcriber.active_requests)
        
    @patch('basic_request.TranscribeAudioRequest')
    async def test_transcribe_pending_completion(self, mock_request_class):
        """Test transcription with pending completion"""
        # Setup mocks
        mock_response = MockTranscribedAudio(pending=True, text="")
        self.client._call_mock.return_value = mock_response
        
        mock_message = MockMessage(is_voice=True)
        self.client.get_messages.return_value = mock_message
        
        # Perform transcription
        request = await self.transcriber.transcribe(
            'test_chat', 12345, validate=True, wait_for_completion=False
        )
        
        # Verify results
        self.assertFalse(request.completed)
        self.assertEqual(request.result.text, "")
        self.assertTrue(request.result.pending)
        
    @patch('basic_request.FloodWaitError')
    async def test_transcribe_rate_limit(self, mock_flood_error):
        """Test transcription rate limit handling"""
        # Setup rate limit error
        flood_error = Mock()
        flood_error.seconds = 30
        self.client._call_mock.side_effect = flood_error
        
        mock_message = MockMessage(is_voice=True)
        self.client.get_messages.return_value = mock_message
        
        # Test rate limit exception
        with self.assertRaises(TranscriptionRateLimitError) as context:
            await self.transcriber.transcribe('test_chat', 12345)
            
        self.assertEqual(context.exception.wait_seconds, 30)
        
    async def test_get_transcription_status(self):
        """Test getting transcription status"""
        # Create a request first
        peer = Mock()
        peer.user_id = 123456
        request = TranscriptionRequest(peer, 12345, self.client)
        self.transcriber.active_requests[request.key] = request
        
        # Mock get_input_entity to return the same peer
        self.client.get_input_entity.return_value = peer
        
        # Get status
        status = await self.transcriber.get_transcription_status('test_chat', 12345)
        
        self.assertEqual(status, request)
        
    async def test_get_transcription_status_not_found(self):
        """Test getting status for non-existent transcription"""
        peer = Mock()
        peer.user_id = 999999  # Different peer
        self.client.get_input_entity.return_value = peer
        
        status = await self.transcriber.get_transcription_status('test_chat', 12345)
        
        self.assertIsNone(status)
        
    def test_cleanup_completed(self):
        """Test cleanup of completed transcriptions"""
        # Create old completed request
        peer = Mock()
        peer.user_id = 123456
        old_request = TranscriptionRequest(peer, 12345, self.client)
        old_request.completed = True
        old_request.started_at = datetime.now() - timedelta(hours=2)  # 2 hours ago
        
        # Create recent completed request
        recent_request = TranscriptionRequest(peer, 54321, self.client)
        recent_request.completed = True
        recent_request.started_at = datetime.now() - timedelta(minutes=30)  # 30 minutes ago
        
        # Create pending request
        pending_request = TranscriptionRequest(peer, 99999, self.client)
        pending_request.completed = False
        
        # Add to active requests
        self.transcriber.active_requests = {
            old_request.key: old_request,
            recent_request.key: recent_request,
            pending_request.key: pending_request
        }
        
        # Cleanup with 1 hour threshold
        self.transcriber.cleanup_completed(max_age_minutes=60)
        
        # Verify old request was removed, others remain
        self.assertNotIn(old_request.key, self.transcriber.active_requests)
        self.assertIn(recent_request.key, self.transcriber.active_requests)
        self.assertIn(pending_request.key, self.transcriber.active_requests)
        
    def test_get_counts(self):
        """Test getting active and completed counts"""
        # Add various requests
        peer = Mock()
        peer.user_id = 123456
        
        for i, completed in enumerate([True, True, False, False, True]):
            request = TranscriptionRequest(peer, i, self.client)
            request.completed = completed
            self.transcriber.active_requests[request.key] = request
            
        self.assertEqual(self.transcriber.get_active_count(), 2)
        self.assertEqual(self.transcriber.get_completed_count(), 3)


class TestVoiceMessageValidator(unittest.TestCase):
    """Test the VoiceMessageValidator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MockTelegramClient()
        self.validator = VoiceMessageValidator(self.client)
        
    async def test_validation_success(self):
        """Test successful validation"""
        # Setup mocks
        entity = Mock()
        entity.id = 123456
        entity.title = "Test Chat"
        
        input_peer = Mock()
        input_peer.user_id = 123456
        
        mock_message = MockMessage(is_voice=True, duration=30)
        
        me = Mock()
        me.premium = True
        
        self.client.get_entity.return_value = entity
        self.client.get_input_entity.return_value = input_peer
        self.client.get_messages.return_value = mock_message
        self.client.get_me.return_value = me
        
        # Perform validation
        result = await self.validator.validate_transcription_request(
            'test_chat', 12345, check_permissions=True, use_cache=False
        )
        
        # Verify result structure
        self.assertEqual(result['chat_id'], 123456)
        self.assertEqual(result['chat_title'], "Test Chat")
        self.assertEqual(result['message_id'], 12345)
        self.assertEqual(result['message'], mock_message)
        self.assertTrue(result['permissions']['is_premium'])
        self.assertEqual(result['voice_info']['duration'], 30)
        
    async def test_validation_non_voice_message(self):
        """Test validation failure for non-voice message"""
        entity = Mock()
        entity.id = 123456
        
        mock_message = MockMessage(is_voice=False)
        
        self.client.get_entity.return_value = entity
        self.client.get_input_entity.return_value = Mock()
        self.client.get_messages.return_value = mock_message
        
        with self.assertRaises(MessageValidationError) as context:
            await self.validator.validate_transcription_request(
                'test_chat', 12345, use_cache=False
            )
            
        self.assertIn("not a voice message", str(context.exception))
        
    def test_cache_functionality(self):
        """Test validation caching"""
        cache_key = "test_chat:12345"
        
        # Test cache miss
        self.assertFalse(self.validator._is_cache_valid(cache_key))
        
        # Add to cache
        self.validator._validation_cache[cache_key] = {
            'result': {'test': 'data'},
            'timestamp': datetime.now()
        }
        
        # Test cache hit
        self.assertTrue(self.validator._is_cache_valid(cache_key))
        
        # Test cache expiration
        self.validator._validation_cache[cache_key]['timestamp'] = datetime.now() - timedelta(hours=1)
        self.assertFalse(self.validator._is_cache_valid(cache_key))


class TestResponseParser(unittest.TestCase):
    """Test the ResponseParser class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.parser = ResponseParser()
        
    def test_parse_transcription_response(self):
        """Test parsing transcription response"""
        mock_response = MockTranscribedAudio(
            transcription_id=123456789,
            text="Hello world",
            pending=False
        )
        
        result = self.parser.parse_transcription_response(mock_response)
        
        self.assertIsInstance(result, TranscriptionResult)
        self.assertEqual(result.transcription_id, 123456789)
        self.assertEqual(result.text, "Hello world")
        self.assertFalse(result.pending)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.word_count, 2)
        
    def test_parse_invalid_response(self):
        """Test parsing invalid response"""
        with self.assertRaises(ValueError):
            self.parser.parse_transcription_response(None)
            
    def test_text_processor_clean_text(self):
        """Test text cleaning functionality"""
        dirty_text = "  Hello  world  ,  this   is   a   test  .  "
        clean_text = TextProcessor.clean_text(dirty_text)
        
        self.assertEqual(clean_text, "Hello world, this is a test.")
        
    def test_text_processor_analyze_text(self):
        """Test text analysis functionality"""
        text = "Hello world! This is a test message."
        analysis = TextProcessor.analyze_text(text)
        
        self.assertEqual(analysis['word_count'], 7)
        self.assertEqual(analysis['sentence_count'], 2)
        self.assertTrue(analysis['has_punctuation'])
        self.assertIn('English', analysis['language_hints'])
        
    def test_parser_statistics(self):
        """Test parser statistics tracking"""
        # Parse some responses
        mock_response = MockTranscribedAudio()
        self.parser.parse_transcription_response(mock_response)
        self.parser.parse_transcription_response(mock_response)
        
        stats = self.parser.get_statistics()
        
        self.assertEqual(stats['responses_parsed'], 2)
        self.assertEqual(stats['updates_parsed'], 0)
        self.assertEqual(stats['total_parsed'], 2)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MockTelegramClient()
        self.transcriber = BasicVoiceTranscriber(self.client)
        self.validator = VoiceMessageValidator(self.client)
        self.parser = ResponseParser()
        
    async def test_complete_transcription_flow(self):
        """Test complete transcription flow from request to completion"""
        # Setup mocks for successful flow
        entity = Mock()
        entity.id = 123456
        entity.title = "Test Chat"
        
        input_peer = Mock()
        input_peer.user_id = 123456
        
        mock_message = MockMessage(is_voice=True, duration=30)
        mock_response = MockTranscribedAudio(pending=False, text="Complete transcription text")
        
        self.client.get_entity.return_value = entity
        self.client.get_input_entity.return_value = input_peer
        self.client.get_messages.return_value = mock_message
        self.client._call_mock.return_value = mock_response
        
        # Step 1: Validate request
        validation_result = await self.validator.validate_transcription_request(
            'test_chat', 12345, use_cache=False
        )
        self.assertEqual(validation_result['chat_id'], 123456)
        
        # Step 2: Send transcription request
        transcription_request = await self.transcriber.transcribe(
            'test_chat', 12345, validate=True, wait_for_completion=False
        )
        self.assertTrue(transcription_request.completed)
        
        # Step 3: Parse response
        parsed_result = self.parser.parse_transcription_response(mock_response)
        self.assertEqual(parsed_result.text, "Complete transcription text")
        
        # Step 4: Process text
        cleaned_text = TextProcessor.clean_text(parsed_result.text)
        analysis = TextProcessor.analyze_text(cleaned_text)
        self.assertEqual(analysis['word_count'], 3)
        
    async def test_error_handling_flow(self):
        """Test error handling throughout the flow"""
        # Test validation error
        self.client.get_entity.side_effect = Exception("Chat not found")
        
        with self.assertRaises(MessageValidationError):
            await self.validator.validate_transcription_request(
                'invalid_chat', 12345, use_cache=False
            )
            
        # Reset mocks for transcription error
        self.client.get_entity.side_effect = None
        self.client.get_entity.return_value = Mock()
        self.client.get_input_entity.return_value = Mock()
        self.client.get_messages.return_value = MockMessage(is_voice=True)
        
        # Test transcription error
        from basic_request import FloodWaitError
        flood_error = Mock()
        flood_error.seconds = 30
        self.client._call_mock.side_effect = flood_error
        
        with self.assertRaises(TranscriptionRateLimitError):
            await self.transcriber.transcribe('test_chat', 12345)


# Test runner
if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)