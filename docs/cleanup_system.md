# Automatic Cleanup System Documentation

## Overview

The Automatic Cleanup System is part of Epic 1 User Story 1.6, designed to prevent memory growth by automatically removing completed voice message transcriptions after configurable time periods. This system ensures that your application maintains optimal performance even during high-volume usage.

## Features

- **Background cleanup tasks** with configurable intervals
- **Multiple cleanup strategies** (age-based, count-based, memory-based, hybrid)
- **Non-interfering cleanup** that doesn't affect active transcriptions
- **Comprehensive metrics and monitoring**
- **Graceful error handling and recovery**
- **Memory pressure detection and response**
- **Safety mechanisms** to prevent accidental data loss

## Architecture

### Core Components

1. **CleanupConfig** - Configuration dataclass for cleanup behavior
2. **CleanupMetrics** - Metrics tracking for cleanup operations
3. **CleanupStrategy** - Enum defining cleanup strategies
4. **TranscriptionMixin** - Extended with cleanup functionality

### Cleanup Strategies

#### Age-Based Cleanup
Removes transcriptions based on their age:
- **Completed transcriptions**: Default 1 hour TTL
- **Failed transcriptions**: Default 30 minutes TTL
- **Stuck pending transcriptions**: Default 5 minutes TTL

#### Count-Based Cleanup
Removes oldest transcriptions when limits are exceeded:
- **Max total states**: Default 1000 transcriptions
- **Max completed states**: Default 500 completed transcriptions
- **Batch processing**: Default 100 transcriptions per cleanup cycle

#### Memory-Based Cleanup
Removes transcriptions when memory pressure is detected:
- **Memory threshold**: Default 100MB
- **Aggressive cleanup threshold**: Default 200MB
- **Dynamic batch sizing** based on memory pressure

#### Hybrid Cleanup (Recommended)
Combines all strategies for optimal performance:
1. Age-based cleanup for very old states
2. Count-based cleanup if limits exceeded
3. Memory-based cleanup if memory pressure detected

## Configuration

### Basic Configuration

```python
from telethon.client.transcription import CleanupConfig, CleanupStrategy

# Default configuration
config = CleanupConfig()

# Custom configuration
custom_config = CleanupConfig(
    enabled=True,
    completed_ttl=3600,      # 1 hour for completed transcriptions
    failed_ttl=1800,         # 30 minutes for failed transcriptions
    pending_timeout=300,     # 5 minutes for stuck pending transcriptions
    max_total_states=1000,   # Maximum total transcription states
    max_completed_states=500, # Maximum completed states to keep
    cleanup_batch_size=100,  # Max states to clean per operation
    cleanup_interval=300,    # Background cleanup every 5 minutes
    background_cleanup=True, # Enable background cleanup task
    preserve_recent=60,      # Never clean states newer than 1 minute
    max_cleanup_percentage=0.3  # Max 30% of states cleaned per run
)

# Apply configuration
client.configure_cleanup(custom_config)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | True | Enable/disable cleanup system |
| `completed_ttl` | int | 3600 | TTL for completed transcriptions (seconds) |
| `failed_ttl` | int | 1800 | TTL for failed transcriptions (seconds) |
| `pending_timeout` | int | 300 | Timeout for stuck pending transcriptions (seconds) |
| `max_total_states` | int | 1000 | Maximum total transcription states |
| `max_completed_states` | int | 500 | Maximum completed states to keep |
| `cleanup_batch_size` | int | 100 | Maximum states to clean per batch |
| `cleanup_interval` | int | 300 | Background cleanup interval (seconds) |
| `background_cleanup` | bool | True | Enable background cleanup task |
| `preserve_recent` | int | 60 | Never clean states newer than this (seconds) |
| `max_cleanup_percentage` | float | 0.3 | Maximum percentage of states to clean per run |

## Usage Examples

### Basic Usage

```python
import asyncio
from telethon import TelegramClient

async def main():
    client = TelegramClient('session', api_id, api_hash)
    await client.start()
    
    # Cleanup system is automatically enabled with default settings
    
    # Request transcription
    result = await client.transcribe_audio(
        entity='chat_id',
        message=message_id,
        wait_for_result=True
    )
    
    # Cleanup happens automatically in the background
    # Check cleanup status
    status = client.get_cleanup_status()
    print(f"Total states: {status['total_states']}")
    
    await client.disconnect()

asyncio.run(main())
```

### Manual Cleanup Triggers

```python
# Trigger cleanup manually with different strategies
result = await client.trigger_cleanup(CleanupStrategy.AGE_BASED)
print(f"Cleaned {result['cleaned']} states in {result['duration']:.2f}s")

# Emergency cleanup - remove all inactive transcriptions
cleaned_count = client.cleanup_all_transcriptions()
print(f"Emergency cleanup: {cleaned_count} states removed")
```

### Monitoring and Metrics

```python
# Get comprehensive cleanup status
status = client.get_cleanup_status()

print("System Status:")
print(f"  Running: {status['running']}")
print(f"  Enabled: {status['config']['enabled']}")
print(f"  Total states: {status['states']['total']}")
print(f"  Active states: {status['states']['active']}")

print("Metrics:")
metrics = status['metrics']
print(f"  Total runs: {metrics['total_runs']}")
print(f"  Total cleaned: {metrics['total_cleaned']}")
print(f"  Average duration: {metrics['average_duration']:.3f}s")
print(f"  Cleanup efficiency: {metrics['cleanup_efficiency']:.1f} states/sec")

print("Memory:")
memory = status['memory']
print(f"  Current usage: {memory['usage_mb']:.1f} MB")
print(f"  Peak usage: {memory['peak_mb']:.1f} MB")
```

## Configuration Presets

### Conservative Preset
Best for applications that need long data retention:
```python
conservative_config = CleanupConfig(
    completed_ttl=86400,     # 24 hours
    failed_ttl=43200,        # 12 hours
    max_total_states=10000,
    cleanup_interval=600,    # 10 minutes
    max_cleanup_percentage=0.1  # Clean only 10% per run
)
```

### Aggressive Preset
Best for memory-constrained environments:
```python
aggressive_config = CleanupConfig(
    completed_ttl=900,       # 15 minutes
    failed_ttl=300,          # 5 minutes
    max_total_states=100,
    cleanup_interval=60,     # 1 minute
    max_cleanup_percentage=0.8  # Clean up to 80% per run
)
```

### Production Preset
Balanced configuration for production environments:
```python
production_config = CleanupConfig(
    completed_ttl=7200,      # 2 hours
    failed_ttl=3600,         # 1 hour
    pending_timeout=600,     # 10 minutes
    max_total_states=5000,
    max_completed_states=2000,
    cleanup_interval=300,    # 5 minutes
    preserve_recent=120,     # 2 minutes safety buffer
    max_cleanup_percentage=0.25  # Conservative cleanup rate
)
```

## Safety Mechanisms

The cleanup system includes several safety mechanisms to prevent data loss:

1. **Active State Protection**: Never cleans transcriptions that are still pending
2. **Recent State Protection**: Never cleans states newer than `preserve_recent` seconds
3. **Batch Size Limits**: Limits how many states can be cleaned in a single operation
4. **Percentage Limits**: Limits what percentage of total states can be cleaned per run
5. **Error Recovery**: Continues operating even if individual cleanup operations fail

## Performance Considerations

### Memory Usage
- Each transcription state uses approximately 1-2 KB of memory
- 1000 states ≈ 1-2 MB memory usage
- Configure `max_total_states` based on available memory

### Cleanup Frequency
- More frequent cleanup (shorter `cleanup_interval`) reduces memory usage
- Less frequent cleanup reduces CPU overhead
- Balance based on your application's traffic patterns

### Batch Sizing
- Larger `cleanup_batch_size` values are more efficient
- Smaller values reduce impact on application performance
- Recommended: 50-200 states per batch

## Troubleshooting

### High Memory Usage
```python
# Check current memory usage
status = client.get_cleanup_status()
memory_mb = status['memory']['usage_mb']

if memory_mb > 100:  # Adjust threshold as needed
    # Trigger aggressive cleanup
    result = await client.trigger_cleanup(CleanupStrategy.MEMORY_BASED)
    print(f"Emergency cleanup: {result['cleaned']} states cleaned")
    
    # Or clean all inactive states
    cleaned = client.cleanup_all_transcriptions()
    print(f"Cleaned all inactive: {cleaned} states")
```

### Cleanup Not Running
```python
# Check if cleanup is enabled and running
status = client.get_cleanup_status()

if not status['config']['enabled']:
    # Enable cleanup
    config = CleanupConfig(enabled=True)
    client.configure_cleanup(config)

if not status['running']:
    # Start background cleanup
    client._start_background_cleanup()
```

### Performance Issues
```python
# Check cleanup efficiency
status = client.get_cleanup_status()
efficiency = status['metrics']['cleanup_efficiency']

if efficiency < 10:  # states per second
    # Increase batch size
    config = CleanupConfig(cleanup_batch_size=200)
    client.configure_cleanup(config)
```

## Integration with Transcription Workflow

The cleanup system is automatically integrated with the transcription workflow:

1. **Transcription Start**: State is created and tracked
2. **Transcription Updates**: State is updated but not cleaned (active protection)
3. **Transcription Complete**: State becomes eligible for cleanup after `preserve_recent` seconds
4. **Background Cleanup**: Automatically removes old states based on configuration
5. **Manual Cleanup**: Can be triggered at any time for immediate cleanup

## Metrics and Monitoring

### Available Metrics
- `total_runs`: Total number of cleanup operations performed
- `total_cleaned`: Total number of states cleaned across all runs
- `last_cleanup`: Timestamp of last cleanup operation
- `last_cleanup_count`: Number of states cleaned in last operation
- `average_cleanup_time`: Average time per cleanup operation

### Monitoring Best Practices
1. Monitor memory usage trends over time
2. Track cleanup efficiency (states cleaned per second)
3. Set up alerts for high memory usage or cleanup failures
4. Review cleanup frequency vs. traffic patterns
5. Adjust configuration based on observed performance

## API Reference

### CleanupConfig
Configuration dataclass for cleanup system behavior.

### CleanupMetrics
Metrics tracking for cleanup operations.

### CleanupStrategy
Enum defining available cleanup strategies:
- `AGE_BASED`: Clean by age (TTL)
- `COUNT_BASED`: Clean oldest when count exceeded
- `MEMORY_BASED`: Clean when memory pressure detected
- `HYBRID`: Combination of all strategies

### TranscriptionMixin Methods

#### `configure_cleanup(config: CleanupConfig)`
Apply new cleanup configuration.

#### `get_cleanup_metrics() -> CleanupMetrics`
Get current cleanup metrics.

#### `get_cleanup_status() -> Dict[str, Any]`
Get comprehensive cleanup system status.

#### `trigger_cleanup(strategy: CleanupStrategy = CleanupStrategy.HYBRID) -> Dict[str, Any]`
Manually trigger cleanup operation.

#### `cleanup_all_transcriptions() -> int`
Clean up all inactive transcriptions immediately.

## Best Practices

1. **Start with default configuration** and adjust based on observed behavior
2. **Monitor memory usage** and cleanup metrics regularly
3. **Use hybrid strategy** for best overall performance
4. **Set conservative `preserve_recent`** values to prevent data loss
5. **Test cleanup behavior** in development before production deployment
6. **Configure alerts** for high memory usage or cleanup failures
7. **Document your configuration choices** for team knowledge sharing

## Thread Safety

The cleanup system is fully thread-safe:
- Uses async locks for state access
- Background cleanup runs in separate asyncio task
- Manual cleanup operations are properly synchronized
- Safe to call from multiple contexts simultaneously

## Error Handling

The cleanup system includes comprehensive error handling:
- Individual cleanup failures don't stop the system
- Errors are logged with appropriate detail levels
- Background cleanup continues running despite errors
- Cleanup metrics track error counts for monitoring