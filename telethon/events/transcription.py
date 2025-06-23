"""
Transcription Events for Telethon

This module provides event handlers for voice message transcription updates,
enabling users to easily respond to transcription progress and completion.
"""

import logging
from typing import Optional, Union

from .common import EventBuilder, EventCommon
from .. import types, utils

logger = logging.getLogger(__name__)


class TranscriptionUpdate(EventBuilder):
    """
    Event for audio transcription updates.
    
    This event is triggered when a transcription update is received,
    either as a progress update or completion notification.
    
    Example:
        @client.on(events.TranscriptionUpdate)
        async def handler(event):
            if event.is_complete:
                print(f"Transcription complete: {event.text}")
            else:
                print(f"Transcription progress: {event.text}")
    """
    
    def __init__(
        self,
        peer_types: tuple = None,
        *,
        incoming: bool = True,
        outgoing: bool = False,
        from_users: Union[tuple, set] = None,
        forwards: bool = None,
        pattern: Union[str, callable] = None,
        blacklist_chats: bool = False,
        func: callable = None
    ):
        """
        Initialize transcription update event builder.
        
        Args:
            peer_types: Tuple of peer types to listen for (users, chats, channels)
            incoming: Whether to handle incoming transcriptions
            outgoing: Whether to handle outgoing transcriptions  
            from_users: Users/chats to listen for transcriptions from
            forwards: Whether to handle forwarded message transcriptions
            pattern: Pattern to match against transcribed text
            blacklist_chats: Whether to blacklist certain chats
            func: Custom filter function
        """
        super().__init__(
            peer_types=peer_types,
            incoming=incoming,
            outgoing=outgoing,
            from_users=from_users,
            forwards=forwards,
            pattern=pattern,
            blacklist_chats=blacklist_chats,
            func=func
        )
    
    @classmethod
    def build(cls, update, others=None, self_id=None):
        """Build transcription event from update."""
        if isinstance(update, types.UpdateTranscribedAudio):
            return cls.Event(update)
        return None
    
    class Event(EventCommon):
        """
        Represents a single transcription update event.
        
        Attributes:
            peer: The peer where the transcription occurred
            message_id: ID of the message being transcribed
            transcription_id: Unique ID of the transcription
            text: Current transcription text
            is_pending: Whether transcription is still in progress
            is_complete: Whether transcription is finished
        """
        
        def __init__(self, update: types.UpdateTranscribedAudio):
            """Initialize from UpdateTranscribedAudio."""
            self._update = update
            
            # Extract core information
            self.peer = update.peer
            self.message_id = update.msg_id
            self.transcription_id = update.transcription_id
            self.text = update.text
            self.is_pending = getattr(update, 'pending', False)
            
            # Calculate peer information
            if hasattr(update.peer, 'user_id'):
                self.peer_id = update.peer.user_id
                self.is_private = True
                self.is_group = False
                self.is_channel = False
            elif hasattr(update.peer, 'chat_id'):
                self.peer_id = update.peer.chat_id
                self.is_private = False
                self.is_group = True
                self.is_channel = False
            elif hasattr(update.peer, 'channel_id'):
                self.peer_id = update.peer.channel_id
                self.is_private = False
                self.is_group = False
                self.is_channel = True
            else:
                self.peer_id = utils.get_peer_id(update.peer)
                self.is_private = False
                self.is_group = False
                self.is_channel = False
            
            # Initialize common event properties
            super().__init__(
                chat_peer=self.peer,
                msg_id=self.message_id,
                broadcast=False
            )
        
        @property
        def is_complete(self) -> bool:
            """Check if transcription is complete."""
            return not self.is_pending
        
        @property
        def chat_id(self) -> int:
            """Get the chat ID where transcription occurred."""
            return self.peer_id
        
        @property
        def user_id(self) -> Optional[int]:
            """Get user ID if this is a private chat transcription."""
            return self.peer_id if self.is_private else None
        
        @property
        def raw_update(self) -> types.UpdateTranscribedAudio:
            """Get the raw update object."""
            return self._update
        
        async def get_message(self):
            """
            Get the original message that was transcribed.
            
            Returns:
                Message object containing the voice/audio
            """
            try:
                # Get the message from the client
                messages = await self._client.get_messages(
                    self.peer, ids=[self.message_id]
                )
                return messages[0] if messages else None
            except Exception as e:
                logger.error(f"Failed to get transcribed message: {e}")
                return None
        
        async def respond(self, *args, **kwargs):
            """
            Respond to the transcription update.
            
            This sends a message to the same chat where the
            transcription occurred.
            """
            return await self._client.send_message(self.peer, *args, **kwargs)
        
        async def reply(self, *args, **kwargs):
            """
            Reply to the original voice message.
            
            This replies directly to the message that was transcribed.
            """
            kwargs['reply_to'] = self.message_id
            return await self._client.send_message(self.peer, *args, **kwargs)
        
        def __str__(self) -> str:
            """String representation of the event."""
            status = "complete" if self.is_complete else "pending"
            text_preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
            return (
                f"TranscriptionUpdate(peer={self.peer_id}, "
                f"msg={self.message_id}, "
                f"status={status}, "
                f"text='{text_preview}')"
            )
        
        def __repr__(self) -> str:
            """Detailed representation of the event."""
            return (
                f"TranscriptionUpdate("
                f"peer_id={self.peer_id}, "
                f"message_id={self.message_id}, "
                f"transcription_id={self.transcription_id}, "
                f"is_pending={self.is_pending}, "
                f"text_length={len(self.text)}"
                f")"
            )


class TranscriptionComplete(TranscriptionUpdate):
    """
    Event for completed transcriptions only.
    
    This is a convenience event that only triggers when a transcription
    is fully completed (not for progress updates).
    
    Example:
        @client.on(events.TranscriptionComplete)
        async def handler(event):
            print(f"Final transcription: {event.text}")
    """
    
    @classmethod
    def build(cls, update, others=None, self_id=None):
        """Build event only for completed transcriptions."""
        if isinstance(update, types.UpdateTranscribedAudio):
            # Only build event if transcription is complete
            if not getattr(update, 'pending', False):
                return cls.Event(update)
        return None


class TranscriptionProgress(TranscriptionUpdate):
    """
    Event for transcription progress updates only.
    
    This is a convenience event that only triggers for intermediate
    updates while transcription is still in progress.
    
    Example:
        @client.on(events.TranscriptionProgress)
        async def handler(event):
            print(f"Transcription progress: {event.text}")
    """
    
    @classmethod
    def build(cls, update, others=None, self_id=None):
        """Build event only for progress updates."""
        if isinstance(update, types.UpdateTranscribedAudio):
            # Only build event if transcription is still pending
            if getattr(update, 'pending', False):
                return cls.Event(update)
        return None


# For backward compatibility and easier imports
TranscriptionEvent = TranscriptionUpdate