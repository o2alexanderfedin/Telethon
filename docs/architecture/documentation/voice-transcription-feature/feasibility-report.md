# Feasibility Report: Voice Message Transcription Support in Telethon

## Issue Summary
- **Issue #3934**: Add support for voice message transcription
- **Status**: CLOSED
- **Request**: Implement MTProto methods for voice message transcription (Speech-To-Text)
- **Requester Note**: Telegram Premium feature that provides better results than external STT services

## Current Status

### 1. MTProto Support ✅
The MTProto protocol already includes the necessary methods and types for voice transcription:

#### Available Methods:
- `messages.transcribeAudio` - Initiates transcription of a voice message
- `messages.rateTranscribedAudio` - Rates transcription quality

#### Available Types:
- `updateTranscribedAudio` - Update received during transcription
- `messages.TranscribedAudio` - Response containing transcription data

### 2. Telethon Implementation Status ❌
- **Raw API Support**: Available (as confirmed by Lonami)
- **Friendly Methods**: Not implemented in v1
- **TL Definitions**: Present in `telethon_generator/data/api.tl`
- **Generated Code**: Would need to be regenerated to include these methods

## Implementation Feasibility

### Technical Feasibility: HIGH ✅

1. **TL Schema Already Present**
   ```tl
   messages.transcribeAudio#269e9a49 peer:InputPeer msg_id:int = messages.TranscribedAudio;
   messages.rateTranscribedAudio#7f1d072f peer:InputPeer msg_id:int transcription_id:long good:Bool = Bool;
   ```

2. **Update Handling Infrastructure Exists**
   - Telethon already has robust update handling via `UpdateMixin`
   - Adding `updateTranscribedAudio` handler would follow existing patterns

3. **Similar Features Already Implemented**
   - Message sending/editing follows similar request/update patterns
   - File upload/download shows async operation handling

### Implementation Approach

#### Option 1: Raw API Usage (Currently Available)
```python
# Users can already do this:
from telethon.tl.functions.messages import TranscribeAudioRequest
result = await client(TranscribeAudioRequest(
    peer=peer,
    msg_id=message_id
))
```

#### Option 2: Friendly Method Implementation (Proposed)
```python
# Proposed friendly method in MessageMixin:
async def transcribe_voice_message(
    self,
    entity,
    message,
    *,
    wait_for_result=True,
    callback=None
):
    """
    Transcribe a voice message using Telegram's STT service.
    
    Args:
        entity: The chat where the message exists
        message: Message ID or Message object containing voice
        wait_for_result: Whether to wait for complete transcription
        callback: Optional callback for progressive updates
        
    Returns:
        Transcription text or TranscribedAudio object
    """
```

### Implementation Complexity

#### Low Complexity Components:
1. **Basic Method Wrapper** - Simple wrapper around raw API
2. **Type Generation** - Already automated via TL generator

#### Medium Complexity Components:
1. **Update Handling** - Need to handle `updateTranscribedAudio`
2. **Progressive Updates** - Transcription text updates over time
3. **Error Handling** - Premium limits, rate limits, etc.

#### High Complexity Components:
1. **State Management** - Tracking ongoing transcriptions
2. **Callback System** - For progressive transcription updates
3. **Integration with Event System** - New event type for transcriptions

## Limitations and Considerations

### 1. Premium Feature Restrictions
- Limited to Premium users or limited trials
- Requires handling of quota information
- Supergroup boost level affects availability

### 2. Asynchronous Nature
- Transcription is not instant
- Requires handling of progressive updates
- May need timeout handling

### 3. Version Compatibility
- Lonami stated: "no plans to add new friendly methods to v1"
- Would likely be a v2 feature

## Recommendation

### For Users (Current Solution):
Use the raw API as suggested by Lonami:
```python
from telethon.tl.functions.messages import TranscribeAudioRequest
from telethon.tl.types import UpdateTranscribedAudio

# Request transcription
result = await client(TranscribeAudioRequest(peer=peer, msg_id=msg_id))

# Handle updates
@client.on(events.Raw(UpdateTranscribedAudio))
async def transcription_handler(event):
    print(f"Transcription update: {event.text}")
```

### For Library Development:
1. **Short Term**: Document raw API usage with examples
2. **Long Term**: Consider for v2 with proper abstraction:
   - Event type for transcription updates
   - Friendly method with progress callbacks
   - Integration with message objects

## Conclusion

**Feasibility: HIGH** - The feature is technically feasible and the infrastructure exists. However:

1. ✅ Can be used today via raw API
2. ❌ Won't get friendly methods in v1 (per maintainer decision)
3. 🔄 Could be considered for v2 with proper design

The implementation would be straightforward but requires design decisions about:
- Update handling patterns
- Progress callback mechanisms
- Error and limit handling
- Integration with existing message methods

Users needing this feature should use the raw API approach, which provides full functionality without waiting for friendly method implementation.