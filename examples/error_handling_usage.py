#!/usr/bin/env python3
"""
Voice Transcription Error Handling Usage Examples

This module demonstrates how to use the error handling framework
for voice transcription operations in Telethon.

The error handling framework provides comprehensive error classification,
recovery suggestions, and automatic retry mechanisms.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List

from telethon import TelegramClient
from telethon.client.voice_errors import (
    # Import error types
    VoiceTranscriptionError,
    InvalidMessageError,
    InvalidPeerError,
    TranscriptionTimeoutError,
    TranscriptionQuotaExceededError,
    TranscriptionRateLimitError,
    NetworkError,
    PermissionError,
    TranscriptionMemoryError,
    
    # Import utilities
    ErrorHandler,
    ErrorContext,
    create_error_context,
    format_error_for_user,
    is_recoverable_error,
    get_automatic_recovery_actions,
    attempt_recovery,
    handle_transcription_errors
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_error_handling():
    """
    Basic example of handling transcription errors.
    """
    print("🔍 Basic Error Handling")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Attempt to transcribe a message
        try:
            result = await client.transcribe_audio(
                entity='invalid_chat',  # This will fail
                message=12345
            )
            print(f"Transcription result: {result}")
            
        except InvalidPeerError as e:
            print(f"❌ Invalid peer error: {e.get_user_friendly_message()}")
            print(f"   Error ID: {e.error_id}")
            print(f"   Peer ID: {e.peer_id}")
            
            # Show recovery suggestions
            print("\n📋 Recovery suggestions:")
            for action in e.recovery_actions:
                print(f"   - {action.description}")
                
        except InvalidMessageError as e:
            print(f"❌ Invalid message: {e.get_user_friendly_message()}")
            print(f"   Field: {e.field_name}")
            
        except VoiceTranscriptionError as e:
            # Catch-all for other transcription errors
            print(f"❌ Transcription error: {e.get_user_friendly_message()}")
            print(f"   Category: {e.category.value}")
            print(f"   Severity: {e.severity.value}")
            
    finally:
        await client.disconnect()


async def example_timeout_handling():
    """
    Example of handling timeout errors with retry logic.
    """
    print("\n⏱️  Timeout Error Handling")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    async def transcribe_with_timeout(timeout: float):
        """Simulate transcription with timeout."""
        try:
            # Simulate a transcription that might timeout
            result = await client.transcribe_audio(
                entity='chat_id',
                message=12345,
                wait_for_result=True,
                timeout=timeout
            )
            return result
        except TranscriptionTimeoutError as e:
            print(f"⏱️  Timeout after {e.timeout_seconds}s")
            print(f"   Operation: {e.operation}")
            
            # Check if we should retry
            if e.recoverable:
                print("   This error is recoverable, retrying with longer timeout...")
                # Retry with double the timeout
                return await transcribe_with_timeout(timeout * 2)
            else:
                raise
    
    try:
        await client.start()
        
        # Start with a short timeout
        result = await transcribe_with_timeout(5.0)
        print(f"✅ Transcription completed: {result}")
        
    except TranscriptionTimeoutError as e:
        print(f"❌ Final timeout: {e.get_detailed_message()}")
        
    finally:
        await client.disconnect()


async def example_rate_limit_handling():
    """
    Example of handling rate limiting with automatic retry.
    """
    print("\n🚦 Rate Limit Error Handling")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Simulate multiple transcription requests
        messages = [12345, 12346, 12347, 12348, 12349]
        
        for msg_id in messages:
            try:
                print(f"📝 Transcribing message {msg_id}...")
                result = await client.transcribe_audio('chat_id', msg_id)
                print(f"✅ Success: {result}")
                
            except TranscriptionRateLimitError as e:
                print(f"🚦 Rate limited: {e.get_user_friendly_message()}")
                
                if e.retry_after:
                    print(f"⏳ Waiting {e.retry_after} seconds...")
                    await asyncio.sleep(e.retry_after)
                    
                    # Retry after waiting
                    print("🔄 Retrying...")
                    result = await client.transcribe_audio('chat_id', msg_id)
                    print(f"✅ Success after retry: {result}")
                    
    finally:
        await client.disconnect()


async def example_quota_handling():
    """
    Example of handling quota exceeded errors.
    """
    print("\n📊 Quota Error Handling")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        try:
            # This might fail if quota is exceeded
            result = await client.transcribe_audio('chat_id', 12345)
            
        except TranscriptionQuotaExceededError as e:
            print(f"📊 Quota exceeded: {e.get_user_friendly_message()}")
            
            if e.trial_remains is not None:
                print(f"   Remaining trials: {e.trial_remains}")
                
            if e.trial_expires:
                print(f"   Resets at: {e.trial_expires}")
                
            # Show suggestions (upgrade to Premium)
            for action in e.recovery_actions:
                print(f"   💡 {action.description}")
                
    finally:
        await client.disconnect()


async def example_automatic_recovery():
    """
    Example of automatic error recovery.
    """
    print("\n🔄 Automatic Error Recovery")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    async def unreliable_transcription():
        """Simulate an unreliable operation."""
        import random
        if random.random() < 0.7:  # 70% failure rate
            raise NetworkError("Network connection lost")
        return "Transcription successful!"
    
    try:
        await client.start()
        
        try:
            # This will automatically retry on network errors
            result = await attempt_recovery(
                NetworkError("Initial failure"),
                unreliable_transcription
            )
            print(f"✅ Success with recovery: {result}")
            
        except NetworkError as e:
            print(f"❌ Failed after retries: {e.get_user_friendly_message()}")
            print(f"   Total attempts: {e.recovery_actions[0].parameters.get('max_retries', 3)}")
            
    finally:
        await client.disconnect()


async def example_error_context():
    """
    Example of using error context for detailed debugging.
    """
    print("\n🔍 Error Context Usage")
    print("=" * 40)
    
    # Create detailed error context
    context = create_error_context(
        operation="batch_transcribe",
        component="BatchProcessor",
        peer_id=123456789,
        msg_id=42,
        transcription_id=999,
        user_data={
            "batch_id": "batch_001",
            "user_id": 987654,
            "attempt": 1
        }
    )
    
    # Simulate an error with context
    error = StateManagementError(
        operation="update_state",
        state_key="123456789:42",
        context=context
    )
    
    print("Error details:")
    print(f"  Message: {error.get_detailed_message()}")
    print(f"  Error ID: {error.error_id}")
    print(f"  Severity: {error.severity.value}")
    print(f"  Category: {error.category.value}")
    
    print("\nError context:")
    error_dict = error.to_dict()
    for key, value in error_dict['context'].items():
        print(f"  {key}: {value}")


async def example_batch_error_handling():
    """
    Example of handling errors in batch operations.
    """
    print("\n📦 Batch Operation Error Handling")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    # Track errors for batch operations
    successful = []
    failed = []
    
    messages = [
        (123456, 1001),  # chat_id, message_id
        (123456, 1002),
        (999999, 1003),  # Invalid chat
        (123456, 1004),
        (123456, 9999),  # Invalid message
    ]
    
    try:
        await client.start()
        
        for chat_id, msg_id in messages:
            try:
                print(f"Processing {chat_id}:{msg_id}...")
                result = await client.transcribe_audio(chat_id, msg_id)
                successful.append((chat_id, msg_id, result))
                
            except VoiceTranscriptionError as e:
                failed.append((chat_id, msg_id, e))
                print(f"  ❌ Failed: {e.get_user_friendly_message()}")
                
                # Continue with next message
                continue
        
        # Summary
        print(f"\n📊 Batch Summary:")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        
        # Analyze failures
        if failed:
            print("\n❌ Failure Analysis:")
            error_types = {}
            for _, _, error in failed:
                error_type = type(error).__name__
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                print(f"  {error_type}: {count}")
                
    finally:
        await client.disconnect()


async def example_error_statistics():
    """
    Example of collecting and analyzing error statistics.
    """
    print("\n📈 Error Statistics")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Simulate various operations that might fail
        operations = [
            ('transcribe', lambda: client.transcribe_audio('chat', 123)),
            ('status', lambda: client.get_transcription_status('chat', 456)),
            ('rate', lambda: client.rate_transcription('chat', 789, 1, True)),
        ]
        
        for op_name, operation in operations:
            try:
                await operation()
            except VoiceTranscriptionError:
                pass  # Errors are tracked automatically
        
        # Get error statistics
        stats = client.get_error_statistics()
        
        print("Error Statistics:")
        print(f"  Total errors: {stats['total_errors']}")
        print(f"  Most common error: {stats.get('most_common_error', 'None')}")
        
        if stats['error_counts']:
            print("\nError breakdown:")
            for error_type, count in stats['error_counts'].items():
                print(f"  {error_type}: {count}")
                
    finally:
        await client.disconnect()


class TranscriptionBot:
    """
    Example bot with comprehensive error handling.
    """
    
    def __init__(self, client: TelegramClient):
        self.client = client
        self.error_handler = ErrorHandler()
    
    @handle_transcription_errors("process_voice_message", "TranscriptionBot")
    async def process_voice_message(self, chat_id: int, message_id: int) -> Optional[str]:
        """
        Process a voice message with automatic error handling.
        """
        # The decorator automatically handles and classifies errors
        result = await self.client.transcribe_audio(
            entity=chat_id,
            message=message_id,
            wait_for_result=True,
            timeout=60.0
        )
        
        # Additional processing
        if len(result) < 10:
            raise ValidationError(
                "Transcription too short",
                field_name="transcription_length"
            )
            
        return result
    
    async def handle_user_request(self, user_id: int, chat_id: int, message_id: int):
        """
        Handle user transcription request with user-friendly error messages.
        """
        try:
            # Process the voice message
            transcription = await self.process_voice_message(chat_id, message_id)
            
            # Send success response
            await self.send_message(
                chat_id,
                f"✅ Transcription:\n{transcription}"
            )
            
        except InvalidMessageError as e:
            # Message doesn't contain voice
            await self.send_message(
                chat_id,
                "❌ This message doesn't contain a voice note. "
                "Please send a voice message to transcribe."
            )
            
        except TranscriptionQuotaExceededError as e:
            # Quota exceeded
            message = format_error_for_user(e)
            await self.send_message(chat_id, f"❌ {message}")
            
        except TranscriptionTimeoutError:
            # Timeout
            await self.send_message(
                chat_id,
                "⏱️ Transcription is taking longer than expected. "
                "Please try again with a shorter voice message."
            )
            
        except PermissionError:
            # No permissions
            await self.send_message(
                chat_id,
                "🔒 I don't have permission to access messages in this chat. "
                "Please make sure I'm added as an admin."
            )
            
        except VoiceTranscriptionError as e:
            # Generic transcription error
            if e.recoverable:
                await self.send_message(
                    chat_id,
                    "⚠️ Temporary issue with transcription. Please try again."
                )
            else:
                message = format_error_for_user(e)
                await self.send_message(chat_id, f"❌ {message}")
                
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await self.send_message(
                chat_id,
                "❌ An unexpected error occurred. Please try again later."
            )
    
    async def send_message(self, chat_id: int, text: str):
        """Send a message to the user."""
        # Implement actual message sending
        print(f"[Bot -> {chat_id}]: {text}")


async def example_bot_usage():
    """
    Example of using error handling in a bot.
    """
    print("\n🤖 Bot Error Handling Example")
    print("=" * 40)
    
    client = TelegramClient('bot_session', api_id=12345, api_hash='your_api_hash')
    bot = TranscriptionBot(client)
    
    try:
        await client.start()
        
        # Simulate various user requests
        test_cases = [
            (1001, 123456, 789),  # Normal request
            (1002, 999999, 123),  # Invalid chat
            (1003, 123456, 999),  # Invalid message
        ]
        
        for user_id, chat_id, msg_id in test_cases:
            print(f"\n👤 User {user_id} requesting transcription...")
            await bot.handle_user_request(user_id, chat_id, msg_id)
            
    finally:
        await client.disconnect()


async def main():
    """
    Run all error handling examples.
    """
    print("🎯 Voice Transcription Error Handling Examples")
    print("=" * 50)
    
    examples = [
        example_basic_error_handling,
        example_timeout_handling,
        example_rate_limit_handling,
        example_quota_handling,
        example_automatic_recovery,
        example_error_context,
        example_batch_error_handling,
        example_error_statistics,
        example_bot_usage
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            logger.error(f"Example failed: {e}", exc_info=True)
        
        print("\n" + "=" * 50)
    
    print("\n✅ All examples completed!")
    print("\nKey takeaways:")
    print("1. Use specific error types for clear error handling")
    print("2. Provide context for better debugging")
    print("3. Implement recovery strategies for recoverable errors")
    print("4. Format errors appropriately for end users")
    print("5. Track error statistics for monitoring")
    print("6. Use the decorator for automatic error handling")


if __name__ == "__main__":
    asyncio.run(main())