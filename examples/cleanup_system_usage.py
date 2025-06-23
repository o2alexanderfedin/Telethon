#!/usr/bin/env python3
"""
Automatic Cleanup System Usage Examples

This module demonstrates how to use the automatic cleanup system
for voice message transcriptions in Telethon.

The cleanup system prevents memory growth by automatically removing
completed transcriptions after configurable time periods.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.client.transcription import CleanupConfig, CleanupStrategy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def example_basic_cleanup_usage():
    """
    Basic example of using the automatic cleanup system.
    """
    print("🧹 Basic Cleanup System Usage")
    print("=" * 40)
    
    # Create Telegram client (replace with your credentials)
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # The cleanup system is automatically initialized with default settings
        # You can check the current status
        status = client.get_cleanup_status()
        print(f"Cleanup enabled: {status['enabled']}")
        print(f"Background running: {status['background_running']}")
        print(f"Total states: {status['total_states']}")
        
        # Request a transcription (this will create a state)
        # Replace with actual chat and message
        try:
            result = await client.transcribe_audio(
                entity='your_chat',
                message=12345,  # Message ID with voice
                wait_for_result=True
            )
            print(f"Transcription: {result}")
        except Exception as e:
            print(f"Note: Transcription example failed (expected): {e}")
        
        # Check cleanup metrics
        metrics = client.get_cleanup_metrics()
        print(f"Total cleanup runs: {metrics.total_runs}")
        print(f"Total states cleaned: {metrics.total_cleaned}")
        
    finally:
        await client.disconnect()

async def example_custom_cleanup_configuration():
    """
    Example of customizing cleanup configuration.
    """
    print("\n⚙️  Custom Cleanup Configuration")
    print("=" * 40)
    
    # Create custom cleanup configuration
    custom_config = CleanupConfig(
        enabled=True,
        completed_ttl=1800,      # 30 minutes for completed transcriptions
        failed_ttl=900,          # 15 minutes for failed transcriptions
        pending_timeout=300,     # 5 minutes for stuck pending transcriptions
        max_total_states=500,    # Maximum 500 total states
        max_completed_states=200, # Maximum 200 completed states
        cleanup_batch_size=50,   # Clean max 50 states per operation
        cleanup_interval=180,    # Run cleanup every 3 minutes
        background_cleanup=True, # Enable background cleanup
        preserve_recent=30,      # Never clean states newer than 30 seconds
        max_cleanup_percentage=0.4  # Clean max 40% of states per run
    )
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Apply custom configuration
        client.configure_cleanup(custom_config)
        print("✅ Custom cleanup configuration applied")
        
        # Verify configuration
        status = client.get_cleanup_status()
        print(f"Completed TTL: {status['config']['completed_ttl']} seconds")
        print(f"Cleanup interval: {status['config']['cleanup_interval']} seconds")
        
    finally:
        await client.disconnect()

async def example_manual_cleanup_triggers():
    """
    Example of manually triggering cleanup operations.
    """
    print("\n🔧 Manual Cleanup Triggers")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Trigger cleanup with different strategies
        
        # 1. Age-based cleanup
        result = await client.trigger_cleanup(CleanupStrategy.AGE_BASED)
        print(f"Age-based cleanup: {result['cleaned']} states cleaned in {result['duration']:.2f}s")
        
        # 2. Count-based cleanup
        result = await client.trigger_cleanup(CleanupStrategy.COUNT_BASED)
        print(f"Count-based cleanup: {result['cleaned']} states cleaned in {result['duration']:.2f}s")
        
        # 3. Memory-based cleanup
        result = await client.trigger_cleanup(CleanupStrategy.MEMORY_BASED)
        print(f"Memory-based cleanup: {result['cleaned']} states cleaned in {result['duration']:.2f}s")
        
        # 4. Hybrid cleanup (recommended)
        result = await client.trigger_cleanup(CleanupStrategy.HYBRID)
        print(f"Hybrid cleanup: {result['cleaned']} states cleaned in {result['duration']:.2f}s")
        
        # 5. Clean all inactive transcriptions immediately
        cleaned_count = client.cleanup_all_transcriptions()
        print(f"Emergency cleanup: {cleaned_count} states cleaned")
        
    finally:
        await client.disconnect()

async def example_cleanup_monitoring():
    """
    Example of monitoring cleanup system performance.
    """
    print("\n📊 Cleanup Monitoring")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Get comprehensive status
        status = client.get_cleanup_status()
        
        print("System Status:")
        print(f"  Running: {status['running']}")
        print(f"  Enabled: {status['config']['enabled']}")
        print(f"  Strategy: {status['config']['strategy']}")
        
        print("\nState Information:")
        print(f"  Total states: {status['states']['total']}")
        print(f"  Active states: {status['states']['active']}")
        
        print("\nMetrics:")
        metrics = status['metrics']
        print(f"  Total runs: {metrics['total_runs']}")
        print(f"  Total cleaned: {metrics['total_cleaned']}")
        print(f"  Last run: {metrics['last_run']}")
        print(f"  Average duration: {metrics['average_duration']:.3f}s")
        print(f"  Cleanup efficiency: {metrics['cleanup_efficiency']:.1f} states/sec")
        
        print("\nMemory Information:")
        memory = status['memory']
        print(f"  Current usage: {memory['usage_mb']:.1f} MB")
        print(f"  Peak usage: {memory['peak_mb']:.1f} MB")
        
    finally:
        await client.disconnect()

async def example_background_cleanup_lifecycle():
    """
    Example of controlling background cleanup lifecycle.
    """
    print("\n🔄 Background Cleanup Lifecycle")
    print("=" * 40)
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        
        # Background cleanup starts automatically if enabled in config
        status = client.get_cleanup_status()
        print(f"Background cleanup running: {status['running']}")
        
        # You can stop background cleanup if needed
        client._stop_background_cleanup()
        print("✅ Background cleanup stopped")
        
        # And restart it
        client._start_background_cleanup()
        print("✅ Background cleanup restarted")
        
        # Let it run for a bit
        print("⏱️  Letting background cleanup run for 5 seconds...")
        await asyncio.sleep(5)
        
        # Check if any cleanup happened
        metrics = client.get_cleanup_metrics()
        print(f"Cleanup runs in 5 seconds: {metrics.total_runs}")
        
    finally:
        await client.disconnect()

async def example_production_configuration():
    """
    Example of production-ready cleanup configuration.
    """
    print("\n🏭 Production Configuration")
    print("=" * 40)
    
    # Production configuration for high-traffic applications
    production_config = CleanupConfig(
        enabled=True,
        
        # Conservative TTL values for production
        completed_ttl=7200,      # 2 hours for completed transcriptions
        failed_ttl=3600,         # 1 hour for failed transcriptions
        pending_timeout=600,     # 10 minutes for stuck pending transcriptions
        
        # Higher limits for production
        max_total_states=5000,   # Can handle more concurrent transcriptions
        max_completed_states=2000,
        cleanup_batch_size=100,  # Moderate batch size
        
        # More frequent cleanup for production
        cleanup_interval=300,    # Every 5 minutes
        background_cleanup=True,
        
        # Conservative safety settings
        preserve_recent=120,     # 2 minutes safety buffer
        max_cleanup_percentage=0.25,  # Clean max 25% per run
    )
    
    client = TelegramClient('session_name', api_id=12345, api_hash='your_api_hash')
    
    try:
        await client.start()
        client.configure_cleanup(production_config)
        
        print("✅ Production cleanup configuration applied")
        print("Key features:")
        print("  - Conservative TTL values for data retention")
        print("  - Higher state limits for scalability")
        print("  - Frequent cleanup to prevent memory growth")
        print("  - Safety buffers to prevent data loss")
        
        # Monitor over time
        for i in range(3):
            await asyncio.sleep(2)
            status = client.get_cleanup_status()
            print(f"  Check {i+1}: {status['states']['total']} total states")
        
    finally:
        await client.disconnect()

def example_configuration_presets():
    """
    Example of different configuration presets for various use cases.
    """
    print("\n📋 Configuration Presets")
    print("=" * 40)
    
    # 1. Conservative preset - keep data longer
    conservative = CleanupConfig(
        completed_ttl=86400,     # 24 hours
        failed_ttl=43200,        # 12 hours
        max_total_states=10000,
        cleanup_interval=600,    # 10 minutes
        max_cleanup_percentage=0.1  # Clean only 10% per run
    )
    print("📚 Conservative preset: Long retention, infrequent cleanup")
    
    # 2. Aggressive preset - clean quickly
    aggressive = CleanupConfig(
        completed_ttl=900,       # 15 minutes
        failed_ttl=300,          # 5 minutes
        max_total_states=100,
        cleanup_interval=60,     # 1 minute
        max_cleanup_percentage=0.8  # Clean up to 80% per run
    )
    print("🏎️  Aggressive preset: Short retention, frequent cleanup")
    
    # 3. Balanced preset - good for most applications
    balanced = CleanupConfig(
        completed_ttl=3600,      # 1 hour
        failed_ttl=1800,         # 30 minutes
        max_total_states=1000,
        cleanup_interval=300,    # 5 minutes
        max_cleanup_percentage=0.3  # Clean up to 30% per run
    )
    print("⚖️  Balanced preset: Moderate retention and cleanup")
    
    # 4. Memory-optimized preset - prioritize low memory usage
    memory_optimized = CleanupConfig(
        completed_ttl=1800,      # 30 minutes
        failed_ttl=600,          # 10 minutes
        max_total_states=200,    # Low limit
        cleanup_interval=120,    # 2 minutes
        preserve_recent=30,      # Short safety buffer
        max_cleanup_percentage=0.6
    )
    print("💾 Memory-optimized preset: Minimize memory usage")

async def main():
    """
    Run all usage examples.
    """
    print("🎯 Automatic Cleanup System Usage Examples")
    print("=" * 50)
    
    try:
        # Note: These examples require actual Telegram credentials
        # For demonstration purposes, we'll show the configuration examples
        
        example_configuration_presets()
        
        # Uncomment these to run with actual Telegram client:
        # await example_basic_cleanup_usage()
        # await example_custom_cleanup_configuration()
        # await example_manual_cleanup_triggers()
        # await example_cleanup_monitoring()
        # await example_background_cleanup_lifecycle()
        # await example_production_configuration()
        
        print("\n✅ All usage examples completed!")
        print("\nKey takeaways:")
        print("1. Cleanup system runs automatically in the background")
        print("2. Configure TTL values based on your data retention needs")
        print("3. Monitor cleanup metrics to optimize performance")
        print("4. Use manual triggers for emergency cleanup")
        print("5. Adjust batch sizes and intervals for your traffic")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())