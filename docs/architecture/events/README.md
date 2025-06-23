# Event System

---
**Navigation:** [← Entity Cache](../sessions/entity-cache.md) | [Home](../index.md) | [Architecture →](architecture.md)

---

## About This Section

The event system documentation covers Telethon's powerful event-driven architecture, which allows applications to react to real-time updates from Telegram.

## Contents

### [Architecture](architecture.md)
- Event system design
- Update processing pipeline
- Handler registration
- Event dispatching

### [Event Types](types.md)
- NewMessage events
- Edit and delete events
- User and chat updates
- Media events
- Raw events

### [Event Handling](handling.md)
- Handler registration
- Event filters
- Priority system
- Error handling

### [Custom Events](custom.md)
- Creating custom events
- Event builders
- Custom filters
- Advanced patterns

## Key Concepts

- **Real-time Updates**: React to messages and changes as they happen
- **Event Filters**: Process only relevant events
- **Async Handlers**: Non-blocking event processing
- **Event Priority**: Control handler execution order

## Event Flow

```
┌─────────────────────────┐
│   Telegram Server       │
├─────────────────────────┤
│   Update Stream         │
├─────────────────────────┤
│   Event Builder         │
├─────────────────────────┤
│   Filter System         │
├─────────────────────────┤
│   User Handlers         │
└─────────────────────────┘
```

## Common Usage

```python
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply('Welcome!')
```

## Next Steps

- Start with [Architecture](architecture.md) to understand the system
- Review [Event Types](types.md) for available events
- See [Internals](../internals/README.md) for implementation details

---
**Navigation:** [← Entity Cache](../sessions/entity-cache.md) | [Home](../index.md) | [Architecture →](architecture.md)

---