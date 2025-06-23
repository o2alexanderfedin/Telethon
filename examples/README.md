# Telethon Examples

This directory contains example implementations and reference code for various Telethon features.

## Voice Transcription Examples

The `voice_transcription/` directory contains reference implementations for the voice transcription feature:

- **automatic_cleanup.py** - Example of automatic cleanup system for transcription states
- **basic_request.py** - Basic voice transcription request implementation
- **error_handling.py** - Comprehensive error handling examples
- **integration.py** - Integration examples with Telethon client
- **response_parser.py** - Response parsing implementation
- **state_manager.py** - State management for active transcriptions
- **transcription_manager.py** - Complete transcription manager example
- **update_handler.py** - Update handling for real-time transcription updates
- **user_type_detection.py** - User type detection (free/premium)
- **validation.py** - Input validation examples

## Usage

These are reference implementations to demonstrate how to use Telethon's voice transcription features. They are not meant to be used directly in production but rather as examples to learn from.

For the actual implementation, see:
- `telethon/client/transcription.py`
- `telethon/client/voice_errors.py`
- `telethon/events/transcription.py`

For tests, see:
- `tests/telethon/voice_transcription/`