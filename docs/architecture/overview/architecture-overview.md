# Architecture Overview

---
**Navigation:** [← Introduction](introduction.md) | [Home](../index.md) | [Up](../index.md) | [Design Principles →](design-principles.md)

---

## System Architecture

Telethon follows a layered architecture design that separates concerns and provides multiple levels of abstraction. This design allows both low-level protocol access and high-level convenience methods.

## High-Level Architecture

```mermaid
graph TB
    subgraph "External Systems"
        TG[Telegram Servers]
        FS[File System]
        NET[Network]
    end
    
    subgraph "Telethon Library"
        subgraph "API Layer"
            TC[TelegramClient]
            EV[Event System]
            HM[Helper Methods]
        end
        
        subgraph "Protocol Layer"
            MPS[MTProtoSender]
            AUT[Authorization]
            CRY[Cryptography]
            SER[Serialization]
        end
        
        subgraph "Transport Layer"
            CON[Connection]
            TCP[TCP Transport]
            HTTP[HTTP Transport]
            DC[DC Manager]
        end
        
        subgraph "Storage Layer"
            SES[Session Storage]
            EC[Entity Cache]
            MB[Message Box]
        end
        
        subgraph "Generated Layer"
            TL[TL Types]
            FN[TL Functions]
            ERR[Error Types]
        end
    end
    
    subgraph "Application"
        APP[User Application]
    end
    
    APP --> TC
    APP --> EV
    TC --> HM
    TC --> MPS
    MPS --> AUT
    MPS --> CRY
    MPS --> SER
    MPS --> CON
    CON --> TCP
    CON --> HTTP
    CON --> DC
    TC --> SES
    SES --> EC
    MPS --> MB
    TC --> TL
    TC --> FN
    MPS --> ERR
    
    CON --> NET
    SES --> FS
    DC --> TG
```

## Component Layers

### 1. Application Layer
The topmost layer where user applications interact with Telethon.

**Key Components:**
- User application code
- Custom event handlers
- Business logic implementation

### 2. API Layer
Provides high-level interfaces for common operations.

**Key Components:**
- **TelegramClient**: Main client class with convenience methods
- **Event System**: Decorator-based event handling
- **Helper Methods**: Utility functions for common tasks
- **Mixins**: Modular functionality (messages, files, chats, etc.)

### 3. Protocol Layer
Implements the MTProto 2.0 protocol specification.

**Key Components:**
- **MTProtoSender**: Core protocol handler
- **Authorization**: Key exchange and authentication
- **Cryptography**: AES, RSA, and hash functions
- **Serialization**: Binary serialization of messages

### 4. Transport Layer
Manages network connections and data transmission.

**Key Components:**
- **Connection**: Abstract connection interface
- **Transports**: TCP, HTTP, and other implementations
- **DC Manager**: Data center selection and migration

### 5. Storage Layer
Handles persistent data and caching.

**Key Components:**
- **Session Storage**: Authentication persistence
- **Entity Cache**: User/chat information caching
- **Message Box**: Update gap detection and recovery

### 6. Generated Layer
Auto-generated code from Telegram's TL schema.

**Key Components:**
- **TL Types**: Data structures (User, Message, etc.)
- **TL Functions**: API methods (SendMessage, GetDialogs, etc.)
- **Error Types**: Typed error responses

## Data Flow

### Request Flow

```mermaid
sequenceDiagram
    participant App as Application
    participant TC as TelegramClient
    participant MPS as MTProtoSender
    participant CON as Connection
    participant TG as Telegram Server
    
    App->>TC: client.send_message()
    TC->>TC: Validate parameters
    TC->>TC: Resolve entities
    TC->>MPS: Send TL request
    MPS->>MPS: Assign msg_id
    MPS->>MPS: Encrypt message
    MPS->>CON: Send bytes
    CON->>TG: TCP/HTTP transport
    TG-->>CON: Encrypted response
    CON-->>MPS: Receive bytes
    MPS->>MPS: Decrypt message
    MPS->>MPS: Process response
    MPS-->>TC: Return result
    TC-->>App: Return Message object
```

### Update Flow

```mermaid
sequenceDiagram
    participant TG as Telegram Server
    participant CON as Connection
    participant MPS as MTProtoSender
    participant MB as MessageBox
    participant EV as Event System
    participant App as Application
    
    TG->>CON: Push update
    CON->>MPS: Receive bytes
    MPS->>MPS: Decrypt update
    MPS->>MB: Process update
    MB->>MB: Check for gaps
    MB->>MPS: Acknowledge
    MPS->>EV: Dispatch event
    EV->>App: Trigger handler
    App->>App: Process event
```

## Key Design Patterns

### 1. Mixin Pattern
Client functionality is divided into focused mixins:

```python
class TelegramClient(
    UserMethods,
    MessageMethods,
    FileMethods,
    ChatMethods,
    # ... other mixins
    TelegramBaseClient
):
    pass
```

### 2. Event-Driven Architecture
Events are handled through decorators:

```python
@client.on(events.NewMessage)
async def handler(event):
    # Handle new messages
    pass
```

### 3. Builder Pattern
Complex objects use builders:

```python
event = events.NewMessage.build(
    chats=['username'],
    pattern=r'hello'
)
```

### 4. Abstract Factory
Connection types are created through factories:

```python
connection = ConnectionTcpFull(
    ip='149.154.167.51',
    port=443
)
```

## Threading Model

```mermaid
graph LR
    subgraph "Main Thread"
        EL[Event Loop]
        TC[TelegramClient]
    end
    
    subgraph "Network Thread"
        RCV[Receive Loop]
        SND[Send Loop]
    end
    
    subgraph "Worker Threads"
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker N]
    end
    
    EL --> TC
    TC --> SND
    RCV --> TC
    TC --> W1
    TC --> W2
    TC --> W3
```

**Key Points:**
- Single event loop for async operations
- Dedicated threads for network I/O
- Worker threads for CPU-intensive tasks
- Thread-safe queues for communication

## Memory Management

### Caching Strategy

```mermaid
graph TD
    subgraph "Memory Cache"
        EC[Entity Cache]
        MC[Message Cache]
        FC[File Cache]
    end
    
    subgraph "Persistent Storage"
        SES[Session DB]
        FILES[Downloaded Files]
    end
    
    subgraph "Eviction Policies"
        LRU[LRU for Entities]
        TTL[TTL for Messages]
        SIZE[Size Limits]
    end
    
    EC --> LRU
    MC --> TTL
    FC --> SIZE
    EC --> SES
    FC --> FILES
```

### Resource Management
- Connection pooling for multiple DCs
- Automatic cleanup of expired data
- Configurable cache sizes
- Lazy loading of large data

## Security Architecture

### Encryption Layers

```mermaid
graph TD
    subgraph "Application Data"
        MSG[Plain Message]
    end
    
    subgraph "MTProto Layer"
        ENC[AES Encryption]
        AUTH[Auth Key]
        SALT[Message Salt]
    end
    
    subgraph "Transport Layer"
        TLS[TLS Optional]
        TCP[TCP Stream]
    end
    
    MSG --> ENC
    AUTH --> ENC
    SALT --> ENC
    ENC --> TLS
    TLS --> TCP
```

### Security Features
- End-to-end encryption for secret chats
- Perfect forward secrecy
- Replay attack prevention
- DH key exchange for authorization

## Scalability Considerations

### Horizontal Scaling
- Multiple client instances
- Connection pooling
- Load distribution across DCs

### Vertical Scaling
- Async I/O for concurrent operations
- Efficient binary protocol
- Minimal memory footprint
- Lazy evaluation

## Next Steps

- Continue to [Design Principles](design-principles.md) for architectural decisions
- See [Core Components](../core/components.md) for detailed component analysis
- Explore [MTProto Sender](../network/mtproto-sender.md) for protocol details

---
**Navigation:** [← Introduction](introduction.md) | [Home](../index.md) | [Up](../index.md) | [Design Principles →](design-principles.md)

---