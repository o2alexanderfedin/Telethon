# Voice Transcription TL Schema Documentation

## Overview

Telegram's MTProto API includes built-in support for voice message transcription. This document details the TL (Type Language) schema definitions for voice transcription functionality in Telethon.

## TL Schema Definitions

### 1. Request Methods

#### messages.transcribeAudio
```tl
messages.transcribeAudio#269e9a49 peer:InputPeer msg_id:int = messages.TranscribedAudio;
```

**Purpose**: Initiates transcription of a voice message.

**Parameters**:
- `peer` (InputPeer): The chat/channel/user where the voice message exists
- `msg_id` (int): The message ID of the voice message to transcribe

**Returns**: `messages.TranscribedAudio`

**Example Usage**:
```python
from telethon.tl.functions.messages import TranscribeAudioRequest

# Transcribe a voice message
result = await client(TranscribeAudioRequest(
    peer=await client.get_input_entity(chat),
    msg_id=voice_message.id
))
```

#### messages.rateTranscribedAudio
```tl
messages.rateTranscribedAudio#7f1d072f peer:InputPeer msg_id:int transcription_id:long good:Bool = Bool;
```

**Purpose**: Provides feedback on transcription quality.

**Parameters**:
- `peer` (InputPeer): The chat where the transcribed message exists
- `msg_id` (int): The original message ID
- `transcription_id` (long): The unique transcription ID
- `good` (Bool): Whether the transcription was accurate

**Returns**: `Bool` - Success status

### 2. Response Types

#### messages.TranscribedAudio
```tl
messages.transcribedAudio#cfb9d957 flags:# pending:flags.0?true transcription_id:long text:string trial_remains_num:flags.1?int trial_remains_until_date:flags.1?int = messages.TranscribedAudio;
```

**Fields**:
- `flags`: Bit flags for optional fields
- `pending` (flag 0): Whether transcription is still in progress
- `transcription_id` (long): Unique identifier for this transcription
- `text` (string): The transcribed text (empty if still pending)
- `trial_remains_num` (flag 1, int): Number of trial transcriptions remaining
- `trial_remains_until_date` (flag 1, int): Unix timestamp when trial resets

**Response States**:
1. **Pending**: `pending=True`, `text=""` - Transcription started
2. **Complete**: `pending=False`, `text="transcribed content"` - Transcription finished

### 3. Update Types

#### updateTranscribedAudio
```tl
updateTranscribedAudio#84cd5a flags:# pending:flags.0?true peer:Peer msg_id:int transcription_id:long text:string = Update;
```

**Purpose**: Real-time update when transcription completes.

**Fields**:
- `flags`: Bit flags for optional fields
- `pending` (flag 0): Whether transcription is still processing
- `peer` (Peer): The chat where the message exists
- `msg_id` (int): The original voice message ID
- `transcription_id` (long): The transcription identifier
- `text` (string): The transcribed text

**Event Handling**:
```python
from telethon.tl.types import UpdateTranscribedAudio

@client.on(events.Raw(UpdateTranscribedAudio))
async def on_transcription_update(event):
    update = event.update
    if not update.pending:
        print(f"Transcription complete: {update.text}")
```

### 4. Related Schema Definitions

#### DocumentAttributeAudio
```tl
documentAttributeAudio#9852f9c6 flags:# voice:flags.10?true duration:int title:flags.0?string performer:flags.1?string waveform:flags.2?bytes = DocumentAttribute;
```

The `voice` flag (bit 10) identifies voice messages that can be transcribed.

## Integration with Telethon

### Schema Location
- **File**: `/telethon_generator/data/api.tl`
- **Lines**: 
  - `messages.transcribeAudio`: Line 2339
  - `messages.rateTranscribedAudio`: Line 2340
  - `updateTranscribedAudio`: Line 393
  - `messages.transcribedAudio`: Line 1500

### Code Generation
To regenerate Python classes from TL schemas:
```bash
cd /path/to/Telethon
python setup.py gen tl
```

This generates:
- `/telethon/tl/functions/messages/transcribe_audio.py`
- `/telethon/tl/functions/messages/rate_transcribed_audio.py`
- `/telethon/tl/types/update_transcribed_audio.py`
- `/telethon/tl/types/messages/transcribed_audio.py`

## Usage Examples

### Basic Transcription Request
```python
from telethon.tl.functions.messages import TranscribeAudioRequest
from telethon.tl.types import UpdateTranscribedAudio

# Start transcription
async def transcribe_voice_message(client, chat, msg_id):
    result = await client(TranscribeAudioRequest(
        peer=await client.get_input_entity(chat),
        msg_id=msg_id
    ))
    
    if result.pending:
        print(f"Transcription started: ID {result.transcription_id}")
        # Wait for UpdateTranscribedAudio
    else:
        print(f"Instant result: {result.text}")
    
    return result

# Handle updates
@client.on(events.Raw(UpdateTranscribedAudio))
async def handle_transcription(event):
    update = event.update
    print(f"Message {update.msg_id}: {update.text}")
```

### With Error Handling
```python
from telethon.errors import FloodWaitError, MessageNotFoundError

async def safe_transcribe(client, chat, msg_id):
    try:
        result = await client(TranscribeAudioRequest(
            peer=await client.get_input_entity(chat),
            msg_id=msg_id
        ))
        return result
    except FloodWaitError as e:
        print(f"Rate limited, wait {e.seconds} seconds")
    except MessageNotFoundError:
        print("Voice message not found")
    except Exception as e:
        print(f"Transcription failed: {e}")
```

## Limitations and Considerations

1. **Message Type**: Only voice messages (documents with `voice=True` attribute) can be transcribed
2. **Rate Limits**: Transcription requests are subject to flood limits
3. **Trial Limits**: Non-premium users may have limited free transcriptions
4. **Language Support**: Transcription quality varies by language
5. **Message Age**: Very old messages might not be transcribable
6. **Privacy**: Transcription requires message access permissions

## Testing the Schema

### Unit Test Example
```python
import pytest
from telethon.tl.functions.messages import TranscribeAudioRequest
from telethon.tl.types import UpdateTranscribedAudio

def test_request_serialization():
    """Test that TranscribeAudioRequest serializes correctly"""
    request = TranscribeAudioRequest(
        peer=InputPeerUser(user_id=123, access_hash=456),
        msg_id=789
    )
    
    # Verify hex ID
    assert request.CONSTRUCTOR_ID == 0x269e9a49
    
    # Verify serialization
    data = bytes(request)
    assert len(data) > 0

def test_update_parsing():
    """Test UpdateTranscribedAudio parsing"""
    # Would test with actual serialized data
    pass
```

## Migration Guide

For developers migrating from other transcription services:

1. **No API Keys**: Uses existing Telegram auth
2. **No External Services**: Built into Telegram's infrastructure  
3. **Real-time Updates**: Use update handlers instead of polling
4. **Automatic Language Detection**: No need to specify language
5. **Cost**: Free for Telegram Premium users

## References

- [Telegram API Documentation](https://core.telegram.org/api)
- [TL Language Reference](https://core.telegram.org/mtproto/TL)
- [Telethon Documentation](https://docs.telethon.dev)
- [Voice Transcription Feature Epic](../features/voice-transcription/epic1-analysis.md)