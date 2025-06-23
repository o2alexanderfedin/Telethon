# Test Plan: Automatic Cleanup System

## Overview

This document outlines the comprehensive test plan for Epic 1 User Story 1.6: Automatic Cleanup System implementation. The test suite validates background cleanup tasks, configurable TTL management, memory monitoring, and performance under various load conditions.

## Test Structure

```
test_automatic_cleanup.py
├── TestCleanupConfig (2 tests)
├── TestCleanupMetrics (2 tests)
├── TestAutomaticCleanupSystem (20+ tests)
└── Performance Tests (2 tests)
```

## Test Categories

### 1. Configuration Tests

#### CleanupConfig
- **test_default_config**: Default configuration values validation
- **test_custom_config**: Custom configuration override testing

#### CleanupMetrics
- **test_metrics_creation**: Basic metrics object creation
- **test_metrics_update**: Metrics update and calculation functionality

### 2. Core System Tests

#### System Lifecycle
- **test_system_creation**: Basic system object creation
- **test_system_start_stop**: System startup and shutdown procedures
- **test_double_start**: Idempotent start operation handling
- **test_stop_without_start**: Safe stop operation without prior start

#### Cleanup Operations
- **test_manual_cleanup_trigger**: Manual cleanup trigger functionality
- **test_cleanup_when_not_running**: Error handling when system not running
- **test_force_cleanup_when_not_running**: Force cleanup override capability

#### Cleanup Strategies
- **test_age_based_cleanup**: Age-based TTL cleanup strategy
- **test_count_based_cleanup**: Count-based cleanup strategy
- **test_memory_based_cleanup**: Memory pressure-based cleanup
- **test_hybrid_cleanup**: Combined strategy cleanup

#### Safety and Validation
- **test_cleanup_safety_checks**: Safety checks for active/recent states
- **test_cleanup_with_errors**: Error handling during cleanup operations

#### Monitoring and Reporting
- **test_cleanup_status**: Status reporting and metrics
- **test_cleanup_history**: Cleanup operation history tracking
- **test_cleanup_recommendations**: Configuration recommendations

#### Observer Pattern
- **test_observer_management**: Observer add/remove functionality
- **test_observer_error_handling**: Error isolation in observer callbacks

#### Background Operations
- **test_background_cleanup_loop**: Background cleanup task execution
- **test_should_perform_cleanup_conditions**: Cleanup trigger conditions

#### Memory Management
- **test_memory_info_collection**: Memory usage monitoring

### 3. Performance Tests

#### Scalability Testing
- **test_performance_cleanup_operations**: Performance with 1000 states
- **test_example_usage**: Example usage pattern validation

## Test Data and Scenarios

### Mock Components

#### MockStateManager
```python
class MockStateManager:
    def __init__(self):
        self.storage = Mock()
        self.storage.get_state_count = Mock(return_value=0)
        self.storage.get_all_states = Mock(return_value=[])
        self.get_active_transcriptions = Mock(return_value=[])
```

#### MockState
```python
class MockState:
    def __init__(self, peer_id, msg_id, status, age_seconds=0):
        self.is_active = status in (PENDING, PROCESSING)
        self.time_since_update = timedelta(seconds=age_seconds)
```

#### MockProcess (psutil)
```python
class MockProcess:
    def memory_info(self):
        return Mock(rss=100*1024*1024, vms=200*1024*1024)  # 100MB/200MB
```

### Test Scenarios

#### Age-Based Cleanup
- **Old completed states** (> TTL) → Should clean
- **Recent completed states** (< TTL) → Should keep
- **Old failed states** (> failed TTL) → Should clean
- **Active states** (any age) → Should keep

#### Count-Based Cleanup
- **Total states > max_total_states** → Clean oldest inactive
- **Completed states > max_completed_states** → Clean oldest completed
- **Within limits** → No cleanup needed

#### Memory-Based Cleanup
- **Memory > threshold** → Trigger cleanup
- **Memory > aggressive_threshold** → Aggressive cleanup
- **Memory < threshold** → No cleanup needed

#### Safety Scenarios
- **Active transcriptions** → Never clean
- **Very recent states** (< preserve_recent_seconds) → Never clean
- **Old inactive states** → Safe to clean

## Configuration Test Matrix

| Scenario | Strategy | TTL | Interval | Memory Threshold | Expected Behavior |
|----------|----------|-----|----------|------------------|-------------------|
| Default | HYBRID | 3600s | 300s | 100MB | Standard operation |
| Aggressive | AGE_BASED | 300s | 60s | 50MB | Frequent cleanup |
| Conservative | COUNT_BASED | 7200s | 600s | 200MB | Minimal cleanup |
| Memory-focused | MEMORY_BASED | 1800s | 120s | 75MB | Memory-driven |
| Disabled | Any | Any | Any | Any | No cleanup |

## Performance Benchmarks

### Targets
- **Cleanup Processing**: <2 seconds for 1000 states
- **Memory Monitoring**: <10ms per check
- **Background Loop**: <100ms overhead per cycle
- **Observer Notifications**: <1ms per observer

### Load Testing Scenarios
- **High State Count**: 1000+ inactive states
- **Memory Pressure**: Simulated high memory usage
- **Concurrent Operations**: Cleanup during active transcriptions
- **Extended Runtime**: 24-hour background operation

## Error Scenarios

### System Errors
- Component initialization failures
- Background task crashes
- Memory monitoring failures
- State removal errors

### Configuration Errors
- Invalid TTL values
- Negative thresholds
- Missing dependencies
- Invalid strategy combinations

### Runtime Errors
- Observer callback exceptions
- State iteration failures
- Memory calculation errors
- Thread synchronization issues

## Test Execution

### Prerequisites
```bash
pip install pytest pytest-asyncio psutil
```

### Running Tests
```bash
# All tests
python -m pytest test_automatic_cleanup.py -v

# Specific test categories
python -m pytest test_automatic_cleanup.py::TestAutomaticCleanupSystem -v

# Performance tests only
python test_automatic_cleanup.py performance

# With coverage
python -m pytest test_automatic_cleanup.py --cov=automatic_cleanup --cov-report=html
```

### Expected Results
- **Unit Tests**: 25+ tests passing
- **Coverage**: >95% code coverage
- **Performance**: 1000 states cleaned in <2 seconds
- **Memory**: Stable memory usage during operation

## Integration Points

### Component Dependencies
- **TranscriptionStateManager**: State storage and retrieval
- **StateStorage**: Direct state manipulation
- **TranscriptionState**: State object properties and methods

### External Dependencies
- **psutil**: System memory monitoring
- **asyncio**: Background task management
- **threading**: Thread-safe operations
- **gc**: Garbage collection coordination

## Validation Criteria

### Functional Requirements
- ✅ **Configurable TTL** for different state types
- ✅ **Background cleanup** without manual intervention
- ✅ **Non-interfering** with active transcriptions
- ✅ **Memory stability** under sustained load
- ✅ **Configurable and disableable** operation

### Performance Requirements
- ✅ **Fast cleanup** processing (1000 states in <2s)
- ✅ **Low overhead** background operations
- ✅ **Efficient memory** monitoring
- ✅ **Responsive** manual triggers

### Reliability Standards
- ✅ **Error isolation** - failures don't crash system
- ✅ **Safe cleanup** - never affects active states
- ✅ **Graceful degradation** under resource pressure
- ✅ **Consistent operation** over extended periods

## Quality Gates

### Code Quality
- All tests must pass
- Coverage >95%
- No memory leaks detected
- Clean code patterns followed

### Performance Quality
- Benchmarks met consistently
- Memory usage stable
- Background operations efficient
- No blocking operations

### Integration Quality
- Proper mocking of dependencies
- Error scenarios covered
- Safety mechanisms validated
- Observer pattern working

## Cleanup Strategy Validation

### Age-Based Strategy
- ✅ Respects different TTLs per state type
- ✅ Preserves recent states regardless of status
- ✅ Handles timezone-aware datetime comparisons
- ✅ Efficient batch processing

### Count-Based Strategy
- ✅ Enforces configurable limits
- ✅ Cleans oldest states first
- ✅ Respects safety constraints
- ✅ Maintains performance under load

### Memory-Based Strategy
- ✅ Accurate memory monitoring
- ✅ Responsive to memory pressure
- ✅ Escalates cleanup intensity appropriately
- ✅ Integrates with garbage collection

### Hybrid Strategy
- ✅ Combines strategies effectively
- ✅ Prioritizes based on urgency
- ✅ Maintains balanced operation
- ✅ Adapts to changing conditions

This comprehensive test plan ensures the Automatic Cleanup System meets all requirements for Epic 1 User Story 1.6, providing reliable, efficient, and configurable cleanup of transcription states to maintain system stability and performance.