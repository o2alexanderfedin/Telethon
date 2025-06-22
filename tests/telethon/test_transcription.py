"""
Tests for voice message transcription functionality.

This test suite covers the Basic Transcription Manager implementation
including client methods, state management, and event handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta

from telethon import TelegramClient, types, functions, events
from telethon.client.transcription import TranscriptionMixin, TranscriptionState
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])