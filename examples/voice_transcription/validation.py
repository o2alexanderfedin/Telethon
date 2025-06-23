"""
Request Validation and Error Handling for Voice Transcription

This module provides comprehensive validation and error handling for voice transcription requests,
implementing robust checks and user-friendly error messages.
"""

import logging
from typing import Union, Optional, Dict, Any
from datetime import datetime, timedelta

try:
    from telethon import TelegramClient
    from telethon.tl.types import Message, Document, DocumentAttributeAudio, InputPeer
    from telethon.errors import (
        FloodWaitError, MessageNotFoundError, ChatAdminRequiredError,
        UserNotMutualContactError, AuthKeyUnregisteredError, PeerIdInvalidError,
        MessageIdInvalidError, AccessHashInvalidError, UserBannedInChannelError
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TelegramClient = Any
    Message = Any
    Document = Any
    DocumentAttributeAudio = Any
    InputPeer = Any


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base class for validation errors"""
    pass


class MessageValidationError(ValidationError):
    """Errors related to message validation"""
    pass


class PermissionValidationError(ValidationError):
    """Errors related to permissions"""
    pass


class RateLimitValidationError(ValidationError):
    """Errors related to rate limiting"""
    def __init__(self, message: str, wait_seconds: Optional[int] = None):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class VoiceMessageValidator:
    """
    Comprehensive validator for voice messages and transcription requests.
    
    Provides detailed validation with clear error messages and suggested fixes.
    """
    
    def __init__(self, client: 'TelegramClient'):
        self.client = client
        self._validation_cache = {}  # Cache validation results
        self._cache_ttl = timedelta(minutes=5)  # Cache valid for 5 minutes
        
    async def validate_transcription_request(
        self,
        chat: Union[int, str],
        msg_id: int,
        check_permissions: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of a transcription request.
        
        Args:
            chat: Chat identifier
            msg_id: Message ID
            check_permissions: Whether to check user permissions
            use_cache: Whether to use cached validation results
            
        Returns:
            Validation result dictionary with message info
            
        Raises:
            MessageValidationError: If message validation fails
            PermissionValidationError: If permission validation fails
        """
        cache_key = f"{chat}:{msg_id}" if use_cache else None
        
        # Check cache first
        if cache_key and self._is_cache_valid(cache_key):
            logger.debug(f"Using cached validation for {cache_key}")
            return self._validation_cache[cache_key]['result']
            
        # Perform validation
        result = await self._perform_validation(chat, msg_id, check_permissions)
        
        # Cache result
        if cache_key:
            self._validation_cache[cache_key] = {
                'result': result,
                'timestamp': datetime.now()
            }
            
        return result
        
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached validation is still valid"""
        if cache_key not in self._validation_cache:
            return False
            
        cached_time = self._validation_cache[cache_key]['timestamp']
        return datetime.now() - cached_time < self._cache_ttl
        
    async def _perform_validation(
        self,
        chat: Union[int, str],
        msg_id: int,
        check_permissions: bool
    ) -> Dict[str, Any]:
        """Perform the actual validation checks"""
        
        # Step 1: Validate chat and get entity
        try:
            entity = await self.client.get_entity(chat)
            input_peer = await self.client.get_input_entity(chat)
        except PeerIdInvalidError:
            raise MessageValidationError(
                f"Invalid chat identifier: {chat}. "
                "Make sure the chat ID is correct or you have access to this chat."
            )
        except Exception as e:
            raise MessageValidationError(f"Failed to resolve chat {chat}: {e}")
            
        # Step 2: Get and validate message
        message = await self._validate_message_exists(entity, msg_id)
        
        # Step 3: Validate message is voice
        voice_info = self._validate_is_voice_message(message)
        
        # Step 4: Check permissions if requested
        permissions = {}
        if check_permissions:
            permissions = await self._validate_permissions(entity, message)
            
        # Step 5: Check voice message properties
        voice_properties = self._analyze_voice_properties(message, voice_info)
        
        return {
            'chat_id': entity.id,
            'chat_title': getattr(entity, 'title', getattr(entity, 'username', str(entity.id))),
            'message_id': msg_id,
            'message': message,
            'entity': entity,
            'input_peer': input_peer,
            'voice_info': voice_info,
            'voice_properties': voice_properties,
            'permissions': permissions,
            'validated_at': datetime.now()
        }
        
    async def _validate_message_exists(self, entity, msg_id: int) -> Message:
        """Validate that the message exists and is accessible"""
        try:
            message = await self.client.get_messages(entity, ids=msg_id)
        except MessageIdInvalidError:
            raise MessageValidationError(
                f"Message ID {msg_id} is invalid. "
                "Check that the message ID is correct and the message still exists."
            )
        except Exception as e:
            raise MessageValidationError(f"Failed to fetch message {msg_id}: {e}")
            
        if not message:
            raise MessageValidationError(
                f"Message {msg_id} not found. "
                "The message may have been deleted or you don't have access to it."
            )
            
        return message
        
    def _validate_is_voice_message(self, message: Message) -> Dict[str, Any]:
        """Validate that the message is a voice message"""
        if not message.media:
            raise MessageValidationError(
                f"Message {message.id} is a text message, not a voice message. "
                "Only voice messages can be transcribed."
            )
            
        if not isinstance(message.media.document, Document):
            media_type = type(message.media).__name__
            raise MessageValidationError(
                f"Message {message.id} contains {media_type}, not a voice message. "
                "Only voice messages can be transcribed."
            )
            
        document = message.media.document
        
        # Find audio attribute
        audio_attr = None
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeAudio):
                audio_attr = attr
                break
                
        if not audio_attr:
            raise MessageValidationError(
                f"Message {message.id} is not an audio file. "
                "Only voice messages can be transcribed."
            )
            
        if not audio_attr.voice:
            raise MessageValidationError(
                f"Message {message.id} is an audio file but not a voice message. "
                "Only voice messages (not music/audio files) can be transcribed."
            )
            
        return {
            'duration': audio_attr.duration,
            'waveform': getattr(audio_attr, 'waveform', None),
            'document_size': document.size,
            'mime_type': document.mime_type,
            'date': message.date
        }
        
    async def _validate_permissions(self, entity, message: Message) -> Dict[str, Any]:
        """Validate user permissions for transcription"""
        permissions = {
            'can_transcribe': True,
            'is_premium': False,
            'warnings': []
        }
        
        try:
            # Check if user is premium (affects rate limits)
            me = await self.client.get_me()
            permissions['is_premium'] = getattr(me, 'premium', False)
            
            # Check message access
            if message.from_id and hasattr(message.from_id, 'user_id'):
                # Check if we can access the sender
                try:
                    sender = await self.client.get_entity(message.from_id.user_id)
                    permissions['sender_accessible'] = True
                except:
                    permissions['sender_accessible'] = False
                    permissions['warnings'].append(
                        "Cannot access message sender info"
                    )
                    
            # Age-based warnings
            if message.date:
                age_days = (datetime.now() - message.date).days
                if age_days > 30:
                    permissions['warnings'].append(
                        f"Message is {age_days} days old. "
                        "Very old messages might not be transcribable."
                    )
                    
        except Exception as e:
            logger.warning(f"Permission check failed: {e}")
            permissions['warnings'].append(f"Could not verify permissions: {e}")
            
        return permissions
        
    def _analyze_voice_properties(self, message: Message, voice_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze voice message properties for transcription suitability"""
        properties = {
            'suitable_for_transcription': True,
            'warnings': [],
            'recommendations': []
        }
        
        # Duration checks
        duration = voice_info.get('duration', 0)
        if duration > 300:  # 5 minutes
            properties['warnings'].append(
                f"Voice message is {duration//60}:{duration%60:02d} long. "
                "Very long messages may take more time to transcribe."
            )
        elif duration < 1:
            properties['warnings'].append(
                "Voice message is very short. Transcription might not be accurate."
            )
            
        # Size checks
        size = voice_info.get('document_size', 0)
        if size > 10 * 1024 * 1024:  # 10MB
            properties['warnings'].append(
                f"Voice message is large ({size // (1024*1024)}MB). "
                "Large files may take longer to process."
            )
            
        # Format checks
        mime_type = voice_info.get('mime_type', '')
        if mime_type and 'ogg' not in mime_type.lower():
            properties['warnings'].append(
                f"Voice message format is {mime_type}. "
                "Telegram voice messages are usually in OGG format."
            )
            
        # Recommendations
        if not properties['warnings']:
            properties['recommendations'].append(
                "Voice message appears suitable for transcription."
            )
        else:
            properties['recommendations'].append(
                "Voice message can be transcribed but may have quality/timing issues."
            )
            
        return properties
        
    def clear_cache(self):
        """Clear the validation cache"""
        self._validation_cache.clear()
        logger.debug("Validation cache cleared")
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get validation cache statistics"""
        now = datetime.now()
        valid_entries = sum(
            1 for entry in self._validation_cache.values()
            if now - entry['timestamp'] < self._cache_ttl
        )
        
        return {
            'total_entries': len(self._validation_cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self._validation_cache) - valid_entries,
            'cache_ttl_minutes': self._cache_ttl.total_seconds() / 60
        }


class ErrorHandler:
    """
    Centralized error handling for voice transcription operations.
    
    Provides user-friendly error messages and suggested solutions.
    """
    
    @staticmethod
    def handle_telethon_error(error: Exception) -> str:
        """
        Convert Telethon errors to user-friendly messages.
        
        Args:
            error: The original Telethon error
            
        Returns:
            User-friendly error message
        """
        if isinstance(error, FloodWaitError):
            return (
                f"Rate limit exceeded. Please wait {error.seconds} seconds before retrying. "
                "Telegram limits the number of transcription requests per time period."
            )
            
        elif isinstance(error, MessageNotFoundError):
            return (
                "The message was not found. It may have been deleted or you don't have "
                "permission to access it."
            )
            
        elif isinstance(error, PeerIdInvalidError):
            return (
                "Invalid chat ID or username. Make sure you have access to this chat "
                "and the ID/username is correct."
            )
            
        elif isinstance(error, MessageIdInvalidError):
            return (
                "Invalid message ID. Check that the message ID is correct and the "
                "message still exists."
            )
            
        elif isinstance(error, UserBannedInChannelError):
            return (
                "You are banned from this channel/group and cannot access messages. "
                "Contact the administrators if this is unexpected."
            )
            
        elif isinstance(error, ChatAdminRequiredError):
            return (
                "Admin privileges are required for this operation in this chat. "
                "Contact the chat administrators."
            )
            
        elif isinstance(error, UserNotMutualContactError):
            return (
                "You need to be mutual contacts with this user to access their messages. "
                "Add each other as contacts first."
            )
            
        elif isinstance(error, AuthKeyUnregisteredError):
            return (
                "Your session is invalid. Please log in again. "
                "This usually happens when the session expires or is revoked."
            )
            
        elif isinstance(error, AccessHashInvalidError):
            return (
                "Access to this chat/user is invalid. The entity may have been deleted "
                "or access permissions changed."
            )
            
        else:
            # Generic error message
            error_name = type(error).__name__
            return f"An error occurred: {error_name}. Details: {str(error)}"
            
    @staticmethod
    def get_retry_suggestion(error: Exception) -> Optional[str]:
        """
        Get retry suggestions for specific errors.
        
        Args:
            error: The original error
            
        Returns:
            Retry suggestion or None if no retry recommended
        """
        if isinstance(error, FloodWaitError):
            return f"Retry after {error.seconds} seconds"
            
        elif isinstance(error, (MessageNotFoundError, PeerIdInvalidError, 
                              MessageIdInvalidError, UserBannedInChannelError)):
            return None  # No point retrying these
            
        elif isinstance(error, AuthKeyUnregisteredError):
            return "Re-authenticate and retry"
            
        else:
            return "Retry after a short delay"


# Example usage
async def example_validation():
    """Example of how to use the validation system"""
    
    client = None  # Placeholder - would be real TelegramClient
    validator = VoiceMessageValidator(client)
    
    try:
        # Validate a transcription request
        result = await validator.validate_transcription_request(
            chat='@username',
            msg_id=12345,
            check_permissions=True
        )
        
        print("Validation successful:")
        print(f"- Chat: {result['chat_title']}")
        print(f"- Message: {result['message_id']}")
        print(f"- Duration: {result['voice_info']['duration']} seconds")
        
        # Check for warnings
        if result['voice_properties']['warnings']:
            print("Warnings:")
            for warning in result['voice_properties']['warnings']:
                print(f"  - {warning}")
                
    except ValidationError as e:
        print(f"Validation failed: {e}")
        
        # Get retry suggestion
        suggestion = ErrorHandler.get_retry_suggestion(e)
        if suggestion:
            print(f"Suggestion: {suggestion}")


if __name__ == "__main__":
    print("Voice Transcription Validation and Error Handling")
    print("See example_validation() function for usage patterns")