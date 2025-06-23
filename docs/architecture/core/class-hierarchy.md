# Class Hierarchy

---
**Navigation:** [← Core Components](components.md) | [Home](../index.md) | [Up](../index.md) | [Module Organization →](module-organization.md)

---

## Overview

Telethon's class hierarchy follows a well-structured object-oriented design that promotes code reuse, maintainability, and clear separation of concerns. The hierarchy uses multiple inheritance patterns, particularly mixins, to compose functionality.

## Main Class Hierarchy

```mermaid
classDiagram
    class TelegramBaseClient {
        <<abstract>>
        +api_id: int
        +api_hash: str
        +session: Session
        +flood_sleep_threshold: int
        +connect()
        +disconnect()
        +is_connected()
    }
    
    class AuthMethods {
        +start()
        +sign_in()
        +sign_up()
        +send_code_request()
        +log_out()
        +edit_2fa()
    }
    
    class MessageMethods {
        +send_message()
        +edit_message()
        +delete_messages()
        +forward_messages()
        +get_messages()
        +iter_messages()
    }
    
    class FileMethods {
        +send_file()
        +upload_file()
        +download_media()
        +download_profile_photo()
        +download_file()
        +iter_download()
    }
    
    class ChatMethods {
        +get_participants()
        +get_admin_log()
        +kick_participant()
        +edit_permissions()
        +create_channel()
        +create_group()
    }
    
    class DialogMethods {
        +get_dialogs()
        +iter_dialogs()
        +get_drafts()
        +archive()
        +unarchive()
    }
    
    class UserMethods {
        +get_me()
        +get_entity()
        +get_input_entity()
        +get_peer_id()
        +is_bot()
        +is_user_authorized()
    }
    
    class UpdateMethods {
        +catch_up()
        +on()
        +add_event_handler()
        +remove_event_handler()
        +list_event_handlers()
        +run_until_disconnected()
    }
    
    class TelegramClient
    
    TelegramBaseClient <|-- TelegramClient
    AuthMethods <|-- TelegramClient
    MessageMethods <|-- TelegramClient
    FileMethods <|-- TelegramClient
    ChatMethods <|-- TelegramClient
    DialogMethods <|-- TelegramClient
    UserMethods <|-- TelegramClient
    UpdateMethods <|-- TelegramClient
```

## TL Object Hierarchy

```mermaid
classDiagram
    class TLObject {
        <<abstract>>
        +CONSTRUCTOR_ID: int
        +SUBCLASS_OF_ID: int
        +to_bytes() bytes
        +from_bytes(data) TLObject
        +to_dict() dict
        +stringify() str
    }
    
    class TLRequest {
        <<abstract>>
        +resolve(client)
        +read_result(reader)
    }
    
    class User {
        +id: int
        +is_self: bool
        +username: str
        +phone: str
        +first_name: str
        +last_name: str
        +photo: UserProfilePhoto
    }
    
    class Chat {
        +id: int
        +title: str
        +photo: ChatPhoto
        +participants_count: int
        +date: datetime
    }
    
    class Channel {
        +id: int
        +title: str
        +username: str
        +photo: ChatPhoto
        +broadcast: bool
        +megagroup: bool
    }
    
    class Message {
        +id: int
        +peer_id: Peer
        +date: datetime
        +message: str
        +out: bool
        +media: MessageMedia
        +reply_to: MessageReplyHeader
    }
    
    TLObject <|-- TLRequest
    TLObject <|-- User
    TLObject <|-- Chat
    TLObject <|-- Channel
    TLObject <|-- Message
```

## Session Hierarchy

```mermaid
classDiagram
    class Session {
        <<abstract>>
        +dc_id: int
        +server_address: str
        +port: int
        +auth_key: AuthKey
        +save()
        +close()
        +get_update_state()
        +set_update_state()
    }
    
    class MemorySession {
        -_dc_id: int
        -_server_address: str
        -_port: int
        -_auth_key: AuthKey
        -_entities: dict
    }
    
    class SQLiteSession {
        -filename: str
        -save_entities: bool
        -_conn: Connection
        -_cursor: Cursor
        +_create_tables()
        +_save_entities()
    }
    
    class StringSession {
        -_string: str
        +save() str
        +load(string)
    }
    
    Session <|-- MemorySession
    Session <|-- SQLiteSession
    Session <|-- StringSession
```

## Event Hierarchy

```mermaid
classDiagram
    class Event {
        <<abstract>>
        +client: TelegramClient
        +original_update: TLObject
        +to_dict() dict
    }
    
    class NewMessage {
        +message: Message
        +pattern: Pattern
        +outgoing: bool
        +incoming: bool
        +from_users: list
        +forwards: bool
    }
    
    class MessageEdited {
        +message: Message
        +pattern: Pattern
        +outgoing: bool
        +incoming: bool
    }
    
    class MessageDeleted {
        +deleted_ids: list
        +peer: Peer
    }
    
    class UserUpdate {
        +user: User
        +status: UserStatus
        +typing: bool
    }
    
    class ChatAction {
        +chat: Chat
        +user: User
        +action: SendMessageAction
    }
    
    class CallbackQuery {
        +id: int
        +user: User
        +message: Message
        +data: bytes
        +chat_instance: int
    }
    
    Event <|-- NewMessage
    Event <|-- MessageEdited
    Event <|-- MessageDeleted
    Event <|-- UserUpdate
    Event <|-- ChatAction
    Event <|-- CallbackQuery
```

## Connection Hierarchy

```mermaid
classDiagram
    class Connection {
        <<abstract>>
        +ip: str
        +port: int
        +loop: asyncio.AbstractEventLoop
        +connect()
        +disconnect()
        +send(data)
        +recv()
    }
    
    class ConnectionTcpFull {
        +packet_codec: PacketCodec
        +_send_packet()
        +_recv_packet()
    }
    
    class ConnectionTcpAbridged {
        +_send_packet()
        +_recv_packet()
    }
    
    class ConnectionTcpIntermediate {
        +_send_packet()
        +_recv_packet()
    }
    
    class ConnectionTcpObfuscated {
        +_init_header: bytes
        +_encrypt: AESModeCTR
        +_decrypt: AESModeCTR
    }
    
    class ConnectionHttp {
        +_session: aiohttp.ClientSession
        +_send_packet()
        +_recv_packet()
    }
    
    Connection <|-- ConnectionTcpFull
    Connection <|-- ConnectionTcpAbridged
    Connection <|-- ConnectionTcpIntermediate
    ConnectionTcpAbridged <|-- ConnectionTcpObfuscated
    Connection <|-- ConnectionHttp
```

## Error Hierarchy

```mermaid
classDiagram
    class TelegramError {
        <<abstract>>
        +message: str
        +code: int
    }
    
    class RPCError {
        +code: int
        +message: str
        +_from_code(code, message)
    }
    
    class InvalidDCError {
        +dc: int
    }
    
    class FloodWaitError {
        +seconds: int
    }
    
    class FileMigrateError {
        +dc: int
    }
    
    class AuthKeyError {
        +message: str
    }
    
    class SecurityError {
        +message: str
    }
    
    class BadMessageError {
        +code: int
    }
    
    TelegramError <|-- RPCError
    RPCError <|-- InvalidDCError
    RPCError <|-- FloodWaitError
    RPCError <|-- FileMigrateError
    TelegramError <|-- AuthKeyError
    TelegramError <|-- SecurityError
    TelegramError <|-- BadMessageError
```

## Custom Type Hierarchy

```mermaid
classDiagram
    class ChatGetter {
        <<interface>>
        +chat: Chat
        +input_chat: InputPeer
        +chat_id: int
        +is_private: bool
        +is_group: bool
        +is_channel: bool
    }
    
    class SenderGetter {
        <<interface>>
        +sender: User
        +input_sender: InputPeer
        +sender_id: int
    }
    
    class Forward {
        +original_date: datetime
        +original_sender: User
        +original_chat: Chat
        +original_message_id: int
    }
    
    class File {
        +id: int
        +name: str
        +mime_type: str
        +size: int
        +width: int
        +height: int
        +duration: int
    }
    
    class Dialog {
        +dialog: TLDialog
        +pinned: bool
        +folder_id: int
        +archived: bool
        +message: Message
        +entity: Entity
    }
    
    class Button {
        +text: str
        +data: bytes
        +url: str
        +resize: bool
        +single_use: bool
        +selective: bool
    }
    
    ChatGetter <|.. Message
    SenderGetter <|.. Message
    ChatGetter <|.. Dialog
```

## Inheritance Patterns

### 1. Mixin Pattern
```python
class TelegramClient(
    UserMethods,
    MessageMethods,
    FileMethods,
    ChatMethods,
    DialogMethods,
    UpdateMethods,
    AuthMethods,
    TelegramBaseClient
):
    """
    Compose functionality through multiple inheritance.
    Each mixin provides a specific set of methods.
    """
    pass
```

### 2. Abstract Base Classes
```python
from abc import ABC, abstractmethod

class Session(ABC):
    """Abstract base for session implementations"""
    
    @abstractmethod
    def save(self):
        """Save session state"""
        pass
    
    @abstractmethod
    def get_auth_key(self):
        """Get authorization key"""
        pass
```

### 3. Protocol Classes
```python
from typing import Protocol

class ChatGetter(Protocol):
    """Protocol for objects that have chat information"""
    
    @property
    def chat(self) -> Chat:
        """Get the chat"""
        ...
    
    @property
    def chat_id(self) -> int:
        """Get the chat ID"""
        ...
```

## Design Benefits

### Separation of Concerns
- Each mixin handles a specific domain
- Clear boundaries between components
- Easy to understand and maintain

### Code Reusability
- Common functionality in base classes
- Mixins can be reused in different contexts
- Protocol classes enable duck typing

### Extensibility
- New mixins can be added easily
- Inheritance allows customization
- Abstract classes define contracts

### Type Safety
- Clear type hierarchies
- Protocol classes for structural typing
- Generated classes maintain type information

## Implementation Examples

### Creating a Custom Client
```python
class CustomClient(MessageMethods, AuthMethods, TelegramBaseClient):
    """Custom client with only messaging and auth"""
    
    def __init__(self, session, api_id, api_hash):
        super().__init__(session, api_id, api_hash)
        # Custom initialization
```

### Extending Events
```python
class CustomEvent(NewMessage):
    """Extended message event with custom logic"""
    
    def __init__(self, message):
        super().__init__(message)
        self.custom_field = self._process_custom()
    
    def _process_custom(self):
        # Custom processing
        pass
```

### Custom Session Implementation
```python
class RedisSession(Session):
    """Session backed by Redis"""
    
    def __init__(self, redis_client):
        self._redis = redis_client
    
    def save(self):
        # Save to Redis
        pass
    
    def get_auth_key(self):
        # Get from Redis
        pass
```

## Next Steps

- Continue to [Module Organization](module-organization.md) for package structure
- See [Dependencies](dependencies.md) for dependency management
- Explore [TelegramClient](../client/telegram-client.md) for client implementation

---
**Navigation:** [← Core Components](components.md) | [Home](../index.md) | [Up](../index.md) | [Module Organization →](module-organization.md)

---