# Voice Transcription Error Handling Framework

## Overview

The Voice Transcription Error Handling Framework is part of Epic 1 User Story 1.7, providing comprehensive error handling with custom exceptions, clear error messages, error recovery mechanisms, and detailed logging for voice transcription operations.

## Features

- **Hierarchical exception system** with specific error types for different failure scenarios
- **Context-aware error messages** with actionable information for debugging
- **Error classification and severity levels** for appropriate handling
- **Recovery suggestions and retry mechanisms** for recoverable errors  
- **Comprehensive error logging and monitoring** with structured data
- **Error aggregation and reporting** for analytics
- **Automatic error handling decorator** for clean code
- **Thread-safe error tracking** with async support

## Architecture

### Error Hierarchy

```
VoiceTranscriptionError (Base)
├── ValidationError
│   ├── InvalidMessageError
│   ├── InvalidPeerError
│   └── MessageValidationError
├── AuthenticationError
│   ├── PermissionError
│   └── TranscriptionNotAvailableError
├── QuotaError
│   └── TranscriptionQuotaExceededError
├── RateLimitError
│   ├── TranscriptionRateLimitError
│   └── APIRateLimitError
├── NetworkError
│   ├── TranscriptionTimeoutError
│   └── ConnectionError
├── APIError
│   ├── TranscriptionRequestError
│   └── TranscriptionProcessingError
├── InternalError
│   ├── StateManagementError
│   └── ConfigurationError
└── ResourceError
    ├── TranscriptionMemoryError
    └── ConcurrencyLimitError
```

### Core Components

#### ErrorSeverity Enum
Defines error severity levels:
- `LOW` - Minor issues, operation can continue
- `MEDIUM` - Significant issues, may need attention
- `HIGH` - Major issues, operation likely failed
- `CRITICAL` - Critical failures, system integrity at risk

#### ErrorCategory Enum
Categorizes errors for better handling:
- `VALIDATION` - Input validation errors
- `AUTHENTICATION` - Auth/permission errors
- `NETWORK` - Network/connection errors
- `API` - Telegram API errors
- `RATE_LIMIT` - Rate limiting errors
- `TIMEOUT` - Timeout errors
- `INTERNAL` - Internal system errors
- `CONFIGURATION` - Configuration errors
- `RESOURCE` - Resource exhaustion errors
- `QUOTA` - Quota/limit errors

#### ErrorContext
Provides contextual information about where and when an error occurred:
```python
@dataclass
class ErrorContext:
    operation: str                           # Operation being performed
    component: str                           # Component where error occurred
    peer_id: Optional[int] = None           # Peer ID if applicable
    msg_id: Optional[int] = None            # Message ID if applicable
    transcription_id: Optional[int] = None  # Transcription ID if applicable
    user_data: Dict[str, Any] = field(default_factory=dict)  # Additional context
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

#### RecoveryAction
Suggests recovery actions for errors:
```python
@dataclass
class RecoveryAction:
    action_type: str        # Type of recovery action
    description: str        # Human-readable description
    automatic: bool = False # Whether action can be automated
    parameters: Dict[str, Any] = field(default_factory=dict)  # Action parameters
```

## Usage

### Basic Error Handling

```python
from telethon.client.voice_errors import (
    InvalidMessageError,
    TranscriptionTimeoutError,
    ErrorHandler,
    create_error_context
)

# Create error context
context = create_error_context(
    operation="transcribe_audio",
    component="TranscriptionMixin",
    peer_id=123456,
    msg_id=789
)

# Raise specific errors
try:
    if not is_voice_message(message):
        raise InvalidMessageError(
            "Message does not contain voice content",
            context=context
        )
except InvalidMessageError as e:
    print(f"Error ID: {e.error_id}")
    print(f"User message: {e.get_user_friendly_message()}")
    print(f"Detailed: {e.get_detailed_message()}")
    
    # Check recovery suggestions
    for action in e.recovery_actions:
        print(f"Suggestion: {action.description}")
```

### Using the Error Handler

```python
# Initialize error handler
error_handler = ErrorHandler()

try:
    # Some operation that might fail
    result = await risky_operation()
except Exception as e:
    # Handle and classify the error
    classified_error = await error_handler.handle_error(
        e, 
        context=context,
        reraise=True  # Will raise the classified error
    )
```

### Error Handling Decorator

The framework provides a decorator for automatic error handling:

```python
from telethon.client.voice_errors import handle_transcription_errors

class TranscriptionMixin:
    @handle_transcription_errors("transcribe_audio", "TranscriptionMixin")
    async def transcribe_audio(self, entity, message):
        # Method implementation
        # Any exceptions will be automatically classified and handled
        pass
```

### Handling Specific Error Types

#### Validation Errors
```python
try:
    result = await client.transcribe_audio(entity, message)
except InvalidMessageError as e:
    # Message doesn't contain voice/audio
    print(f"Invalid message: {e.get_user_friendly_message()}")
    # Suggestions: Verify that the message contains a voice note
except InvalidPeerError as e:
    # Invalid chat/peer ID
    print(f"Invalid peer: {e.peer_id}")
    # Suggestions: Verify the chat ID or username is correct
```

#### Rate Limiting Errors
```python
try:
    result = await client.transcribe_audio(entity, message)
except TranscriptionRateLimitError as e:
    if e.retry_after:
        print(f"Rate limited, retry after {e.retry_after} seconds")
        await asyncio.sleep(e.retry_after)
        # Retry the operation
```

#### Quota Errors
```python
try:
    result = await client.transcribe_audio(entity, message)
except TranscriptionQuotaExceededError as e:
    print(f"Quota exceeded: {e.trial_remains} trials remaining")
    if e.trial_expires:
        print(f"Resets at: {e.trial_expires}")
    # Suggestion: Consider upgrading to Telegram Premium
```

#### Network and Timeout Errors
```python
try:
    result = await client.transcribe_audio(
        entity, message, 
        wait_for_result=True,
        timeout=30.0
    )
except TranscriptionTimeoutError as e:
    print(f"Timed out after {e.timeout_seconds}s")
    # Consider increasing timeout or using callback pattern
except NetworkError as e:
    # Network issues - errors are marked as recoverable
    if e.recoverable:
        # Can retry with exponential backoff
        pass
```

### Error Recovery

The framework supports automatic and manual recovery:

```python
from telethon.client.voice_errors import (
    attempt_recovery,
    get_automatic_recovery_actions,
    is_recoverable_error
)

try:
    result = await transcribe_operation()
except VoiceTranscriptionError as e:
    if is_recoverable_error(e):
        # Attempt automatic recovery
        try:
            result = await attempt_recovery(e, transcribe_operation)
        except Exception as retry_error:
            # Recovery failed
            print("Recovery failed, manual intervention needed")
    
    # Get recovery suggestions
    auto_actions = get_automatic_recovery_actions(e)
    for action in auto_actions:
        print(f"Auto recovery: {action.action_type}")
```

### Error Statistics and Monitoring

```python
# Get error statistics
stats = client.get_error_statistics()
print(f"Total errors: {stats['total_errors']}")
print(f"Most common: {stats['most_common_error']}")
print(f"Error breakdown: {stats['error_counts']}")

# Error handler tracks metrics automatically
error_handler = ErrorHandler()
# ... errors occur during operations ...
stats = error_handler.get_error_statistics()
```

## Error Types Reference

### Validation Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `InvalidMessageError` | Message doesn't contain voice/audio | Yes | Verify message contains voice note |
| `InvalidPeerError` | Invalid peer/chat ID | Yes | Verify chat ID or username |
| `MessageValidationError` | General message validation failure | Yes | Check message requirements |

### Authentication Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `PermissionError` | Insufficient permissions | No | Check bot permissions in chat |
| `TranscriptionNotAvailableError` | Feature not available | No | Check availability requirements |

### Quota and Limit Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `TranscriptionQuotaExceededError` | Transcription quota exceeded | No | Upgrade to Premium or wait |
| `TranscriptionRateLimitError` | Rate limit hit | Yes | Wait and retry after specified time |
| `APIRateLimitError` | General API rate limit | Yes | Wait and retry |

### Network Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `TranscriptionTimeoutError` | Operation timed out | Yes | Retry with longer timeout |
| `NetworkError` | General network error | Yes | Retry with exponential backoff |
| `ConnectionError` | Connection failed | Yes | Check network and retry |

### API Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `TranscriptionRequestError` | Request failed | Yes | Retry the request |
| `TranscriptionProcessingError` | Processing failed | No | Check error details |

### Internal Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `StateManagementError` | State tracking error | No | Check logs for details |
| `ConfigurationError` | Configuration invalid | No | Fix configuration |

### Resource Errors

| Error | Description | Recoverable | Recovery Actions |
|-------|-------------|-------------|------------------|
| `TranscriptionMemoryError` | Memory exhausted | Yes | Clean up old transcriptions |
| `ConcurrencyLimitError` | Too many concurrent operations | Yes | Wait for capacity |

## Best Practices

### 1. Always Provide Context
```python
context = create_error_context(
    operation="transcribe_audio",
    component="MyBot",
    peer_id=chat_id,
    msg_id=message_id,
    user_data={"user_id": user_id}
)
```

### 2. Use Specific Error Types
```python
# Good - specific error with context
raise InvalidMessageError(
    "Voice messages not supported in this chat",
    context=context
)

# Avoid - generic error
raise Exception("Invalid message")
```

### 3. Handle Errors at Appropriate Levels
```python
# Low level - classify and add context
try:
    result = await api_call()
except Exception as e:
    raise TranscriptionRequestError(
        "API call failed",
        context=context,
        original_error=e
    )

# High level - handle user-facing errors
try:
    text = await client.transcribe_audio(chat, message)
except VoiceTranscriptionError as e:
    await bot.send_message(
        chat,
        format_error_for_user(e)
    )
```

### 4. Log Errors Appropriately
```python
# The framework automatically logs based on severity
# You can also access error details for custom logging
except VoiceTranscriptionError as e:
    error_data = e.to_dict()
    # Send to monitoring system
    monitoring.track_error(error_data)
```

### 5. Implement Recovery Strategies
```python
# For recoverable errors, implement retry logic
@retry_on_recoverable_errors(max_attempts=3)
async def reliable_transcribe(client, chat, message):
    return await client.transcribe_audio(chat, message)
```

## Integration with Telethon

The error handling framework is fully integrated with Telethon's transcription functionality:

1. **Automatic Classification** - Telethon errors are automatically classified into appropriate transcription error types
2. **Context Preservation** - Error context flows through the entire transcription pipeline
3. **Recovery Integration** - Recovery actions work with Telethon's async patterns
4. **Logging Integration** - Uses Telethon's logging infrastructure

## Advanced Usage

### Custom Error Types

You can extend the framework with custom error types:

```python
class MyCustomError(VoiceTranscriptionError):
    """Custom error for specific use case."""
    
    def __init__(self, custom_field: str, **kwargs):
        super().__init__(
            f"Custom error: {custom_field}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.API,
            **kwargs
        )
        self.custom_field = custom_field
```

### Custom Recovery Actions

```python
# Add custom recovery action
error.add_recovery_action(RecoveryAction(
    action_type="custom_recovery",
    description="Try alternative transcription method",
    automatic=True,
    parameters={"method": "fallback_api"}
))

# Implement custom recovery
async def custom_recovery_handler(error: VoiceTranscriptionError):
    for action in error.recovery_actions:
        if action.action_type == "custom_recovery":
            method = action.parameters.get("method")
            return await fallback_transcription(method)
```

### Error Aggregation

```python
# Aggregate errors for batch operations
errors = []
for message in messages:
    try:
        await client.transcribe_audio(chat, message)
    except VoiceTranscriptionError as e:
        errors.append(e)

# Analyze error patterns
error_types = Counter(type(e).__name__ for e in errors)
print(f"Error summary: {error_types}")
```

## Thread Safety

The error handling framework is thread-safe:
- Error handler uses async locks for metric updates
- Error IDs are unique across threads
- Context objects are immutable after creation
- Recovery actions are safely shareable

## Performance Considerations

- Error object creation is lightweight
- Context and recovery actions use efficient data structures
- Logging is asynchronous and non-blocking
- Metrics collection has minimal overhead
- Error classification is O(1) for most error types

## Migration Guide

If you're upgrading from basic exception handling:

```python
# Old approach
try:
    result = await transcribe()
except Exception as e:
    logger.error(f"Transcription failed: {e}")
    raise

# New approach
from telethon.client.voice_errors import handle_transcription_errors

@handle_transcription_errors("transcribe", "MyComponent")
async def transcribe():
    # Errors are automatically classified and logged
    pass
```

## Troubleshooting

### Common Issues

1. **Missing Context in Errors**
   - Always create context at operation start
   - Pass context through method calls
   - Use the decorator for automatic context extraction

2. **Unclassified Errors**
   - Check if error is in known Telethon errors
   - Add custom classification if needed
   - Internal errors are caught as fallback

3. **Recovery Not Working**
   - Check if error is marked as recoverable
   - Verify recovery action parameters
   - Ensure async recovery handlers are awaited

4. **High Error Rates**
   - Use error statistics to identify patterns
   - Check for systematic issues (permissions, configuration)
   - Implement appropriate retry strategies

## Implementation Status

### Completed Features ✅

- **Error Hierarchy**: Complete hierarchical exception system with 20+ specific error types
- **Error Classification**: Automatic classification of Telethon and Python exceptions
- **Recovery Actions**: Comprehensive recovery action system with automatic retry capabilities
- **Error Context**: Rich context preservation throughout the error pipeline
- **Error Handler**: Thread-safe error handler with metrics collection
- **Decorators**: Automatic error handling decorators for methods
- **Logging**: Severity-based logging with structured error data
- **User Messages**: User-friendly error formatting with recovery suggestions
- **Integration**: Full integration with TranscriptionMixin and Telethon patterns
- **Testing**: Comprehensive test suite with 748 lines of tests
- **Documentation**: Complete documentation with examples and best practices

### Error Types Implemented

1. **Base Error**: `VoiceTranscriptionError` - Root exception with common functionality
2. **Validation Errors**: `InvalidMessageError`, `InvalidPeerError`, `MessageValidationError`
3. **Authentication Errors**: `PermissionError`, `TranscriptionNotAvailableError`
4. **Quota Errors**: `TranscriptionQuotaExceededError`
5. **Rate Limit Errors**: `TranscriptionRateLimitError`, `APIRateLimitError`
6. **Network Errors**: `TranscriptionTimeoutError`, `ConnectionError`, `NetworkError`
7. **API Errors**: `TranscriptionRequestError`, `TranscriptionProcessingError`
8. **Internal Errors**: `StateManagementError`, `ConfigurationError`
9. **Resource Errors**: `TranscriptionMemoryError`, `ConcurrencyLimitError`

### Key Features

- **Automatic Error Classification**: Telethon exceptions automatically mapped to appropriate types
- **Context Extraction**: Decorator extracts context from method parameters
- **Recovery Automation**: Automatic retry with configurable strategies
- **Metrics Collection**: Error counts and statistics tracking
- **Thread Safety**: Async locks for concurrent error handling
- **Extensibility**: Easy to add new error types and recovery actions

## Future Enhancements

Potential improvements for future versions:

1. **Enhanced Recovery Strategies**
   - Circuit breaker pattern for repeated failures
   - Adaptive retry delays based on error patterns
   - Recovery action prioritization

2. **Advanced Metrics**
   - Error rate trending
   - Recovery success rates
   - Performance impact analysis

3. **Error Aggregation**
   - Error grouping for batch operations
   - Summary reports for multiple errors
   - Error correlation analysis

4. **Integration Improvements**
   - Webhook support for error notifications
   - Integration with monitoring systems
   - Custom error handlers for specific use cases