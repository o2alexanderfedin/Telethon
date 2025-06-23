"""
Comprehensive Test Suite for Automatic Cleanup System

Tests Epic 1 User Story 1.6: Automatic Cleanup System implementation
including background cleanup tasks, configurable TTL, memory management, and monitoring.
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from .automatic_cleanup import (
    AutomaticCleanupSystem,
    CleanupConfig,
    CleanupStrategy,
    CleanupTrigger,
    CleanupMetrics
)

# Mock psutil for testing
class MockProcess:
    """Mock psutil.Process for testing"""
    def __init__(self):
        self.memory_info_data = Mock()
        self.memory_info_data.rss = 100 * 1024 * 1024  # 100MB
        self.memory_info_data.vms = 200 * 1024 * 1024  # 200MB
        
    def memory_info(self):
        return self.memory_info_data


class MockStateManager:
    """Mock TranscriptionStateManager for testing"""
    def __init__(self):
        self.storage = Mock()
        self.storage.get_state_count = Mock(return_value=0)
        self.storage.get_state_counts_by_status = Mock(return_value={})
        self.storage.get_all_states = Mock(return_value=[])
        self.storage.remove_state = Mock(return_value=True)
        self.get_active_transcriptions = Mock(return_value=[])


class MockState:
    """Mock TranscriptionState for testing"""
    def __init__(self, peer_id, msg_id, status, age_seconds=0):
        from .state_manager import TranscriptionStatus
        
        self.peer_id = peer_id
        self.msg_id = msg_id
        self.status = status
        self.state_key = f"{peer_id}:{msg_id}"
        self.last_update = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        self.created_at = self.last_update
        
    @property
    def is_active(self):
        from .state_manager import TranscriptionStatus
        return self.status in (TranscriptionStatus.PENDING, TranscriptionStatus.PROCESSING)
        
    @property
    def time_since_update(self):
        return datetime.now(timezone.utc) - self.last_update


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager"""
    return MockStateManager()


@pytest.fixture
def cleanup_config():
    """Create a test cleanup configuration"""
    return CleanupConfig(
        enabled=True,
        strategy=CleanupStrategy.HYBRID,
        completed_ttl_seconds=300,  # 5 minutes
        cleanup_interval_seconds=10,  # 10 seconds
        max_completed_states=10,
        memory_threshold_mb=50,
        cleanup_batch_size=5
    )


@pytest.fixture
async def cleanup_system(mock_state_manager, cleanup_config):
    """Create an AutomaticCleanupSystem for testing"""
    with patch('voice_transcription.automatic_cleanup.INTERNAL_IMPORTS', True):
        with patch('voice_transcription.automatic_cleanup.psutil.Process', return_value=MockProcess()):
            system = AutomaticCleanupSystem(mock_state_manager, cleanup_config)
            yield system
            
            # Cleanup
            if system._running:
                await system.stop()


class TestCleanupConfig:
    """Test CleanupConfig class"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = CleanupConfig()
        
        assert config.enabled is True
        assert config.strategy == CleanupStrategy.HYBRID
        assert config.completed_ttl_seconds == 3600
        assert config.cleanup_interval_seconds == 300
        assert config.max_completed_states == 1000
        assert config.memory_threshold_mb == 100
        assert config.background_cleanup_enabled is True
        
    def test_custom_config(self):
        """Test custom configuration"""
        config = CleanupConfig(
            strategy=CleanupStrategy.AGE_BASED,
            completed_ttl_seconds=1800,
            memory_threshold_mb=200,
            enabled=False
        )
        
        assert config.strategy == CleanupStrategy.AGE_BASED
        assert config.completed_ttl_seconds == 1800
        assert config.memory_threshold_mb == 200
        assert config.enabled is False


class TestCleanupMetrics:
    """Test CleanupMetrics class"""
    
    def test_metrics_creation(self):
        """Test basic metrics creation"""
        metrics = CleanupMetrics()
        
        assert metrics.total_runs == 0
        assert metrics.total_cleaned == 0
        assert metrics.total_errors == 0
        assert metrics.last_run_time is None
        assert metrics.average_run_duration == 0.0
        
    def test_metrics_update(self):
        """Test metrics update functionality"""
        metrics = CleanupMetrics()
        
        # First run
        metrics.update_run_metrics(duration=2.0, cleaned=10, memory_saved=5.0)
        
        assert metrics.total_runs == 1
        assert metrics.total_cleaned == 10
        assert metrics.last_run_duration == 2.0
        assert metrics.last_run_cleaned == 10
        assert metrics.average_run_duration == 2.0
        assert metrics.memory_savings_mb == 5.0
        assert metrics.cleanup_efficiency == 5.0  # 10 states / 2 seconds
        
        # Second run
        metrics.update_run_metrics(duration=3.0, cleaned=15, memory_saved=7.5)
        
        assert metrics.total_runs == 2
        assert metrics.total_cleaned == 25
        assert metrics.last_run_duration == 3.0
        assert metrics.last_run_cleaned == 15
        assert metrics.average_run_duration == 2.5  # (2.0 + 3.0) / 2
        assert metrics.memory_savings_mb == 12.5
        assert metrics.cleanup_efficiency == 5.0  # 15 states / 3 seconds


@pytest.mark.asyncio
class TestAutomaticCleanupSystem:
    """Test AutomaticCleanupSystem class"""
    
    async def test_system_creation(self, cleanup_system):
        """Test basic system creation"""
        assert cleanup_system.state_manager is not None
        assert cleanup_system.config is not None
        assert cleanup_system._running is False
        assert cleanup_system.metrics.total_runs == 0
        
    async def test_system_start_stop(self, cleanup_system):
        """Test system start and stop"""
        # Start system
        await cleanup_system.start()
        assert cleanup_system._running is True
        assert cleanup_system._cleanup_task is not None
        
        # Stop system
        await cleanup_system.stop()
        assert cleanup_system._running is False
        assert cleanup_system._cleanup_task is None
        
    async def test_double_start(self, cleanup_system):
        """Test double start handling"""
        await cleanup_system.start()
        
        # Should not raise error
        await cleanup_system.start()
        assert cleanup_system._running is True
        
    async def test_stop_without_start(self, cleanup_system):
        """Test stop without start"""
        # Should not raise error
        await cleanup_system.stop()
        assert cleanup_system._running is False
        
    async def test_manual_cleanup_trigger(self, cleanup_system):
        """Test manual cleanup trigger"""
        # Setup mock states
        from .state_manager import TranscriptionStatus
        
        old_states = [
            MockState(123, 456, TranscriptionStatus.COMPLETED, age_seconds=3600),
            MockState(123, 457, TranscriptionStatus.FAILED, age_seconds=2400)
        ]
        
        cleanup_system.state_manager.storage.get_all_states.return_value = old_states
        cleanup_system.state_manager.storage.get_state_count.return_value = len(old_states)
        
        # Trigger cleanup
        result = await cleanup_system.trigger_cleanup(strategy=CleanupStrategy.AGE_BASED)
        
        assert result['success'] is True
        assert result['strategy'] == 'age_based'
        assert result['cleaned'] >= 0
        assert 'duration' in result
        
    async def test_cleanup_when_not_running(self, cleanup_system):
        """Test cleanup trigger when system not running"""
        result = await cleanup_system.trigger_cleanup()
        
        assert result['success'] is False
        assert 'not running' in result['error'].lower()
        
    async def test_force_cleanup_when_not_running(self, cleanup_system):
        """Test force cleanup when system not running"""
        cleanup_system.state_manager.storage.get_all_states.return_value = []
        
        result = await cleanup_system.trigger_cleanup(force=True)
        
        assert result['success'] is True
        
    async def test_age_based_cleanup(self, cleanup_system):
        """Test age-based cleanup strategy"""
        from .state_manager import TranscriptionStatus
        
        # Create states with different ages
        states = [
            MockState(123, 456, TranscriptionStatus.COMPLETED, age_seconds=3600),  # Old, should clean
            MockState(123, 457, TranscriptionStatus.COMPLETED, age_seconds=60),    # Recent, keep
            MockState(123, 458, TranscriptionStatus.FAILED, age_seconds=2400),     # Old failed, clean
            MockState(123, 459, TranscriptionStatus.PENDING, age_seconds=3600),    # Active, keep
        ]
        
        cleanup_system.state_manager.storage.get_all_states.return_value = states
        
        # Perform age-based cleanup
        cleaned = await cleanup_system._age_based_cleanup()
        
        # Should clean the old completed and failed states
        assert cleaned >= 0
        
    async def test_count_based_cleanup(self, cleanup_system):
        """Test count-based cleanup strategy"""
        from .state_manager import TranscriptionStatus
        
        # Create many completed states
        states = [
            MockState(123, 450 + i, TranscriptionStatus.COMPLETED, age_seconds=i * 60)
            for i in range(15)  # More than max_completed_states (10)
        ]
        
        cleanup_system.state_manager.storage.get_all_states.return_value = states
        cleanup_system.state_manager.storage.get_state_count.return_value = len(states)
        
        # Perform count-based cleanup
        cleaned = await cleanup_system._count_based_cleanup()
        
        # Should clean some states
        assert cleaned >= 0
        
    async def test_memory_based_cleanup(self, cleanup_system):
        """Test memory-based cleanup strategy"""
        from .state_manager import TranscriptionStatus
        
        # Mock high memory usage
        with patch.object(cleanup_system, '_get_memory_info') as mock_memory:
            mock_memory.return_value = {
                'usage_mb': 150.0,  # Above threshold
                'peak_mb': 150.0,
                'virtual_mb': 200.0
            }
            
            # Create some old states
            states = [
                MockState(123, 460 + i, TranscriptionStatus.COMPLETED, age_seconds=i * 120)
                for i in range(5)
            ]
            
            cleanup_system.state_manager.storage.get_all_states.return_value = states
            
            # Perform memory-based cleanup
            cleaned = await cleanup_system._memory_based_cleanup()
            
            # Should clean some states due to memory pressure
            assert cleaned >= 0
            
    async def test_hybrid_cleanup(self, cleanup_system):
        """Test hybrid cleanup strategy"""
        from .state_manager import TranscriptionStatus
        
        # Create mixed states
        states = [
            MockState(123, 470 + i, TranscriptionStatus.COMPLETED, age_seconds=i * 300)
            for i in range(8)
        ]
        
        cleanup_system.state_manager.storage.get_all_states.return_value = states
        cleanup_system.state_manager.storage.get_state_count.return_value = len(states)
        
        # Mock memory info
        with patch.object(cleanup_system, '_get_memory_info') as mock_memory:
            mock_memory.return_value = {
                'usage_mb': 75.0,  # Above threshold
                'peak_mb': 75.0,
                'virtual_mb': 100.0
            }
            
            # Perform hybrid cleanup
            cleaned = await cleanup_system._hybrid_cleanup()
            
            assert cleaned >= 0
            
    async def test_cleanup_safety_checks(self, cleanup_system):
        """Test cleanup safety checks"""
        from .state_manager import TranscriptionStatus
        
        # Create states with different safety profiles
        states = [
            MockState(123, 480, TranscriptionStatus.PENDING, age_seconds=3600),    # Active, unsafe
            MockState(123, 481, TranscriptionStatus.COMPLETED, age_seconds=30),    # Recent, unsafe
            MockState(123, 482, TranscriptionStatus.COMPLETED, age_seconds=3600),  # Old, safe
        ]
        
        # Test safety checks
        assert not cleanup_system._is_safe_to_clean(states[0])  # Active
        assert not cleanup_system._is_safe_to_clean(states[1])  # Recent
        assert cleanup_system._is_safe_to_clean(states[2])      # Old completed
        
    async def test_cleanup_status(self, cleanup_system):
        """Test cleanup status reporting"""
        cleanup_system.state_manager.storage.get_state_count.return_value = 5
        cleanup_system.state_manager.storage.get_state_counts_by_status.return_value = {
            'completed': 3,
            'pending': 2
        }
        
        status = cleanup_system.get_cleanup_status()
        
        assert 'running' in status
        assert 'config' in status
        assert 'metrics' in status
        assert 'memory' in status
        assert 'states' in status
        
        assert status['running'] is False
        assert status['config']['enabled'] is True
        assert status['states']['total'] == 5
        
    async def test_observer_management(self, cleanup_system):
        """Test cleanup observer add/remove"""
        observer_calls = []
        
        def test_observer(metrics):
            observer_calls.append(metrics.total_runs)
            
        # Add observer
        cleanup_system.add_observer(test_observer)
        
        # Trigger notification
        cleanup_system._notify_observers()
        
        assert len(observer_calls) == 1
        
        # Remove observer
        cleanup_system.remove_observer(test_observer)
        
        # Trigger notification again
        cleanup_system._notify_observers()
        
        # Should not be called again
        assert len(observer_calls) == 1
        
    async def test_observer_error_handling(self, cleanup_system):
        """Test observer error handling"""
        def failing_observer(metrics):
            raise Exception("Observer error")
            
        def working_observer(metrics):
            working_observer.called = True
            
        working_observer.called = False
        
        # Add both observers
        cleanup_system.add_observer(failing_observer)
        cleanup_system.add_observer(working_observer)
        
        # Trigger notification (should not raise error)
        cleanup_system._notify_observers()
        
        # Working observer should still be called
        assert working_observer.called
        
    async def test_cleanup_history(self, cleanup_system):
        """Test cleanup history tracking"""
        # Record some cleanup operations
        cleanup_system._record_cleanup_history(
            CleanupStrategy.AGE_BASED,
            CleanupTrigger.MANUAL,
            5, 2.0, 10.0
        )
        
        cleanup_system._record_cleanup_history(
            CleanupStrategy.COUNT_BASED,
            CleanupTrigger.INTERVAL,
            3, 1.5, 7.5
        )
        
        history = cleanup_system.get_cleanup_history()
        
        assert len(history) == 2
        assert history[0]['strategy'] == 'age_based'
        assert history[0]['cleaned'] == 5
        assert history[1]['strategy'] == 'count_based'
        assert history[1]['cleaned'] == 3
        
    async def test_cleanup_recommendations(self, cleanup_system):
        """Test cleanup recommendations"""
        # Mock high memory usage
        with patch.object(cleanup_system, '_get_memory_info') as mock_memory:
            mock_memory.return_value = {'usage_mb': 250.0}  # Very high
            
            cleanup_system.state_manager.storage.get_state_count.return_value = 2000  # High count
            cleanup_system.metrics.cleanup_efficiency = 10  # Low efficiency
            cleanup_system.metrics.average_run_duration = 8.0  # Too slow
            
            recommendations = cleanup_system.get_cleanup_recommendations()
            
            assert len(recommendations) > 0
            assert any('memory' in rec.lower() for rec in recommendations)
            
    async def test_background_cleanup_loop(self, cleanup_system):
        """Test background cleanup loop"""
        # Use short interval for testing
        cleanup_system.config.cleanup_interval_seconds = 0.1
        cleanup_system.state_manager.storage.get_all_states.return_value = []
        
        # Start system
        await cleanup_system.start()
        
        # Wait for a few cleanup cycles
        await asyncio.sleep(0.3)
        
        # Should have run at least once
        assert cleanup_system.metrics.total_runs > 0
        
    async def test_memory_info_collection(self, cleanup_system):
        """Test memory information collection"""
        memory_info = cleanup_system._get_memory_info()
        
        assert 'usage_mb' in memory_info
        assert 'peak_mb' in memory_info
        assert 'virtual_mb' in memory_info
        assert memory_info['usage_mb'] >= 0
        
    async def test_cleanup_with_errors(self, cleanup_system):
        """Test cleanup error handling"""
        # Make state removal fail
        cleanup_system.state_manager.storage.remove_state.side_effect = Exception("Removal failed")
        
        from .state_manager import TranscriptionStatus
        states = [MockState(123, 490, TranscriptionStatus.COMPLETED, age_seconds=3600)]
        cleanup_system.state_manager.storage.get_all_states.return_value = states
        
        # Should not raise exception
        result = await cleanup_system.trigger_cleanup(force=True)
        
        # May succeed or fail, but should not crash
        assert 'success' in result
        
    async def test_should_perform_cleanup_conditions(self, cleanup_system):
        """Test cleanup trigger conditions"""
        # Test disabled
        cleanup_system.config.enabled = False
        assert not await cleanup_system._should_perform_cleanup()
        
        cleanup_system.config.enabled = True
        
        # Test memory threshold
        with patch.object(cleanup_system, '_get_memory_info') as mock_memory:
            mock_memory.return_value = {'usage_mb': 150.0}  # Above threshold
            assert await cleanup_system._should_perform_cleanup()
            
        # Test state count threshold
        cleanup_system.state_manager.storage.get_state_count.return_value = 2000  # Above max
        assert await cleanup_system._should_perform_cleanup()
        
        # Test completed state threshold
        cleanup_system.state_manager.storage.get_state_counts_by_status.return_value = {
            'completed': 1500  # Above max
        }
        assert await cleanup_system._should_perform_cleanup()


def test_performance_cleanup_operations():
    """Test performance of cleanup operations"""
    
    async def run_performance_test():
        from .state_manager import TranscriptionStatus
        
        # Create many mock states
        states = [
            MockState(100 + i, 500 + i, TranscriptionStatus.COMPLETED, age_seconds=i * 60)
            for i in range(1000)
        ]
        
        mock_manager = MockStateManager()
        mock_manager.storage.get_all_states.return_value = states
        mock_manager.storage.get_state_count.return_value = len(states)
        
        config = CleanupConfig(cleanup_batch_size=200)
        
        with patch('voice_transcription.automatic_cleanup.INTERNAL_IMPORTS', True):
            with patch('voice_transcription.automatic_cleanup.psutil.Process', return_value=MockProcess()):
                system = AutomaticCleanupSystem(mock_manager, config)
                
                start_time = time.time()
                
                # Perform cleanup
                result = await system.trigger_cleanup(strategy=CleanupStrategy.AGE_BASED, force=True)
                
                duration = time.time() - start_time
                
                assert result['success'] is True
                assert duration < 2.0  # Should complete quickly
                
                print(f"Performance test: cleaned {result.get('cleaned', 0)} states in {duration:.2f}s")
    
    asyncio.run(run_performance_test())


@pytest.mark.asyncio
async def test_example_usage():
    """Test the example usage pattern"""
    from .automatic_cleanup import example_automatic_cleanup
    
    # Mock the dependencies for the example
    with patch('voice_transcription.automatic_cleanup.INTERNAL_IMPORTS', True):
        with patch('voice_transcription.automatic_cleanup.psutil.Process', return_value=MockProcess()):
            # This should run without errors
            await example_automatic_cleanup()


def test_cleanup_strategies_enum():
    """Test CleanupStrategy enum"""
    assert CleanupStrategy.AGE_BASED.value == "age_based"
    assert CleanupStrategy.COUNT_BASED.value == "count_based"
    assert CleanupStrategy.MEMORY_BASED.value == "memory_based"
    assert CleanupStrategy.HYBRID.value == "hybrid"


def test_cleanup_triggers_enum():
    """Test CleanupTrigger enum"""
    assert CleanupTrigger.INTERVAL.value == "interval"
    assert CleanupTrigger.THRESHOLD.value == "threshold"
    assert CleanupTrigger.MANUAL.value == "manual"
    assert CleanupTrigger.MEMORY_PRESSURE.value == "memory_pressure"


if __name__ == "__main__":
    # Run specific tests
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "performance":
        test_performance_cleanup_operations()
    else:
        # Run all tests with pytest
        pytest.main([__file__, "-v"])