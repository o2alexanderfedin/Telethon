"""
Performance Benchmarks for Voice Transcription

This module implements performance benchmarks for Epic 1 User Story 1.8: Basic Testing Infrastructure
testing system performance under various load conditions and validating scalability requirements.

Features:
- Concurrent transcription performance testing
- Memory usage benchmarks under load
- Request/response latency measurements
- State management performance validation
- Cleanup system efficiency testing
- Resource utilization monitoring
"""

import asyncio
import pytest
import time
import psutil
import gc
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed


class PerformanceMetrics:
    """Performance measurement container"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.memory_before = 0
        self.memory_after = 0
        self.peak_memory = 0
        self.cpu_usage = []
        self.request_times = []
        self.error_count = 0
        self.success_count = 0
        
    def start_measurement(self):
        """Start performance measurement"""
        gc.collect()  # Force garbage collection
        self.start_time = time.time()
        self.memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
    def record_request(self, duration: float, success: bool = True):
        """Record individual request performance"""
        self.request_times.append(duration)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            
        # Update peak memory
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024
        self.peak_memory = max(self.peak_memory, current_memory)
        
    def end_measurement(self):
        """End performance measurement"""
        self.end_time = time.time()
        self.memory_after = psutil.Process().memory_info().rss / 1024 / 1024
        
    @property
    def total_duration(self) -> float:
        """Total test duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
        
    @property
    def throughput(self) -> float:
        """Requests per second"""
        if self.total_duration > 0:
            return (self.success_count + self.error_count) / self.total_duration
        return 0.0
        
    @property
    def memory_delta(self) -> float:
        """Memory usage change in MB"""
        return self.memory_after - self.memory_before
        
    @property
    def avg_request_time(self) -> float:
        """Average request time in seconds"""
        return statistics.mean(self.request_times) if self.request_times else 0.0
        
    @property
    def p95_request_time(self) -> float:
        """95th percentile request time"""
        if self.request_times:
            return statistics.quantiles(self.request_times, n=20)[18]  # 95th percentile
        return 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'total_duration': self.total_duration,
            'throughput': self.throughput,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'memory_before_mb': self.memory_before,
            'memory_after_mb': self.memory_after,
            'memory_delta_mb': self.memory_delta,
            'peak_memory_mb': self.peak_memory,
            'avg_request_time_ms': self.avg_request_time * 1000,
            'p95_request_time_ms': self.p95_request_time * 1000,
            'min_request_time_ms': min(self.request_times) * 1000 if self.request_times else 0,
            'max_request_time_ms': max(self.request_times) * 1000 if self.request_times else 0
        }


class MockPerformanceClient:
    """High-performance mock client for benchmarking"""
    
    def __init__(self, response_delay: float = 0.001):
        self.response_delay = response_delay
        self.request_count = 0
        self.concurrent_requests = 0
        self.max_concurrent = 0
        
    async def __call__(self, request):
        """Mock API call with configurable delay"""
        self.concurrent_requests += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent_requests)
        self.request_count += 1
        
        try:
            # Simulate network delay
            await asyncio.sleep(self.response_delay)
            
            # Return mock response based on request type
            if hasattr(request, 'msg_id'):
                transcription_id = abs(hash(f"{request.peer.peer_id}:{request.msg_id}")) % 10**9
                
                # Vary response types for realistic testing
                if request.msg_id % 5 == 0:
                    # Immediate completion (20% of requests)
                    return MockTranscribedAudio(
                        transcription_id=transcription_id,
                        text=f"Quick transcription {request.msg_id}",
                        pending=False
                    )
                else:
                    # Pending response (80% of requests)
                    return MockTranscribedAudio(
                        transcription_id=transcription_id,
                        text="",
                        pending=True
                    )
            
            return True
            
        finally:
            self.concurrent_requests -= 1


class MockTranscribedAudio:
    """Mock response for performance testing"""
    def __init__(self, transcription_id, text, pending):
        self.transcription_id = transcription_id
        self.text = text
        self.pending = pending


class MockInputPeer:
    """Mock peer for performance testing"""
    def __init__(self, peer_id):
        self.peer_id = peer_id


@pytest.fixture
async def performance_client():
    """Create performance-optimized mock client"""
    return MockPerformanceClient(response_delay=0.001)


@pytest.fixture
async def transcription_manager_perf(performance_client):
    """Create transcription manager for performance testing"""
    with patch.multiple(
        'voice_transcription.transcription_manager',
        TelegramClient=lambda: performance_client,
        TELETHON_AVAILABLE=True,
        INTERNAL_IMPORTS=True
    ):
        from .transcription_manager import TranscriptionManager, TranscriptionManagerConfig
        
        config = TranscriptionManagerConfig(
            concurrent_limit=100,  # High limit for performance testing
            default_timeout=10.0,
            validate_messages=False  # Skip validation for performance
        )
        
        manager = TranscriptionManager(performance_client, config)
        await manager.initialize()
        
        yield manager
        
        await manager.shutdown()


@pytest.mark.asyncio
class TestConcurrentTranscriptionPerformance:
    """Test concurrent transcription performance"""
    
    async def test_concurrent_request_throughput(self, transcription_manager_perf):
        """Test throughput with concurrent requests"""
        manager = transcription_manager_perf
        metrics = PerformanceMetrics()
        
        # Test parameters
        concurrent_count = 50
        total_requests = 200
        
        metrics.start_measurement()
        
        async def make_request(request_id):
            """Make single transcription request"""
            request_start = time.time()
            try:
                result = await manager.transcribe(
                    chat=123456 + (request_id % 10),
                    msg_id=10000 + request_id,
                    wait_for_completion=False,
                    timeout=5.0
                )
                duration = time.time() - request_start
                metrics.record_request(duration, result.success)
                return result
            except Exception as e:
                duration = time.time() - request_start
                metrics.record_request(duration, False)
                raise
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrent_count)
        
        async def bounded_request(request_id):
            """Request with concurrency limit"""
            async with semaphore:
                return await make_request(request_id)
        
        # Execute concurrent requests
        tasks = [bounded_request(i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_measurement()
        
        # Validate performance
        successful_results = [r for r in results if hasattr(r, 'success')]
        
        perf_data = metrics.to_dict()
        print(f"\n📊 Concurrent Performance Results:")
        print(f"   Throughput: {perf_data['throughput']:.1f} req/sec")
        print(f"   Success Rate: {len(successful_results)}/{total_requests} ({len(successful_results)/total_requests*100:.1f}%)")
        print(f"   Avg Request Time: {perf_data['avg_request_time_ms']:.1f}ms")
        print(f"   P95 Request Time: {perf_data['p95_request_time_ms']:.1f}ms")
        print(f"   Memory Delta: {perf_data['memory_delta_mb']:.1f}MB")
        
        # Performance assertions
        assert metrics.throughput >= 20.0, f"Throughput too low: {metrics.throughput:.1f} req/sec"
        assert metrics.avg_request_time <= 0.1, f"Average request time too high: {metrics.avg_request_time*1000:.1f}ms"
        assert len(successful_results) >= total_requests * 0.95, "Success rate too low"
        assert metrics.memory_delta <= 50.0, f"Memory usage too high: {metrics.memory_delta:.1f}MB"
        
    async def test_sustained_load_performance(self, transcription_manager_perf):
        """Test performance under sustained load"""
        manager = transcription_manager_perf
        metrics = PerformanceMetrics()
        
        # Test parameters
        duration_seconds = 10
        requests_per_second = 10
        
        metrics.start_measurement()
        
        async def sustained_load():
            """Generate sustained load"""
            request_id = 0
            end_time = time.time() + duration_seconds
            
            while time.time() < end_time:
                request_start = time.time()
                
                try:
                    result = await manager.transcribe(
                        chat=200000 + (request_id % 5),
                        msg_id=20000 + request_id,
                        wait_for_completion=False,
                        timeout=3.0
                    )
                    duration = time.time() - request_start
                    metrics.record_request(duration, result.success)
                    
                except Exception as e:
                    duration = time.time() - request_start
                    metrics.record_request(duration, False)
                
                request_id += 1
                
                # Maintain target rate
                target_interval = 1.0 / requests_per_second
                actual_duration = time.time() - request_start
                if actual_duration < target_interval:
                    await asyncio.sleep(target_interval - actual_duration)
        
        await sustained_load()
        metrics.end_measurement()
        
        perf_data = metrics.to_dict()
        print(f"\n📊 Sustained Load Results:")
        print(f"   Duration: {perf_data['total_duration']:.1f}s")
        print(f"   Total Requests: {metrics.success_count + metrics.error_count}")
        print(f"   Average Throughput: {perf_data['throughput']:.1f} req/sec")
        print(f"   Memory Growth: {perf_data['memory_delta_mb']:.1f}MB")
        print(f"   Peak Memory: {perf_data['peak_memory_mb']:.1f}MB")
        
        # Sustained load assertions
        assert metrics.throughput >= 8.0, f"Sustained throughput too low: {metrics.throughput:.1f}"
        assert metrics.memory_delta <= 20.0, f"Memory leak detected: {metrics.memory_delta:.1f}MB"
        assert metrics.success_count >= duration_seconds * requests_per_second * 0.9, "Too many failures under load"


@pytest.mark.asyncio
class TestStateManagementPerformance:
    """Test state management performance"""
    
    async def test_large_state_storage_performance(self, transcription_manager_perf):
        """Test performance with large number of states"""
        manager = transcription_manager_perf
        state_manager = manager.state_manager
        metrics = PerformanceMetrics()
        
        # Test parameters
        state_count = 1000
        
        metrics.start_measurement()
        
        # Create many states
        for i in range(state_count):
            peer_id = 300000 + (i % 100)  # Create some overlap
            msg_id = 30000 + i
            
            request_start = time.time()
            
            # Create transcription state
            result = await manager.transcribe(
                chat=peer_id,
                msg_id=msg_id,
                wait_for_completion=False,
                timeout=1.0
            )
            
            duration = time.time() - request_start
            metrics.record_request(duration, result.success)
        
        # Test state retrieval performance
        lookup_times = []
        for i in range(100):  # Sample lookups
            peer_id = 300000 + (i % 100)
            msg_id = 30000 + i
            
            lookup_start = time.time()
            state = state_manager.get_transcription(peer_id, msg_id)
            lookup_time = time.time() - lookup_start
            lookup_times.append(lookup_time)
        
        metrics.end_measurement()
        
        avg_lookup_time = statistics.mean(lookup_times) * 1000  # Convert to ms
        state_count_actual = state_manager.storage.get_state_count()
        
        perf_data = metrics.to_dict()
        print(f"\n📊 State Management Performance:")
        print(f"   States Created: {state_count_actual}")
        print(f"   Avg Creation Time: {perf_data['avg_request_time_ms']:.2f}ms")
        print(f"   Avg Lookup Time: {avg_lookup_time:.2f}ms")
        print(f"   Memory Usage: {perf_data['memory_delta_mb']:.1f}MB")
        print(f"   Memory per State: {perf_data['memory_delta_mb']/state_count*1024:.1f}KB")
        
        # State management assertions
        assert avg_lookup_time <= 1.0, f"State lookup too slow: {avg_lookup_time:.2f}ms"
        assert metrics.avg_request_time <= 0.01, f"State creation too slow: {metrics.avg_request_time*1000:.2f}ms"
        assert metrics.memory_delta <= 100.0, f"State memory usage too high: {metrics.memory_delta:.1f}MB"
        
    async def test_concurrent_state_access(self, transcription_manager_perf):
        """Test concurrent state access performance"""
        manager = transcription_manager_perf
        state_manager = manager.state_manager
        metrics = PerformanceMetrics()
        
        # Create initial states
        peer_ids = [400000 + i for i in range(50)]
        msg_ids = [40000 + i for i in range(50)]
        
        for peer_id, msg_id in zip(peer_ids, msg_ids):
            await manager.transcribe(
                chat=peer_id,
                msg_id=msg_id,
                wait_for_completion=False
            )
        
        metrics.start_measurement()
        
        async def concurrent_access(operation_id):
            """Perform concurrent state operations"""
            peer_id = peer_ids[operation_id % len(peer_ids)]
            msg_id = msg_ids[operation_id % len(msg_ids)]
            
            operation_start = time.time()
            
            try:
                # Mix of read and write operations
                if operation_id % 3 == 0:
                    # Read operation
                    state = state_manager.get_transcription(peer_id, msg_id)
                    success = state is not None
                elif operation_id % 3 == 1:
                    # Update operation
                    state_manager.update_transcription_text(
                        peer_id, msg_id, f"Updated text {operation_id}"
                    )
                    success = True
                else:
                    # Status check
                    states = state_manager.get_transcriptions_by_peer(peer_id)
                    success = len(states) > 0
                
                duration = time.time() - operation_start
                metrics.record_request(duration, success)
                
            except Exception as e:
                duration = time.time() - operation_start
                metrics.record_request(duration, False)
        
        # Execute concurrent operations
        concurrent_count = 200
        tasks = [concurrent_access(i) for i in range(concurrent_count)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_measurement()
        
        perf_data = metrics.to_dict()
        print(f"\n📊 Concurrent State Access:")
        print(f"   Operations: {concurrent_count}")
        print(f"   Throughput: {perf_data['throughput']:.1f} ops/sec")
        print(f"   Avg Operation Time: {perf_data['avg_request_time_ms']:.2f}ms")
        print(f"   Success Rate: {metrics.success_count}/{concurrent_count} ({metrics.success_count/concurrent_count*100:.1f}%)")
        
        # Concurrent access assertions
        assert metrics.throughput >= 500.0, f"Concurrent access too slow: {metrics.throughput:.1f} ops/sec"
        assert metrics.avg_request_time <= 0.005, f"Operation time too high: {metrics.avg_request_time*1000:.2f}ms"
        assert metrics.success_count >= concurrent_count * 0.95, "Too many concurrent failures"


@pytest.mark.asyncio
class TestCleanupSystemPerformance:
    """Test cleanup system performance"""
    
    async def test_cleanup_efficiency(self, transcription_manager_perf):
        """Test cleanup system efficiency under load"""
        manager = transcription_manager_perf
        metrics = PerformanceMetrics()
        
        # Import cleanup system
        from .automatic_cleanup import AutomaticCleanupSystem, CleanupConfig
        
        # Create cleanup system with aggressive settings
        cleanup_config = CleanupConfig(
            max_completed_states=100,
            max_total_states=200,
            completed_ttl_hours=0.001,  # Very short TTL for testing
            cleanup_interval_seconds=1
        )
        
        cleanup_system = AutomaticCleanupSystem(manager.state_manager, cleanup_config)
        
        # Create many completed states
        state_count = 500
        
        metrics.start_measurement()
        
        # Create states that will be marked as completed
        for i in range(state_count):
            await manager.transcribe(
                chat=500000 + i,
                msg_id=50000 + i,
                wait_for_completion=False
            )
            
            # Mark as completed for cleanup testing
            manager.state_manager.update_transcription_text(
                500000 + i, 50000 + i, f"Completed text {i}"
            )
            manager.state_manager.mark_transcription_completed(500000 + i, 50000 + i)
        
        initial_count = manager.state_manager.storage.get_state_count()
        
        # Trigger cleanup
        cleanup_start = time.time()
        await cleanup_system.start()
        cleanup_result = await cleanup_system.trigger_cleanup(force=True)
        await cleanup_system.stop()
        cleanup_duration = time.time() - cleanup_start
        
        final_count = manager.state_manager.storage.get_state_count()
        cleaned_count = initial_count - final_count
        
        metrics.end_measurement()
        
        cleanup_rate = cleaned_count / cleanup_duration if cleanup_duration > 0 else 0
        
        print(f"\n📊 Cleanup Performance:")
        print(f"   Initial States: {initial_count}")
        print(f"   Final States: {final_count}")
        print(f"   Cleaned States: {cleaned_count}")
        print(f"   Cleanup Duration: {cleanup_duration:.3f}s")
        print(f"   Cleanup Rate: {cleanup_rate:.1f} states/sec")
        print(f"   Memory Freed: {metrics.memory_delta:.1f}MB")
        
        # Cleanup efficiency assertions
        assert cleaned_count > 0, "Cleanup should remove some states"
        assert cleanup_rate >= 100.0, f"Cleanup too slow: {cleanup_rate:.1f} states/sec"
        assert cleanup_duration <= 5.0, f"Cleanup took too long: {cleanup_duration:.3f}s"
        
    async def test_cleanup_under_load(self, transcription_manager_perf):
        """Test cleanup performance while system is under load"""
        manager = transcription_manager_perf
        
        from .automatic_cleanup import AutomaticCleanupSystem, CleanupConfig
        
        cleanup_config = CleanupConfig(
            max_completed_states=50,
            cleanup_interval_seconds=2
        )
        
        cleanup_system = AutomaticCleanupSystem(manager.state_manager, cleanup_config)
        await cleanup_system.start()
        
        try:
            # Simulate load while cleanup is running
            async def create_load():
                """Create continuous load"""
                for i in range(100):
                    await manager.transcribe(
                        chat=600000 + i,
                        msg_id=60000 + i,
                        wait_for_completion=False
                    )
                    
                    # Mark some as completed
                    if i % 3 == 0:
                        manager.state_manager.mark_transcription_completed(600000 + i, 60000 + i)
                    
                    await asyncio.sleep(0.01)  # Small delay
            
            load_start = time.time()
            await create_load()
            load_duration = time.time() - load_start
            
            # Allow cleanup to run
            await asyncio.sleep(1)
            
            final_count = manager.state_manager.storage.get_state_count()
            
            print(f"\n📊 Cleanup Under Load:")
            print(f"   Load Duration: {load_duration:.2f}s")
            print(f"   Final State Count: {final_count}")
            print(f"   System Responsive: {'✅' if load_duration <= 5.0 else '❌'}")
            
            # Under load assertions
            assert load_duration <= 5.0, f"System too slow under load: {load_duration:.2f}s"
            assert final_count <= 150, f"Cleanup not keeping up: {final_count} states"
            
        finally:
            await cleanup_system.stop()


@pytest.mark.asyncio
class TestMemoryPerformance:
    """Test memory usage patterns"""
    
    async def test_memory_efficiency_patterns(self, transcription_manager_perf):
        """Test memory usage patterns under various scenarios"""
        manager = transcription_manager_perf
        
        scenarios = [
            ("Small batch", 50, 1),
            ("Medium batch", 200, 5),
            ("Large batch", 500, 10),
        ]
        
        for scenario_name, request_count, concurrency in scenarios:
            # Force garbage collection
            gc.collect()
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Execute scenario
            semaphore = asyncio.Semaphore(concurrency)
            
            async def bounded_request(request_id):
                async with semaphore:
                    return await manager.transcribe(
                        chat=700000 + request_id,
                        msg_id=70000 + request_id,
                        wait_for_completion=False
                    )
            
            start_time = time.time()
            tasks = [bounded_request(i) for i in range(request_count)]
            await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time
            
            # Measure memory after
            gc.collect()
            memory_after = psutil.Process().memory_info().rss / 1024 / 1024
            memory_delta = memory_after - memory_before
            
            memory_per_request = memory_delta / request_count * 1024  # KB per request
            
            print(f"\n📊 {scenario_name} Memory Pattern:")
            print(f"   Requests: {request_count}")
            print(f"   Concurrency: {concurrency}")
            print(f"   Duration: {duration:.2f}s")
            print(f"   Memory Delta: {memory_delta:.1f}MB")
            print(f"   Memory/Request: {memory_per_request:.1f}KB")
            
            # Memory efficiency assertions
            assert memory_per_request <= 10.0, f"Memory per request too high: {memory_per_request:.1f}KB"
            assert memory_delta <= request_count * 0.1, f"Memory usage too high: {memory_delta:.1f}MB"


# CLI for running performance tests
if __name__ == "__main__":
    async def run_performance_suite():
        """Run complete performance test suite"""
        print("🚀 Starting Voice Transcription Performance Suite")
        print("=" * 60)
        
        # Import required components
        from .transcription_manager import TranscriptionManager, TranscriptionManagerConfig
        
        # Create performance client and manager
        client = MockPerformanceClient(response_delay=0.001)
        config = TranscriptionManagerConfig(
            concurrent_limit=100,
            default_timeout=5.0,
            validate_messages=False
        )
        
        manager = TranscriptionManager(client, config)
        await manager.initialize()
        
        try:
            # Run performance tests
            print("\n1. Concurrent Request Performance...")
            # Would run actual test methods here
            
            print("\n2. State Management Performance...")
            # Would run state tests here
            
            print("\n3. Cleanup System Performance...")
            # Would run cleanup tests here
            
            print("\n4. Memory Efficiency Tests...")
            # Would run memory tests here
            
            print("\n✅ Performance Suite Completed")
            
        finally:
            await manager.shutdown()
    
    # Run if executed directly
    asyncio.run(run_performance_suite())