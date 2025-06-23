"""
Pytest Configuration and Shared Fixtures

This module provides shared pytest configuration and fixtures for the voice transcription
testing infrastructure, supporting Epic 1 User Story 1.8: Basic Testing Infrastructure.

Features:
- Async test support configuration
- Shared mock objects and fixtures
- Test environment setup and teardown
- Performance testing utilities
- Coverage integration hooks
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, patch
import logging

# Add the voice_transcription module to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure pytest for async testing
pytest_plugins = ['pytest_asyncio']

# Default pytest markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.timeout(30)  # 30 second timeout per test
]


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers and settings"""
    
    # Register custom markers
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_network: mark test as requiring network access"
    )
    
    # Configure logging for tests
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during testing
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Disable specific loggers during testing
    logging.getLogger('asyncio').setLevel(logging.ERROR)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers"""
    
    for item in items:
        # Auto-mark tests based on file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
            
        # Auto-mark async tests
        if asyncio.iscoroutinefunction(item.obj):
            item.add_marker(pytest.mark.asyncio)


# ============================================================================
# Session-Level Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session"""
    
    # Create a new event loop for the test session
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    
    # Set as the current event loop
    asyncio.set_event_loop(loop)
    
    yield loop
    
    # Clean up
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """Global test configuration"""
    
    return {
        'base_path': Path(__file__).parent.parent,
        'test_timeout': 30,
        'mock_api_delay': 0.001,  # 1ms for fast tests
        'performance_api_delay': 0.01,  # 10ms for realistic performance tests
        'max_concurrent_tests': 50,
        'memory_limit_mb': 500,
        'coverage_threshold': 90.0
    }


# ============================================================================
# Mock Objects and Clients
# ============================================================================

@pytest.fixture
def mock_telegram_client():
    """Create a comprehensive mock Telegram client"""
    
    client = AsyncMock()
    
    # Basic properties
    client.user_id = 123456789
    client.session_id = "test_session_123"
    client.connected = True
    
    # API call mock with realistic behavior
    async def mock_api_call(request):
        """Mock API call with deterministic responses"""
        
        # Small delay for realism
        await asyncio.sleep(0.001)
        
        request_type = type(request).__name__
        
        if request_type == "TranscribeAudioRequest":
            # Generate deterministic response based on message ID
            transcription_id = abs(hash(f"{request.peer.peer_id}:{request.msg_id}")) % 10**9
            
            # Different response types based on message ID
            if request.msg_id % 10 == 0:
                # Immediate completion (10% of requests)
                return Mock(
                    transcription_id=transcription_id,
                    text=f"Transcribed message {request.msg_id}",
                    pending=False,
                    trial_remains_num=None,
                    trial_remains_until_date=None
                )
            elif request.msg_id % 10 == 1:
                # Error case (10% of requests)
                from unittest.mock import MagicMock
                error = MagicMock()
                error.__class__.__name__ = "PeerIdInvalidError"
                raise error
            else:
                # Pending case (80% of requests)
                return Mock(
                    transcription_id=transcription_id,
                    text="",
                    pending=True,
                    trial_remains_num=5,
                    trial_remains_until_date=None
                )
                
        elif request_type == "RateTranscribedAudioRequest":
            return True
        else:
            raise ValueError(f"Unknown request type: {request_type}")
    
    client.__call__ = mock_api_call
    
    # Entity resolution mock
    async def mock_get_input_entity(entity):
        """Mock entity resolution"""
        peer = Mock()
        
        if isinstance(entity, int):
            peer.peer_id = entity
        elif isinstance(entity, str):
            if entity.startswith("@"):
                peer.peer_id = abs(hash(entity)) % 10**9
            else:
                peer.peer_id = int(entity)
        else:
            peer.peer_id = hash(str(entity)) % 10**9
            
        return peer
    
    client.get_input_entity = mock_get_input_entity
    
    # Event handling
    client._event_handlers = []
    
    def add_event_handler(handler, event_type):
        client._event_handlers.append((handler, event_type))
        
    def remove_event_handler(handler, event_type):
        client._event_handlers = [
            (h, t) for h, t in client._event_handlers 
            if h != handler or t != event_type
        ]
    
    client.add_event_handler = add_event_handler
    client.remove_event_handler = remove_event_handler
    
    return client


@pytest.fixture
def mock_performance_client(test_config):
    """High-performance mock client for benchmarking"""
    
    client = AsyncMock()
    
    # Performance tracking
    client.request_count = 0
    client.concurrent_requests = 0
    client.max_concurrent = 0
    client.total_delay = 0.0
    
    async def performance_api_call(request):
        """Performance-optimized mock API call"""
        
        client.concurrent_requests += 1
        client.max_concurrent = max(client.max_concurrent, client.concurrent_requests)
        client.request_count += 1
        
        try:
            # Configurable delay for performance testing
            delay = test_config['performance_api_delay']
            await asyncio.sleep(delay)
            client.total_delay += delay
            
            # Quick response generation
            if hasattr(request, 'msg_id'):
                transcription_id = request.msg_id * 1000000 + request.peer.peer_id % 1000000
                return Mock(
                    transcription_id=transcription_id,
                    text=f"Fast response {request.msg_id}",
                    pending=request.msg_id % 5 != 0  # 20% immediate, 80% pending
                )
            return True
            
        finally:
            client.concurrent_requests -= 1
    
    client.__call__ = performance_api_call
    client.get_input_entity = lambda entity: Mock(peer_id=hash(str(entity)) % 10**9)
    
    return client


# ============================================================================
# Component Fixtures
# ============================================================================

@pytest.fixture
async def transcription_manager(mock_telegram_client):
    """Create transcription manager with mock client"""
    
    with patch.multiple(
        'voice_transcription.transcription_manager',
        TelegramClient=lambda: mock_telegram_client,
        TELETHON_AVAILABLE=True,
        INTERNAL_IMPORTS=True
    ):
        # Import after patching
        from voice_transcription.transcription_manager import (
            TranscriptionManager, 
            TranscriptionManagerConfig
        )
        
        config = TranscriptionManagerConfig(
            concurrent_limit=50,
            default_timeout=5.0,
            validate_messages=False  # Skip validation in tests
        )
        
        manager = TranscriptionManager(mock_telegram_client, config)
        await manager.initialize()
        
        yield manager
        
        await manager.shutdown()


@pytest.fixture
async def state_manager():
    """Create standalone state manager"""
    
    from voice_transcription.state_manager import TranscriptionStateManager
    
    manager = TranscriptionStateManager()
    yield manager
    
    # Cleanup
    manager.storage.clear_all_states()


@pytest.fixture
async def cleanup_system(state_manager):
    """Create cleanup system with test configuration"""
    
    from voice_transcription.automatic_cleanup import (
        AutomaticCleanupSystem,
        CleanupConfig
    )
    
    config = CleanupConfig(
        max_completed_states=10,
        max_total_states=20,
        completed_ttl_hours=0.001,  # Very short for testing
        cleanup_interval_seconds=0.1
    )
    
    system = AutomaticCleanupSystem(state_manager, config)
    yield system
    
    # Ensure cleanup system is stopped
    if system.running:
        await system.stop()


@pytest.fixture
def error_handler():
    """Create error handler for testing"""
    
    from voice_transcription.error_handling import ErrorHandler
    
    handler = ErrorHandler()
    yield handler


# ============================================================================
# Data Fixtures
# ============================================================================

@pytest.fixture
def sample_test_data():
    """Comprehensive sample test data"""
    
    return {
        'peer_ids': [123456789, -1001234567890, 234567890, 345678901],
        'message_ids': [1001, 1002, 1003, 1004, 1005],
        'transcription_ids': [1111111111, 2222222222, 3333333333, 4444444444],
        'transcription_texts': [
            "Hello, this is a test message.",
            "The quick brown fox jumps over the lazy dog.",
            "Voice transcription testing in progress.",
            "Multiple sentences. Each should be handled correctly.",
            ""  # Empty transcription
        ],
        'error_scenarios': {
            'invalid_peer': {'peer_id': 'invalid', 'msg_id': 1001},
            'invalid_message': {'peer_id': 123456, 'msg_id': 'invalid'},
            'zero_message': {'peer_id': 123456, 'msg_id': 0},
            'negative_peer': {'peer_id': -123, 'msg_id': 1001}
        }
    }


@pytest.fixture
def performance_data_sets():
    """Data sets for performance testing"""
    
    import random
    
    def generate_requests(count, base_peer=100000, base_msg=10000):
        """Generate realistic request data"""
        requests = []
        for i in range(count):
            peer_id = base_peer + random.randint(1, 1000)
            msg_id = base_msg + i + random.randint(1, 100)
            requests.append((peer_id, msg_id))
        return requests
    
    return {
        'small': generate_requests(10),
        'medium': generate_requests(50),
        'large': generate_requests(200),
        'xlarge': generate_requests(1000)
    }


# ============================================================================
# Test Environment Setup
# ============================================================================

@pytest.fixture(autouse=True)
def test_environment_setup(tmp_path, monkeypatch):
    """Automatic test environment setup for each test"""
    
    # Set up temporary directory for test files
    test_dir = tmp_path / "voice_transcription_test"
    test_dir.mkdir()
    
    # Set environment variables for testing
    monkeypatch.setenv("VOICE_TRANSCRIPTION_TEST_MODE", "1")
    monkeypatch.setenv("VOICE_TRANSCRIPTION_TEST_DIR", str(test_dir))
    
    # Change to test directory
    original_cwd = os.getcwd()
    os.chdir(test_dir)
    
    yield {
        'test_dir': test_dir,
        'original_cwd': original_cwd
    }
    
    # Cleanup
    os.chdir(original_cwd)


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Automatic cleanup after each test"""
    
    yield
    
    # Force garbage collection
    import gc
    gc.collect()
    
    # Cancel any remaining tasks
    tasks = [task for task in asyncio.all_tasks() if not task.done()]
    if tasks:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# ============================================================================
# Utility Functions
# ============================================================================

def assert_coverage_threshold(coverage_percentage: float, threshold: float = 90.0):
    """Assert that coverage meets the required threshold"""
    assert coverage_percentage >= threshold, (
        f"Coverage {coverage_percentage:.1f}% is below threshold {threshold:.1f}%"
    )


def assert_performance_metrics(
    duration: float,
    throughput: float,
    memory_mb: float,
    max_duration: float = 10.0,
    min_throughput: float = 10.0,
    max_memory: float = 100.0
):
    """Assert that performance metrics meet requirements"""
    
    assert duration <= max_duration, (
        f"Duration {duration:.2f}s exceeds limit {max_duration:.2f}s"
    )
    assert throughput >= min_throughput, (
        f"Throughput {throughput:.1f} req/s below minimum {min_throughput:.1f} req/s"
    )
    assert memory_mb <= max_memory, (
        f"Memory usage {memory_mb:.1f}MB exceeds limit {max_memory:.1f}MB"
    )


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """Wait for a condition to become true with timeout"""
    
    start_time = asyncio.get_event_loop().time()
    
    while True:
        if condition_func():
            return True
            
        if asyncio.get_event_loop().time() - start_time > timeout:
            return False
            
        await asyncio.sleep(interval)


# ============================================================================
# Test Markers and Decorators
# ============================================================================

def requires_telethon(func):
    """Skip test if Telethon is not available"""
    
    try:
        import telethon
        return func
    except ImportError:
        return pytest.mark.skip(reason="Telethon not available")(func)


def performance_test(min_throughput: float = 10.0, max_memory_mb: float = 100.0):
    """Mark and configure performance tests"""
    
    def decorator(func):
        func = pytest.mark.performance(func)
        func = pytest.mark.slow(func)
        func._performance_config = {
            'min_throughput': min_throughput,
            'max_memory_mb': max_memory_mb
        }
        return func
    return decorator


# ============================================================================
# Debug Utilities
# ============================================================================

@pytest.fixture
def debug_info():
    """Provide debug information for test troubleshooting"""
    
    import psutil
    import platform
    
    return {
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'memory_available': psutil.virtual_memory().available / 1024 / 1024,  # MB
        'cpu_count': psutil.cpu_count(),
        'test_start_time': asyncio.get_event_loop().time()
    }


def log_test_metrics(test_name: str, duration: float, memory_used: float = 0.0):
    """Log test performance metrics"""
    
    logging.info(
        f"Test Metrics - {test_name}: "
        f"Duration={duration:.3f}s, Memory={memory_used:.1f}MB"
    )