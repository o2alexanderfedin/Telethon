# Release Notes - Telethon v1.41.0

## Release Date: 2025-06-23

### 🎉 Major Features

#### Voice Transcription Support
This release introduces comprehensive voice message transcription capabilities to Telethon.

### ✨ New Features

- **Voice Transcription Module** (`telethon.client.voice_transcription`)
  - Complete implementation for transcribing voice messages
  - Automatic state management and update handling
  - Error handling framework with recovery mechanisms
  - User type detection (Free/Premium/Bot)
  - Automatic cleanup system for completed transcriptions
  - Real-time transcription progress updates

### 🔧 Technical Improvements

- **High-level API**: Simple `transcribe_audio()` method on TelegramClient
- **Comprehensive Error Handling**: Detailed error types and recovery actions
- **State Management**: Track transcription progress and handle updates
- **Test Suite**: 14 test files with unit, integration, and performance tests
- **Documentation**: Complete architecture and API documentation

### 📝 API Changes

- Added `transcribe_audio()` method to TelegramClient
- New `voice_transcription` module with advanced features
- Replaced `voice_errors.py` with `voice_transcription.error_handling`

### 🐛 Bug Fixes

- Improved error handling for voice message operations
- Better cleanup of transcription resources

### 📚 Documentation

- Added comprehensive voice transcription documentation
- Migration guides for the new feature
- Architecture documentation for developers

### 🔄 Migration

For users upgrading from previous versions:
- The old `voice_errors` module is deprecated, use `voice_transcription.error_handling`
- All existing transcription code remains compatible

### Example Usage

```python
from telethon import TelegramClient

async with TelegramClient('session', api_id, api_hash) as client:
    # Simple transcription
    result = await client.transcribe_audio('me', message_id)
    print(f"Transcription: {result.text}")
    
    # Advanced usage with TranscriptionManager
    from telethon.client.voice_transcription import TranscriptionManager
    
    manager = TranscriptionManager(client)
    await manager.initialize()
    
    result = await manager.transcribe(
        chat='me',
        msg_id=12345,
        wait_for_completion=True
    )
```

### Contributors

- Voice Transcription Implementation Team
- Architecture and Documentation Team

### Notes

This release completes Epic 1 (Core Infrastructure) and partial Epic 2 (User Experience) for the voice transcription feature roadmap.