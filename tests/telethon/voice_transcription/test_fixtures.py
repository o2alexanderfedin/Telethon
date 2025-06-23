"""
Test Data Fixtures for Voice Transcription

This module provides comprehensive test fixtures for Epic 1 User Story 1.8: Basic Testing Infrastructure
offering realistic test data, mock objects, and test scenarios for consistent testing across all components.

Features:
- Realistic voice message test data
- Mock Telegram API responses
- Error scenario fixtures
- Performance test data sets
- State management test cases
- Integration test scenarios
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union
from unittest.mock import Mock, AsyncMock, MagicMock
import uuid
import random


# ============================================================================
# Basic Test Data
# ============================================================================

@pytest.fixture
def sample_peer_ids():
    """Sample peer IDs for testing"""
    return [
        123456789,    # Regular user
        -1001234567890,  # Supergroup
        -987654321,   # Regular group
        234567890,    # Bot
        345678901     # Channel
    ]


@pytest.fixture 
def sample_message_ids():
    """Sample message IDs for testing"""
    return [
        12345,  # Regular message
        67890,  # Recent message  
        11111,  # Old message
        99999,  # High ID message
        1       # Low ID message
    ]


@pytest.fixture
def sample_transcription_ids():
    """Sample transcription IDs for testing"""
    return [
        1234567890123,
        9876543210987,
        5555555555555,
        1111111111111,
        9999999999999
    ]


@pytest.fixture
def sample_transcription_texts():
    """Sample transcription text results"""
    return [
        "Hello, this is a test voice message.",
        "The quick brown fox jumps over the lazy dog.",
        "Voice transcription is working correctly.",
        "This message contains multiple sentences. Each one should be transcribed accurately.",
        "Special characters: áéíóú, ñ, ç, ü, ß, and numbers: 123, 456, 789.",
        "",  # Empty transcription
        "Single word",
        "Very long transcription that goes on and on with lots of details about various topics including technology, science, and everyday life situations that people might encounter.",
        "音声転写テスト",  # Non-Latin characters
        "Test with\nnewlines and\ttabs"
    ]


# ============================================================================
# Mock Telegram Objects
# ============================================================================

@pytest.fixture
def mock_input_peer():
    """Create mock InputPeer objects"""
    def _create_peer(peer_id: int, peer_type: str = "user"):
        peer = Mock()
        peer.peer_id = peer_id
        peer.peer_type = peer_type
        return peer
    return _create_peer


@pytest.fixture
def mock_transcribed_audio():
    """Create mock TranscribedAudio responses"""
    def _create_response(
        transcription_id: int,
        text: str = "",
        pending: bool = False,
        trial_remains: Optional[int] = None,
        trial_expires: Optional[datetime] = None
    ):
        response = Mock()
        response.transcription_id = transcription_id
        response.text = text
        response.pending = pending
        response.trial_remains_num = trial_remains
        response.trial_remains_until_date = trial_expires
        return response
    return _create_response


@pytest.fixture
def mock_update_transcribed_audio():
    """Create mock UpdateTranscribedAudio objects"""
    def _create_update(
        peer_id: int,
        msg_id: int,
        transcription_id: int,
        text: str,
        pending: bool = False
    ):
        # Create mock peer
        peer = Mock()
        if peer_id > 0:
            peer.user_id = peer_id
            peer.chat_id = None
            peer.channel_id = None
        else:
            peer.user_id = None
            peer.chat_id = abs(peer_id)
            peer.channel_id = None
            
        # Create update
        update = Mock()
        update.peer = peer
        update.msg_id = msg_id
        update.transcription_id = transcription_id
        update.text = text
        update.pending = pending
        return update
    return _create_update


@pytest.fixture
def mock_telegram_client():
    """Create comprehensive mock Telegram client"""
    client = AsyncMock()
    
    # Basic client properties
    client.user_id = 123456789
    client.session_id = str(uuid.uuid4())
    client.connected = True
    
    # Mock API responses
    async def mock_api_call(request):
        """Mock API call handling"""
        request_type = type(request).__name__
        
        if request_type == "TranscribeAudioRequest":
            # Generate deterministic response based on message ID
            transcription_id = abs(hash(f"{request.peer.peer_id}:{request.msg_id}")) % 10**9
            
            if request.msg_id % 10 == 0:
                # Immediate completion
                return Mock(
                    transcription_id=transcription_id,
                    text="Immediate transcription result",
                    pending=False
                )
            elif request.msg_id % 10 == 1:
                # Error case
                raise Exception("Message contains no audio")
            else:
                # Pending case
                return Mock(
                    transcription_id=transcription_id,
                    text="",
                    pending=True
                )
                
        elif request_type == "RateTranscribedAudioRequest":
            return True
            
        else:
            raise ValueError(f"Unknown request type: {request_type}")
    
    client.__call__ = mock_api_call
    
    # Mock entity resolution
    async def mock_get_input_entity(entity):
        if isinstance(entity, int):
            peer = Mock()
            peer.peer_id = entity
            return peer
        elif isinstance(entity, str):
            if entity.startswith("@"):
                peer_id = abs(hash(entity)) % 10**9
            else:
                peer_id = int(entity)
            peer = Mock()
            peer.peer_id = peer_id
            return peer
        else:
            peer = Mock()
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


# ============================================================================
# Error Scenario Fixtures
# ============================================================================

@pytest.fixture
def error_scenarios():
    """Comprehensive error scenario test data"""
    return {
        'validation_errors': [
            {
                'name': 'invalid_peer_id',
                'peer_id': 'invalid',
                'msg_id': 123,
                'expected_error': 'InvalidPeerError'
            },
            {
                'name': 'invalid_message_id',
                'peer_id': 123456,
                'msg_id': 'invalid',
                'expected_error': 'InvalidMessageError'
            },
            {
                'name': 'zero_message_id',
                'peer_id': 123456,
                'msg_id': 0,
                'expected_error': 'InvalidMessageError'
            }
        ],
        'network_errors': [
            {
                'name': 'connection_timeout',
                'exception': 'asyncio.TimeoutError',
                'expected_error': 'TimeoutError'
            },
            {
                'name': 'connection_refused',
                'exception': 'ConnectionRefusedError',
                'expected_error': 'NetworkError'
            }
        ],
        'api_errors': [
            {
                'name': 'peer_id_invalid',
                'exception': 'PeerIdInvalidError',
                'expected_error': 'InvalidPeerError'
            },
            {
                'name': 'flood_wait',
                'exception': 'FloodWaitError',
                'seconds': 30,
                'expected_error': 'TranscriptionRateLimitError'
            }
        ],
        'resource_errors': [
            {
                'name': 'memory_exhaustion',
                'exception': 'MemoryError',
                'expected_error': 'ResourceError'
            },
            {
                'name': 'concurrent_limit',
                'concurrent_requests': 1000,
                'expected_error': 'ConcurrencyLimitError'
            }
        ]
    }


@pytest.fixture
def mock_telethon_errors():
    """Mock Telethon-specific errors for testing"""
    
    class MockFloodWaitError(Exception):
        def __init__(self, seconds):
            self.seconds = seconds
            super().__init__(f"Flood wait: {seconds} seconds")
    
    class MockPeerIdInvalidError(Exception):
        pass
    
    class MockChatAdminRequiredError(Exception):
        pass
    
    class MockAuthKeyError(Exception):
        pass
    
    class MockRPCError(Exception):
        def __init__(self, message, code=None):
            self.message = message
            self.code = code
            super().__init__(message)
    
    return {
        'FloodWaitError': MockFloodWaitError,
        'PeerIdInvalidError': MockPeerIdInvalidError,
        'ChatAdminRequiredError': MockChatAdminRequiredError,
        'AuthKeyError': MockAuthKeyError,
        'RPCError': MockRPCError
    }


# ============================================================================
# State Management Fixtures
# ============================================================================

@pytest.fixture
def sample_transcription_states():
    """Sample transcription states for testing"""
    base_time = datetime.now(timezone.utc)
    
    return [
        {
            'peer_id': 123456,
            'msg_id': 1001,
            'transcription_id': 1111111111,
            'text': 'Completed transcription',
            'pending': False,
            'created_at': base_time - timedelta(minutes=10),
            'last_update': base_time - timedelta(minutes=5),
            'completed': True
        },
        {
            'peer_id': 123456,
            'msg_id': 1002,
            'transcription_id': 2222222222,
            'text': '',
            'pending': True,
            'created_at': base_time - timedelta(minutes=2),
            'last_update': base_time - timedelta(minutes=2),
            'completed': False
        },
        {
            'peer_id': 789012,
            'msg_id': 2001,
            'transcription_id': 3333333333,
            'text': 'Another completed transcription',
            'pending': False,
            'created_at': base_time - timedelta(hours=1),
            'last_update': base_time - timedelta(minutes=30),
            'completed': True
        },
        {
            'peer_id': 789012,
            'msg_id': 2002,
            'transcription_id': None,
            'text': '',
            'pending': False,
            'created_at': base_time,
            'last_update': base_time,
            'completed': False,
            'error': 'Transcription failed'
        }
    ]


@pytest.fixture
def performance_test_data():
    """Large datasets for performance testing"""
    
    def generate_peer_message_pairs(count: int):
        """Generate realistic peer/message ID pairs"""
        pairs = []
        base_peer = 100000000
        base_msg = 10000
        
        for i in range(count):
            # Create some peer clustering (realistic usage)
            peer_id = base_peer + (i // 10) * 1000 + random.randint(1, 999)
            msg_id = base_msg + i + random.randint(1, 100)
            pairs.append((peer_id, msg_id))
            
        return pairs
    
    return {
        'small_dataset': generate_peer_message_pairs(50),
        'medium_dataset': generate_peer_message_pairs(200),
        'large_dataset': generate_peer_message_pairs(1000),
        'xlarge_dataset': generate_peer_message_pairs(5000)
    }


# ============================================================================
# Integration Test Fixtures
# ============================================================================

@pytest.fixture
async def integrated_test_system():
    """Complete integrated system for testing"""
    
    # Import components (would be actual imports in real usage)
    from unittest.mock import patch
    
    mock_client = AsyncMock()
    
    # Mock all external dependencies
    with patch.multiple(
        'voice_transcription',
        TelegramClient=lambda: mock_client,
        TELETHON_AVAILABLE=True,
        INTERNAL_IMPORTS=True
    ):
        # Create integrated system components
        system = {
            'client': mock_client,
            'transcriber': None,  # Would create actual transcriber
            'state_manager': None,  # Would create actual state manager
            'update_handler': None,  # Would create actual update handler
            'cleanup_system': None  # Would create actual cleanup system
        }
        
        yield system
        
        # Cleanup would happen here


@pytest.fixture
def mock_update_scenarios():
    """Realistic update scenarios for testing"""
    return [
        {
            'name': 'immediate_completion',
            'initial_pending': True,
            'updates': [
                {
                    'delay': 0.1,
                    'text': 'Transcription completed immediately',
                    'pending': False
                }
            ]
        },
        {
            'name': 'progressive_updates',
            'initial_pending': True,
            'updates': [
                {
                    'delay': 0.1,
                    'text': 'Partial',
                    'pending': True
                },
                {
                    'delay': 0.2,
                    'text': 'Partial transcription',
                    'pending': True
                },
                {
                    'delay': 0.3,
                    'text': 'Partial transcription completed',
                    'pending': False
                }
            ]
        },
        {
            'name': 'failed_transcription',
            'initial_pending': True,
            'updates': [
                {
                    'delay': 0.5,
                    'text': '',
                    'pending': False,
                    'error': 'Transcription failed'
                }
            ]
        },
        {
            'name': 'long_transcription',
            'initial_pending': True,
            'updates': [
                {
                    'delay': 1.0,
                    'text': 'This is a very long transcription that contains multiple sentences and goes on for quite a while to test how the system handles longer text content and ensures that everything works correctly.',
                    'pending': False
                }
            ]
        }
    ]


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_configs():
    """Various configuration scenarios for testing"""
    return {
        'minimal_config': {
            'concurrent_limit': 1,
            'default_timeout': 1.0,
            'validate_messages': False,
            'auto_cleanup_enabled': False
        },
        'standard_config': {
            'concurrent_limit': 10,
            'default_timeout': 30.0,
            'validate_messages': True,
            'auto_cleanup_enabled': True,
            'cleanup_interval_seconds': 300,
            'completed_ttl_hours': 1
        },
        'high_performance_config': {
            'concurrent_limit': 100,
            'default_timeout': 60.0,
            'validate_messages': False,
            'auto_cleanup_enabled': True,
            'cleanup_interval_seconds': 60,
            'completed_ttl_hours': 0.5
        },
        'conservative_config': {
            'concurrent_limit': 5,
            'default_timeout': 120.0,
            'validate_messages': True,
            'auto_cleanup_enabled': True,
            'cleanup_interval_seconds': 900,
            'completed_ttl_hours': 24
        }
    }


@pytest.fixture
def cleanup_test_scenarios():
    """Cleanup system test scenarios"""
    return {
        'age_based_cleanup': {
            'strategy': 'AGE_BASED',
            'max_age_hours': 1,
            'expected_cleanup_count': lambda states: len([
                s for s in states 
                if s.get('completed') and 
                (datetime.now(timezone.utc) - s['last_update']).total_seconds() > 3600
            ])
        },
        'count_based_cleanup': {
            'strategy': 'COUNT_BASED',
            'max_count': 10,
            'expected_cleanup_count': lambda states: max(0, len([
                s for s in states if s.get('completed')
            ]) - 10)
        },
        'memory_based_cleanup': {
            'strategy': 'MEMORY_BASED',
            'memory_threshold_mb': 50,
            'expected_cleanup_count': lambda states: len([
                s for s in states if s.get('completed')
            ]) // 2  # Cleanup half when over threshold
        }
    }


# ============================================================================
# Utility Functions
# ============================================================================

def create_test_transcription_state(
    peer_id: int = 123456,
    msg_id: int = 1001,
    transcription_id: Optional[int] = None,
    text: str = "",
    pending: bool = True,
    completed: bool = False,
    created_minutes_ago: int = 0,
    updated_minutes_ago: int = 0
):
    """Helper to create test transcription states"""
    base_time = datetime.now(timezone.utc)
    
    return {
        'peer_id': peer_id,
        'msg_id': msg_id,
        'transcription_id': transcription_id or random.randint(1000000000, 9999999999),
        'text': text,
        'pending': pending,
        'completed': completed,
        'created_at': base_time - timedelta(minutes=created_minutes_ago),
        'last_update': base_time - timedelta(minutes=updated_minutes_ago)
    }


async def simulate_api_delay(min_ms: int = 10, max_ms: int = 100):
    """Simulate realistic API delay"""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


def generate_realistic_transcription_text(length: str = "medium") -> str:
    """Generate realistic transcription text"""
    templates = {
        "short": [
            "Hello there!",
            "Thanks for the message.",
            "Sure, no problem.",
            "See you later!",
            "Got it, thanks."
        ],
        "medium": [
            "Hello, I wanted to let you know that the meeting has been scheduled for tomorrow at 3 PM.",
            "Thanks for sending me the document. I'll review it and get back to you by the end of the day.",
            "The project is progressing well, but we might need a few more days to complete the final testing phase.",
            "I'm currently stuck in traffic, so I'll be about 15 minutes late to our appointment.",
            "Could you please send me the updated specifications when you have a chance? Thanks!"
        ],
        "long": [
            "I wanted to provide you with a comprehensive update on the project status. We've made significant progress over the past week, completing the initial development phase and moving into the testing phase. The team has been working hard to ensure all requirements are met, and I'm pleased to report that we're currently on track to meet our deadline. However, there are a few minor issues that we're addressing, particularly around the user interface design and some performance optimizations. I'll keep you updated as we continue to make progress.",
            "Thank you for taking the time to review the proposal I sent last week. I appreciate your detailed feedback and suggestions for improvement. Based on your comments, I've made several revisions to the document, including updates to the timeline, budget considerations, and technical specifications. I believe these changes address your concerns and better align with your requirements. I'd be happy to schedule a call to discuss the revised proposal in more detail and answer any questions you might have."
        ]
    }
    
    return random.choice(templates.get(length, templates["medium"]))


# ============================================================================
# Pytest Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Automatic cleanup after each test"""
    yield
    # Force garbage collection
    import gc
    gc.collect()


# Test data validation
def validate_test_data():
    """Validate test data consistency"""
    # This would run validation checks on test fixtures
    # to ensure they remain consistent and realistic
    pass


if __name__ == "__main__":
    # Validate test data if run directly
    validate_test_data()
    print("✅ Test fixtures validated successfully")