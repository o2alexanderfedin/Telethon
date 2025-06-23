"""
Response Parsing for Voice Transcription

This module handles parsing and processing of transcription responses,
including immediate responses and update events.
"""

import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timezone
from dataclasses import dataclass

try:
    from telethon.tl.types.messages import TranscribedAudio
    from telethon.tl.types import UpdateTranscribedAudio
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TranscribedAudio = Any
    UpdateTranscribedAudio = Any


logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """
    Parsed transcription result with metadata.
    
    This class provides a clean interface to transcription data,
    regardless of whether it came from an immediate response or update.
    """
    transcription_id: int
    text: str
    pending: bool
    confidence: Optional[float] = None
    language: Optional[str] = None
    trial_remains_num: Optional[int] = None
    trial_remains_until_date: Optional[datetime] = None
    raw_response: Optional[Any] = None
    parsed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.parsed_at is None:
            self.parsed_at = datetime.now(timezone.utc)
            
    @property
    def is_complete(self) -> bool:
        """True if transcription is complete"""
        return not self.pending
        
    @property
    def has_trial_info(self) -> bool:
        """True if trial information is available"""
        return self.trial_remains_num is not None
        
    @property
    def word_count(self) -> int:
        """Number of words in transcription"""
        return len(self.text.split()) if self.text else 0
        
    @property
    def char_count(self) -> int:
        """Number of characters in transcription"""
        return len(self.text) if self.text else 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'transcription_id': self.transcription_id,
            'text': self.text,
            'pending': self.pending,
            'confidence': self.confidence,
            'language': self.language,
            'trial_remains_num': self.trial_remains_num,
            'trial_remains_until_date': self.trial_remains_until_date.isoformat() if self.trial_remains_until_date else None,
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None,
            'word_count': self.word_count,
            'char_count': self.char_count,
            'is_complete': self.is_complete
        }
        
    def __repr__(self):
        status = "complete" if self.is_complete else "pending"
        return f"TranscriptionResult(id={self.transcription_id}, {status}, {self.char_count} chars)"


@dataclass
class TranscriptionUpdate:
    """
    Parsed transcription update from UpdateTranscribedAudio.
    """
    transcription_id: int
    text: str
    pending: bool
    peer_id: int
    msg_id: int
    update_time: datetime
    raw_update: Optional[Any] = None
    
    def __post_init__(self):
        if self.update_time is None:
            self.update_time = datetime.now(timezone.utc)
            
    @property
    def is_completion_update(self) -> bool:
        """True if this update indicates completion"""
        return not self.pending
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'transcription_id': self.transcription_id,
            'text': self.text,
            'pending': self.pending,
            'peer_id': self.peer_id,
            'msg_id': self.msg_id,
            'update_time': self.update_time.isoformat(),
            'is_completion_update': self.is_completion_update
        }


class ResponseParser:
    """
    Parser for voice transcription responses and updates.
    
    Handles both immediate responses from TranscribeAudioRequest
    and async updates from UpdateTranscribedAudio.
    """
    
    def __init__(self):
        self.parse_stats = {
            'responses_parsed': 0,
            'updates_parsed': 0,
            'errors': 0
        }
        
    def parse_transcription_response(self, response: TranscribedAudio) -> TranscriptionResult:
        """
        Parse immediate transcription response.
        
        Args:
            response: TranscribedAudio object from API
            
        Returns:
            Parsed TranscriptionResult
            
        Raises:
            ValueError: If response is invalid
        """
        try:
            if not response:
                raise ValueError("Response is None or empty")
                
            # Parse trial date if present
            trial_date = None
            if hasattr(response, 'trial_remains_until_date') and response.trial_remains_until_date:
                # Convert Unix timestamp to datetime
                if isinstance(response.trial_remains_until_date, int):
                    trial_date = datetime.fromtimestamp(response.trial_remains_until_date, tz=timezone.utc)
                else:
                    trial_date = response.trial_remains_until_date
                    
            result = TranscriptionResult(
                transcription_id=response.transcription_id,
                text=response.text or "",
                pending=getattr(response, 'pending', False),
                trial_remains_num=getattr(response, 'trial_remains_num', None),
                trial_remains_until_date=trial_date,
                raw_response=response
            )
            
            self.parse_stats['responses_parsed'] += 1
            
            logger.debug(f"Parsed transcription response: {result}")
            return result
            
        except Exception as e:
            self.parse_stats['errors'] += 1
            logger.error(f"Failed to parse transcription response: {e}")
            raise ValueError(f"Invalid transcription response: {e}") from e
            
    def parse_transcription_update(self, update: UpdateTranscribedAudio) -> TranscriptionUpdate:
        """
        Parse transcription update event.
        
        Args:
            update: UpdateTranscribedAudio object from update handler
            
        Returns:
            Parsed TranscriptionUpdate
            
        Raises:
            ValueError: If update is invalid
        """
        try:
            if not update:
                raise ValueError("Update is None or empty")
                
            # Extract peer ID
            peer_id = self._extract_peer_id(update.peer)
            
            result = TranscriptionUpdate(
                transcription_id=update.transcription_id,
                text=update.text or "",
                pending=getattr(update, 'pending', False),
                peer_id=peer_id,
                msg_id=update.msg_id,
                update_time=datetime.now(timezone.utc),
                raw_update=update
            )
            
            self.parse_stats['updates_parsed'] += 1
            
            logger.debug(f"Parsed transcription update: {result}")
            return result
            
        except Exception as e:
            self.parse_stats['errors'] += 1
            logger.error(f"Failed to parse transcription update: {e}")
            raise ValueError(f"Invalid transcription update: {e}") from e
            
    def _extract_peer_id(self, peer) -> int:
        """Extract peer ID from peer object"""
        if hasattr(peer, 'user_id'):
            return peer.user_id
        elif hasattr(peer, 'chat_id'):
            return peer.chat_id
        elif hasattr(peer, 'channel_id'):
            return peer.channel_id
        else:
            logger.warning(f"Unknown peer type: {type(peer)}")
            return 0
            
    def create_result_from_update(self, update: TranscriptionUpdate) -> TranscriptionResult:
        """
        Convert TranscriptionUpdate to TranscriptionResult.
        
        Args:
            update: TranscriptionUpdate object
            
        Returns:
            TranscriptionResult with update data
        """
        return TranscriptionResult(
            transcription_id=update.transcription_id,
            text=update.text,
            pending=update.pending,
            raw_response=update.raw_update,
            parsed_at=update.update_time
        )
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get parsing statistics"""
        total_parsed = self.parse_stats['responses_parsed'] + self.parse_stats['updates_parsed']
        error_rate = (self.parse_stats['errors'] / max(1, total_parsed + self.parse_stats['errors'])) * 100
        
        return {
            **self.parse_stats,
            'total_parsed': total_parsed,
            'error_rate_percent': round(error_rate, 2)
        }
        
    def reset_statistics(self):
        """Reset parsing statistics"""
        self.parse_stats = {
            'responses_parsed': 0,
            'updates_parsed': 0,
            'errors': 0
        }


class TextProcessor:
    """
    Post-processing for transcribed text.
    
    Provides text cleaning, formatting, and analysis features.
    """
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean transcribed text.
        
        Args:
            text: Raw transcribed text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        # Basic cleaning
        cleaned = text.strip()
        
        # Remove excessive whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Fix common transcription issues
        cleaned = TextProcessor._fix_common_issues(cleaned)
        
        return cleaned
        
    @staticmethod
    def _fix_common_issues(text: str) -> str:
        """Fix common transcription issues"""
        # This could be expanded with more sophisticated fixes
        fixes = {
            '  ': ' ',  # Double spaces
            ' ,': ',',  # Space before comma
            ' .': '.',  # Space before period
            ' ?': '?',  # Space before question mark
            ' !': '!',  # Space before exclamation
        }
        
        for old, new in fixes.items():
            text = text.replace(old, new)
            
        return text
        
    @staticmethod
    def analyze_text(text: str) -> Dict[str, Any]:
        """
        Analyze transcribed text.
        
        Args:
            text: Transcribed text
            
        Returns:
            Analysis results
        """
        if not text:
            return {
                'word_count': 0,
                'char_count': 0,
                'sentence_count': 0,
                'avg_word_length': 0,
                'has_punctuation': False,
                'language_hints': []
            }
            
        words = text.split()
        sentences = [s.strip() for s in text.replace('!', '.').replace('?', '.').split('.') if s.strip()]
        
        # Check for punctuation
        punctuation_chars = set('.,!?;:')
        has_punctuation = any(char in text for char in punctuation_chars)
        
        # Average word length
        avg_word_length = sum(len(word) for word in words) / max(1, len(words))
        
        # Simple language hints (could be improved with proper detection)
        language_hints = TextProcessor._detect_language_hints(text)
        
        return {
            'word_count': len(words),
            'char_count': len(text),
            'sentence_count': len(sentences),
            'avg_word_length': round(avg_word_length, 1),
            'has_punctuation': has_punctuation,
            'language_hints': language_hints
        }
        
    @staticmethod
    def _detect_language_hints(text: str) -> List[str]:
        """Detect possible language hints from text"""
        hints = []
        
        # Simple heuristics - could be improved with proper language detection
        if any(char in text for char in 'äöüß'):
            hints.append('German')
        if any(char in text for char in 'àáâãäèéêëìíîïñòóôõöùúûüý'):
            hints.append('Romance language')
        if any(char in text for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            hints.append('Cyrillic script')
            
        # Common English patterns
        english_words = {'the', 'and', 'is', 'it', 'you', 'that', 'he', 'was', 'for', 'on'}
        text_words = set(word.lower() for word in text.split())
        if len(english_words.intersection(text_words)) >= 2:
            hints.append('English')
            
        return hints


# Example usage
def example_response_parsing():
    """Example of how to use the response parsing system"""
    
    parser = ResponseParser()
    text_processor = TextProcessor()
    
    # Mock response (normally would come from Telethon)
    class MockResponse:
        def __init__(self):
            self.transcription_id = 123456789
            self.text = "Hello world, this is a test transcription."
            self.pending = False
            self.trial_remains_num = 5
            self.trial_remains_until_date = 1640995200  # Unix timestamp
            
    # Parse response
    mock_response = MockResponse()
    result = parser.parse_transcription_response(mock_response)
    
    print("Parsed result:")
    print(f"  ID: {result.transcription_id}")
    print(f"  Text: {result.text}")
    print(f"  Complete: {result.is_complete}")
    print(f"  Words: {result.word_count}")
    
    # Process text
    cleaned_text = text_processor.clean_text(result.text)
    analysis = text_processor.analyze_text(cleaned_text)
    
    print("\nText analysis:")
    print(f"  Word count: {analysis['word_count']}")
    print(f"  Has punctuation: {analysis['has_punctuation']}")
    print(f"  Language hints: {analysis['language_hints']}")
    
    # Statistics
    stats = parser.get_statistics()
    print(f"\nParser stats: {stats}")


if __name__ == "__main__":
    print("Voice Transcription Response Parser")
    print("See example_response_parsing() function for usage patterns")
    example_response_parsing()