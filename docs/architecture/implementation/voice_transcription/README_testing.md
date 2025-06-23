# Voice Transcription Testing Infrastructure

This document provides comprehensive guidance for testing the voice transcription system implemented for **Epic 1 User Story 1.8: Basic Testing Infrastructure**.

## Overview

The testing infrastructure provides:
- ✅ **Unit tests** for all core classes and methods
- ✅ **Integration tests** for complete API request/response flow
- ✅ **Performance benchmarks** for concurrent operations
- ✅ **Test coverage monitoring** with >90% requirement
- ✅ **Mock servers** for realistic testing
- ✅ **Test data fixtures** for consistent scenarios

## Quick Start

### Running All Tests
```bash
# Run complete test suite with coverage
python tests/test_runner.py --coverage --verbose

# Run only unit tests
python tests/test_runner.py --category unit

# Run only integration tests  
python tests/test_runner.py --category integration

# Run only performance tests
python tests/test_runner.py --category performance
```

### Coverage Analysis
```bash
# Generate coverage report
python test_coverage_config.py

# HTML coverage report only
python test_coverage_config.py --html-only

# Validate existing coverage
python test_coverage_config.py --validate-only
```

### Performance Benchmarks
```bash
# Run performance tests directly
python -m pytest test_performance.py -v

# Run specific performance category
python -m pytest test_performance.py::TestConcurrentTranscriptionPerformance -v
```

## Test Structure

```
voice_transcription/
├── tests/
│   ├── test_runner.py              # Main test runner
│   └── test_*.py                   # Individual unit tests
├── test_integration.py             # Integration tests
├── test_performance.py             # Performance benchmarks
├── test_coverage_config.py         # Coverage monitoring
├── test_fixtures.py                # Test data and mocks
└── README_testing.md              # This documentation
```

## Test Categories

### 1. Unit Tests
Individual component testing with mocked dependencies.

**Available Tests:**
- `test_basic_request.py` - BasicVoiceTranscriber testing
- `test_state_manager.py` - State management testing
- `test_transcription_manager.py` - Manager coordination testing
- `test_automatic_cleanup.py` - Cleanup system testing
- `test_error_handling.py` - Error framework testing
- `test_update_handler.py` - Update processing testing

**Running Unit Tests:**
```bash
# All unit tests
python tests/test_runner.py --category unit

# Specific component
python -m pytest tests/test_transcription_manager.py -v

# With coverage
python -m pytest tests/ --cov=voice_transcription --cov-report=html
```

### 2. Integration Tests
End-to-end workflow testing with mock Telegram API.

**Test Scenarios:**
- Complete transcription flow (request → response → update)
- Concurrent transcription handling
- State lifecycle management
- Update processing and validation
- Error handling integration

**Running Integration Tests:**
```bash
# All integration tests
python tests/test_runner.py --category integration

# Specific integration test
python -m pytest test_integration.py::TestCompleteTranscriptionFlow -v
```

### 3. Performance Tests
System performance validation under load.

**Performance Metrics:**
- **Throughput**: ≥20 requests/second
- **Request Time**: <100ms average, <200ms P95
- **Memory Usage**: <50MB growth under load
- **State Lookup**: <1ms average
- **Cleanup Rate**: ≥100 states/second

**Running Performance Tests:**
```bash
# All performance tests
python tests/test_runner.py --category performance

# Specific performance area
python -m pytest test_performance.py::TestConcurrentTranscriptionPerformance -v
```

## Coverage Requirements

### Epic 1 Requirements
- **Overall Coverage**: ≥90%
- **Core Components**: ≥95%
- **Supporting Components**: ≥85%

### Module Thresholds
```python
module_thresholds = {
    'basic_request': 95.0,
    'transcription_manager': 95.0,
    'state_manager': 95.0,
    'error_handling': 95.0,
    'update_handler': 90.0,
    'automatic_cleanup': 90.0,
    'validation': 85.0,
    'response_parser': 85.0,
    'integration': 80.0
}
```

### Monitoring Coverage
```bash
# Check current coverage
python test_coverage_config.py

# Generate detailed report
python test_coverage_config.py --pattern "test_*.py"

# View HTML report
open coverage_html/index.html
```

## Test Data and Fixtures

### Available Fixtures

**Basic Data:**
- `sample_peer_ids` - Realistic peer IDs
- `sample_message_ids` - Various message IDs
- `sample_transcription_texts` - Realistic transcription results

**Mock Objects:**
- `mock_telegram_client` - Complete Telegram API mock
- `mock_transcribed_audio` - Mock API responses
- `mock_update_transcribed_audio` - Mock update events

**Error Scenarios:**
- `error_scenarios` - Comprehensive error cases
- `mock_telethon_errors` - Telethon-specific errors

**Performance Data:**
- `performance_test_data` - Large datasets for load testing

### Using Fixtures
```python
import pytest
from test_fixtures import *

@pytest.mark.asyncio
async def test_my_feature(mock_telegram_client, sample_peer_ids):
    # Use fixtures in your tests
    transcriber = BasicVoiceTranscriber(mock_telegram_client)
    result = await transcriber.transcribe(
        chat=sample_peer_ids[0], 
        msg_id=12345
    )
    assert result.success
```

## Mock Components

### Telegram Client Mock
Provides realistic API behavior:
```python
# Deterministic responses based on message ID
msg_id % 10 == 0  # Immediate completion
msg_id % 10 == 1  # Error response  
others            # Pending response with update
```

### Update Simulation
```python
# Automatic update delivery after delay
await asyncio.sleep(0.5)  # Simulate processing
# Update sent to registered handlers
```

### Error Simulation
```python
# Configurable error scenarios
error_scenarios['validation_errors']  # Input validation
error_scenarios['network_errors']     # Network issues
error_scenarios['api_errors']         # Telegram API errors
```

## Test Configuration

### Test Runner Configuration
```python
# Test categories and file mapping
test_categories = {
    'unit': [
        'test_state_manager.py',
        'test_transcription_manager.py',
        'test_automatic_cleanup.py',
        'test_error_handling.py'
    ],
    'integration': ['test_integration.py'],
    'performance': ['test_performance.py']
}
```

### Coverage Configuration  
```python
# Coverage settings
source_packages = ['voice_transcription']
omit_patterns = ['*/test*', '*/tests/*', '*/__pycache__/*']
minimum_coverage = 90.0
```

### Performance Configuration
```python
# Performance test parameters
concurrent_count = 50      # Concurrent requests
total_requests = 200       # Total test requests
duration_seconds = 10      # Sustained load duration
requests_per_second = 10   # Target rate
```

## Continuous Integration

### Pre-commit Testing
```bash
# Run before committing
python tests/test_runner.py --coverage --no-performance
```

### Full Test Suite
```bash
# Complete validation
python tests/test_runner.py --coverage --verbose --report test_report.json
```

### Coverage Validation
```bash
# Ensure coverage thresholds
python test_coverage_config.py --validate-only
```

## Debugging Tests

### Verbose Output
```bash
# Detailed test output
python -m pytest -v --tb=long

# Show print statements
python -m pytest -s
```

### Individual Test Debugging
```python
# Run single test with debugging
python -m pytest test_transcription_manager.py::test_specific_method -v -s
```

### Mock Debugging
```python
# Debug mock calls
mock_client.assert_called_with(expected_request)
print(f"Mock call args: {mock_client.call_args}")
```

## Common Test Patterns

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_async_operation(mock_telegram_client):
    transcriber = BasicVoiceTranscriber(mock_telegram_client)
    result = await transcriber.transcribe(chat=123, msg_id=456)
    assert result.success
```

### Error Testing Pattern
```python
@pytest.mark.asyncio
async def test_error_handling(mock_telegram_client, error_scenarios):
    # Configure mock to raise error
    mock_telegram_client.side_effect = Exception("Test error")
    
    transcriber = BasicVoiceTranscriber(mock_telegram_client)
    result = await transcriber.transcribe(chat=123, msg_id=456)
    
    assert not result.success
    assert "Test error" in result.error
```

### Performance Testing Pattern
```python
@pytest.mark.asyncio
async def test_performance(transcription_manager_perf):
    metrics = PerformanceMetrics()
    metrics.start_measurement()
    
    # Execute performance test
    tasks = [manager.transcribe(chat=i, msg_id=1000+i) for i in range(100)]
    results = await asyncio.gather(*tasks)
    
    metrics.end_measurement()
    assert metrics.throughput >= 20.0
```

## Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Ensure PYTHONPATH includes voice_transcription
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Coverage Not Working:**
```bash
# Install coverage dependencies
pip install coverage pytest-cov
```

**Performance Tests Slow:**
```bash
# Reduce test parameters for development
# Edit test_performance.py configuration
```

**Mock Client Issues:**
```python
# Verify mock setup
assert hasattr(mock_client, '__call__')
assert hasattr(mock_client, 'get_input_entity')
```

### Test Environment

**Required Dependencies:**
```bash
pip install pytest pytest-asyncio pytest-cov coverage psutil
```

**Optional Dependencies:**
```bash
pip install pytest-html pytest-json-report  # Enhanced reporting
```

## Best Practices

### Writing Tests
1. **Use fixtures** for consistent test data
2. **Mock external dependencies** completely
3. **Test both success and error paths**
4. **Include performance considerations**
5. **Validate state changes** explicitly

### Test Organization
1. **Group related tests** in classes
2. **Use descriptive test names**
3. **Include docstrings** for complex tests
4. **Separate unit/integration/performance** tests
5. **Use parametrized tests** for multiple scenarios

### Coverage Goals
1. **Aim for >95%** on core components
2. **Focus on critical paths** first
3. **Test error conditions** thoroughly
4. **Include edge cases**
5. **Document uncovered code** reasons

## Epic 1 Validation

### Requirements Checklist
- ✅ Unit tests for all core classes and methods
- ✅ Integration tests for API request/response flow  
- ✅ Mock tests for update handling
- ✅ Performance tests for concurrent operations
- ✅ Test coverage >90% for Epic 1 code

### Success Metrics
- ✅ All tests pass consistently
- ✅ Coverage thresholds met
- ✅ Performance requirements validated
- ✅ Integration tests use realistic scenarios
- ✅ Error handling comprehensively tested

This testing infrastructure ensures the voice transcription system meets all Epic 1 requirements and provides a solid foundation for future development.