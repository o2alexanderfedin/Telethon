#!/usr/bin/env python3
"""
Integration test example for voice transcription TL schemas.
This demonstrates how to test the voice transcription functionality once schemas are generated.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# These imports will work after running 'python setup.py gen tl' in Telethon
try:
    from telethon import TelegramClient, events
    from telethon.tl.functions.messages import TranscribeAudioRequest, RateTranscribedAudioRequest
    from telethon.tl.types import UpdateTranscribedAudio, DocumentAttributeAudio
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    print("⚠️  Telethon not available. Install and generate TL classes first.")


logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class VoiceTranscriptionTester:
    """Test voice transcription functionality"""
    
    def __init__(self, api_id, api_hash, session_name='voice_test'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self.transcriptions = {}  # Track active transcriptions
        
    async def start(self):
        """Initialize client and handlers"""
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        
        # Register update handler
        self.client.add_event_handler(
            self.handle_transcription_update,
            events.Raw(UpdateTranscribedAudio)
        )
        
        await self.client.start()
        logger.info("Client started successfully")
        
    async def handle_transcription_update(self, event):
        """Handle transcription completion updates"""
        update = event.update
        key = f"{update.peer.user_id}:{update.msg_id}"
        
        logger.info(f"Transcription update for message {update.msg_id}")
        
        if not update.pending:
            logger.info(f"Transcription complete: {update.text[:50]}...")
            
            # Store completed transcription
            if key in self.transcriptions:
                self.transcriptions[key]['text'] = update.text
                self.transcriptions[key]['completed'] = True
                self.transcriptions[key]['completed_at'] = datetime.now()
        else:
            logger.info("Transcription still pending...")
            
    async def test_voice_message(self, chat, voice_msg_id):
        """Test transcribing a specific voice message"""
        logger.info(f"Testing voice transcription for message {voice_msg_id}")
        
        try:
            # Get message to verify it's a voice message
            message = await self.client.get_messages(chat, ids=voice_msg_id)
            
            if not message or not message.voice:
                logger.error("Message is not a voice message")
                return False
                
            # Start transcription
            logger.info("Sending transcription request...")
            result = await self.client(TranscribeAudioRequest(
                peer=await self.client.get_input_entity(chat),
                msg_id=voice_msg_id
            ))
            
            # Track transcription
            key = f"{chat}:{voice_msg_id}"
            self.transcriptions[key] = {
                'transcription_id': result.transcription_id,
                'started_at': datetime.now(),
                'pending': result.pending,
                'text': result.text if not result.pending else None,
                'completed': not result.pending
            }
            
            if result.pending:
                logger.info(f"Transcription started (ID: {result.transcription_id})")
                logger.info("Waiting for completion update...")
                
                # Wait for update (timeout after 30 seconds)
                for i in range(30):
                    await asyncio.sleep(1)
                    if self.transcriptions[key].get('completed'):
                        break
                        
                if self.transcriptions[key].get('completed'):
                    logger.info(f"✅ Transcription received: {self.transcriptions[key]['text']}")
                    return True
                else:
                    logger.warning("Transcription timed out")
                    return False
            else:
                logger.info(f"✅ Instant transcription: {result.text}")
                return True
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return False
            
    async def test_rate_transcription(self, chat, msg_id, transcription_id, good=True):
        """Test rating a transcription"""
        logger.info(f"Rating transcription {transcription_id} as {'good' if good else 'bad'}")
        
        try:
            result = await self.client(RateTranscribedAudioRequest(
                peer=await self.client.get_input_entity(chat),
                msg_id=msg_id,
                transcription_id=transcription_id,
                good=good
            ))
            
            if result:
                logger.info("✅ Rating submitted successfully")
            return result
            
        except Exception as e:
            logger.error(f"Rating failed: {e}")
            return False
            
    async def find_voice_messages(self, chat, limit=10):
        """Find recent voice messages in a chat"""
        logger.info(f"Searching for voice messages in {chat}")
        
        voice_messages = []
        async for message in self.client.iter_messages(chat, limit=limit):
            if message.voice:
                voice_messages.append(message)
                logger.info(f"Found voice message: ID {message.id} from {message.date}")
                
        logger.info(f"Found {len(voice_messages)} voice messages")
        return voice_messages
        
    async def run_tests(self, test_chat):
        """Run a series of tests"""
        logger.info("=== Starting Voice Transcription Tests ===")
        
        # Find voice messages
        voice_msgs = await self.find_voice_messages(test_chat, limit=50)
        
        if not voice_msgs:
            logger.warning("No voice messages found in test chat")
            return
            
        # Test transcription on first voice message
        test_msg = voice_msgs[0]
        success = await self.test_voice_message(test_chat, test_msg.id)
        
        if success:
            # Get transcription info
            key = f"{test_chat}:{test_msg.id}"
            trans_info = self.transcriptions.get(key)
            
            if trans_info and trans_info.get('transcription_id'):
                # Test rating
                await self.test_rate_transcription(
                    test_chat,
                    test_msg.id,
                    trans_info['transcription_id'],
                    good=True
                )
                
        logger.info("=== Tests Complete ===")
        
        # Show summary
        logger.info("\nTranscription Summary:")
        for key, info in self.transcriptions.items():
            logger.info(f"- {key}: {'Completed' if info.get('completed') else 'Pending'}")
            if info.get('text'):
                logger.info(f"  Text: {info['text'][:100]}...")
                

async def main():
    """Main test function"""
    if not TELETHON_AVAILABLE:
        print("\nTo run these tests:")
        print("1. Install Telethon: pip install telethon")
        print("2. Generate TL classes: cd Telethon && python setup.py gen tl")
        print("3. Configure API credentials")
        return
        
    # You need to set these
    API_ID = None  # Your API ID
    API_HASH = None  # Your API Hash
    TEST_CHAT = 'me'  # Chat to test in ('me' for saved messages)
    
    if not API_ID or not API_HASH:
        print("Please set API_ID and API_HASH in the script")
        return
        
    tester = VoiceTranscriptionTester(API_ID, API_HASH)
    
    try:
        await tester.start()
        await tester.run_tests(TEST_CHAT)
    finally:
        await tester.client.disconnect()
        

if __name__ == "__main__":
    asyncio.run(main())