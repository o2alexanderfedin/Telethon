"""
Basic Request Implementation for Voice Transcription

This module provides a high-level wrapper around the raw TL classes for voice transcription,
implementing the requirements from Epic 1 User Story 1.2: Basic Request Implementation.

Features:
- Request creation and validation
- Parameter type checking
- Response parsing
- Error handling
- Integration with Telethon client
"""

import asyncio
import logging
from typing import Union, Optional, Callable, Any
from datetime import datetime

try:
    from telethon import TelegramClient, events
    from telethon.tl.functions.messages import TranscribeAudioRequest, RateTranscribedAudioRequest
    from telethon.tl.types.messages import TranscribedAudio
    from telethon.tl.types import UpdateTranscribedAudio, InputPeer, Message
    from telethon.errors import (
        FloodWaitError, MessageNotFoundError, ChatAdminRequiredError,
        UserNotMutualContactError, AuthKeyUnregisteredError
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    # Fallback types for development without Telethon
    TelegramClient = Any
    TranscribeAudioRequest = Any
    RateTranscribedAudioRequest = Any
    TranscribedAudio = Any
    UpdateTranscribedAudio = Any
    InputPeer = Any
    Message = Any


logger = logging.getLogger(__name__)


class VoiceTranscriptionError(Exception):
    """Base exception for voice transcription errors"""
    pass


class InvalidMessageError(VoiceTranscriptionError):
    """Raised when message is not a voice message"""
    pass


class TranscriptionRateLimitError(VoiceTranscriptionError):
    """Raised when hitting transcription rate limits"""
    def __init__(self, message: str, wait_seconds: int = None):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class TranscriptionRequest:
    """Represents a transcription request with metadata"""
    
    def __init__(self, peer: InputPeer, msg_id: int, client: 'TelegramClient'):
        self.peer = peer
        self.msg_id = msg_id
        self.client = client
        self.started_at = datetime.now()
        self.transcription_id: Optional[int] = None
        self.result: Optional[TranscribedAudio] = None
        self.completed = False
        self.error: Optional[Exception] = None
        
    @property
    def key(self) -> str:
        """Unique key for this transcription request"""
        if hasattr(self.peer, 'user_id'):
            peer_id = self.peer.user_id
        elif hasattr(self.peer, 'chat_id'):
            peer_id = self.peer.chat_id
        elif hasattr(self.peer, 'channel_id'):
            peer_id = self.peer.channel_id
        else:
            peer_id = "unknown"
        return f"{peer_id}:{self.msg_id}"
        
    def __repr__(self):
        status = "completed" if self.completed else "pending"
        return f"TranscriptionRequest({self.key}, {status})"


class BasicVoiceTranscriber:
    """
    Basic implementation of voice message transcription using raw TL API.
    
    This class provides a simple interface for transcribing voice messages
    while handling the complexity of the underlying MTProto API.
    """
    
    def __init__(self, client: 'TelegramClient'):
        """
        Initialize the transcriber with a Telethon client.
        
        Args:
            client: Authenticated TelegramClient instance
        """
        if not TELETHON_AVAILABLE:
            raise ImportError("Telethon is required for voice transcription")
            
        self.client = client
        self.active_requests = {}  # key -> TranscriptionRequest
        self._update_handler_registered = False
        
    def _register_update_handler(self):
        """Register handler for transcription completion updates"""
        if not self._update_handler_registered:
            self.client.add_event_handler(
                self._handle_transcription_update,
                events.Raw(UpdateTranscribedAudio)
            )
            self._update_handler_registered = True
            logger.debug("Registered UpdateTranscribedAudio handler")
            
    async def _handle_transcription_update(self, event):
        """Handle transcription completion updates"""
        update = event.update
        
        # Find the corresponding request
        if hasattr(update.peer, 'user_id'):
            peer_id = update.peer.user_id
        elif hasattr(update.peer, 'chat_id'):
            peer_id = update.peer.chat_id
        elif hasattr(update.peer, 'channel_id'):
            peer_id = update.peer.channel_id
        else:
            logger.warning(f"Unknown peer type in transcription update: {update.peer}")
            return
            
        key = f"{peer_id}:{update.msg_id}"
        request = self.active_requests.get(key)
        
        if not request:
            logger.debug(f"Received update for unknown transcription: {key}")
            return
            
        logger.info(f"Transcription update for {key}: pending={update.pending}")
        
        # Update the request
        request.transcription_id = update.transcription_id
        
        if not update.pending:
            # Transcription completed
            request.result = TranscribedAudio(
                transcription_id=update.transcription_id,
                text=update.text,
                pending=False
            )
            request.completed = True
            logger.info(f"Transcription completed for {key}: {len(update.text)} characters")
        
    async def validate_message(self, chat: Union[int, str], msg_id: int) -> Message:
        """
        Validate that the message exists and is a voice message.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID
            
        Returns:
            Message object if valid
            
        Raises:
            MessageNotFoundError: If message doesn't exist
            InvalidMessageError: If message is not a voice message
        """
        try:
            message = await self.client.get_messages(chat, ids=msg_id)
        except Exception as e:
            raise MessageNotFoundError(f"Message {msg_id} not found") from e
            
        if not message:
            raise MessageNotFoundError(f"Message {msg_id} not found")
            
        if not message.voice:
            raise InvalidMessageError(
                f"Message {msg_id} is not a voice message. "
                f"Type: {type(message.media).__name__ if message.media else 'text'}"
            )
            
        return message
        
    async def transcribe(
        self,
        chat: Union[int, str],
        msg_id: int,
        validate: bool = True,
        wait_for_completion: bool = False,
        timeout: Optional[float] = 30.0
    ) -> TranscriptionRequest:
        """
        Transcribe a voice message.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID of the voice message
            validate: Whether to validate the message before transcribing
            wait_for_completion: Whether to wait for transcription to complete
            timeout: Timeout for waiting (if wait_for_completion=True)
            
        Returns:
            TranscriptionRequest object
            
        Raises:
            InvalidMessageError: If message is not a voice message
            TranscriptionRateLimitError: If rate limited
            VoiceTranscriptionError: For other transcription errors
        """
        # Validate message if requested
        if validate:
            await self.validate_message(chat, msg_id)
            
        # Get input peer
        try:
            input_peer = await self.client.get_input_entity(chat)
        except Exception as e:
            raise VoiceTranscriptionError(f"Failed to resolve chat: {e}") from e
            
        # Create request object
        request = TranscriptionRequest(input_peer, msg_id, self.client)
        key = request.key
        
        # Register update handler if needed
        self._register_update_handler()
        
        # Store request for tracking
        self.active_requests[key] = request
        
        try:
            # Send transcription request
            tl_request = TranscribeAudioRequest(peer=input_peer, msg_id=msg_id)
            result = await self.client(tl_request)
            
            # Process immediate response
            request.result = result
            request.transcription_id = result.transcription_id
            
            if not result.pending:
                # Transcription completed immediately
                request.completed = True
                logger.info(f"Immediate transcription for {key}: {len(result.text)} characters")
            else:
                logger.info(f"Transcription started for {key}: ID {result.transcription_id}")
                
                # Wait for completion if requested
                if wait_for_completion:
                    await self._wait_for_completion(request, timeout)
                    
        except FloodWaitError as e:
            request.error = e
            raise TranscriptionRateLimitError(
                f"Rate limited. Wait {e.seconds} seconds.",
                wait_seconds=e.seconds
            ) from e
        except Exception as e:
            request.error = e
            raise VoiceTranscriptionError(f"Transcription failed: {e}") from e
            
        return request
        
    async def _wait_for_completion(self, request: TranscriptionRequest, timeout: Optional[float]):
        """Wait for transcription to complete"""
        if timeout is None:
            timeout = 30.0
            
        start_time = asyncio.get_event_loop().time()
        
        while not request.completed:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning(f"Transcription timeout for {request.key}")
                break
                
            # Wait a bit before checking again
            await asyncio.sleep(0.5)
            
    async def get_transcription_status(self, chat: Union[int, str], msg_id: int) -> Optional[TranscriptionRequest]:
        """
        Get the status of a transcription request.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID
            
        Returns:
            TranscriptionRequest if found, None otherwise
        """
        input_peer = await self.client.get_input_entity(chat)
        temp_request = TranscriptionRequest(input_peer, msg_id, self.client)
        key = temp_request.key
        
        return self.active_requests.get(key)
        
    async def rate_transcription(
        self,
        chat: Union[int, str],
        msg_id: int,
        transcription_id: int,
        good: bool
    ) -> bool:
        """
        Rate the quality of a transcription.
        
        Args:
            chat: Chat ID, username, or entity
            msg_id: Message ID
            transcription_id: Transcription ID from the response
            good: Whether the transcription was accurate
            
        Returns:
            True if rating was submitted successfully
            
        Raises:
            VoiceTranscriptionError: If rating fails
        """
        try:
            input_peer = await self.client.get_input_entity(chat)
            
            request = RateTranscribedAudioRequest(
                peer=input_peer,
                msg_id=msg_id,
                transcription_id=transcription_id,
                good=good
            )
            
            result = await self.client(request)
            logger.info(f"Rated transcription {transcription_id} as {'good' if good else 'bad'}")
            return bool(result)
            
        except Exception as e:
            raise VoiceTranscriptionError(f"Failed to rate transcription: {e}") from e
            
    def cleanup_completed(self, max_age_minutes: int = 60):
        """
        Clean up completed transcription requests older than max_age_minutes.
        
        Args:
            max_age_minutes: Maximum age in minutes for completed requests
        """
        now = datetime.now()
        keys_to_remove = []
        
        for key, request in self.active_requests.items():
            if request.completed:
                age_minutes = (now - request.started_at).total_seconds() / 60
                if age_minutes > max_age_minutes:
                    keys_to_remove.append(key)
                    
        for key in keys_to_remove:
            del self.active_requests[key]
            
        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} completed transcription requests")
            
    def get_active_count(self) -> int:
        """Get the number of active (pending) transcription requests"""
        return sum(1 for req in self.active_requests.values() if not req.completed)
        
    def get_completed_count(self) -> int:
        """Get the number of completed transcription requests"""
        return sum(1 for req in self.active_requests.values() if req.completed)


# Example usage
async def example_usage():
    """Example of how to use the BasicVoiceTranscriber"""
    
    # Initialize client (not shown - requires API credentials)
    # client = TelegramClient('session', api_id, api_hash)
    # await client.start()
    
    client = None  # Placeholder
    transcriber = BasicVoiceTranscriber(client)
    
    try:
        # Transcribe a voice message and wait for completion
        request = await transcriber.transcribe(
            chat='me',  # Saved Messages
            msg_id=12345,
            wait_for_completion=True,
            timeout=30.0
        )
        
        if request.completed and request.result:
            print(f"Transcription: {request.result.text}")
            
            # Rate the transcription as good
            await transcriber.rate_transcription(
                chat='me',
                msg_id=12345,
                transcription_id=request.result.transcription_id,
                good=True
            )
        else:
            print("Transcription is still pending")
            
    except InvalidMessageError:
        print("Message is not a voice message")
    except TranscriptionRateLimitError as e:
        print(f"Rate limited: {e}")
        if e.wait_seconds:
            print(f"Wait {e.wait_seconds} seconds before retrying")
    except VoiceTranscriptionError as e:
        print(f"Transcription error: {e}")


if __name__ == "__main__":
    # Note: This won't run without proper Telethon setup
    print("Basic Voice Transcription Implementation")
    print("See example_usage() function for usage patterns")
    print("Requires Telethon installation and TL class generation")