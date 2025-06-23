"""
Automatic Cleanup System for Voice Transcription

This module implements Epic 1 User Story 1.6: Automatic Cleanup System
providing background cleanup tasks to prevent memory growth by automatically
removing completed transcriptions after configurable TTL.

Features:
- Background cleanup tasks with configurable intervals
- Multiple cleanup strategies (age-based, count-based, memory-based)
- Non-interfering cleanup that doesn't affect active transcriptions
- Comprehensive metrics and monitoring
- Graceful error handling and recovery
- Memory pressure detection and response
"""

import asyncio
import logging
import threading
import weakref
import gc
import psutil
import os
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import time

try:
    from .state_manager import TranscriptionStateManager, TranscriptionState, TranscriptionStatus
    INTERNAL_IMPORTS = True
except ImportError:
    # Fallback for development
    INTERNAL_IMPORTS = False
    TranscriptionStateManager = Any
    TranscriptionState = Any
    TranscriptionStatus = Any


logger = logging.getLogger(__name__)


class CleanupStrategy(Enum):
    """Cleanup strategy types"""
    AGE_BASED = "age_based"          # Clean by age (TTL)
    COUNT_BASED = "count_based"      # Clean oldest when count exceeded
    MEMORY_BASED = "memory_based"    # Clean when memory pressure detected
    HYBRID = "hybrid"                # Combination of strategies


class CleanupTrigger(Enum):
    """Cleanup trigger types"""
    INTERVAL = "interval"            # Time-based intervals
    THRESHOLD = "threshold"          # Count/memory thresholds
    MANUAL = "manual"                # Manual trigger
    MEMORY_PRESSURE = "memory_pressure"  # System memory pressure


@dataclass
class CleanupConfig:
    """Configuration for automatic cleanup system"""
    
    # General settings
    enabled: bool = True
    strategy: CleanupStrategy = CleanupStrategy.HYBRID
    
    # Age-based cleanup
    completed_ttl_seconds: int = 3600        # 1 hour for completed
    failed_ttl_seconds: int = 1800           # 30 minutes for failed
    expired_ttl_seconds: int = 900           # 15 minutes for expired
    
    # Interval-based cleanup
    cleanup_interval_seconds: int = 300      # 5 minutes
    background_cleanup_enabled: bool = True
    
    # Count-based cleanup
    max_completed_states: int = 1000         # Max completed states to keep
    max_total_states: int = 1500             # Max total states
    cleanup_batch_size: int = 100            # Max states to clean per batch
    
    # Memory-based cleanup  
    memory_threshold_mb: int = 100           # Memory threshold in MB
    memory_check_interval: int = 60          # Memory check interval in seconds
    aggressive_cleanup_threshold_mb: int = 200  # Aggressive cleanup threshold
    
    # Performance settings
    max_cleanup_duration_seconds: float = 5.0  # Max time per cleanup cycle
    cleanup_thread_pool_size: int = 2          # Background thread pool size
    
    # Monitoring and metrics
    enable_metrics: bool = True
    metrics_retention_hours: int = 24
    log_cleanup_operations: bool = True
    
    # Safety settings
    preserve_recent_seconds: int = 60        # Never clean states newer than this
    max_cleanup_percentage: float = 0.5      # Max % of states to clean per run


@dataclass
class CleanupMetrics:
    """Metrics for cleanup operations"""
    total_runs: int = 0
    total_cleaned: int = 0
    total_errors: int = 0
    last_run_time: Optional[datetime] = None
    last_run_duration: float = 0.0
    last_run_cleaned: int = 0
    average_run_duration: float = 0.0
    memory_savings_mb: float = 0.0
    
    # Strategy-specific metrics
    age_based_cleaned: int = 0
    count_based_cleaned: int = 0
    memory_based_cleaned: int = 0
    
    # Performance metrics
    peak_memory_usage_mb: float = 0.0
    cleanup_efficiency: float = 0.0  # states cleaned per second
    
    def update_run_metrics(self, duration: float, cleaned: int, memory_saved: float = 0.0):
        """Update metrics after a cleanup run"""
        self.total_runs += 1
        self.total_cleaned += cleaned
        self.last_run_time = datetime.now(timezone.utc)
        self.last_run_duration = duration
        self.last_run_cleaned = cleaned
        self.memory_savings_mb += memory_saved
        
        # Update average duration
        if self.total_runs > 1:
            self.average_run_duration = (
                (self.average_run_duration * (self.total_runs - 1) + duration) / self.total_runs
            )
        else:
            self.average_run_duration = duration
            
        # Update efficiency
        if duration > 0:
            self.cleanup_efficiency = cleaned / duration


class AutomaticCleanupSystem:
    """
    Automatic cleanup system for transcription states.
    
    This system provides background cleanup of completed transcriptions
    to prevent memory growth while ensuring active transcriptions are
    never affected.
    """
    
    def __init__(
        self,
        state_manager: TranscriptionStateManager,
        config: Optional[CleanupConfig] = None
    ):
        """
        Initialize the automatic cleanup system.
        
        Args:
            state_manager: TranscriptionStateManager to clean up
            config: Optional cleanup configuration
        """
        if not INTERNAL_IMPORTS:
            raise ImportError("Required voice transcription modules not available")
            
        self.state_manager = state_manager
        self.config = config or CleanupConfig()
        
        # System state
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self._lock = threading.RLock()
        
        # Metrics and monitoring
        self.metrics = CleanupMetrics()
        self._observers: List[Callable[[CleanupMetrics], None]] = []
        self._last_memory_check = datetime.now(timezone.utc)
        
        # Cleanup history for analysis
        self._cleanup_history: List[Dict[str, Any]] = []
        self._max_history_size = 100
        
        logger.info(f"Automatic cleanup system initialized with strategy: {self.config.strategy.value}")
        
    async def start(self):
        """Start the automatic cleanup system"""
        if self._running:
            logger.warning("Cleanup system already running")
            return
            
        try:
            self._running = True
            
            # Start thread pool for background operations
            if self.config.cleanup_thread_pool_size > 0:
                self._thread_pool = ThreadPoolExecutor(
                    max_workers=self.config.cleanup_thread_pool_size,
                    thread_name_prefix="cleanup"
                )
                
            # Start background cleanup task if enabled
            if self.config.background_cleanup_enabled:
                self._cleanup_task = asyncio.create_task(self._background_cleanup_loop())
                
            logger.info("Automatic cleanup system started")
            
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start cleanup system: {e}")
            raise
            
    async def stop(self):
        """Stop the automatic cleanup system"""
        if not self._running:
            return
            
        try:
            self._running = False
            
            # Cancel background task
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                self._cleanup_task = None
                
            # Shutdown thread pool
            if self._thread_pool:
                self._thread_pool.shutdown(wait=True)
                self._thread_pool = None
                
            logger.info("Automatic cleanup system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping cleanup system: {e}")
            
    async def trigger_cleanup(
        self,
        strategy: Optional[CleanupStrategy] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Manually trigger a cleanup operation.
        
        Args:
            strategy: Specific cleanup strategy to use
            force: Force cleanup even if not needed
            
        Returns:
            Cleanup results dictionary
        """
        if not self._running and not force:
            logger.warning("Cleanup system not running")
            return {'success': False, 'error': 'System not running'}
            
        strategy = strategy or self.config.strategy
        
        try:
            start_time = time.time()
            logger.info(f"Manual cleanup triggered with strategy: {strategy.value}")
            
            result = await self._perform_cleanup(
                strategy=strategy,
                trigger=CleanupTrigger.MANUAL
            )
            
            duration = time.time() - start_time
            logger.info(f"Manual cleanup completed in {duration:.2f}s, cleaned {result.get('cleaned', 0)} states")
            
            return result
            
        except Exception as e:
            logger.error(f"Manual cleanup failed: {e}")
            return {'success': False, 'error': str(e)}
            
    def get_cleanup_status(self) -> Dict[str, Any]:
        """Get current cleanup system status"""
        with self._lock:
            memory_info = self._get_memory_info()
            
            return {
                'running': self._running,
                'config': {
                    'enabled': self.config.enabled,
                    'strategy': self.config.strategy.value,
                    'cleanup_interval': self.config.cleanup_interval_seconds,
                    'completed_ttl': self.config.completed_ttl_seconds,
                    'background_enabled': self.config.background_cleanup_enabled
                },
                'metrics': {
                    'total_runs': self.metrics.total_runs,
                    'total_cleaned': self.metrics.total_cleaned,
                    'last_run': self.metrics.last_run_time.isoformat() if self.metrics.last_run_time else None,
                    'last_duration': self.metrics.last_run_duration,
                    'average_duration': self.metrics.average_run_duration,
                    'cleanup_efficiency': self.metrics.cleanup_efficiency
                },
                'memory': memory_info,
                'states': {
                    'total': self.state_manager.storage.get_state_count(),
                    'by_status': self.state_manager.storage.get_state_counts_by_status(),
                    'active': len(self.state_manager.get_active_transcriptions())
                }
            }
            
    def add_observer(self, observer: Callable[[CleanupMetrics], None]):
        """Add cleanup metrics observer"""
        with self._lock:
            self._observers.append(observer)
            
    def remove_observer(self, observer: Callable[[CleanupMetrics], None]):
        """Remove cleanup metrics observer"""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
                
    async def _background_cleanup_loop(self):
        """Background cleanup loop"""
        logger.info("Background cleanup loop started")
        
        try:
            while self._running:
                try:
                    # Wait for next cleanup interval
                    await asyncio.sleep(self.config.cleanup_interval_seconds)
                    
                    if not self._running:
                        break
                        
                    # Check if cleanup is needed
                    if await self._should_perform_cleanup():
                        await self._perform_cleanup(
                            strategy=self.config.strategy,
                            trigger=CleanupTrigger.INTERVAL
                        )
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in background cleanup loop: {e}")
                    self.metrics.total_errors += 1
                    
                    # Wait before retrying on error
                    await asyncio.sleep(min(60, self.config.cleanup_interval_seconds))
                    
        except asyncio.CancelledError:
            logger.info("Background cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Background cleanup loop failed: {e}")
        finally:
            logger.info("Background cleanup loop stopped")
            
    async def _should_perform_cleanup(self) -> bool:
        """Check if cleanup should be performed"""
        if not self.config.enabled:
            return False
            
        # Check memory pressure
        memory_info = self._get_memory_info()
        if memory_info['usage_mb'] > self.config.memory_threshold_mb:
            logger.debug(f"Memory threshold exceeded: {memory_info['usage_mb']}MB > {self.config.memory_threshold_mb}MB")
            return True
            
        # Check state counts
        total_states = self.state_manager.storage.get_state_count()
        if total_states > self.config.max_total_states:
            logger.debug(f"State count threshold exceeded: {total_states} > {self.config.max_total_states}")
            return True
            
        # Check completed state counts
        state_counts = self.state_manager.storage.get_state_counts_by_status()
        completed_count = state_counts.get('completed', 0) + state_counts.get('failed', 0)
        if completed_count > self.config.max_completed_states:
            logger.debug(f"Completed state threshold exceeded: {completed_count} > {self.config.max_completed_states}")
            return True
            
        # Always cleanup periodically even if no thresholds exceeded
        return True
        
    async def _perform_cleanup(
        self,
        strategy: CleanupStrategy,
        trigger: CleanupTrigger
    ) -> Dict[str, Any]:
        """Perform cleanup operation"""
        start_time = time.time()
        start_memory = self._get_memory_info()['usage_mb']
        cleaned_count = 0
        
        try:
            logger.debug(f"Starting cleanup: strategy={strategy.value}, trigger={trigger.value}")
            
            if strategy == CleanupStrategy.AGE_BASED:
                cleaned_count = await self._age_based_cleanup()
                self.metrics.age_based_cleaned += cleaned_count
                
            elif strategy == CleanupStrategy.COUNT_BASED:
                cleaned_count = await self._count_based_cleanup()
                self.metrics.count_based_cleaned += cleaned_count
                
            elif strategy == CleanupStrategy.MEMORY_BASED:
                cleaned_count = await self._memory_based_cleanup()
                self.metrics.memory_based_cleaned += cleaned_count
                
            elif strategy == CleanupStrategy.HYBRID:
                cleaned_count = await self._hybrid_cleanup()
                
            # Force garbage collection after cleanup
            gc.collect()
            
            # Calculate metrics
            duration = time.time() - start_time
            end_memory = self._get_memory_info()['usage_mb']
            memory_saved = max(0, start_memory - end_memory)
            
            # Update metrics
            self.metrics.update_run_metrics(duration, cleaned_count, memory_saved)
            
            # Record cleanup history
            self._record_cleanup_history(strategy, trigger, cleaned_count, duration, memory_saved)
            
            # Notify observers
            self._notify_observers()
            
            result = {
                'success': True,
                'strategy': strategy.value,
                'trigger': trigger.value,
                'cleaned': cleaned_count,
                'duration': duration,
                'memory_saved_mb': memory_saved,
                'efficiency': cleaned_count / duration if duration > 0 else 0
            }
            
            if self.config.log_cleanup_operations and cleaned_count > 0:
                logger.info(f"Cleanup completed: {cleaned_count} states in {duration:.2f}s, {memory_saved:.1f}MB saved")
                
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.total_errors += 1
            
            logger.error(f"Cleanup failed after {duration:.2f}s: {e}")
            return {
                'success': False,
                'error': str(e),
                'duration': duration,
                'cleaned': cleaned_count
            }
            
    async def _age_based_cleanup(self) -> int:
        """Perform age-based cleanup"""
        total_cleaned = 0
        current_time = datetime.now(timezone.utc)
        
        # Clean completed states
        completed_cutoff = current_time - timedelta(seconds=self.config.completed_ttl_seconds)
        total_cleaned += self._cleanup_states_by_criteria(
            lambda state: (state.status == TranscriptionStatus.COMPLETED and 
                          state.last_update < completed_cutoff)
        )
        
        # Clean failed states
        failed_cutoff = current_time - timedelta(seconds=self.config.failed_ttl_seconds)
        total_cleaned += self._cleanup_states_by_criteria(
            lambda state: (state.status == TranscriptionStatus.FAILED and 
                          state.last_update < failed_cutoff)
        )
        
        # Clean expired states
        expired_cutoff = current_time - timedelta(seconds=self.config.expired_ttl_seconds)
        total_cleaned += self._cleanup_states_by_criteria(
            lambda state: (state.status == TranscriptionStatus.EXPIRED and 
                          state.last_update < expired_cutoff)
        )
        
        return total_cleaned
        
    async def _count_based_cleanup(self) -> int:
        """Perform count-based cleanup"""
        total_states = self.state_manager.storage.get_state_count()
        
        if total_states <= self.config.max_total_states:
            return 0
            
        # Calculate how many to clean
        target_count = int(self.config.max_total_states * 0.8)  # Clean to 80% of max
        to_clean = total_states - target_count
        to_clean = min(to_clean, self.config.cleanup_batch_size)
        
        # Get oldest non-active states
        all_states = self.state_manager.storage.get_all_states()
        inactive_states = [state for state in all_states if not state.is_active]
        
        # Sort by last_update (oldest first)
        inactive_states.sort(key=lambda s: s.last_update)
        
        # Clean oldest states
        cleaned = 0
        for state in inactive_states[:to_clean]:
            if self._is_safe_to_clean(state):
                self.state_manager.storage.remove_state(state.peer_id, state.msg_id)
                cleaned += 1
                
        return cleaned
        
    async def _memory_based_cleanup(self) -> int:
        """Perform memory-based cleanup"""
        memory_info = self._get_memory_info()
        
        if memory_info['usage_mb'] < self.config.memory_threshold_mb:
            return 0
            
        # Determine cleanup intensity based on memory pressure
        if memory_info['usage_mb'] > self.config.aggressive_cleanup_threshold_mb:
            # Aggressive cleanup
            batch_size = self.config.cleanup_batch_size * 2
            preserve_recent = self.config.preserve_recent_seconds // 2
        else:
            # Normal cleanup
            batch_size = self.config.cleanup_batch_size
            preserve_recent = self.config.preserve_recent_seconds
            
        # Clean oldest completed/failed states first
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=preserve_recent)
        
        return self._cleanup_states_by_criteria(
            lambda state: (not state.is_active and 
                          state.last_update < cutoff_time),
            max_count=batch_size
        )
        
    async def _hybrid_cleanup(self) -> int:
        """Perform hybrid cleanup combining multiple strategies"""
        total_cleaned = 0
        
        # First, do age-based cleanup for very old states
        total_cleaned += await self._age_based_cleanup()
        
        # Then check if we still need more cleanup
        memory_info = self._get_memory_info()
        total_states = self.state_manager.storage.get_state_count()
        
        # Do count-based cleanup if needed
        if total_states > self.config.max_total_states:
            total_cleaned += await self._count_based_cleanup()
            
        # Do memory-based cleanup if needed
        if memory_info['usage_mb'] > self.config.memory_threshold_mb:
            total_cleaned += await self._memory_based_cleanup()
            
        return total_cleaned
        
    def _cleanup_states_by_criteria(
        self,
        criteria_func: Callable[[TranscriptionState], bool],
        max_count: Optional[int] = None
    ) -> int:
        """Clean up states matching criteria"""
        all_states = self.state_manager.storage.get_all_states()
        to_clean = []
        
        for state in all_states:
            if criteria_func(state) and self._is_safe_to_clean(state):
                to_clean.append(state)
                
        # Limit cleanup count
        if max_count:
            to_clean = to_clean[:max_count]
            
        # Apply maximum cleanup percentage safety limit
        total_states = len(all_states)
        max_allowed = int(total_states * self.config.max_cleanup_percentage)
        to_clean = to_clean[:max_allowed]
        
        # Remove states
        cleaned = 0
        for state in to_clean:
            try:
                self.state_manager.storage.remove_state(state.peer_id, state.msg_id)
                cleaned += 1
            except Exception as e:
                logger.error(f"Failed to clean state {state.state_key}: {e}")
                
        return cleaned
        
    def _is_safe_to_clean(self, state: TranscriptionState) -> bool:
        """Check if a state is safe to clean"""
        # Never clean active states
        if state.is_active:
            return False
            
        # Never clean very recent states
        min_age = timedelta(seconds=self.config.preserve_recent_seconds)
        if state.time_since_update < min_age:
            return False
            
        return True
        
    def _get_memory_info(self) -> Dict[str, float]:
        """Get current memory usage information"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            usage_mb = memory_info.rss / 1024 / 1024
            
            # Update peak usage
            if usage_mb > self.metrics.peak_memory_usage_mb:
                self.metrics.peak_memory_usage_mb = usage_mb
                
            return {
                'usage_mb': usage_mb,
                'peak_mb': self.metrics.peak_memory_usage_mb,
                'virtual_mb': memory_info.vms / 1024 / 1024
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory info: {e}")
            return {'usage_mb': 0.0, 'peak_mb': 0.0, 'virtual_mb': 0.0}
            
    def _record_cleanup_history(
        self,
        strategy: CleanupStrategy,
        trigger: CleanupTrigger,
        cleaned: int,
        duration: float,
        memory_saved: float
    ):
        """Record cleanup operation in history"""
        with self._lock:
            self._cleanup_history.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'strategy': strategy.value,
                'trigger': trigger.value,
                'cleaned': cleaned,
                'duration': duration,
                'memory_saved_mb': memory_saved
            })
            
            # Limit history size
            if len(self._cleanup_history) > self._max_history_size:
                self._cleanup_history = self._cleanup_history[-self._max_history_size:]
                
    def _notify_observers(self):
        """Notify cleanup metrics observers"""
        for observer in self._observers:
            try:
                observer(self.metrics)
            except Exception as e:
                logger.error(f"Observer error: {e}")
                
    def get_cleanup_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent cleanup history"""
        with self._lock:
            return self._cleanup_history[-limit:]
            
    def get_cleanup_recommendations(self) -> List[str]:
        """Get cleanup configuration recommendations"""
        recommendations = []
        
        memory_info = self._get_memory_info()
        state_count = self.state_manager.storage.get_state_count()
        
        # Memory recommendations
        if memory_info['usage_mb'] > self.config.aggressive_cleanup_threshold_mb:
            recommendations.append(
                f"High memory usage ({memory_info['usage_mb']:.1f}MB). "
                f"Consider lowering TTL or increasing cleanup frequency."
            )
            
        # State count recommendations
        if state_count > self.config.max_total_states * 1.5:
            recommendations.append(
                f"Very high state count ({state_count}). "
                f"Consider aggressive cleanup or lower max_total_states."
            )
            
        # Efficiency recommendations
        if self.metrics.cleanup_efficiency < 50:  # states per second
            recommendations.append(
                "Low cleanup efficiency. Consider increasing cleanup_batch_size."
            )
            
        # Frequency recommendations
        if self.metrics.average_run_duration > self.config.max_cleanup_duration_seconds:
            recommendations.append(
                f"Cleanup taking too long ({self.metrics.average_run_duration:.1f}s). "
                f"Consider reducing batch size or increasing cleanup frequency."
            )
            
        return recommendations


# Example usage
async def example_automatic_cleanup():
    """Example of how to use the AutomaticCleanupSystem"""
    
    # Create state manager (would be real in practice)
    state_manager = None  # Placeholder
    
    # Create custom config
    config = CleanupConfig(
        enabled=True,
        strategy=CleanupStrategy.HYBRID,
        completed_ttl_seconds=1800,  # 30 minutes
        cleanup_interval_seconds=180,  # 3 minutes
        max_completed_states=500,
        memory_threshold_mb=50
    )
    
    # Create cleanup system
    cleanup_system = AutomaticCleanupSystem(state_manager, config)
    
    # Add metrics observer
    def log_cleanup_metrics(metrics: CleanupMetrics):
        print(f"Cleanup metrics: {metrics.total_runs} runs, {metrics.total_cleaned} cleaned")
        
    cleanup_system.add_observer(log_cleanup_metrics)
    
    try:
        # Start automatic cleanup
        await cleanup_system.start()
        
        # Manual cleanup trigger
        result = await cleanup_system.trigger_cleanup(strategy=CleanupStrategy.AGE_BASED)
        print(f"Manual cleanup result: {result}")
        
        # Get status
        status = cleanup_system.get_cleanup_status()
        print(f"Cleanup status: {status}")
        
        # Get recommendations
        recommendations = cleanup_system.get_cleanup_recommendations()
        for rec in recommendations:
            print(f"Recommendation: {rec}")
            
    finally:
        await cleanup_system.stop()


if __name__ == "__main__":
    print("Automatic Cleanup System for Voice Transcription")
    print("See example_automatic_cleanup() function for usage patterns")
    asyncio.run(example_automatic_cleanup())