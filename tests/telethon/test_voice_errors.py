"""
Tests for voice transcription error handling framework.

This test suite covers the error handling framework implementation
including custom exceptions, error classification, recovery actions,
and error logging functionality.
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from telethon.client.voice_errors import (
    # Base classes
    VoiceTranscriptionError,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    RecoveryAction,
    ErrorHandler,
    
    # Validation errors
    ValidationError,
    InvalidMessageError,
    InvalidPeerError,
    MessageValidationError,
    
    # Authentication errors
    AuthenticationError,
    PermissionError,
    TranscriptionNotAvailableError,
    
    # Quota errors
    QuotaError,
    TranscriptionQuotaExceededError,
    
    # Rate limit errors
    RateLimitError,
    TranscriptionRateLimitError,
    APIRateLimitError,
    
    # Network errors
    NetworkError,
    TranscriptionTimeoutError,
    ConnectionError,
    
    # API errors
    APIError,
    TranscriptionRequestError,
    TranscriptionProcessingError,
    
    # Internal errors
    InternalError,
    StateManagementError,
    ConfigurationError,
    
    # Resource errors
    ResourceError,
    TranscriptionMemoryError,
    ConcurrencyLimitError,
    
    # Utility functions
    create_error_context,
    format_error_for_user,
    is_recoverable_error,
    get_automatic_recovery_actions,
    handle_transcription_errors,
    attempt_recovery
)

from telethon.errors import (
    RPCError, AuthKeyError, FloodWaitError,
    PeerIdInvalidError, ChatAdminRequiredError
)


class TestErrorContext:
    """Test ErrorContext functionality."""
    
    def test_error_context_creation(self):
        """Test creating error context."""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            peer_id=123456,
            msg_id=789,
            transcription_id=456
        )
        
        assert context.operation == "test_operation"
        assert context.component == "test_component"
        assert context.peer_id == 123456
        assert context.msg_id == 789
        assert context.transcription_id == 456
        assert isinstance(context.timestamp, datetime)
        assert context.user_data == {}
    
    def test_error_context_to_dict(self):
        """Test converting error context to dictionary."""
        context = ErrorContext(
            operation="transcribe",
            component="mixin",
            peer_id=123,
            user_data={"key": "value"}
        )
        
        data = context.to_dict()
        
        assert data['operation'] == "transcribe"
        assert data['component'] == "mixin"
        assert data['peer_id'] == 123
        assert data['user_data'] == {"key": "value"}
        assert 'timestamp' in data


class TestRecoveryAction:
    """Test RecoveryAction functionality."""
    
    def test_recovery_action_creation(self):
        """Test creating recovery action."""
        action = RecoveryAction(
            action_type="retry",
            description="Retry the operation",
            automatic=True,
            parameters={"max_retries": 3}
        )
        
        assert action.action_type == "retry"
        assert action.description == "Retry the operation"
        assert action.automatic is True
        assert action.parameters == {"max_retries": 3}
    
    def test_recovery_action_to_dict(self):
        """Test converting recovery action to dictionary."""
        action = RecoveryAction(
            action_type="wait_and_retry",
            description="Wait 5 seconds",
            automatic=True,
            parameters={"delay": 5}
        )
        
        data = action.to_dict()
        
        assert data['action_type'] == "wait_and_retry"
        assert data['description'] == "Wait 5 seconds"
        assert data['automatic'] is True
        assert data['parameters'] == {"delay": 5}


class TestBaseErrorClass:
    """Test VoiceTranscriptionError base functionality."""
    
    def test_base_error_creation(self):
        """Test creating base error."""
        error = VoiceTranscriptionError(
            message="Test error",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API,
            recoverable=True
        )
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.HIGH
        assert error.category == ErrorCategory.API
        assert error.recoverable is True
        assert error.recovery_actions == []
        assert error.original_error is None
        assert error.error_id is not None
    
    def test_error_id_generation(self):
        """Test unique error ID generation."""
        error1 = VoiceTranscriptionError("Error 1")
        error2 = VoiceTranscriptionError("Error 2")
        
        assert error1.error_id != error2.error_id
        assert len(error1.error_id) > 10
        assert "_" in error1.error_id
    
    def test_add_recovery_action(self):
        """Test adding recovery actions."""
        error = VoiceTranscriptionError("Test error")
        action = RecoveryAction("retry", "Retry operation")
        
        error.add_recovery_action(action)
        
        assert len(error.recovery_actions) == 1
        assert error.recovery_actions[0] == action
    
    def test_detailed_message(self):
        """Test detailed error message generation."""
        context = ErrorContext(
            operation="test",
            component="comp",
            peer_id=123,
            msg_id=456,
            transcription_id=789
        )
        
        original = ValueError("Original error")
        
        error = VoiceTranscriptionError(
            message="Test error",
            context=context,
            original_error=original
        )
        
        detailed = error.get_detailed_message()
        
        assert "Test error" in detailed
        assert "Peer: 123" in detailed
        assert "Message: 456" in detailed
        assert "Transcription: 789" in detailed
        assert "ValueError: Original error" in detailed
    
    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        context = ErrorContext("op", "comp")
        action = RecoveryAction("retry", "Retry")
        
        error = VoiceTranscriptionError(
            message="Test",
            context=context,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            recoverable=True
        )
        error.add_recovery_action(action)
        
        data = error.to_dict()
        
        assert data['error_id'] == error.error_id
        assert data['error_type'] == "VoiceTranscriptionError"
        assert data['message'] == "Test"
        assert data['severity'] == "medium"
        assert data['category'] == "network"
        assert data['recoverable'] is True
        assert data['context'] is not None
        assert len(data['recovery_actions']) == 1


class TestValidationErrors:
    """Test validation error classes."""
    
    def test_invalid_message_error(self):
        """Test InvalidMessageError."""
        error = InvalidMessageError()
        
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.recoverable is True
        assert error.field_name == "message"
        assert len(error.recovery_actions) == 1
        assert error.recovery_actions[0].action_type == "verify_message"
    
    def test_invalid_peer_error(self):
        """Test InvalidPeerError."""
        error = InvalidPeerError(peer_id="invalid_peer")
        
        assert "Invalid peer ID: invalid_peer" in str(error)
        assert error.peer_id == "invalid_peer"
        assert error.field_name == "peer"
        assert len(error.recovery_actions) == 1
        assert error.recovery_actions[0].action_type == "resolve_peer"
    
    def test_validation_error_user_message(self):
        """Test user-friendly message for validation errors."""
        error = ValidationError("Invalid value", field_name="audio")
        
        msg = error.get_user_friendly_message()
        assert msg == "Invalid audio: Invalid value"
        
        error2 = ValidationError("Bad input")
        msg2 = error2.get_user_friendly_message()
        assert msg2 == "Validation error: Bad input"


class TestAuthenticationErrors:
    """Test authentication and permission errors."""
    
    def test_permission_error(self):
        """Test PermissionError."""
        error = PermissionError(operation="transcribe_audio")
        
        assert "Insufficient permissions for operation: transcribe_audio" in str(error)
        assert error.operation == "transcribe_audio"
        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH
        assert not error.recoverable
        assert len(error.recovery_actions) == 1
    
    def test_transcription_not_available_error(self):
        """Test TranscriptionNotAvailableError."""
        error = TranscriptionNotAvailableError(reason="Premium only")
        
        assert "Transcription not available: Premium only" in str(error)
        assert error.reason == "Premium only"
        assert error.category == ErrorCategory.API
        assert not error.recoverable


class TestQuotaErrors:
    """Test quota-related errors."""
    
    def test_transcription_quota_exceeded(self):
        """Test TranscriptionQuotaExceededError."""
        expires = datetime.now(timezone.utc) + timedelta(days=1)
        
        error = TranscriptionQuotaExceededError(
            trial_remains=5,
            trial_expires=expires
        )
        
        assert "Voice transcription quota exceeded" in str(error)
        assert "(5 trials remaining)" in str(error)
        assert error.trial_remains == 5
        assert error.trial_expires == expires
        assert error.category == ErrorCategory.QUOTA
        assert not error.recoverable
        assert len(error.recovery_actions) == 1
        assert "Premium" in error.recovery_actions[0].description


class TestRateLimitErrors:
    """Test rate limiting errors."""
    
    def test_transcription_rate_limit_error(self):
        """Test TranscriptionRateLimitError."""
        error = TranscriptionRateLimitError(retry_after=60)
        
        assert "Transcription rate limit exceeded" in str(error)
        assert "retry after 60 seconds" in str(error)
        assert error.retry_after == 60
        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.recoverable is True
        assert len(error.recovery_actions) == 1
        
        action = error.recovery_actions[0]
        assert action.action_type == "wait_and_retry"
        assert action.automatic is True
        assert action.parameters['retry_after'] == 60
    
    def test_api_rate_limit_error(self):
        """Test APIRateLimitError."""
        error = APIRateLimitError()
        
        assert "API rate limit exceeded" in str(error)
        assert error.retry_after is None
        assert error.recoverable is True


class TestNetworkErrors:
    """Test network and timeout errors."""
    
    def test_transcription_timeout_error(self):
        """Test TranscriptionTimeoutError."""
        error = TranscriptionTimeoutError(
            operation="wait_for_result",
            timeout_seconds=30.0
        )
        
        assert "Transcription 'wait_for_result' timed out after 30.0 seconds" in str(error)
        assert error.operation == "wait_for_result"
        assert error.timeout_seconds == 30.0
        assert error.category == ErrorCategory.TIMEOUT
        assert error.recoverable is True
        assert len(error.recovery_actions) == 1
    
    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Network unreachable")
        
        assert str(error) == "Network unreachable"
        assert error.category == ErrorCategory.NETWORK
        assert error.recoverable is True
        assert len(error.recovery_actions) == 1
        
        action = error.recovery_actions[0]
        assert action.action_type == "retry_request"
        assert action.parameters['max_retries'] == 3


class TestAPIErrors:
    """Test API-specific errors."""
    
    def test_transcription_request_error(self):
        """Test TranscriptionRequestError."""
        error = TranscriptionRequestError("API call failed")
        
        assert str(error) == "API call failed"
        assert error.category == ErrorCategory.API
        assert error.recoverable is True
        assert len(error.recovery_actions) == 1
        assert error.recovery_actions[0].action_type == "retry_request"
    
    def test_transcription_processing_error(self):
        """Test TranscriptionProcessingError."""
        error = TranscriptionProcessingError(transcription_id=12345)
        
        assert "Transcription processing failed for transcription 12345" in str(error)
        assert error.transcription_id == 12345
        assert not error.recoverable


class TestInternalErrors:
    """Test internal system errors."""
    
    def test_state_management_error(self):
        """Test StateManagementError."""
        error = StateManagementError(
            operation="update_state",
            state_key="123:456"
        )
        
        assert "State management error in operation: update_state" in str(error)
        assert "for state: 123:456" in str(error)
        assert error.operation == "update_state"
        assert error.state_key == "123:456"
        assert error.category == ErrorCategory.INTERNAL
        assert error.severity == ErrorSeverity.CRITICAL
        assert not error.recoverable
    
    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError(
            config_name="cleanup_config",
            message="Invalid TTL value"
        )
        
        assert "Configuration error in cleanup_config: Invalid TTL value" in str(error)
        assert error.config_name == "cleanup_config"
        assert error.category == ErrorCategory.CONFIGURATION


class TestResourceErrors:
    """Test resource-related errors."""
    
    def test_transcription_memory_error(self):
        """Test TranscriptionMemoryError."""
        error = TranscriptionMemoryError(current_usage=150.5)
        
        assert "Memory resources exhausted for transcriptions" in str(error)
        assert "(current usage: 150.5MB)" in str(error)
        assert error.current_usage == 150.5
        assert error.category == ErrorCategory.RESOURCE
        assert error.recoverable is True
        assert len(error.recovery_actions) == 1
        assert "cleanup" in error.recovery_actions[0].action_type
    
    def test_concurrency_limit_error(self):
        """Test ConcurrencyLimitError."""
        error = ConcurrencyLimitError(current_count=10, max_count=5)
        
        assert "Transcription concurrency limit exceeded: 10/5" in str(error)
        assert error.current_count == 10
        assert error.max_count == 5
        assert error.recoverable is True
        assert len(error.recovery_actions) == 1
        assert "wait_for_capacity" in error.recovery_actions[0].action_type


class TestErrorHandler:
    """Test ErrorHandler functionality."""
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler instance."""
        return ErrorHandler(logger_name="test_handler")
    
    @pytest.mark.asyncio
    async def test_handle_error_classification(self, error_handler):
        """Test error classification."""
        original = ValueError("Test error")
        context = ErrorContext("test", "handler")
        
        classified = await error_handler.handle_error(
            original, context, reraise=False
        )
        
        assert isinstance(classified, ValidationError)
        assert classified.original_error == original
        assert classified.context == context
        assert "Validation error: Test error" in str(classified)
    
    @pytest.mark.asyncio
    async def test_handle_error_already_classified(self, error_handler):
        """Test handling already classified errors."""
        original = InvalidMessageError("Already classified")
        
        classified = await error_handler.handle_error(
            original, reraise=False
        )
        
        assert classified is original
    
    @pytest.mark.asyncio
    async def test_classify_telethon_errors(self, error_handler):
        """Test classification of Telethon-specific errors."""
        # FloodWaitError
        flood_error = FloodWaitError(seconds=60)
        classified = error_handler._classify_error(flood_error)
        assert isinstance(classified, TranscriptionRateLimitError)
        assert classified.retry_after == 60
        
        # PeerIdInvalidError
        peer_error = PeerIdInvalidError()
        classified = error_handler._classify_error(peer_error)
        assert isinstance(classified, InvalidPeerError)
        
        # ChatAdminRequiredError
        admin_error = ChatAdminRequiredError()
        context = ErrorContext("test", "handler", operation="transcribe")
        classified = error_handler._classify_error(admin_error, context)
        assert isinstance(classified, PermissionError)
        assert classified.operation == "transcribe"
        
        # AuthKeyError
        auth_error = AuthKeyError()
        classified = error_handler._classify_error(auth_error)
        assert isinstance(classified, AuthenticationError)
    
    @pytest.mark.asyncio
    async def test_classify_python_errors(self, error_handler):
        """Test classification of standard Python errors."""
        # asyncio.TimeoutError
        timeout_error = asyncio.TimeoutError()
        context = ErrorContext("wait", "handler", operation="transcribe")
        classified = error_handler._classify_error(timeout_error, context)
        assert isinstance(classified, TranscriptionTimeoutError)
        assert classified.operation == "transcribe"
        
        # ConnectionError
        conn_error = ConnectionError("Network issue")
        classified = error_handler._classify_error(conn_error)
        assert isinstance(classified, NetworkError)
        
        # MemoryError
        mem_error = MemoryError()
        classified = error_handler._classify_error(mem_error)
        assert isinstance(classified, TranscriptionMemoryError)
        
        # Unknown error
        unknown_error = RuntimeError("Unknown")
        classified = error_handler._classify_error(unknown_error)
        assert isinstance(classified, InternalError)
        assert "Unclassified error" in str(classified)
    
    def test_error_statistics(self, error_handler):
        """Test error statistics collection."""
        # Simulate some errors
        error_handler._update_metrics(InvalidMessageError())
        error_handler._update_metrics(InvalidMessageError())
        error_handler._update_metrics(TranscriptionTimeoutError("op", 30))
        
        stats = error_handler.get_error_statistics()
        
        assert stats['total_errors'] == 3
        assert stats['error_counts']['InvalidMessageError'] == 2
        assert stats['error_counts']['TranscriptionTimeoutError'] == 1
        assert stats['most_common_error'] == 'InvalidMessageError'
    
    @pytest.mark.asyncio
    async def test_error_logging(self, error_handler, caplog):
        """Test error logging functionality."""
        # Critical error
        critical = InternalError("Critical failure")
        critical.severity = ErrorSeverity.CRITICAL
        with caplog.at_level(logging.CRITICAL):
            error_handler._log_error(critical)
            assert "CRITICAL ERROR" in caplog.text
            assert "Critical failure" in caplog.text
        
        # Warning error
        warning = ValidationError("Warning issue")
        warning.severity = ErrorSeverity.MEDIUM
        with caplog.at_level(logging.WARNING):
            error_handler._log_error(warning)
            assert "WARNING" in caplog.text


class TestErrorDecorator:
    """Test error handling decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_async_function(self):
        """Test decorator on async function."""
        @handle_transcription_errors("test_op", "test_comp")
        async def test_func(peer_id: int, msg_id: int):
            raise ValueError("Test error")
        
        with pytest.raises(ValidationError) as exc_info:
            await test_func(123, 456)
        
        error = exc_info.value
        assert error.context.operation == "test_op"
        assert error.context.component == "test_comp"
        assert error.context.peer_id == 123
        assert error.context.msg_id == 456
    
    def test_decorator_sync_function(self):
        """Test decorator on sync function."""
        @handle_transcription_errors("sync_op", "sync_comp", reraise=False, default_return="default")
        def test_func():
            raise RuntimeError("Sync error")
        
        result = test_func()
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_decorator_no_error(self):
        """Test decorator when no error occurs."""
        @handle_transcription_errors("no_error", "test")
        async def test_func():
            return "success"
        
        result = await test_func()
        assert result == "success"


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_error_context(self):
        """Test create_error_context helper."""
        context = create_error_context(
            operation="test",
            component="util",
            peer_id=123,
            msg_id=456
        )
        
        assert context.operation == "test"
        assert context.component == "util"
        assert context.peer_id == 123
        assert context.msg_id == 456
    
    def test_format_error_for_user(self):
        """Test format_error_for_user."""
        error = InvalidMessageError("Bad message")
        error.add_recovery_action(RecoveryAction(
            "manual_action",
            "Check the message format",
            automatic=False
        ))
        error.add_recovery_action(RecoveryAction(
            "auto_action",
            "Auto retry",
            automatic=True
        ))
        
        msg = format_error_for_user(error)
        
        assert "Invalid message: Bad message" in msg
        assert "Check the message format" in msg
        assert "Auto retry" not in msg  # Automatic actions not shown
    
    def test_is_recoverable_error(self):
        """Test is_recoverable_error."""
        recoverable = NetworkError("Network issue")
        assert is_recoverable_error(recoverable) is True
        
        not_recoverable = AuthenticationError("Auth failed")
        assert is_recoverable_error(not_recoverable) is False
        
        generic = ValueError("Generic error")
        assert is_recoverable_error(generic) is False
    
    def test_get_automatic_recovery_actions(self):
        """Test get_automatic_recovery_actions."""
        error = NetworkError("Network error")
        error.add_recovery_action(RecoveryAction(
            "manual", "Manual action", automatic=False
        ))
        error.add_recovery_action(RecoveryAction(
            "auto1", "Auto action 1", automatic=True
        ))
        error.add_recovery_action(RecoveryAction(
            "auto2", "Auto action 2", automatic=True
        ))
        
        auto_actions = get_automatic_recovery_actions(error)
        
        assert len(auto_actions) == 3  # Network error has 1 default + 2 added
        auto_types = [a.action_type for a in auto_actions]
        assert "retry_request" in auto_types
        assert "auto1" in auto_types
        assert "auto2" in auto_types
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_wait_and_retry(self):
        """Test attempt_recovery with wait_and_retry action."""
        error = TranscriptionRateLimitError(retry_after=1)
        
        retry_count = 0
        async def retry_func():
            nonlocal retry_count
            retry_count += 1
            return "success"
        
        result = await attempt_recovery(error, retry_func)
        
        assert result == "success"
        assert retry_count == 1
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_retry_request(self):
        """Test attempt_recovery with retry_request action."""
        error = NetworkError("Network error")
        
        attempt_count = 0
        async def retry_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ConnectionError("Still failing")
            return "success"
        
        result = await attempt_recovery(error, retry_func)
        
        assert result == "success"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_not_recoverable(self):
        """Test attempt_recovery with non-recoverable error."""
        error = AuthenticationError("Auth failed")
        
        async def retry_func():
            return "should not reach"
        
        with pytest.raises(AuthenticationError):
            await attempt_recovery(error, retry_func)
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_max_retries_exceeded(self):
        """Test attempt_recovery when max retries exceeded."""
        error = NetworkError("Network error")
        
        async def retry_func():
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            await attempt_recovery(error, retry_func)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])