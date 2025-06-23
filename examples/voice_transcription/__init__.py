"""
Voice Transcription Basic Request Implementation

This package provides a high-level interface for voice message transcription
using Telethon's TL (Type Language) API classes.

Main Components:
- BasicVoiceTranscriber: Main transcription interface
- VoiceMessageValidator: Request validation system  
- ResponseParser: Response and update parsing
- Error handling and user-friendly messages

Example Usage:
    from voice_transcription import BasicVoiceTranscriber
    
    transcriber = BasicVoiceTranscriber(client)
    request = await transcriber.transcribe(chat='me', msg_id=12345)
    
    if request.completed:
        print(f"Transcription: {request.result.text}")
"""

from .basic_request import (
    BasicVoiceTranscriber,
    TranscriptionRequest, 
    VoiceTranscriptionError,
    InvalidMessageError,
    TranscriptionRateLimitError
)

from .validation import (
    VoiceMessageValidator,
    ValidationError,
    MessageValidationError,
    PermissionValidationError,
    RateLimitValidationError,
    ErrorHandler
)

from .response_parser import (
    ResponseParser,
    TranscriptionResult,
    TranscriptionUpdate,
    TextProcessor
)

from .update_handler import (
    VoiceTranscriptionUpdateHandler,
    UpdateEvent,
    UpdateValidator,
    UpdateProcessor,
    HandlerRegistration,
    create_completion_filter,
    create_peer_filter,
    create_transcription_filter
)

from .integration import (
    TranscriptionCoordinator,
    IntegratedVoiceTranscriber
)

from .state_manager import (
    TranscriptionState,
    TranscriptionStatus,
    StateStorage,
    TranscriptionStateManager
)

from .transcription_manager import (
    TranscriptionManager,
    TranscriptionManagerConfig,
    TranscriptionResult
)

from .automatic_cleanup import (
    AutomaticCleanupSystem,
    CleanupConfig,
    CleanupStrategy,
    CleanupTrigger,
    CleanupMetrics
)

from .error_handling import (
    # Base classes
    VoiceTranscriptionError, ErrorContext, RecoveryAction,
    ErrorSeverity, ErrorCategory, ErrorHandler,
    
    # Validation errors
    ValidationError, InvalidMessageError, InvalidPeerError, MessageValidationError,
    
    # Authentication errors  
    AuthenticationError, PermissionError, TranscriptionNotAvailableError,
    
    # Rate limiting errors
    RateLimitError, TranscriptionRateLimitError, APIRateLimitError,
    
    # Network errors
    NetworkError, TimeoutError, ConnectionError,
    
    # API errors
    APIError, TranscriptionRequestError, TranscriptionProcessingError,
    
    # Internal errors
    InternalError, StateManagementError, ConfigurationError,
    
    # Resource errors
    ResourceError, MemoryError, ConcurrencyLimitError,
    
    # Utilities
    create_error_context, format_error_for_user, is_recoverable_error,
    get_automatic_recovery_actions, handle_transcription_errors
)

__version__ = "1.0.0"
__author__ = "Telethon Voice Transcription Team"

__all__ = [
    # Main classes
    "BasicVoiceTranscriber",
    "VoiceMessageValidator", 
    "ResponseParser",
    "VoiceTranscriptionUpdateHandler",
    "IntegratedVoiceTranscriber",
    "TranscriptionStateManager",
    "TranscriptionManager",
    "AutomaticCleanupSystem",
    "ErrorHandler",
    
    # Data classes
    "TranscriptionRequest",
    "TranscriptionResult",
    "TranscriptionUpdate",
    "UpdateEvent",
    "HandlerRegistration",
    "TranscriptionState",
    "TranscriptionStatus",
    "TranscriptionManagerConfig",
    "CleanupConfig",
    "CleanupStrategy",
    "CleanupTrigger",
    "CleanupMetrics",
    "ErrorContext",
    "RecoveryAction",
    "ErrorSeverity",
    "ErrorCategory",
    
    # Integration classes
    "TranscriptionCoordinator",
    "UpdateValidator",
    "UpdateProcessor",
    "StateStorage",
    
    # Utilities
    "TextProcessor",
    "create_completion_filter",
    "create_peer_filter", 
    "create_transcription_filter",
    "create_error_context",
    "format_error_for_user",
    "is_recoverable_error",
    "get_automatic_recovery_actions",
    "handle_transcription_errors",
    
    # Exceptions - Base
    "VoiceTranscriptionError",
    
    # Exceptions - Validation
    "ValidationError",
    "InvalidMessageError",
    "InvalidPeerError", 
    "MessageValidationError",
    
    # Exceptions - Authentication
    "AuthenticationError",
    "PermissionError",
    "TranscriptionNotAvailableError",
    
    # Exceptions - Rate Limiting
    "RateLimitError",
    "TranscriptionRateLimitError",
    "APIRateLimitError",
    
    # Exceptions - Network
    "NetworkError",
    "TimeoutError",
    "ConnectionError",
    
    # Exceptions - API
    "APIError",
    "TranscriptionRequestError",
    "TranscriptionProcessingError",
    
    # Exceptions - Internal
    "InternalError",
    "StateManagementError",
    "ConfigurationError",
    
    # Exceptions - Resource
    "ResourceError",
    "MemoryError",
    "ConcurrencyLimitError"
]