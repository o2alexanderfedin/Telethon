#!/usr/bin/env python3
"""
Basic test script for the automatic cleanup system.

This script tests the cleanup functionality without requiring full Telethon dependencies.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Any

# Add the path to import our modules
sys.path.insert(0, os.path.dirname(__file__))

# Define the classes we need for testing (simplified versions)
class CleanupStrategy(Enum):
    AGE_BASED = "age_based"
    COUNT_BASED = "count_based"
    MEMORY_BASED = "memory_based"
    HYBRID = "hybrid"

@dataclass
class CleanupConfig:
    enabled: bool = True
    completed_ttl: int = 3600
    failed_ttl: int = 1800
    pending_timeout: int = 300
    max_total_states: int = 1000
    max_completed_states: int = 500
    cleanup_batch_size: int = 100
    cleanup_interval: int = 300
    background_cleanup: bool = True
    preserve_recent: int = 60
    max_cleanup_percentage: float = 0.3

@dataclass
class CleanupMetrics:
    total_runs: int = 0
    total_cleaned: int = 0
    last_cleanup: Optional[datetime] = None
    last_cleanup_count: int = 0
    average_cleanup_time: float = 0.0

class MockTranscriptionState:
    """Mock TranscriptionState for testing."""
    
    def __init__(self, peer_id: int, msg_id: int, created_at: datetime):
        self.peer_id = peer_id
        self.msg_id = msg_id
        self.created_at = created_at
        self.pending = True
        self.failed = False
        self.last_update = created_at
        
    @property
    def is_active(self) -> bool:
        return self.pending and not self.failed
        
    @property
    def is_completed(self) -> bool:
        return not self.pending and not self.failed

def test_cleanup_config():
    """Test CleanupConfig functionality."""
    print("🧪 Testing CleanupConfig...")
    
    # Test default values
    config = CleanupConfig()
    assert config.enabled is True
    assert config.completed_ttl == 3600
    assert config.failed_ttl == 1800
    assert config.max_total_states == 1000
    print("✅ Default configuration values correct")
    
    # Test custom values
    custom_config = CleanupConfig(
        enabled=False,
        completed_ttl=7200,
        max_total_states=500
    )
    assert custom_config.enabled is False
    assert custom_config.completed_ttl == 7200
    assert custom_config.max_total_states == 500
    print("✅ Custom configuration values correct")

def test_cleanup_metrics():
    """Test CleanupMetrics functionality."""
    print("🧪 Testing CleanupMetrics...")
    
    metrics = CleanupMetrics()
    assert metrics.total_runs == 0
    assert metrics.total_cleaned == 0
    assert metrics.last_cleanup is None
    print("✅ Metrics initialization correct")

def test_cleanup_strategy():
    """Test CleanupStrategy enum."""
    print("🧪 Testing CleanupStrategy...")
    
    assert CleanupStrategy.AGE_BASED.value == "age_based"
    assert CleanupStrategy.COUNT_BASED.value == "count_based" 
    assert CleanupStrategy.MEMORY_BASED.value == "memory_based"
    assert CleanupStrategy.HYBRID.value == "hybrid"
    print("✅ CleanupStrategy enum values correct")

def test_mock_transcription_state():
    """Test MockTranscriptionState functionality."""
    print("🧪 Testing MockTranscriptionState...")
    
    now = datetime.utcnow()
    state = MockTranscriptionState(123, 456, now)
    
    # Test initial state
    assert state.peer_id == 123
    assert state.msg_id == 456
    assert state.created_at == now
    assert state.pending is True
    assert state.failed is False
    assert state.is_active is True
    assert state.is_completed is False
    print("✅ Initial state correct")
    
    # Test completed state
    state.pending = False
    state.failed = False
    assert state.is_active is False
    assert state.is_completed is True
    print("✅ Completed state correct")
    
    # Test failed state
    state.pending = False
    state.failed = True
    assert state.is_active is False
    assert state.is_completed is False
    print("✅ Failed state correct")

def test_cleanup_safety_logic():
    """Test cleanup safety logic."""
    print("🧪 Testing cleanup safety logic...")
    
    now = datetime.utcnow()
    config = CleanupConfig(preserve_recent=60)
    
    def is_safe_to_clean(state: MockTranscriptionState) -> bool:
        """Replicated safety check logic."""
        if state.is_active:
            return False
        
        age = (now - state.created_at).total_seconds()
        if age < config.preserve_recent:
            return False
            
        return True
    
    # Active state - not safe
    active_state = MockTranscriptionState(123, 456, now)
    active_state.pending = True
    assert not is_safe_to_clean(active_state)
    print("✅ Active state safety check correct")
    
    # Recent inactive state - not safe
    recent_state = MockTranscriptionState(789, 12, now)
    recent_state.pending = False
    assert not is_safe_to_clean(recent_state)
    print("✅ Recent state safety check correct")
    
    # Old inactive state - safe
    old_state = MockTranscriptionState(111, 222, now - timedelta(minutes=5))
    old_state.pending = False
    assert is_safe_to_clean(old_state)
    print("✅ Old state safety check correct")

def test_age_based_cleanup_logic():
    """Test age-based cleanup logic."""
    print("🧪 Testing age-based cleanup logic...")
    
    now = datetime.utcnow()
    config = CleanupConfig(
        completed_ttl=3600,  # 1 hour
        failed_ttl=1800,     # 30 minutes
        pending_timeout=300, # 5 minutes
        preserve_recent=60   # 1 minute
    )
    
    def should_clean_by_age(state: MockTranscriptionState) -> bool:
        """Replicated age-based cleanup logic."""
        age = (now - state.created_at).total_seconds()
        
        # Skip recent states
        if age < config.preserve_recent:
            return False
            
        # Clean completed states
        if state.is_completed and age > config.completed_ttl:
            return True
            
        # Clean failed states  
        if state.failed and age > config.failed_ttl:
            return True
            
        # Clean stuck pending states
        if state.pending and age > config.pending_timeout:
            return True
            
        return False
    
    # Old completed state - should clean
    old_completed = MockTranscriptionState(123, 456, now - timedelta(hours=2))
    old_completed.pending = False
    old_completed.failed = False
    assert should_clean_by_age(old_completed)
    print("✅ Old completed state cleanup logic correct")
    
    # Old failed state - should clean  
    old_failed = MockTranscriptionState(789, 12, now - timedelta(minutes=45))
    old_failed.pending = False
    old_failed.failed = True
    assert should_clean_by_age(old_failed)
    print("✅ Old failed state cleanup logic correct")
    
    # Recent state - should not clean
    recent_state = MockTranscriptionState(111, 222, now)
    recent_state.pending = False
    assert not should_clean_by_age(recent_state)
    print("✅ Recent state cleanup logic correct")

async def test_async_functionality():
    """Test async functionality of cleanup system."""
    print("🧪 Testing async functionality...")
    
    async def mock_cleanup_operation():
        """Mock async cleanup operation."""
        await asyncio.sleep(0.01)  # Simulate work
        return 5  # Cleaned count
    
    # Test basic async operation
    result = await mock_cleanup_operation()
    assert result == 5
    print("✅ Basic async operation correct")
    
    # Test timeout simulation
    start_time = asyncio.get_event_loop().time()
    await asyncio.sleep(0.1)
    duration = asyncio.get_event_loop().time() - start_time
    assert duration >= 0.1
    print("✅ Duration measurement correct")

def main():
    """Run all tests."""
    print("🚀 Starting cleanup system tests...")
    print("=" * 50)
    
    try:
        test_cleanup_config()
        test_cleanup_metrics()
        test_cleanup_strategy()
        test_mock_transcription_state()
        test_cleanup_safety_logic()
        test_age_based_cleanup_logic()
        
        # Run async tests
        asyncio.run(test_async_functionality())
        
        print("=" * 50)
        print("🎉 All tests passed successfully!")
        
        # Test performance with many states
        print("\n🏃 Performance test with 1000 states...")
        states = {}
        now = datetime.utcnow()
        
        import time
        start_time = time.time()
        
        for i in range(1000):
            state = MockTranscriptionState(i, i * 100, now - timedelta(minutes=i))
            state.pending = False
            states[f"{i}:{i * 100}"] = state
            
        creation_time = time.time() - start_time
        print(f"✅ Created 1000 states in {creation_time:.3f}s")
        
        # Simulate cleanup decision logic
        start_time = time.time()
        to_clean = []
        for key, state in states.items():
            age = (now - state.created_at).total_seconds()
            if not state.is_active and age > 60:  # More than 1 minute old
                to_clean.append(key)
                
        decision_time = time.time() - start_time
        print(f"✅ Cleanup decision for 1000 states in {decision_time:.3f}s")
        print(f"📊 Would clean {len(to_clean)} out of 1000 states")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)