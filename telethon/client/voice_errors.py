"""
Voice Transcription Error Handling Framework

This module implements Epic 1 User Story 1.7: Error Handling Framework
providing comprehensive error handling with custom exceptions, clear error messages,
error recovery mechanisms, and detailed logging for voice transcription operations.

Features:
- Hierarchical exception system with specific error types
- Context-aware error messages with actionable information
- Error classification and severity levels
- Recovery suggestions and retry mechanisms
- Comprehensive error logging and monitoring
- Error aggregation and reporting
"""

import logging
import traceback
import functools
import asyncio
from typing import Dict, List, Optional, Any, Callable, Union, Type
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import sys
import inspect

from ..errors import RPCError, AuthKeyError, FloodWaitError
from ..errors.rpcerrorlist import (
    MessageNotModifiedError, MessageEmptyError, 
    PeerIdInvalidError, ChatAdminRequiredError,
    AudioContentUrlEmptyError, VoiceMessagesNotAllowedError
)


logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"              # Minor issues, operation can continue
    MEDIUM = "medium"        # Significant issues, may need attention
    HIGH = "high"            # Major issues, operation likely failed
    CRITICAL = "critical"    # Critical failures, system integrity at risk


class ErrorCategory(Enum):
    """Error categories for classification"""
    VALIDATION = "validation"          # Input validation errors
    AUTHENTICATION = "authentication"  # Auth/permission errors
    NETWORK = "network"                # Network/connection errors
    API = "api"                        # Telegram API errors
    RATE_LIMIT = "rate_limit"          # Rate limiting errors
    TIMEOUT = "timeout"                # Timeout errors
    INTERNAL = "internal"              # Internal system errors
    CONFIGURATION = "configuration"    # Configuration errors
    RESOURCE = "resource"              # Resource exhaustion errors
    QUOTA = "quota"                    # Quota/limit errors


@dataclass
class ErrorContext:
    """Context information for errors"""
    operation: str                           # Operation being performed
    component: str                           # Component where error occurred
    peer_id: Optional[int] = None           # Peer ID if applicable
    msg_id: Optional[int] = None            # Message ID if applicable
    transcription_id: Optional[int] = None  # Transcription ID if applicable
    user_data: Dict[str, Any] = field(default_factory=dict)  # Additional context
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'operation': self.operation,
            'component': self.component,
            'peer_id': self.peer_id,
            'msg_id': self.msg_id,
            'transcription_id': self.transcription_id,
            'user_data': self.user_data,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RecoveryAction:
    """Suggested recovery action for an error"""
    action_type: str                    # Type of recovery action
    description: str                    # Human-readable description
    automatic: bool = False             # Whether action can be automated
    parameters: Dict[str, Any] = field(default_factory=dict)  # Action parameters
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'action_type': self.action_type,
            'description': self.description,
            'automatic': self.automatic,
            'parameters': self.parameters
        }


# Base Exception Classes

class VoiceTranscriptionError(Exception):
    """
    Base exception for all voice transcription errors.
    
    This is the root exception class that all other transcription-related
    exceptions inherit from. It provides common functionality for error
    handling, logging, and recovery suggestions.
    """
    
    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        recoverable: bool = False,
        recovery_actions: Optional[List[RecoveryAction]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext(operation="unknown", component="unknown")
        self.severity = severity
        self.category = category
        self.recoverable = recoverable
        self.recovery_actions = recovery_actions or []
        self.original_error = original_error
        self.error_id = self._generate_error_id()
        
    def _generate_error_id(self) -> str:
        """Generate unique error ID for tracking"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        component = self.context.component[:8] if self.context else "unknown"
        return f"{component}_{timestamp}_{id(self) % 10000:04d}"
        
    def add_recovery_action(self, action: RecoveryAction):
        """Add a recovery action suggestion"""
        self.recovery_actions.append(action)
        
    def get_detailed_message(self) -> str:
        """Get detailed error message with context"""
        details = [self.message]
        
        if self.context:
            if self.context.peer_id:
                details.append(f"Peer: {self.context.peer_id}")
            if self.context.msg_id:
                details.append(f"Message: {self.context.msg_id}")
            if self.context.transcription_id:
                details.append(f"Transcription: {self.context.transcription_id}")
                
        if self.original_error:
            details.append(f"Caused by: {type(self.original_error).__name__}: {self.original_error}")
            
        return " | ".join(details)
        
    def get_user_friendly_message(self) -> str:
        """Get user-friendly error message"""
        return self.message
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization"""
        return {
            'error_id': self.error_id,
            'error_type': type(self).__name__,
            'message': self.message,
            'severity': self.severity.value,
            'category': self.category.value,
            'recoverable': self.recoverable,
            'context': self.context.to_dict() if self.context else None,
            'recovery_actions': [action.to_dict() for action in self.recovery_actions],
            'original_error': str(self.original_error) if self.original_error else None,
            'traceback': traceback.format_exc() if self.original_error else None
        }


# Validation Errors

class ValidationError(VoiceTranscriptionError):
    """Base class for validation errors"""
    
    def __init__(self, message: str, field_name: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            recoverable=True,
            **kwargs
        )
        self.field_name = field_name
        
    def get_user_friendly_message(self) -> str:
        if self.field_name:
            return f"Invalid {self.field_name}: {self.message}"
        return f"Validation error: {self.message}"


class InvalidMessageError(ValidationError):
    """Error when message is invalid for transcription"""
    
    def __init__(self, message: str = "Message is not valid for transcription", **kwargs):
        super().__init__(message, field_name="message", **kwargs)
        self.add_recovery_action(RecoveryAction(
            action_type="verify_message",
            description="Verify that the message contains a voice note or audio file",
            automatic=False
        ))


class InvalidPeerError(ValidationError):
    """Error when peer is invalid"""
    
    def __init__(self, peer_id: Any, **kwargs):
        message = f"Invalid peer ID: {peer_id}"
        super().__init__(message, field_name="peer", **kwargs)
        self.peer_id = peer_id
        self.add_recovery_action(RecoveryAction(
            action_type="resolve_peer",
            description="Verify the chat ID or username is correct",
            automatic=False
        ))


class MessageValidationError(ValidationError):
    """Error in message validation"""
    
    def __init__(self, message: str, validation_type: str = "general", **kwargs):
        super().__init__(message, **kwargs)
        self.validation_type = validation_type


# Authentication and Permission Errors

class AuthenticationError(VoiceTranscriptionError):
    """Base class for authentication errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTHENTICATION,
            recoverable=False,
            **kwargs
        )


class PermissionError(AuthenticationError):
    """Error when user lacks required permissions"""
    
    def __init__(self, operation: str, **kwargs):
        message = f"Insufficient permissions for operation: {operation}"
        super().__init__(message, **kwargs)
        self.operation = operation
        self.add_recovery_action(RecoveryAction(
            action_type="check_permissions",
            description="Verify bot has necessary permissions in the chat",
            automatic=False
        ))


class TranscriptionNotAvailableError(VoiceTranscriptionError):
    """Error when transcription is not available"""
    
    def __init__(self, reason: str = "Transcription not available", **kwargs):
        super().__init__(
            f"Transcription not available: {reason}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.API,
            recoverable=False,
            **kwargs
        )
        self.reason = reason


# Quota and Limit Errors

class QuotaError(VoiceTranscriptionError):
    """Base class for quota-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.QUOTA,
            recoverable=False,
            **kwargs
        )


class TranscriptionQuotaExceededError(QuotaError):
    """Error when transcription quota is exceeded"""
    
    def __init__(self, 
                 trial_remains: Optional[int] = None,
                 trial_expires: Optional[datetime] = None,
                 **kwargs):
        message = "Voice transcription quota exceeded"
        if trial_remains is not None:
            message += f" ({trial_remains} trials remaining)"
        if trial_expires:
            message += f", expires at {trial_expires}"
            
        super().__init__(message, **kwargs)
        self.trial_remains = trial_remains
        self.trial_expires = trial_expires
        
        self.add_recovery_action(RecoveryAction(
            action_type="check_premium",
            description="Consider upgrading to Telegram Premium for unlimited transcriptions",
            automatic=False
        ))


# Rate Limiting Errors

class RateLimitError(VoiceTranscriptionError):
    """Base class for rate limiting errors"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.RATE_LIMIT,
            recoverable=True,
            **kwargs
        )
        self.retry_after = retry_after
        
        if retry_after:
            self.add_recovery_action(RecoveryAction(
                action_type="wait_and_retry",
                description=f"Wait {retry_after} seconds before retrying",
                automatic=True,
                parameters={'retry_after': retry_after}
            ))


class TranscriptionRateLimitError(RateLimitError):
    """Error when transcription rate limit is exceeded"""
    
    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        message = "Transcription rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message, retry_after=retry_after, **kwargs)


class APIRateLimitError(RateLimitError):
    """Error when API rate limit is exceeded"""
    
    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        message = "API rate limit exceeded"
        super().__init__(message, retry_after=retry_after, **kwargs)


# Network and Timeout Errors

class NetworkError(VoiceTranscriptionError):
    """Base class for network-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK,
            recoverable=True,
            **kwargs
        )
        self.add_recovery_action(RecoveryAction(
            action_type="retry_request",
            description="Retry the request after a short delay",
            automatic=True,
            parameters={'max_retries': 3, 'delay': 5}
        ))


class TranscriptionTimeoutError(NetworkError):
    """Error when transcription operation times out"""
    
    def __init__(self, operation: str, timeout_seconds: float, **kwargs):
        message = f"Transcription '{operation}' timed out after {timeout_seconds} seconds"
        super().__init__(message, **kwargs)
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        self.category = ErrorCategory.TIMEOUT


class ConnectionError(NetworkError):
    """Error when connection fails"""
    
    def __init__(self, message: str = "Connection failed", **kwargs):
        super().__init__(message, **kwargs)


# API-specific Errors

class APIError(VoiceTranscriptionError):
    """Base class for API errors"""
    
    def __init__(self, message: str, api_error_code: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API,
            **kwargs
        )
        self.api_error_code = api_error_code


class TranscriptionRequestError(APIError):
    """Error in transcription request"""
    
    def __init__(self, message: str = "Transcription request failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)
        self.add_recovery_action(RecoveryAction(
            action_type="retry_request",
            description="Retry the transcription request",
            automatic=True
        ))


class TranscriptionProcessingError(APIError):
    """Error during transcription processing"""
    
    def __init__(self, transcription_id: Optional[int] = None, **kwargs):
        message = "Transcription processing failed"
        if transcription_id:
            message += f" for transcription {transcription_id}"
        super().__init__(message, recoverable=False, **kwargs)
        self.transcription_id = transcription_id


# Internal System Errors

class InternalError(VoiceTranscriptionError):
    """Base class for internal system errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.INTERNAL,
            recoverable=False,
            **kwargs
        )


class StateManagementError(InternalError):
    """Error in state management operations"""
    
    def __init__(self, operation: str, state_key: Optional[str] = None, **kwargs):
        message = f"State management error in operation: {operation}"
        if state_key:
            message += f" for state: {state_key}"
        super().__init__(message, **kwargs)
        self.operation = operation
        self.state_key = state_key


class ConfigurationError(InternalError):
    """Error in system configuration"""
    
    def __init__(self, config_name: str, message: str, **kwargs):
        full_message = f"Configuration error in {config_name}: {message}"
        super().__init__(full_message, category=ErrorCategory.CONFIGURATION, **kwargs)
        self.config_name = config_name


# Resource Errors

class ResourceError(VoiceTranscriptionError):
    """Base class for resource-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.RESOURCE,
            recoverable=True,
            **kwargs
        )


class TranscriptionMemoryError(ResourceError):
    """Error when memory resources are exhausted"""
    
    def __init__(self, current_usage: Optional[float] = None, **kwargs):
        message = "Memory resources exhausted for transcriptions"
        if current_usage:
            message += f" (current usage: {current_usage:.1f}MB)"
        super().__init__(message, **kwargs)
        self.current_usage = current_usage
        
        self.add_recovery_action(RecoveryAction(
            action_type="cleanup_resources",
            description="Clean up old transcription states to free memory",
            automatic=True
        ))


class ConcurrencyLimitError(ResourceError):
    """Error when concurrency limits are exceeded"""
    
    def __init__(self, current_count: int, max_count: int, **kwargs):
        message = f"Transcription concurrency limit exceeded: {current_count}/{max_count}"
        super().__init__(message, **kwargs)
        self.current_count = current_count
        self.max_count = max_count
        
        self.add_recovery_action(RecoveryAction(
            action_type="wait_for_capacity",
            description="Wait for active transcriptions to complete",
            automatic=True
        ))


# Error Handler and Utilities

class ErrorHandler:
    """
    Central error handler for voice transcription operations.
    
    Provides error classification, logging, recovery suggestions,
    and metrics collection for all transcription-related errors.
    """
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
        self.error_counts: Dict[str, int] = {}
        self.recovery_attempts: Dict[str, int] = {}
        self._lock = asyncio.Lock()
        
    async def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        reraise: bool = True
    ) -> VoiceTranscriptionError:
        """
        Handle and classify an error.
        
        Args:
            error: The original error
            context: Error context information
            reraise: Whether to reraise the error
            
        Returns:
            Classified VoiceTranscriptionError
        """
        async with self._lock:
            # Classify error
            classified_error = self._classify_error(error, context)
            
            # Log error
            self._log_error(classified_error)
            
            # Update metrics
            self._update_metrics(classified_error)
        
        # Reraise if requested
        if reraise:
            raise classified_error
            
        return classified_error
        
    def _classify_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None
    ) -> VoiceTranscriptionError:
        """Classify an error into appropriate transcription error type"""
        
        # If already a transcription error, return as-is
        if isinstance(error, VoiceTranscriptionError):
            if context and not error.context:
                error.context = context
            return error
            
        # Classify Telethon-specific errors
        if isinstance(error, FloodWaitError):
            return TranscriptionRateLimitError(
                retry_after=getattr(error, 'seconds', None),
                context=context,
                original_error=error
            )
            
        if isinstance(error, PeerIdInvalidError):
            return InvalidPeerError(
                peer_id=getattr(context, 'peer_id', None) if context else None,
                context=context,
                original_error=error
            )
            
        if isinstance(error, ChatAdminRequiredError):
            return PermissionError(
                operation=getattr(context, 'operation', 'unknown') if context else 'unknown',
                context=context,
                original_error=error
            )
            
        if isinstance(error, AuthKeyError):
            return AuthenticationError(
                "Authentication failed",
                context=context,
                original_error=error
            )
            
        if isinstance(error, (AudioContentUrlEmptyError, VoiceMessagesNotAllowedError)):
            return TranscriptionNotAvailableError(
                reason=str(error),
                context=context,
                original_error=error
            )
            
        if isinstance(error, RPCError):
            return APIError(
                f"API error: {error}",
                api_error_code=getattr(error, 'code', None),
                context=context,
                original_error=error
            )
            
        # Standard Python errors
        if isinstance(error, asyncio.TimeoutError):
            return TranscriptionTimeoutError(
                operation=getattr(context, 'operation', 'unknown') if context else 'unknown',
                timeout_seconds=30.0,  # Default timeout
                context=context,
                original_error=error
            )
            
        if isinstance(error, ConnectionError):
            return NetworkError(
                f"Network error: {error}",
                context=context,
                original_error=error
            )
            
        if isinstance(error, MemoryError):
            return TranscriptionMemoryError(
                context=context,
                original_error=error
            )
            
        if isinstance(error, ValueError):
            return ValidationError(
                f"Validation error: {error}",
                context=context,
                original_error=error
            )
            
        # Generic internal error for unclassified errors
        return InternalError(
            f"Unclassified error: {type(error).__name__}: {error}",
            context=context,
            original_error=error
        )
        
    def _log_error(self, error: VoiceTranscriptionError):
        """Log error with appropriate level and detail"""
        
        error_dict = error.to_dict()
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(
                f"CRITICAL ERROR [{error.error_id}]: {error.get_detailed_message()}",
                extra={'error_data': error_dict}
            )
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(
                f"ERROR [{error.error_id}]: {error.get_detailed_message()}",
                extra={'error_data': error_dict}
            )
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(
                f"WARNING [{error.error_id}]: {error.get_detailed_message()}",
                extra={'error_data': error_dict}
            )
        else:  # LOW
            self.logger.info(
                f"INFO [{error.error_id}]: {error.get_detailed_message()}",
                extra={'error_data': error_dict}
            )
            
        # Log recovery actions if available
        if error.recovery_actions:
            recovery_msgs = [action.description for action in error.recovery_actions]
            self.logger.info(f"Recovery suggestions for [{error.error_id}]: {'; '.join(recovery_msgs)}")
            
    def _update_metrics(self, error: VoiceTranscriptionError):
        """Update error metrics"""
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_counts': dict(self.error_counts),
            'most_common_error': max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None,
            'recovery_attempts': dict(self.recovery_attempts)
        }


# Decorators for Error Handling

def handle_transcription_errors(
    context_operation: str,
    context_component: str,
    reraise: bool = True,
    default_return: Any = None
):
    """
    Decorator to automatically handle transcription errors.
    
    Args:
        context_operation: Operation name for context
        context_component: Component name for context
        reraise: Whether to reraise classified errors
        default_return: Default return value if error is not reraised
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            handler = ErrorHandler()
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(
                    operation=context_operation,
                    component=context_component
                )
                
                # Extract context from function arguments if possible
                if args and hasattr(args[0], '__class__'):
                    # Try to extract peer_id, msg_id from method arguments
                    sig = inspect.signature(func)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    
                    if 'peer_id' in bound_args.arguments:
                        context.peer_id = bound_args.arguments['peer_id']
                    if 'msg_id' in bound_args.arguments:
                        context.msg_id = bound_args.arguments['msg_id']
                    if 'entity' in bound_args.arguments:
                        # Try to extract peer_id from entity
                        entity = bound_args.arguments['entity']
                        if isinstance(entity, int):
                            context.peer_id = entity
                            
                classified_error = await handler.handle_error(e, context, reraise=False)
                
                if reraise:
                    raise classified_error
                else:
                    return default_return
                    
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            handler = ErrorHandler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(
                    operation=context_operation,
                    component=context_component
                )
                # Note: sync version doesn't support async handle_error
                classified_error = handler._classify_error(e, context)
                handler._log_error(classified_error)
                handler._update_metrics(classified_error)
                
                if reraise:
                    raise classified_error
                else:
                    return default_return
                    
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Utility Functions

def create_error_context(
    operation: str,
    component: str,
    **kwargs
) -> ErrorContext:
    """Create error context with common fields"""
    return ErrorContext(
        operation=operation,
        component=component,
        **kwargs
    )


def format_error_for_user(error: VoiceTranscriptionError) -> str:
    """Format error message for end users"""
    message = error.get_user_friendly_message()
    
    if error.recovery_actions:
        suggestions = [action.description for action in error.recovery_actions if not action.automatic]
        if suggestions:
            message += f"\n\nSuggestions: {'; '.join(suggestions)}"
            
    return message


def is_recoverable_error(error: Exception) -> bool:
    """Check if an error is recoverable"""
    if isinstance(error, VoiceTranscriptionError):
        return error.recoverable
    return False


def get_automatic_recovery_actions(error: VoiceTranscriptionError) -> List[RecoveryAction]:
    """Get automatic recovery actions for an error"""
    return [action for action in error.recovery_actions if action.automatic]


async def attempt_recovery(error: VoiceTranscriptionError, retry_func: Callable) -> Any:
    """Attempt automatic recovery for an error"""
    if not error.recoverable:
        raise error
        
    auto_actions = get_automatic_recovery_actions(error)
    if not auto_actions:
        raise error
        
    for action in auto_actions:
        if action.action_type == "wait_and_retry":
            retry_after = action.parameters.get('retry_after', 5)
            await asyncio.sleep(retry_after)
            return await retry_func()
        elif action.action_type == "retry_request":
            max_retries = action.parameters.get('max_retries', 3)
            delay = action.parameters.get('delay', 5)
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        await asyncio.sleep(delay)
                    return await retry_func()
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Recovery attempt {attempt + 1}/{max_retries} failed: {e}")
                    
    raise error