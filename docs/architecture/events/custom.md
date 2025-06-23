# Custom Events

---
**Navigation:** [← Event Handling](handling.md) | [Home](../index.md) | [Up](../index.md) | [Protocol →](../protocol/README.md)

---

## Overview

Telethon's event system is extensible, allowing you to create custom event types for specific use cases. Custom events can encapsulate complex logic, provide specialized filtering, and integrate with external systems.

## Creating Custom Events

### Basic Custom Event

```python
from telethon.events.common import EventBuilder, EventCommon
from telethon.tl import types

class CustomEvent(EventCommon):
    """
    Base class for custom events.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize custom attributes
        
    @property
    def custom_property(self):
        """Example custom property."""
        return self._custom_data

class CustomEventBuilder(EventBuilder):
    """
    Builder for custom events.
    """
    
    def __init__(self, func=None, **kwargs):
        super().__init__(func=func)
        self.kwargs = kwargs
        
    @classmethod
    def build(cls, update, others=None, self_id=None):
        """
        Build event from update.
        
        Args:
            update: The Telegram update
            others: Dict of {ID: entity}
            self_id: Current user ID
            
        Returns:
            CustomEvent or None if not applicable
        """
        # Check if update matches our event type
        if not isinstance(update, types.UpdateSomething):
            return None
            
        # Create and return event
        return CustomEvent(
            original_update=update,
            # Extract relevant data
        )
```

### Advanced Custom Event Example

```python
class ReactionEvent(EventCommon):
    """
    Event triggered when a reaction is added/removed.
    """
    
    def __init__(self, peer, msg_id, reaction, added, user_id, **kwargs):
        super().__init__(**kwargs)
        self.peer = peer
        self.msg_id = msg_id
        self.reaction = reaction
        self.added = added  # True if added, False if removed
        self.user_id = user_id
        
    @property
    def emoji(self):
        """Get reaction emoji."""
        if isinstance(self.reaction, types.ReactionEmoji):
            return self.reaction.emoticon
        elif isinstance(self.reaction, types.ReactionCustomEmoji):
            return f"custom:{self.reaction.document_id}"
        return None
        
    async def get_message(self):
        """Get the message that was reacted to."""
        return await self.client.get_messages(
            self.peer,
            ids=self.msg_id
        )
        
    async def respond_with_reaction(self, reaction):
        """React to the same message."""
        return await self.client.send_reaction(
            self.peer,
            self.msg_id,
            reaction
        )

class ReactionEventBuilder(EventBuilder):
    """
    Builder for reaction events.
    """
    
    def __init__(self, chats=None, func=None, emoji=None, added=None):
        super().__init__(chats=chats, func=func)
        self.emoji = emoji
        self.added = added
        
    @classmethod
    def build(cls, update, others=None, self_id=None):
        """Build reaction event from update."""
        if isinstance(update, types.UpdateMessageReactions):
            # Single message reactions update
            return cls._build_from_reactions(update, others)
            
        elif isinstance(update, types.UpdateBotMessageReaction):
            # Bot reaction update
            return cls._build_from_bot_reaction(update, others)
            
        return None
        
    @classmethod
    def _build_from_reactions(cls, update, others):
        """Build from UpdateMessageReactions."""
        peer = update.peer
        
        for reaction in update.reactions.recent_reactions:
            yield ReactionEvent(
                peer=peer,
                msg_id=update.msg_id,
                reaction=reaction.reaction,
                added=True,  # Recent reactions are additions
                user_id=reaction.peer_id.user_id,
                original_update=update
            )
            
    def filter(self, event):
        """Filter reaction events."""
        if self.emoji and event.emoji != self.emoji:
            return False
            
        if self.added is not None and event.added != self.added:
            return False
            
        return super().filter(event)
```

## Composite Events

### Combining Multiple Updates

```python
class ConversationEvent(EventCommon):
    """
    Event that tracks conversation context.
    """
    
    def __init__(self, messages, user, **kwargs):
        super().__init__(**kwargs)
        self.messages = messages  # List of recent messages
        self.user = user
        self._context = None
        
    @property
    def context(self):
        """Get conversation context."""
        if self._context is None:
            self._context = self._build_context()
        return self._context
        
    def _build_context(self):
        """Build conversation context."""
        return {
            'message_count': len(self.messages),
            'time_span': self._calculate_time_span(),
            'topics': self._extract_topics(),
            'sentiment': self._analyze_sentiment(),
        }
        
    def _calculate_time_span(self):
        """Calculate conversation time span."""
        if not self.messages:
            return 0
        return (
            self.messages[-1].date - self.messages[0].date
        ).total_seconds()
        
    async def get_full_history(self, limit=100):
        """Get extended conversation history."""
        return await self.client.get_messages(
            self.chat,
            limit=limit,
            from_user=self.user
        )

class ConversationEventBuilder(EventBuilder):
    """
    Builder that aggregates messages into conversations.
    """
    
    def __init__(self, window=300, min_messages=2, **kwargs):
        super().__init__(**kwargs)
        self.window = window  # Time window in seconds
        self.min_messages = min_messages
        self._conversations = defaultdict(list)
        
    def build(self, update, others=None, self_id=None):
        """Build conversation events."""
        if not isinstance(update, types.UpdateNewMessage):
            return None
            
        message = update.message
        user_id = message.from_id.user_id if message.from_id else None
        
        if not user_id:
            return None
            
        # Add to conversation buffer
        key = (message.peer_id, user_id)
        self._conversations[key].append(message)
        
        # Clean old messages
        cutoff = datetime.now() - timedelta(seconds=self.window)
        self._conversations[key] = [
            msg for msg in self._conversations[key]
            if msg.date > cutoff
        ]
        
        # Check if we have enough messages
        if len(self._conversations[key]) >= self.min_messages:
            return ConversationEvent(
                messages=self._conversations[key][:],
                user=others.get(user_id),
                original_update=update
            )
            
        return None
```

## Event Transformers

### Enriching Events

```python
class EventEnricher:
    """
    Enriches events with additional data.
    """
    
    def __init__(self, client):
        self.client = client
        self._cache = {}
        
    async def enrich(self, event):
        """Enrich event with additional data."""
        # Add user details
        if hasattr(event, 'sender_id'):
            event.sender = await self._get_user(event.sender_id)
            
        # Add chat details
        if hasattr(event, 'chat_id'):
            event.chat = await self._get_chat(event.chat_id)
            
        # Add custom metadata
        event.metadata = await self._get_metadata(event)
        
        return event
        
    async def _get_user(self, user_id):
        """Get user with caching."""
        if user_id not in self._cache:
            self._cache[user_id] = await self.client.get_entity(user_id)
        return self._cache[user_id]
        
    async def _get_metadata(self, event):
        """Get event metadata."""
        return {
            'timestamp': datetime.now(),
            'event_type': type(event).__name__,
            'session_id': self.client.session.filename,
        }

# Usage
enricher = EventEnricher(client)

@client.on(events.NewMessage())
async def enriched_handler(event):
    # Enrich event
    event = await enricher.enrich(event)
    
    # Now we have additional data
    print(f"Message from {event.sender.first_name}")
    print(f"Chat type: {event.chat.__class__.__name__}")
    print(f"Metadata: {event.metadata}")
```

### Event Aggregators

```python
class AggregatedEvent(EventCommon):
    """
    Event that aggregates multiple sub-events.
    """
    
    def __init__(self, events, event_type, **kwargs):
        super().__init__(**kwargs)
        self.events = events
        self.event_type = event_type
        self.count = len(events)
        
    @property
    def time_range(self):
        """Get time range of aggregated events."""
        if not self.events:
            return None, None
            
        times = [e.date for e in self.events if hasattr(e, 'date')]
        return min(times), max(times)
        
    def get_unique_users(self):
        """Get unique users from events."""
        users = set()
        for event in self.events:
            if hasattr(event, 'sender_id'):
                users.add(event.sender_id)
        return users

class EventAggregator:
    """
    Aggregates events over time windows.
    """
    
    def __init__(self, window=60, threshold=10):
        self.window = window  # Time window in seconds
        self.threshold = threshold  # Min events to trigger
        self._buffer = defaultdict(list)
        self._timers = {}
        
    def add_event(self, event, key=None):
        """Add event to aggregation buffer."""
        if key is None:
            key = type(event).__name__
            
        self._buffer[key].append(event)
        
        # Start timer if needed
        if key not in self._timers:
            self._timers[key] = asyncio.create_task(
                self._flush_after_timeout(key)
            )
            
        # Check threshold
        if len(self._buffer[key]) >= self.threshold:
            return self._flush_buffer(key)
            
        return None
        
    async def _flush_after_timeout(self, key):
        """Flush buffer after timeout."""
        await asyncio.sleep(self.window)
        return self._flush_buffer(key)
        
    def _flush_buffer(self, key):
        """Flush and return aggregated event."""
        if key not in self._buffer or not self._buffer[key]:
            return None
            
        events = self._buffer[key]
        self._buffer[key] = []
        
        if key in self._timers:
            self._timers[key].cancel()
            del self._timers[key]
            
        return AggregatedEvent(
            events=events,
            event_type=key
        )
```

## External Integration Events

### Webhook Events

```python
class WebhookEvent(EventCommon):
    """
    Event triggered by external webhook.
    """
    
    def __init__(self, endpoint, method, headers, data, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = endpoint
        self.method = method
        self.headers = headers
        self.data = data
        
    @property
    def json(self):
        """Parse JSON data."""
        if isinstance(self.data, (str, bytes)):
            return json.loads(self.data)
        return self.data
        
    async def respond(self, status=200, data=None):
        """Send webhook response."""
        # Implementation depends on webhook server
        pass

class WebhookEventBuilder:
    """
    Integrates external webhooks as events.
    """
    
    def __init__(self, client, port=8080):
        self.client = client
        self.port = port
        self.app = None
        self._handlers = {}
        
    async def start(self):
        """Start webhook server."""
        from aiohttp import web
        
        self.app = web.Application()
        self.app.router.add_route('*', '/{path:.*}', self._handle_request)
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        
    async def _handle_request(self, request):
        """Handle incoming webhook."""
        # Create event
        event = WebhookEvent(
            endpoint=request.path,
            method=request.method,
            headers=dict(request.headers),
            data=await request.read()
        )
        
        # Dispatch to Telethon event system
        await self.client._dispatch_update(event)
        
        return web.Response(status=200)
        
    def on_webhook(self, endpoint, method='POST'):
        """Decorator for webhook handlers."""
        def decorator(func):
            key = (endpoint, method)
            self._handlers[key] = func
            return func
        return decorator
```

### Database Change Events

```python
class DatabaseChangeEvent(EventCommon):
    """
    Event triggered by database changes.
    """
    
    def __init__(self, table, operation, old_data, new_data, **kwargs):
        super().__init__(**kwargs)
        self.table = table
        self.operation = operation  # INSERT, UPDATE, DELETE
        self.old_data = old_data
        self.new_data = new_data
        
    @property
    def changed_fields(self):
        """Get fields that changed."""
        if self.operation != 'UPDATE':
            return []
            
        changes = []
        for key in self.new_data:
            if key in self.old_data and self.old_data[key] != self.new_data[key]:
                changes.append(key)
        return changes

class DatabaseWatcher:
    """
    Watches database for changes and emits events.
    """
    
    def __init__(self, client, db_connection):
        self.client = client
        self.db = db_connection
        self._watching = False
        
    async def start_watching(self, tables):
        """Start watching specified tables."""
        self._watching = True
        
        # PostgreSQL LISTEN/NOTIFY example
        for table in tables:
            await self.db.execute(f"""
                CREATE OR REPLACE FUNCTION notify_{table}() 
                RETURNS trigger AS $$
                BEGIN
                    PERFORM pg_notify(
                        'table_change',
                        json_build_object(
                            'table', TG_TABLE_NAME,
                            'operation', TG_OP,
                            'old', row_to_json(OLD),
                            'new', row_to_json(NEW)
                        )::text
                    );
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                
                CREATE TRIGGER {table}_notify
                AFTER INSERT OR UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION notify_{table}();
            """)
            
        # Listen for notifications
        await self.db.add_listener('table_change', self._handle_notification)
        
    async def _handle_notification(self, connection, pid, channel, payload):
        """Handle database notification."""
        data = json.loads(payload)
        
        event = DatabaseChangeEvent(
            table=data['table'],
            operation=data['operation'],
            old_data=data.get('old'),
            new_data=data.get('new')
        )
        
        # Dispatch to Telethon
        await self.client._dispatch_update(event)
```

## Event Pipelines

### Event Processing Pipeline

```python
class EventPipeline:
    """
    Pipeline for processing events through stages.
    """
    
    def __init__(self):
        self.stages = []
        
    def add_stage(self, stage):
        """Add processing stage."""
        self.stages.append(stage)
        return self
        
    async def process(self, event):
        """Process event through pipeline."""
        result = event
        
        for stage in self.stages:
            result = await stage(result)
            
            # Stage can stop pipeline
            if result is None:
                return None
                
            # Stage can transform event
            if isinstance(result, EventCommon):
                event = result
                
        return event

# Pipeline stages
async def validation_stage(event):
    """Validate event data."""
    if hasattr(event, 'text') and len(event.text) > 4096:
        return None  # Drop oversized messages
    return event

async def enrichment_stage(event):
    """Enrich with additional data."""
    if hasattr(event, 'sender_id'):
        event.risk_score = await calculate_risk_score(event.sender_id)
    return event

async def transformation_stage(event):
    """Transform event format."""
    if hasattr(event, 'text'):
        # Clean text
        event.text = clean_text(event.text)
        # Extract entities
        event.entities = extract_entities(event.text)
    return event

# Usage
pipeline = EventPipeline()
pipeline.add_stage(validation_stage)
pipeline.add_stage(enrichment_stage)
pipeline.add_stage(transformation_stage)

@client.on(events.NewMessage())
async def pipelined_handler(event):
    # Process through pipeline
    event = await pipeline.process(event)
    
    if event is None:
        return  # Event was filtered out
        
    # Use enriched event
    if event.risk_score > 0.8:
        await event.reply("High risk message detected")
```

## Best Practices

### Custom Event Design

1. **Extend Existing Events**: Build on Telethon's base classes
2. **Clear Semantics**: Make event purpose obvious
3. **Efficient Filtering**: Implement fast filter methods
4. **Proper Cleanup**: Handle resources in event lifecycle
5. **Document Behavior**: Clearly document custom events

### Integration Guidelines

1. **Loose Coupling**: Keep events independent
2. **Error Isolation**: Handle errors in custom events
3. **Performance**: Consider event frequency and processing cost
4. **Testing**: Write tests for custom event logic
5. **Compatibility**: Ensure compatibility with Telethon updates

## Example: Complete Custom Event System

```python
# Analytics event system
class AnalyticsEvent(EventCommon):
    """Base class for analytics events."""
    
    def __init__(self, event_name, properties=None, **kwargs):
        super().__init__(**kwargs)
        self.event_name = event_name
        self.properties = properties or {}
        self.timestamp = datetime.now()
        
    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            'event': self.event_name,
            'properties': self.properties,
            'timestamp': self.timestamp.isoformat(),
            'user_id': getattr(self, 'sender_id', None),
            'chat_id': getattr(self, 'chat_id', None),
        }

class AnalyticsTracker:
    """Tracks and processes analytics events."""
    
    def __init__(self, client):
        self.client = client
        self.events = []
        self.processors = []
        
    def track(self, event_name, **properties):
        """Track an analytics event."""
        event = AnalyticsEvent(event_name, properties)
        self.events.append(event)
        
        # Process event
        for processor in self.processors:
            processor(event)
            
        return event
        
    def add_processor(self, processor):
        """Add event processor."""
        self.processors.append(processor)
        
    def get_metrics(self):
        """Get analytics metrics."""
        return {
            'total_events': len(self.events),
            'unique_users': len(set(
                e.properties.get('user_id') 
                for e in self.events 
                if 'user_id' in e.properties
            )),
            'event_types': Counter(
                e.event_name for e in self.events
            ),
        }

# Integration with Telethon
tracker = AnalyticsTracker(client)

@client.on(events.NewMessage())
async def track_messages(event):
    tracker.track('message_received',
        user_id=event.sender_id,
        chat_id=event.chat_id,
        message_length=len(event.text),
        has_media=bool(event.media)
    )

# Custom processor
def amplitude_processor(event):
    """Send events to Amplitude."""
    # Integration code here
    pass

tracker.add_processor(amplitude_processor)
```

## Next Steps

- Review the [Protocol Overview](../protocol/overview.md) for protocol details
- See [Session Overview](../sessions/overview.md) for session management
- Explore [API Layer](../api/tl-schema.md) for Telegram API details

---
**Navigation:** [← Event Handling](handling.md) | [Home](../index.md) | [Up](../index.md) | [Protocol →](../protocol/README.md)

---