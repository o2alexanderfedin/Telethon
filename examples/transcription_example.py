#!/usr/bin/env python3
"""
Voice Message Transcription Example

This example demonstrates how to use Telethon's voice message transcription
features, including the Basic Transcription Manager implementation.

Features demonstrated:
- Basic transcription of voice messages
- Handling transcription events and progress updates
- Rating transcription quality
- Managing transcription state
- Error handling and timeouts

Requirements:
- Telethon with transcription support
- Valid Telegram API credentials
- Telegram Premium account for unlimited transcriptions
"""

import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.custom import Message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Replace with your API credentials
API_ID = 'your_api_id'
API_HASH = 'your_api_hash'
SESSION_NAME = 'transcription_example'


async def main():
    """Main example function."""
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        logger.info("Connected to Telegram")
        
        # Example 1: Basic transcription
        await example_basic_transcription(client)
        
        # Example 2: Event-based transcription handling
        await example_event_handling(client)
        
        # Example 3: Batch transcription
        await example_batch_transcription(client)
        
        # Example 4: Error handling
        await example_error_handling(client)
        
        logger.info("All examples completed")


async def example_basic_transcription(client: TelegramClient):
    """Example 1: Basic voice message transcription."""
    logger.info("=== Example 1: Basic Transcription ===")
    
    try:
        # Get recent messages from saved messages
        messages = await client.get_messages('me', limit=10)
        
        # Find a voice message
        voice_message = None
        for msg in messages:
            if msg.voice or (msg.document and msg.document.mime_type.startswith('audio/')):
                voice_message = msg
                break
        
        if not voice_message:
            logger.info("No voice messages found. Send a voice message to 'Saved Messages' first.")
            return
        
        logger.info(f"Found voice message: {voice_message.id}")
        
        # Method 1: Simple transcription (wait for result)
        logger.info("Requesting transcription (wait for completion)...")
        try:
            text = await client.transcribe_audio(
                entity='me',
                message=voice_message.id,
                wait_for_result=True,
                timeout=30.0
            )
            logger.info(f"Transcription result: '{text}'")
            
            # Rate the transcription quality
            if text:
                # Get transcription state to access transcription_id
                state = await client.get_transcription_status('me', voice_message.id)
                if state and state.transcription_id:
                    await client.rate_transcription(
                        entity='me',
                        message=voice_message.id,
                        transcription_id=state.transcription_id,
                        good=True  # Rate as good quality
                    )
                    logger.info("Rated transcription as good quality")
        
        except TimeoutError:
            logger.error("Transcription timed out")
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
        
        # Method 2: Async transcription (don't wait)
        logger.info("Requesting async transcription...")
        state = await client.transcribe_audio(
            entity='me',
            message=voice_message.id,
            wait_for_result=False
        )
        
        logger.info(f"Transcription state: {state}")
        logger.info(f"Initial text: '{state.text}'")
        logger.info(f"Is pending: {state.is_pending}")
        
        # Poll for completion
        while state.is_active:
            await asyncio.sleep(1)
            updated_state = await client.get_transcription_status('me', voice_message.id)
            if updated_state:
                logger.info(f"Progress: '{updated_state.text}' (pending: {updated_state.is_pending})")
                if not updated_state.is_active:
                    break
        
        logger.info("Example 1 completed")
        
    except Exception as e:
        logger.error(f"Example 1 failed: {e}")


async def example_event_handling(client: TelegramClient):
    """Example 2: Event-based transcription handling."""
    logger.info("=== Example 2: Event-Based Handling ===")
    
    # Set up event handlers
    @client.on(events.TranscriptionProgress)
    async def on_transcription_progress(event):
        """Handle transcription progress updates."""
        logger.info(f"Progress update: '{event.text}' (length: {len(event.text)})")
    
    @client.on(events.TranscriptionComplete)
    async def on_transcription_complete(event):
        """Handle completed transcriptions."""
        logger.info(f"Transcription complete: '{event.text}'")
        
        # You can respond to the transcription
        if "hello" in event.text.lower():
            await event.respond("I heard you say hello!")
        
        # Or reply to the original voice message
        await event.reply(f"Transcription: {event.text}")
    
    @client.on(events.TranscriptionUpdate)
    async def on_any_transcription_update(event):
        """Handle any transcription update."""
        status = "complete" if event.is_complete else "in progress"
        logger.info(f"Transcription {status}: {event.transcription_id}")
    
    # Start a transcription to trigger events
    try:
        messages = await client.get_messages('me', limit=5)
        voice_message = None
        
        for msg in messages:
            if msg.voice or (msg.document and msg.document.mime_type.startswith('audio/')):
                voice_message = msg
                break
        
        if voice_message:
            logger.info("Starting transcription with event handling...")
            await client.transcribe_audio(
                entity='me',
                message=voice_message.id,
                wait_for_result=False
            )
            
            # Wait a bit to see events
            await asyncio.sleep(10)
        else:
            logger.info("No voice messages found for event example")
    
    except Exception as e:
        logger.error(f"Event handling example failed: {e}")
    
    logger.info("Example 2 completed")


async def example_batch_transcription(client: TelegramClient):
    """Example 3: Batch transcription of multiple voice messages."""
    logger.info("=== Example 3: Batch Transcription ===")
    
    try:
        # Get multiple voice messages
        messages = await client.get_messages('me', limit=20)
        voice_messages = [
            msg for msg in messages
            if msg.voice or (msg.document and msg.document.mime_type.startswith('audio/'))
        ]
        
        if not voice_messages:
            logger.info("No voice messages found for batch transcription")
            return
        
        logger.info(f"Found {len(voice_messages)} voice messages")
        
        # Start multiple transcriptions
        transcription_tasks = []
        for msg in voice_messages[:3]:  # Limit to 3 to avoid hitting rate limits
            task = client.transcribe_audio(
                entity='me',
                message=msg.id,
                wait_for_result=False
            )
            transcription_tasks.append(task)
        
        # Wait for all to start
        states = await asyncio.gather(*transcription_tasks, return_exceptions=True)
        
        logger.info(f"Started {len(states)} transcriptions")
        
        # Monitor progress
        active_states = [s for s in states if not isinstance(s, Exception)]
        while active_states:
            await asyncio.sleep(2)
            
            # Check status of all transcriptions
            for i, state in enumerate(active_states[:]):
                updated = await client.get_transcription_status('me', state.msg_id)
                if updated and not updated.is_active:
                    if updated.is_completed:
                        logger.info(f"Transcription {i+1} completed: '{updated.text}'")
                    else:
                        logger.info(f"Transcription {i+1} failed: {updated.error}")
                    active_states.remove(state)
        
        logger.info("All batch transcriptions completed")
    
    except Exception as e:
        logger.error(f"Batch transcription example failed: {e}")
    
    logger.info("Example 3 completed")


async def example_error_handling(client: TelegramClient):
    """Example 4: Error handling and edge cases."""
    logger.info("=== Example 4: Error Handling ===")
    
    # Test 1: Invalid message type
    try:
        await client.transcribe_audio(
            entity='me',
            message="invalid_message_id",
            wait_for_result=False
        )
    except TypeError as e:
        logger.info(f"✓ Correctly caught invalid message type: {e}")
    
    # Test 2: Non-existent message
    try:
        await client.transcribe_audio(
            entity='me',
            message=999999999,  # Very unlikely to exist
            wait_for_result=True,
            timeout=5.0
        )
    except Exception as e:
        logger.info(f"✓ Correctly caught non-existent message error: {e}")
    
    # Test 3: Timeout handling
    try:
        # Find a voice message
        messages = await client.get_messages('me', limit=10)
        voice_message = None
        for msg in messages:
            if msg.voice:
                voice_message = msg
                break
        
        if voice_message:
            await client.transcribe_audio(
                entity='me',
                message=voice_message.id,
                wait_for_result=True,
                timeout=0.1  # Very short timeout to test timeout handling
            )
    except TimeoutError as e:
        logger.info(f"✓ Correctly caught timeout error: {e}")
    except Exception as e:
        logger.info(f"Got different error (might be expected): {e}")
    
    # Test 4: Get status of non-existent transcription
    status = await client.get_transcription_status('me', 999999999)
    if status is None:
        logger.info("✓ Correctly returned None for non-existent transcription")
    
    logger.info("Example 4 completed")


async def example_advanced_usage(client: TelegramClient):
    """Advanced usage patterns and tips."""
    logger.info("=== Advanced Usage Tips ===")
    
    # Tip 1: Using callbacks for progress tracking
    def progress_callback(state, old_text):
        """Custom progress callback."""
        new_chars = len(state.text) - len(old_text)
        logger.info(f"Added {new_chars} characters to transcription")
    
    # Tip 2: Checking trial information
    try:
        messages = await client.get_messages('me', limit=5)
        voice_msg = next((m for m in messages if m.voice), None)
        
        if voice_msg:
            state = await client.transcribe_audio(
                entity='me',
                message=voice_msg.id,
                wait_for_result=False,
                callback=progress_callback
            )
            
            # Check trial information
            if state.trial_remains_num is not None:
                logger.info(f"Free transcriptions remaining: {state.trial_remains_num}")
                if state.trial_remains_until_date:
                    logger.info(f"Trial expires: {state.trial_remains_until_date}")
    
    except Exception as e:
        logger.error(f"Advanced usage example failed: {e}")


if __name__ == '__main__':
    """
    To run this example:
    
    1. Install Telethon: pip install telethon
    2. Get API credentials from https://my.telegram.org
    3. Replace API_ID and API_HASH with your credentials
    4. Send some voice messages to your "Saved Messages"
    5. Run: python transcription_example.py
    
    Note: You may need Telegram Premium for unlimited transcriptions.
    Free users have limited transcriptions per day.
    """
    
    if API_ID == 'your_api_id' or API_HASH == 'your_api_hash':
        print("Please set your API_ID and API_HASH in the script")
        exit(1)
    
    asyncio.run(main())