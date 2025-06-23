# API Layer

---
**Navigation:** [← Message Format](../protocol/message-format.md) | [Home](../index.md) | [TL Schema →](tl-schema.md)

---

## About This Section

The API layer documentation covers the Type Language (TL) schema system, type definitions, and API versioning used in Telethon to interact with Telegram's API.

## Contents

### [TL Schema](tl-schema.md)
- Type Language overview
- Schema definition format
- Code generation process
- Schema updates

### [Voice Transcription TL Schema](voice-transcription-tl-schema.md)
- Voice transcription API methods
- Request/response types
- Update handling
- Integration examples

### [Types and Functions](types-functions.md)
- Common types reference
- Function categories
- Request/response patterns
- Type hierarchies

### [Custom Types](custom-types.md)
- Creating custom types
- Type extensions
- Helper utilities
- Type validation

### [API Versioning](versioning.md)
- Layer system
- Backward compatibility
- Migration strategies
- Version negotiation

### Tools
- [`validate-tl-schemas.py`](validate-tl-schemas.py) - Validate TL schema integration

## Key Concepts

- **TL (Type Language)**: Schema definition language for API types
- **Constructors**: Define how objects are serialized
- **Functions**: RPC methods that can be called
- **Layers**: API version management system

## Type System Overview

```
┌─────────────────────────┐
│    User Types (High)    │  - Message, User, Chat
├─────────────────────────┤
│   Generated Types       │  - From TL schema
├─────────────────────────┤
│   Base Types (Core)     │  - Int, String, Bytes
├─────────────────────────┤
│  Serialization Layer    │  - Binary encoding
└─────────────────────────┘
```

## Next Steps

- Start with [TL Schema](tl-schema.md) to understand type definitions
- Review [Types and Functions](types-functions.md) for API reference
- See [Sessions](../sessions/README.md) for data persistence

---
**Navigation:** [← Message Format](../protocol/message-format.md) | [Home](../index.md) | [TL Schema →](tl-schema.md)

---