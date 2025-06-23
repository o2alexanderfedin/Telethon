"""
User Type Detection System

This module implements Epic 2 User Story 2.1: User Type Detection System,
providing accurate detection and caching of user types (Free/Premium/Bot) for
voice transcription quota and policy management.

Features:
- Premium status detection with multiple verification methods
- Bot account identification with special handling
- Intelligent caching system with TTL and invalidation
- Fallback mechanisms for API failures
- Thread-safe operations for concurrent access
- Comprehensive logging and monitoring
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from typing import Dict, Optional, Any, Union, List, Callable
from threading import RLock
import weakref
import hashlib

# Telethon imports with availability checking
try:
    from telethon import TelegramClient
    from telethon.tl.types import User, Chat, Channel
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.errors import (
        PeerIdInvalidError, 
        UserIdInvalidError,
        FloodWaitError,
        RPCError
    )
    TELETHON_AVAILABLE = True
except ImportError:
    # Mock for testing without Telethon
    TelegramClient = object
    User = Chat = Channel = object
    GetFullUserRequest = object
    
    class PeerIdInvalidError(Exception):
        pass
    
    class UserIdInvalidError(Exception):
        pass
        
    class FloodWaitError(Exception):
        def __init__(self, seconds):
            self.seconds = seconds
            
    class RPCError(Exception):
        pass
    
    TELETHON_AVAILABLE = False


class UserType(Enum):
    """User type enumeration for transcription access levels"""
    FREE = auto()
    PREMIUM = auto()
    BOT = auto()
    UNKNOWN = auto()


class DetectionConfidence(Enum):
    """Confidence level for user type detection"""
    HIGH = auto()      # Multiple sources confirm
    MEDIUM = auto()    # Single reliable source
    LOW = auto()       # Heuristic or fallback
    UNCERTAIN = auto() # No reliable information


@dataclass
class UserTypeInfo:
    """Complete user type information with metadata"""
    user_id: int
    user_type: UserType
    confidence: DetectionConfidence
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    verification_methods: List[str] = field(default_factory=list)
    premium_features: Optional[Dict[str, Any]] = None
    bot_info: Optional[Dict[str, Any]] = None
    last_verified: Optional[datetime] = None
    verification_failures: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if cached information has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def age_seconds(self) -> float:
        """Get age of cached information in seconds"""
        return (datetime.now(timezone.utc) - self.cached_at).total_seconds()
    
    @property
    def is_reliable(self) -> bool:
        """Check if detection is reliable enough for decisions"""
        return (
            self.confidence in (DetectionConfidence.HIGH, DetectionConfidence.MEDIUM) and
            not self.is_expired and
            self.verification_failures < 3
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'user_id': self.user_id,
            'user_type': self.user_type.name,
            'confidence': self.confidence.name,
            'cached_at': self.cached_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'verification_methods': self.verification_methods.copy(),
            'premium_features': self.premium_features.copy() if self.premium_features else None,
            'bot_info': self.bot_info.copy() if self.bot_info else None,
            'last_verified': self.last_verified.isoformat() if self.last_verified else None,
            'verification_failures': self.verification_failures,
            'age_seconds': self.age_seconds,
            'is_reliable': self.is_reliable
        }


class UserTypeDetectionError(Exception):
    """Base exception for user type detection errors"""
    pass


class DetectionTimeoutError(UserTypeDetectionError):
    """Raised when detection takes too long"""
    pass


class DetectionUnavailableError(UserTypeDetectionError):
    """Raised when detection services are unavailable"""
    pass


class CacheInvalidationCallback:
    """Callback system for cache invalidation events"""
    
    def __init__(self):
        self._callbacks: List[Callable[[int, UserTypeInfo], None]] = []
        
    def register(self, callback: Callable[[int, UserTypeInfo], None]):
        """Register a callback for cache invalidation"""
        self._callbacks.append(callback)
        
    def unregister(self, callback: Callable[[int, UserTypeInfo], None]):
        """Unregister a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    def notify(self, user_id: int, old_info: UserTypeInfo):
        """Notify all callbacks of cache invalidation"""
        for callback in self._callbacks:
            try:
                callback(user_id, old_info)
            except Exception as e:
                logging.warning(f"Cache invalidation callback failed: {e}")


class UserTypeDetector:
    """
    Advanced user type detection system with caching and fallbacks.
    
    Provides reliable detection of Free/Premium/Bot users with intelligent
    caching, multiple verification methods, and comprehensive error handling.
    """
    
    def __init__(
        self,
        client: TelegramClient,
        cache_ttl_hours: float = 1.0,
        max_cache_size: int = 10000,
        verification_timeout: float = 30.0,
        enable_background_refresh: bool = True
    ):
        """
        Initialize user type detector.
        
        Args:
            client: Telegram client instance
            cache_ttl_hours: Cache time-to-live in hours
            max_cache_size: Maximum number of cached entries
            verification_timeout: Timeout for verification operations
            enable_background_refresh: Enable background cache refresh
        """
        self._client = client
        self._cache: Dict[int, UserTypeInfo] = {}
        self._cache_lock = RLock()
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._max_cache_size = max_cache_size
        self._verification_timeout = verification_timeout
        self._enable_background_refresh = enable_background_refresh
        
        # Statistics and monitoring
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'detections_performed': 0,
            'verification_failures': 0,
            'fallback_used': 0,
            'premium_detected': 0,
            'bot_detected': 0,
            'free_detected': 0
        }
        
        # Cache invalidation system
        self._invalidation_callbacks = CacheInvalidationCallback()
        
        # Background refresh task
        self._refresh_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Detection methods registry
        self._detection_methods = [
            self._detect_premium_via_user_info,
            self._detect_bot_via_user_properties,
            self._detect_via_heuristics
        ]
        
        # Start background refresh if enabled
        if self._enable_background_refresh:
            self._start_background_refresh()
    
    async def get_user_type(
        self, 
        user_id: int, 
        force_refresh: bool = False,
        timeout: Optional[float] = None
    ) -> UserType:
        """
        Get user type with caching and fallback.
        
        Args:
            user_id: Telegram user ID
            force_refresh: Force fresh detection bypassing cache
            timeout: Custom timeout for this operation
            
        Returns:
            Detected user type
            
        Raises:
            DetectionTimeoutError: If detection times out
            DetectionUnavailableError: If detection is not available
            UserTypeDetectionError: Other detection errors
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_info = self._get_cached_info(user_id)
            if cached_info and cached_info.is_reliable:
                self._stats['cache_hits'] += 1
                return cached_info.user_type
        
        self._stats['cache_misses'] += 1
        
        # Perform fresh detection
        try:
            user_info = await self._detect_user_type_full(
                user_id, 
                timeout or self._verification_timeout
            )
            
            # Cache the result
            self._cache_user_info(user_info)
            
            # Update statistics
            self._stats['detections_performed'] += 1
            self._stats[f'{user_info.user_type.name.lower()}_detected'] += 1
            
            return user_info.user_type
            
        except asyncio.TimeoutError:
            # Try fallback on timeout
            fallback_type = self._get_fallback_user_type(user_id)
            self._stats['fallback_used'] += 1
            raise DetectionTimeoutError(f"Detection timed out for user {user_id}, using fallback: {fallback_type}")
            
        except Exception as e:
            # Log error and use fallback
            logging.error(f"User type detection failed for {user_id}: {e}")
            self._stats['verification_failures'] += 1
            
            fallback_type = self._get_fallback_user_type(user_id)
            self._stats['fallback_used'] += 1
            
            # Cache fallback result with low confidence
            fallback_info = UserTypeInfo(
                user_id=user_id,
                user_type=fallback_type,
                confidence=DetectionConfidence.LOW,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                verification_methods=['fallback'],
                verification_failures=1
            )
            self._cache_user_info(fallback_info)
            
            return fallback_type
    
    async def get_user_info(self, user_id: int, force_refresh: bool = False) -> UserTypeInfo:
        """
        Get complete user type information.
        
        Args:
            user_id: Telegram user ID
            force_refresh: Force fresh detection
            
        Returns:
            Complete user type information
        """
        # Check cache first
        if not force_refresh:
            cached_info = self._get_cached_info(user_id)
            if cached_info and cached_info.is_reliable:
                return cached_info
        
        # Perform detection
        await self.get_user_type(user_id, force_refresh)
        
        # Return cached info (should now be available)
        cached_info = self._get_cached_info(user_id)
        if cached_info:
            return cached_info
        
        # Fallback info if cache failed
        return UserTypeInfo(
            user_id=user_id,
            user_type=UserType.UNKNOWN,
            confidence=DetectionConfidence.UNCERTAIN,
            verification_methods=['fallback']
        )
    
    async def _detect_user_type_full(self, user_id: int, timeout: float) -> UserTypeInfo:
        """
        Perform comprehensive user type detection.
        
        Args:
            user_id: User ID to detect
            timeout: Operation timeout
            
        Returns:
            Complete user type information
        """
        start_time = datetime.now(timezone.utc)
        verification_methods = []
        confidence = DetectionConfidence.UNCERTAIN
        user_type = UserType.UNKNOWN
        premium_features = None
        bot_info = None
        
        try:
            # Run detection methods with timeout
            detection_task = asyncio.create_task(
                self._run_detection_methods(user_id)
            )
            
            result = await asyncio.wait_for(detection_task, timeout)
            
            user_type = result['user_type']
            confidence = result['confidence']
            verification_methods = result['methods']
            premium_features = result.get('premium_features')
            bot_info = result.get('bot_info')
            
        except asyncio.TimeoutError:
            logging.warning(f"Detection timeout for user {user_id}")
            raise
        except Exception as e:
            logging.error(f"Detection error for user {user_id}: {e}")
            raise UserTypeDetectionError(f"Detection failed: {e}")
        
        # Calculate expiration time based on confidence
        if confidence == DetectionConfidence.HIGH:
            expires_at = start_time + self._cache_ttl
        elif confidence == DetectionConfidence.MEDIUM:
            expires_at = start_time + (self._cache_ttl / 2)
        else:
            expires_at = start_time + timedelta(minutes=15)
        
        return UserTypeInfo(
            user_id=user_id,
            user_type=user_type,
            confidence=confidence,
            cached_at=start_time,
            expires_at=expires_at,
            verification_methods=verification_methods,
            premium_features=premium_features,
            bot_info=bot_info,
            last_verified=start_time
        )
    
    async def _run_detection_methods(self, user_id: int) -> Dict[str, Any]:
        """
        Run all detection methods and aggregate results.
        
        Args:
            user_id: User ID to detect
            
        Returns:
            Aggregated detection results
        """
        results = []
        
        # Run each detection method
        for method in self._detection_methods:
            try:
                result = await method(user_id)
                if result:
                    results.append(result)
            except Exception as e:
                logging.debug(f"Detection method {method.__name__} failed for {user_id}: {e}")
                continue
        
        # Aggregate results
        return self._aggregate_detection_results(results)
    
    async def _detect_premium_via_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Detect Premium status via user information.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Detection result or None if unavailable
        """
        if not TELETHON_AVAILABLE:
            return None
        
        try:
            # Get full user information
            user_full = await self._client(GetFullUserRequest(user_id))
            user = user_full.users[0] if user_full.users else None
            
            if not user:
                return None
            
            # Check Premium indicators
            is_premium = getattr(user, 'premium', False)
            
            if is_premium:
                premium_features = {
                    'verified_premium': True,
                    'detected_via': 'user_info',
                    'user_flags': getattr(user, 'flags', None)
                }
                
                return {
                    'user_type': UserType.PREMIUM,
                    'confidence': DetectionConfidence.HIGH,
                    'method': 'premium_user_info',
                    'premium_features': premium_features
                }
            
            # If explicitly not premium, high confidence Free
            return {
                'user_type': UserType.FREE,
                'confidence': DetectionConfidence.HIGH,
                'method': 'user_info_not_premium'
            }
            
        except (PeerIdInvalidError, UserIdInvalidError):
            return None
        except FloodWaitError as e:
            logging.warning(f"Flood wait for user info: {e.seconds}s")
            return None
        except Exception as e:
            logging.debug(f"Premium detection via user info failed: {e}")
            return None
    
    async def _detect_bot_via_user_properties(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Detect Bot accounts via user properties.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Detection result or None if unavailable
        """
        if not TELETHON_AVAILABLE:
            return None
        
        try:
            # Get user entity
            user = await self._client.get_entity(user_id)
            
            if hasattr(user, 'bot') and user.bot:
                bot_info = {
                    'is_bot': True,
                    'username': getattr(user, 'username', None),
                    'verified': getattr(user, 'verified', False),
                    'inline_geo': getattr(user, 'bot_inline_geo', False),
                    'bot_chat_history': getattr(user, 'bot_chat_history', False)
                }
                
                return {
                    'user_type': UserType.BOT,
                    'confidence': DetectionConfidence.HIGH,
                    'method': 'bot_properties',
                    'bot_info': bot_info
                }
            
            return None
            
        except Exception as e:
            logging.debug(f"Bot detection failed: {e}")
            return None
    
    async def _detect_via_heuristics(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Detect user type via heuristics and patterns.
        
        Args:
            user_id: User ID to analyze
            
        Returns:
            Detection result or None if uncertain
        """
        # Heuristic: User ID patterns
        if user_id < 0:
            # Negative IDs are typically channels/groups, not users
            return None
        
        # Heuristic: Very low user IDs might be special accounts
        if user_id < 1000:
            return {
                'user_type': UserType.BOT,
                'confidence': DetectionConfidence.LOW,
                'method': 'low_userid_heuristic'
            }
        
        # Default heuristic: Assume Free user
        return {
            'user_type': UserType.FREE,
            'confidence': DetectionConfidence.LOW,
            'method': 'default_heuristic'
        }
    
    def _aggregate_detection_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate multiple detection results into final decision.
        
        Args:
            results: List of detection results
            
        Returns:
            Final aggregated result
        """
        if not results:
            return {
                'user_type': UserType.UNKNOWN,
                'confidence': DetectionConfidence.UNCERTAIN,
                'methods': ['no_results']
            }
        
        # Sort by confidence level
        confidence_order = {
            DetectionConfidence.HIGH: 3,
            DetectionConfidence.MEDIUM: 2,
            DetectionConfidence.LOW: 1,
            DetectionConfidence.UNCERTAIN: 0
        }
        
        results.sort(key=lambda r: confidence_order[r['confidence']], reverse=True)
        
        # Use highest confidence result
        primary_result = results[0]
        
        # Aggregate verification methods
        methods = [r['method'] for r in results]
        
        # Determine final confidence
        if len(results) > 1 and results[0]['confidence'] == results[1]['confidence']:
            # Multiple high-confidence results agree
            final_confidence = DetectionConfidence.HIGH
        else:
            final_confidence = primary_result['confidence']
        
        return {
            'user_type': primary_result['user_type'],
            'confidence': final_confidence,
            'methods': methods,
            'premium_features': primary_result.get('premium_features'),
            'bot_info': primary_result.get('bot_info')
        }
    
    def _get_cached_info(self, user_id: int) -> Optional[UserTypeInfo]:
        """
        Get cached user information if valid.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            Cached information or None if not available/expired
        """
        with self._cache_lock:
            info = self._cache.get(user_id)
            
            if info is None:
                return None
            
            if info.is_expired:
                # Remove expired entry
                del self._cache[user_id]
                return None
            
            return info
    
    def _cache_user_info(self, info: UserTypeInfo):
        """
        Cache user type information.
        
        Args:
            info: User information to cache
        """
        with self._cache_lock:
            # Check cache size limit
            if len(self._cache) >= self._max_cache_size:
                self._evict_oldest_entries()
            
            # Cache the information
            old_info = self._cache.get(info.user_id)
            self._cache[info.user_id] = info
            
            # Notify callbacks if user type changed
            if (old_info and 
                old_info.user_type != info.user_type and 
                old_info.is_reliable):
                self._invalidation_callbacks.notify(info.user_id, old_info)
    
    def _evict_oldest_entries(self):
        """Evict oldest cache entries to maintain size limit"""
        if len(self._cache) <= self._max_cache_size:
            return
        
        # Sort by age and remove oldest entries
        entries = list(self._cache.items())
        entries.sort(key=lambda item: item[1].cached_at)
        
        # Remove oldest 10% of entries
        remove_count = max(1, len(entries) // 10)
        for i in range(remove_count):
            user_id, _ = entries[i]
            del self._cache[user_id]
    
    def _get_fallback_user_type(self, user_id: int) -> UserType:
        """
        Get fallback user type when detection fails.
        
        Args:
            user_id: User ID
            
        Returns:
            Conservative fallback user type
        """
        # Conservative fallback: assume Free user
        # This prevents Premium users from being denied service
        # but might allow some Free users excess usage
        return UserType.FREE
    
    def _start_background_refresh(self):
        """Start background cache refresh task"""
        if self._refresh_task and not self._refresh_task.done():
            return
        
        self._refresh_task = asyncio.create_task(self._background_refresh_loop())
    
    async def _background_refresh_loop(self):
        """Background loop to refresh expiring cache entries"""
        while not self._shutdown_event.is_set():
            try:
                await self._refresh_expiring_entries()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.warning(f"Background refresh error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute
    
    async def _refresh_expiring_entries(self):
        """Refresh cache entries that are expiring soon"""
        cutoff_time = datetime.now(timezone.utc) + timedelta(minutes=15)
        expiring_users = []
        
        with self._cache_lock:
            for user_id, info in self._cache.items():
                if (info.expires_at and 
                    info.expires_at < cutoff_time and 
                    info.is_reliable):
                    expiring_users.append(user_id)
        
        # Refresh expiring entries (limit to avoid overload)
        for user_id in expiring_users[:10]:
            try:
                await self.get_user_type(user_id, force_refresh=True)
                await asyncio.sleep(1)  # Rate limit refreshes
            except Exception as e:
                logging.debug(f"Background refresh failed for {user_id}: {e}")
    
    def invalidate_cache(self, user_id: Optional[int] = None):
        """
        Invalidate cached user information.
        
        Args:
            user_id: Specific user to invalidate, or None for all
        """
        with self._cache_lock:
            if user_id is not None:
                if user_id in self._cache:
                    old_info = self._cache[user_id]
                    del self._cache[user_id]
                    self._invalidation_callbacks.notify(user_id, old_info)
            else:
                # Clear entire cache
                old_cache = self._cache.copy()
                self._cache.clear()
                
                # Notify for all entries
                for uid, info in old_cache.items():
                    self._invalidation_callbacks.notify(uid, info)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache and detection statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._cache_lock:
            cache_size = len(self._cache)
            expired_count = sum(1 for info in self._cache.values() if info.is_expired)
            
        hit_rate = 0.0
        total_requests = self._stats['cache_hits'] + self._stats['cache_misses']
        if total_requests > 0:
            hit_rate = self._stats['cache_hits'] / total_requests
        
        return {
            'cache_size': cache_size,
            'cache_expired_entries': expired_count,
            'cache_hit_rate': hit_rate,
            'max_cache_size': self._max_cache_size,
            **self._stats.copy()
        }
    
    def register_invalidation_callback(self, callback: Callable[[int, UserTypeInfo], None]):
        """
        Register callback for cache invalidation events.
        
        Args:
            callback: Function to call when cache is invalidated
        """
        self._invalidation_callbacks.register(callback)
    
    def unregister_invalidation_callback(self, callback: Callable[[int, UserTypeInfo], None]):
        """
        Unregister cache invalidation callback.
        
        Args:
            callback: Function to unregister
        """
        self._invalidation_callbacks.unregister(callback)
    
    async def shutdown(self):
        """Shutdown the detector and cleanup resources"""
        self._shutdown_event.set()
        
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        
        with self._cache_lock:
            self._cache.clear()


# Utility functions
def create_user_type_detector(
    client: TelegramClient,
    **kwargs
) -> UserTypeDetector:
    """
    Create a user type detector with standard configuration.
    
    Args:
        client: Telegram client
        **kwargs: Additional configuration options
        
    Returns:
        Configured user type detector
    """
    return UserTypeDetector(client, **kwargs)


async def detect_user_type_simple(
    client: TelegramClient, 
    user_id: int
) -> UserType:
    """
    Simple user type detection without caching.
    
    Args:
        client: Telegram client
        user_id: User ID to detect
        
    Returns:
        Detected user type
    """
    detector = UserTypeDetector(
        client, 
        cache_ttl_hours=0,  # No caching
        enable_background_refresh=False
    )
    
    try:
        return await detector.get_user_type(user_id)
    finally:
        await detector.shutdown()


def is_premium_user(user_type: UserType) -> bool:
    """Check if user type is Premium"""
    return user_type == UserType.PREMIUM


def is_free_user(user_type: UserType) -> bool:
    """Check if user type is Free"""
    return user_type == UserType.FREE


def is_bot_user(user_type: UserType) -> bool:
    """Check if user type is Bot"""
    return user_type == UserType.BOT


def get_user_type_display_name(user_type: UserType) -> str:
    """Get display name for user type"""
    return {
        UserType.FREE: "Free User",
        UserType.PREMIUM: "Premium User", 
        UserType.BOT: "Bot Account",
        UserType.UNKNOWN: "Unknown User"
    }.get(user_type, "Unknown")


if __name__ == "__main__":
    # Example usage and testing
    async def main():
        # This would require a real client in practice
        print("User Type Detection System")
        print("This module requires integration with a Telegram client for actual operation.")
        
        # Demo with mock data
        demo_info = UserTypeInfo(
            user_id=123456789,
            user_type=UserType.PREMIUM,
            confidence=DetectionConfidence.HIGH,
            verification_methods=['premium_user_info']
        )
        
        print(f"Demo user info: {demo_info.to_dict()}")
    
    asyncio.run(main())