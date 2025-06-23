# Custom Types

---
**Navigation:** [← Types and Functions](types-functions.md) | [Home](../index.md) | [Up](../index.md) | [API Versioning →](versioning.md)

---

## Overview

Telethon allows creation of custom types that extend or wrap the base Telegram types. This enables developers to add convenience methods, implement business logic, and create domain-specific abstractions while maintaining compatibility with the underlying API.

## Creating Custom Types

### Basic Custom Type

```python
from telethon.tl.types import Message
from typing import Optional, List
import re

class CustomMessage(Message):
    """
    Extended message type with additional functionality.
    """
    
    def __init__(self, original_message: Message):
        # Copy all attributes from original
        self.__dict__.update(original_message.__dict__)
        self._original = original_message
        
    @property
    def is_command(self) -> bool:
        """Check if message is a bot command."""
        if not self.message:
            return False
        return self.message.startswith('/')
        
    @property
    def command(self) -> Optional[str]:
        """Extract command from message."""
        if not self.is_command:
            return None
            
        match = re.match(r'^/(\w+)(?:@\w+)?(?:\s|$)', self.message)
        return match.group(1) if match else None
        
    @property
    def command_args(self) -> List[str]:
        """Extract command arguments."""
        if not self.is_command:
            return []
            
        # Remove command part
        text = re.sub(r'^/\w+(?:@\w+)?\s*', '', self.message)
        return text.split() if text else []
        
    @property
    def mentions(self) -> List[str]:
        """Extract @mentions from message."""
        if not self.message:
            return []
            
        return re.findall(r'@(\w+)', self.message)
        
    @property
    def hashtags(self) -> List[str]:
        """Extract #hashtags from message."""
        if not self.message:
            return []
            
        return re.findall(r'#(\w+)', self.message)
        
    def has_keyword(self, keyword: str) -> bool:
        """Check if message contains keyword."""
        if not self.message:
            return False
            
        return keyword.lower() in self.message.lower()
```

### Type Wrapper Pattern

```python
class EntityWrapper:
    """
    Wraps Telegram entities with additional functionality.
    """
    
    def __init__(self, entity):
        self._entity = entity
        self._cached_data = {}
        
    def __getattr__(self, name):
        """Delegate attribute access to wrapped entity."""
        return getattr(self._entity, name)
        
    @classmethod
    def wrap(cls, entity):
        """Factory method to wrap entities."""
        if isinstance(entity, User):
            return UserWrapper(entity)
        elif isinstance(entity, Chat):
            return ChatWrapper(entity)
        elif isinstance(entity, Channel):
            return ChannelWrapper(entity)
        else:
            return cls(entity)
            
class UserWrapper(EntityWrapper):
    """Enhanced user type."""
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts) or f"User{self.id}"
        
    @property
    def mention(self) -> str:
        """Get user mention string."""
        if self.username:
            return f"@{self.username}"
        else:
            return f"[{self.full_name}](tg://user?id={self.id})"
            
    def is_admin_in(self, chat_id: int) -> bool:
        """Check if user is admin in chat."""
        # This would require additional API calls
        # Cached result example
        cache_key = f"admin_{chat_id}"
        if cache_key not in self._cached_data:
            # Fetch and cache admin status
            self._cached_data[cache_key] = self._fetch_admin_status(chat_id)
        return self._cached_data[cache_key]
```

## Custom Collections

### Message Collection

```python
class MessageCollection:
    """
    Collection of messages with utility methods.
    """
    
    def __init__(self, messages: List[Message]):
        self.messages = messages
        self._by_id = {msg.id: msg for msg in messages}
        self._by_sender = self._group_by_sender()
        
    def _group_by_sender(self):
        """Group messages by sender."""
        grouped = {}
        for msg in self.messages:
            if msg.from_id:
                sender_id = self._get_sender_id(msg.from_id)
                if sender_id not in grouped:
                    grouped[sender_id] = []
                grouped[sender_id].append(msg)
        return grouped
        
    def filter_by_text(self, pattern: str) -> 'MessageCollection':
        """Filter messages by text pattern."""
        import re
        regex = re.compile(pattern, re.IGNORECASE)
        filtered = [
            msg for msg in self.messages
            if msg.message and regex.search(msg.message)
        ]
        return MessageCollection(filtered)
        
    def filter_by_date(self, start: datetime, end: datetime) -> 'MessageCollection':
        """Filter messages by date range."""
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
        filtered = [
            msg for msg in self.messages
            if start_ts <= msg.date <= end_ts
        ]
        return MessageCollection(filtered)
        
    def get_media_messages(self) -> 'MessageCollection':
        """Get only messages with media."""
        filtered = [msg for msg in self.messages if msg.media]
        return MessageCollection(filtered)
        
    def get_reply_chains(self) -> Dict[int, List[Message]]:
        """Build reply chains from messages."""
        chains = {}
        
        for msg in self.messages:
            if msg.reply_to and msg.reply_to.reply_to_msg_id:
                reply_to_id = msg.reply_to.reply_to_msg_id
                if reply_to_id not in chains:
                    chains[reply_to_id] = []
                chains[reply_to_id].append(msg)
                
        return chains
        
    def to_dataframe(self):
        """Convert to pandas DataFrame for analysis."""
        import pandas as pd
        
        data = []
        for msg in self.messages:
            data.append({
                'id': msg.id,
                'date': datetime.fromtimestamp(msg.date),
                'from_id': self._get_sender_id(msg.from_id) if msg.from_id else None,
                'text': msg.message,
                'views': msg.views,
                'forwards': msg.forwards,
                'has_media': bool(msg.media),
                'is_reply': bool(msg.reply_to),
            })
            
        return pd.DataFrame(data)
```

## Type Builders

### Fluent Builders

```python
class MessageBuilder:
    """
    Fluent builder for creating messages.
    """
    
    def __init__(self):
        self._text = ""
        self._entities = []
        self._reply_markup = None
        self._reply_to = None
        self._schedule_date = None
        self._silent = False
        
    def text(self, text: str) -> 'MessageBuilder':
        """Set message text."""
        self._text = text
        return self
        
    def bold(self, text: str) -> 'MessageBuilder':
        """Add bold text."""
        offset = len(self._text)
        self._text += text
        self._entities.append(
            MessageEntityBold(offset=offset, length=len(text))
        )
        return self
        
    def italic(self, text: str) -> 'MessageBuilder':
        """Add italic text."""
        offset = len(self._text)
        self._text += text
        self._entities.append(
            MessageEntityItalic(offset=offset, length=len(text))
        )
        return self
        
    def link(self, text: str, url: str) -> 'MessageBuilder':
        """Add text link."""
        offset = len(self._text)
        self._text += text
        self._entities.append(
            MessageEntityTextUrl(offset=offset, length=len(text), url=url)
        )
        return self
        
    def mention(self, text: str, user_id: int) -> 'MessageBuilder':
        """Add user mention."""
        offset = len(self._text)
        self._text += text
        self._entities.append(
            MessageEntityMentionName(
                offset=offset,
                length=len(text),
                user_id=user_id
            )
        )
        return self
        
    def newline(self) -> 'MessageBuilder':
        """Add newline."""
        self._text += '\n'
        return self
        
    def reply_to(self, msg_id: int) -> 'MessageBuilder':
        """Set reply to message."""
        self._reply_to = msg_id
        return self
        
    def silent(self) -> 'MessageBuilder':
        """Make message silent."""
        self._silent = True
        return self
        
    def schedule(self, date: datetime) -> 'MessageBuilder':
        """Schedule message."""
        self._schedule_date = int(date.timestamp())
        return self
        
    def buttons(self, buttons) -> 'MessageBuilder':
        """Add reply markup."""
        self._reply_markup = buttons
        return self
        
    def build(self) -> dict:
        """Build message parameters."""
        return {
            'message': self._text,
            'entities': self._entities if self._entities else None,
            'reply_to': self._reply_to,
            'reply_markup': self._reply_markup,
            'silent': self._silent,
            'schedule_date': self._schedule_date,
        }
        
# Usage example
msg = (MessageBuilder()
    .text("Check out ")
    .bold("Telethon")
    .text(" - ")
    .link("powerful Python library", "https://github.com/LonamiWebs/Telethon")
    .text(" for ")
    .italic("Telegram API")
    .newline()
    .text("Created by ")
    .mention("Lonami", user_id=12345)
    .silent()
    .build())
```

## Type Validators

### Custom Validators

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Messageable(Protocol):
    """Protocol for entities that can receive messages."""
    
    id: int
    access_hash: int
    
    def get_input_peer(self) -> InputPeer:
        ...

class TypeValidator:
    """
    Advanced type validation.
    """
    
    @staticmethod
    def is_messageable(entity) -> bool:
        """Check if entity can receive messages."""
        return isinstance(entity, Messageable)
        
    @staticmethod
    def validate_media(media) -> List[str]:
        """Validate media object."""
        errors = []
        
        if isinstance(media, MessageMediaPhoto):
            if not media.photo:
                errors.append("Photo media missing photo")
            elif media.ttl_seconds and media.ttl_seconds < 0:
                errors.append("Invalid TTL seconds")
                
        elif isinstance(media, MessageMediaDocument):
            if not media.document:
                errors.append("Document media missing document")
            else:
                doc = media.document
                if doc.size > 2 * 1024 * 1024 * 1024:  # 2GB
                    errors.append("Document too large")
                    
        elif isinstance(media, MessageMediaGeo):
            if not media.geo:
                errors.append("Geo media missing location")
            else:
                geo = media.geo
                if not (-90 <= geo.lat <= 90):
                    errors.append("Invalid latitude")
                if not (-180 <= geo.long <= 180):
                    errors.append("Invalid longitude")
                    
        return errors
        
    @classmethod
    def validate_request(cls, request) -> List[str]:
        """Validate request before sending."""
        errors = []
        
        # Check required fields
        for field_name, field_type in request.__annotations__.items():
            value = getattr(request, field_name, None)
            
            if value is None and not cls._is_optional(field_type):
                errors.append(f"Missing required field: {field_name}")
                
        # Validate specific request types
        if isinstance(request, SendMessageRequest):
            if not request.message and not request.media:
                errors.append("Message must have text or media")
                
            if request.schedule_date and request.schedule_date < time.time():
                errors.append("Schedule date must be in future")
                
        return errors
```

## Type Converters

### Advanced Conversion

```python
class TypeConverter:
    """
    Advanced type conversion utilities.
    """
    
    @staticmethod
    def to_json(obj: TLObject) -> dict:
        """Convert TL object to JSON-serializable dict."""
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
            
        result = {
            '_': obj.__class__.__name__,
        }
        
        for key, value in obj.__dict__.items():
            if key.startswith('_'):
                continue
                
            if isinstance(value, TLObject):
                result[key] = TypeConverter.to_json(value)
            elif isinstance(value, list):
                result[key] = [
                    TypeConverter.to_json(item) if isinstance(item, TLObject) else item
                    for item in value
                ]
            elif isinstance(value, bytes):
                result[key] = base64.b64encode(value).decode()
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
                
        return result
        
    @staticmethod
    def from_json(data: dict, expected_type: Type[TLObject]) -> TLObject:
        """Create TL object from JSON dict."""
        # Implementation would handle type reconstruction
        pass
        
    @staticmethod
    def to_protobuf(obj: TLObject) -> bytes:
        """Convert to protobuf format."""
        # Implementation for protobuf conversion
        pass
```

## Type Mixins

### Functionality Mixins

```python
class TimestampMixin:
    """Mixin for timestamp functionality."""
    
    @property
    def datetime(self) -> datetime:
        """Get datetime from timestamp."""
        return datetime.fromtimestamp(self.date)
        
    @property
    def age(self) -> timedelta:
        """Get age of object."""
        return datetime.now() - self.datetime
        
    def is_older_than(self, duration: timedelta) -> bool:
        """Check if older than duration."""
        return self.age > duration

class MediaMixin:
    """Mixin for media handling."""
    
    @property
    def media_type(self) -> Optional[str]:
        """Get media type name."""
        if not hasattr(self, 'media') or not self.media:
            return None
            
        media_types = {
            MessageMediaPhoto: 'photo',
            MessageMediaDocument: 'document',
            MessageMediaGeo: 'location',
            MessageMediaContact: 'contact',
            MessageMediaPoll: 'poll',
            MessageMediaWebPage: 'webpage',
        }
        
        for media_class, name in media_types.items():
            if isinstance(self.media, media_class):
                return name
                
        return 'unknown'
        
    @property
    def has_photo(self) -> bool:
        """Check if has photo media."""
        return isinstance(self.media, MessageMediaPhoto)
        
    @property
    def has_document(self) -> bool:
        """Check if has document media."""
        return isinstance(self.media, MessageMediaDocument)

# Combined custom type
class RichMessage(Message, TimestampMixin, MediaMixin):
    """Message with additional functionality."""
    pass
```

## Type Registry

### Dynamic Type Registration

```python
class TypeRegistry:
    """
    Registry for custom types.
    """
    
    def __init__(self):
        self._types = {}
        self._converters = {}
        
    def register_type(self, constructor_id: int, type_class: Type[TLObject]):
        """Register custom type."""
        self._types[constructor_id] = type_class
        
    def register_converter(self, from_type: Type, to_type: Type, converter: Callable):
        """Register type converter."""
        key = (from_type, to_type)
        self._converters[key] = converter
        
    def create_object(self, constructor_id: int, **kwargs) -> TLObject:
        """Create object by constructor ID."""
        if constructor_id not in self._types:
            raise ValueError(f"Unknown constructor: {constructor_id:x}")
            
        type_class = self._types[constructor_id]
        return type_class(**kwargs)
        
    def convert(self, obj, to_type: Type):
        """Convert object to different type."""
        from_type = type(obj)
        key = (from_type, to_type)
        
        if key in self._converters:
            return self._converters[key](obj)
            
        # Try to find compatible converter
        for (f_type, t_type), converter in self._converters.items():
            if issubclass(from_type, f_type) and issubclass(to_type, t_type):
                return converter(obj)
                
        raise ValueError(f"No converter from {from_type} to {to_type}")

# Global registry
registry = TypeRegistry()

# Register custom types
registry.register_type(0x12345678, CustomMessage)
registry.register_converter(Message, CustomMessage, lambda m: CustomMessage(m))
```

## Best Practices

### Custom Type Design

1. **Extend, Don't Replace**: Build on existing types rather than replacing
2. **Maintain Compatibility**: Ensure custom types work with Telethon internals
3. **Add Value**: Only create custom types that add meaningful functionality
4. **Document Behavior**: Clearly document custom type behavior
5. **Test Thoroughly**: Test custom types with various edge cases

### Performance Considerations

1. **Lazy Loading**: Load additional data only when needed
2. **Cache Results**: Cache expensive computations
3. **Minimize Overhead**: Keep custom type overhead minimal
4. **Batch Operations**: Support batch operations in collections
5. **Memory Efficiency**: Be mindful of memory usage in collections

## Next Steps

- Continue to [API Versioning](versioning.md) for version handling
- Review [Type Language](tl-schema.md) for schema details
- See [Error Handling](../internals/errors.md) for custom error types

---
**Navigation:** [← Types and Functions](types-functions.md) | [Home](../index.md) | [Up](../index.md) | [API Versioning →](versioning.md)

---