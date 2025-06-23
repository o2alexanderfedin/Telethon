"""
Comprehensive Test Suite for Error Handling Framework

Tests Epic 1 User Story 1.7: Error Handling Framework implementation
including custom exceptions, error classification, recovery mechanisms, and logging.
"""

import asyncio
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from typing import List, Dict, Any

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


class TestErrorContext:
    """Test ErrorContext class"""
    
    def test_context_creation(self):
        """Test basic context creation"""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            peer_id=123,
            msg_id=456
        )
        
        assert context.operation == "test_operation"
        assert context.component == "test_component"
        assert context.peer_id == 123
        assert context.msg_id == 456
        assert context.transcription_id is None
        assert isinstance(context.timestamp, datetime)
        
    def test_context_to_dict(self):
        """Test context serialization"""
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            user_data={"key": "value"}
        )
        
        data = context.to_dict()
        
        assert data['operation'] == "test_op"
        assert data['component'] == "test_comp"
        assert data['user_data'] == {"key": "value"}
        assert 'timestamp' in data


class TestRecoveryAction:
    """Test RecoveryAction class"""
    
    def test_recovery_action_creation(self):
        """Test basic recovery action creation"""
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
        """Test recovery action serialization"""
        action = RecoveryAction(
            action_type="wait",
            description="Wait and retry",
            automatic=False
        )
        
        data = action.to_dict()
        
        assert data['action_type'] == "wait"
        assert data['description'] == "Wait and retry"
        assert data['automatic'] is False
        assert data['parameters'] == {}


class TestVoiceTranscriptionError:
    """Test base VoiceTranscriptionError class"""
    
    def test_basic_error_creation(self):
        """Test basic error creation"""
        error = VoiceTranscriptionError("Test error")
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.category == ErrorCategory.INTERNAL
        assert error.recoverable is False
        assert len(error.recovery_actions) == 0
        assert error.error_id is not None
        
    def test_error_with_context(self):
        """Test error with context"""
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            peer_id=123
        )
        
        error = VoiceTranscriptionError(
            "Test error with context",
            context=context,
            severity=ErrorSeverity.HIGH,
            recoverable=True
        )
        
        assert error.context is context
        assert error.severity == ErrorSeverity.HIGH
        assert error.recoverable is True
        
    def test_error_id_generation(self):
        """Test unique error ID generation"""
        error1 = VoiceTranscriptionError("Error 1")
        error2 = VoiceTranscriptionError("Error 2")
        
        assert error1.error_id != error2.error_id
        assert len(error1.error_id) > 0
        assert len(error2.error_id) > 0
        
    def test_recovery_action_management(self):
        """Test recovery action add functionality"""
        error = VoiceTranscriptionError("Test error")
        
        action = RecoveryAction(
            action_type="retry",
            description="Retry operation"
        )
        
        error.add_recovery_action(action)
        
        assert len(error.recovery_actions) == 1
        assert error.recovery_actions[0] is action
        
    def test_detailed_message(self):
        """Test detailed error message generation"""
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            peer_id=123,
            msg_id=456,
            transcription_id=789
        )
        
        original_error = ValueError("Original error")
        
        error = VoiceTranscriptionError(
            "Test error",
            context=context,
            original_error=original_error
        )
        
        detailed = error.get_detailed_message()
        
        assert "Test error" in detailed
        assert "Peer: 123" in detailed
        assert "Message: 456" in detailed
        assert "Transcription: 789" in detailed
        assert "ValueError: Original error" in detailed
        
    def test_error_serialization(self):
        """Test error to_dict functionality"""
        context = ErrorContext(operation="test", component="test")
        error = VoiceTranscriptionError(
            "Test error",
            context=context,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION
        )
        
        data = error.to_dict()
        
        assert data['error_type'] == "VoiceTranscriptionError"
        assert data['message'] == "Test error"
        assert data['severity'] == "high"
        assert data['category'] == "validation"
        assert 'error_id' in data
        assert 'context' in data


class TestValidationErrors:
    """Test validation error classes"""
    
    def test_validation_error(self):
        """Test basic ValidationError"""
        error = ValidationError("Invalid input", field_name="test_field")
        
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.recoverable is True
        assert error.field_name == "test_field"
        
        user_message = error.get_user_friendly_message()
        assert "Invalid test_field" in user_message
        
    def test_invalid_message_error(self):
        """Test InvalidMessageError"""
        error = InvalidMessageError()
        
        assert "not valid for transcription" in str(error)
        assert error.field_name == "message"
        assert len(error.recovery_actions) > 0
        assert any("voice note" in action.description for action in error.recovery_actions)
        
    def test_invalid_peer_error(self):
        """Test InvalidPeerError"""
        error = InvalidPeerError(peer_id="invalid_peer")
        
        assert error.peer_id == "invalid_peer"
        assert "Invalid peer ID" in str(error)
        assert error.field_name == "peer"
        assert len(error.recovery_actions) > 0
        
    def test_message_validation_error(self):
        """Test MessageValidationError"""
        error = MessageValidationError("Invalid format", validation_type="format")
        
        assert error.validation_type == "format"
        assert error.category == ErrorCategory.VALIDATION


class TestAuthenticationErrors:
    """Test authentication error classes"""
    
    def test_authentication_error(self):
        """Test base AuthenticationError"""
        error = AuthenticationError("Auth failed")
        
        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.recoverable is False
        
    def test_permission_error(self):
        """Test PermissionError"""
        error = PermissionError("transcribe_audio")
        
        assert error.operation == "transcribe_audio"
        assert "Insufficient permissions" in str(error)
        assert len(error.recovery_actions) > 0
        
    def test_transcription_not_available_error(self):
        """Test TranscriptionNotAvailableError"""
        error = TranscriptionNotAvailableError("Feature disabled")
        
        assert error.reason == "Feature disabled"
        assert error.category == ErrorCategory.API
        assert error.recoverable is False


class TestRateLimitErrors:
    """Test rate limiting error classes"""
    
    def test_rate_limit_error(self):
        """Test base RateLimitError"""
        error = RateLimitError("Rate limited", retry_after=30)
        
        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.retry_after == 30
        assert error.recoverable is True
        assert len(error.recovery_actions) > 0
        
        # Check automatic recovery action
        auto_actions = [a for a in error.recovery_actions if a.automatic]
        assert len(auto_actions) > 0
        assert auto_actions[0].parameters['retry_after'] == 30
        
    def test_transcription_rate_limit_error(self):
        """Test TranscriptionRateLimitError"""
        error = TranscriptionRateLimitError(retry_after=60)
        
        assert error.retry_after == 60
        assert "rate limit exceeded" in str(error).lower()
        assert "60 seconds" in str(error)
        
    def test_api_rate_limit_error(self):
        """Test APIRateLimitError"""
        error = APIRateLimitError(retry_after=120)
        
        assert error.retry_after == 120
        assert "API rate limit" in str(error)


class TestNetworkErrors:
    """Test network error classes"""
    
    def test_network_error(self):
        """Test base NetworkError"""
        error = NetworkError("Connection failed")
        
        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.HIGH
        assert error.recoverable is True
        assert len(error.recovery_actions) > 0
        
        # Check retry action
        retry_action = error.recovery_actions[0]
        assert retry_action.action_type == "retry_request"
        assert retry_action.automatic is True
        
    def test_timeout_error(self):
        """Test TimeoutError"""
        error = TimeoutError("transcribe", 30.0)
        
        assert error.operation == "transcribe"
        assert error.timeout_seconds == 30.0
        assert error.category == ErrorCategory.TIMEOUT
        assert "timed out after 30.0 seconds" in str(error)
        
    def test_connection_error(self):
        """Test ConnectionError"""
        error = ConnectionError("Network unreachable")
        
        assert "Network unreachable" in str(error)
        assert error.category == ErrorCategory.NETWORK


class TestAPIErrors:
    """Test API error classes"""
    
    def test_api_error(self):
        """Test base APIError"""
        error = APIError("API call failed", api_error_code="500")
        
        assert error.category == ErrorCategory.API
        assert error.severity == ErrorSeverity.HIGH
        assert error.api_error_code == "500"
        
    def test_transcription_request_error(self):
        """Test TranscriptionRequestError"""
        error = TranscriptionRequestError("Request invalid")
        
        assert "Request invalid" in str(error)
        assert error.recoverable is True
        assert len(error.recovery_actions) > 0
        
    def test_transcription_processing_error(self):
        """Test TranscriptionProcessingError"""
        error = TranscriptionProcessingError(transcription_id=12345)
        
        assert error.transcription_id == 12345
        assert "12345" in str(error)
        assert error.recoverable is False


class TestInternalErrors:
    """Test internal error classes"""
    
    def test_internal_error(self):
        """Test base InternalError"""
        error = InternalError("System failure")
        
        assert error.category == ErrorCategory.INTERNAL
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.recoverable is False
        
    def test_state_management_error(self):
        """Test StateManagementError"""
        error = StateManagementError("create_state", state_key="123:456")
        
        assert error.operation == "create_state"
        assert error.state_key == "123:456"
        assert "create_state" in str(error)
        assert "123:456" in str(error)
        
    def test_configuration_error(self):
        """Test ConfigurationError"""
        error = ConfigurationError("database", "Invalid connection string")
        
        assert error.config_name == "database"
        assert error.category == ErrorCategory.CONFIGURATION
        assert "Configuration error in database" in str(error)


class TestResourceErrors:
    """Test resource error classes"""
    
    def test_resource_error(self):
        """Test base ResourceError"""
        error = ResourceError("Resource exhausted")
        
        assert error.category == ErrorCategory.RESOURCE
        assert error.severity == ErrorSeverity.HIGH
        assert error.recoverable is True
        
    def test_memory_error(self):
        """Test MemoryError"""
        error = MemoryError(current_usage=150.5)
        
        assert error.current_usage == 150.5
        assert "150.5MB" in str(error)
        assert len(error.recovery_actions) > 0
        
        cleanup_action = error.recovery_actions[0]
        assert cleanup_action.action_type == "cleanup_resources"
        assert cleanup_action.automatic is True
        
    def test_concurrency_limit_error(self):
        """Test ConcurrencyLimitError"""
        error = ConcurrencyLimitError(current_count=15, max_count=10)
        
        assert error.current_count == 15
        assert error.max_count == 10
        assert "15/10" in str(error)
        assert len(error.recovery_actions) > 0
        
        wait_action = error.recovery_actions[0]
        assert wait_action.action_type == "wait_for_capacity"


class TestErrorHandler:
    """Test ErrorHandler class"""
    
    def test_handler_creation(self):
        """Test basic handler creation"""
        handler = ErrorHandler()
        
        assert handler.logger is not None
        assert isinstance(handler.error_counts, dict)
        assert isinstance(handler.recovery_attempts, dict)
        
    def test_handle_existing_transcription_error(self):
        """Test handling already classified errors"""
        handler = ErrorHandler()
        original_error = ValidationError("Test validation error")
        
        classified = handler.handle_error(original_error, reraise=False)
        
        assert classified is original_error
        assert handler.error_counts.get("ValidationError", 0) == 1
        
    def test_handle_generic_exception(self):
        """Test handling generic exceptions"""
        handler = ErrorHandler()
        
        # Test ValueError
        value_error = ValueError("Invalid value")
        classified = handler.handle_error(value_error, reraise=False)
        
        assert isinstance(classified, ValidationError)
        assert "Invalid value" in str(classified)
        assert classified.original_error is value_error
        
    def test_handle_timeout_error(self):
        """Test handling timeout errors"""
        handler = ErrorHandler()
        
        timeout_error = asyncio.TimeoutError()
        context = ErrorContext(operation="test_op", component="test_comp")
        classified = handler.handle_error(timeout_error, context=context, reraise=False)
        
        assert isinstance(classified, TimeoutError)
        assert classified.operation == "test_op"
        assert classified.context is context
        
    def test_error_statistics(self):
        """Test error statistics collection"""
        handler = ErrorHandler()
        
        # Handle multiple errors
        handler.handle_error(ValueError("Error 1"), reraise=False)
        handler.handle_error(ValueError("Error 2"), reraise=False)
        handler.handle_error(TypeError("Error 3"), reraise=False)
        
        stats = handler.get_error_statistics()
        
        assert stats['total_errors'] == 3
        assert stats['error_counts']['ValidationError'] == 2
        assert stats['error_counts']['InternalError'] == 1
        assert stats['most_common_error'] == 'ValidationError'
        
    def test_error_logging(self, caplog):
        """Test error logging functionality"""
        handler = ErrorHandler()
        
        with caplog.at_level(logging.WARNING):
            error = ValidationError("Test error", severity=ErrorSeverity.MEDIUM)
            handler._log_error(error)
            
        assert "WARNING" in caplog.text
        assert "Test error" in caplog.text
        assert error.error_id in caplog.text


class TestErrorClassification:
    """Test error classification functionality"""
    
    def test_classify_with_context(self):
        """Test error classification with context"""
        handler = ErrorHandler()
        context = ErrorContext(
            operation="transcribe",
            component="transcriber",
            peer_id=123,
            msg_id=456
        )
        
        error = ValueError("Test error")
        classified = handler._classify_error(error, context)
        
        assert isinstance(classified, ValidationError)
        assert classified.context is context
        assert classified.context.peer_id == 123
        assert classified.context.msg_id == 456
        
    @patch('voice_transcription.error_handling.TELETHON_AVAILABLE', True)
    def test_classify_telethon_errors(self):
        """Test classification of Telethon-specific errors"""
        handler = ErrorHandler()
        
        # Mock Telethon errors
        class MockFloodWaitError(Exception):
            def __init__(self, seconds):
                self.seconds = seconds
                super().__init__(f"Flood wait {seconds}")
                
        # Test FloodWaitError
        flood_error = MockFloodWaitError(30)
        with patch('voice_transcription.error_handling.FloodWaitError', MockFloodWaitError):
            classified = handler._classify_error(flood_error)
            
        assert isinstance(classified, TranscriptionRateLimitError)
        # Note: retry_after might not be set due to mocking limitations


class TestErrorDecorator:
    """Test error handling decorator"""
    
    @pytest.mark.asyncio
    async def test_async_decorator_success(self):
        """Test decorator with successful async function"""
        
        @handle_transcription_errors("test_op", "test_comp")
        async def success_function():
            return "success"
            
        result = await success_function()
        assert result == "success"
        
    @pytest.mark.asyncio
    async def test_async_decorator_error(self):
        """Test decorator with failing async function"""
        
        @handle_transcription_errors("test_op", "test_comp")
        async def failing_function():
            raise ValueError("Test error")
            
        with pytest.raises(ValidationError) as exc_info:
            await failing_function()
            
        error = exc_info.value
        assert isinstance(error, ValidationError)
        assert error.context.operation == "test_op"
        assert error.context.component == "test_comp"
        
    def test_sync_decorator_error(self):
        """Test decorator with failing sync function"""
        
        @handle_transcription_errors("test_op", "test_comp")
        def failing_function():
            raise ValueError("Test error")
            
        with pytest.raises(ValidationError) as exc_info:
            failing_function()
            
        error = exc_info.value
        assert isinstance(error, ValidationError)
        assert error.context.operation == "test_op"
        
    @pytest.mark.asyncio
    async def test_decorator_no_reraise(self):
        """Test decorator with reraise=False"""
        
        @handle_transcription_errors("test_op", "test_comp", reraise=False, default_return="error")
        async def failing_function():
            raise ValueError("Test error")
            
        result = await failing_function()
        assert result == "error"
        
    @pytest.mark.asyncio
    async def test_decorator_context_extraction(self):
        """Test context extraction from function arguments"""
        
        @handle_transcription_errors("test_op", "test_comp")
        async def function_with_args(peer_id, msg_id, chat):
            raise ValueError("Test error")
            
        with pytest.raises(ValidationError) as exc_info:
            await function_with_args(peer_id=123, msg_id=456, chat=789)
            
        error = exc_info.value
        assert error.context.peer_id == 123
        assert error.context.msg_id == 456


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_error_context(self):
        """Test create_error_context utility"""
        context = create_error_context(
            "test_op",
            "test_comp",
            peer_id=123,
            custom_field="value"
        )
        
        assert context.operation == "test_op"
        assert context.component == "test_comp"
        assert context.peer_id == 123
        assert context.user_data.get("custom_field") == "value"
        
    def test_format_error_for_user(self):
        """Test format_error_for_user utility"""
        error = ValidationError("Test validation error")
        error.add_recovery_action(RecoveryAction(
            action_type="manual",
            description="Check your input",
            automatic=False
        ))
        error.add_recovery_action(RecoveryAction(
            action_type="auto",
            description="Auto retry",
            automatic=True
        ))
        
        formatted = format_error_for_user(error)
        
        assert "Test validation error" in formatted
        assert "Check your input" in formatted
        assert "Auto retry" not in formatted  # Automatic actions not shown
        
    def test_is_recoverable_error(self):
        """Test is_recoverable_error utility"""
        recoverable_error = ValidationError("Recoverable")
        non_recoverable_error = InternalError("Not recoverable")
        generic_error = ValueError("Generic")
        
        assert is_recoverable_error(recoverable_error) is True
        assert is_recoverable_error(non_recoverable_error) is False
        assert is_recoverable_error(generic_error) is False
        
    def test_get_automatic_recovery_actions(self):
        """Test get_automatic_recovery_actions utility"""
        error = VoiceTranscriptionError("Test error")
        
        manual_action = RecoveryAction("manual", "Manual action", automatic=False)
        auto_action = RecoveryAction("auto", "Auto action", automatic=True)
        
        error.add_recovery_action(manual_action)
        error.add_recovery_action(auto_action)
        
        auto_actions = get_automatic_recovery_actions(error)
        
        assert len(auto_actions) == 1
        assert auto_actions[0] is auto_action


@pytest.mark.asyncio
async def test_example_usage():
    """Test the example usage pattern"""
    from .error_handling import example_error_handling
    
    # This should run without errors (even though it raises exceptions internally)
    await example_error_handling()


def test_error_enums():
    """Test error enums"""
    # Test ErrorSeverity
    assert ErrorSeverity.LOW.value == "low"
    assert ErrorSeverity.MEDIUM.value == "medium"
    assert ErrorSeverity.HIGH.value == "high"
    assert ErrorSeverity.CRITICAL.value == "critical"
    
    # Test ErrorCategory
    assert ErrorCategory.VALIDATION.value == "validation"
    assert ErrorCategory.AUTHENTICATION.value == "authentication"
    assert ErrorCategory.NETWORK.value == "network"
    assert ErrorCategory.API.value == "api"
    assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
    assert ErrorCategory.TIMEOUT.value == "timeout"
    assert ErrorCategory.INTERNAL.value == "internal"
    assert ErrorCategory.CONFIGURATION.value == "configuration"
    assert ErrorCategory.RESOURCE.value == "resource"


if __name__ == "__main__":
    # Run all tests with pytest
    pytest.main([__file__, "-v"])