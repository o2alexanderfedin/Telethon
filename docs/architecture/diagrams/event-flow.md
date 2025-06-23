# Event Flow

---
**Navigation:** [← Network Flow](network-flow.md) | [Home](../index.md) | [Up](../index.md) | [Client →](../client/README.md)

---

## Overview

This document visualizes how events flow through Telethon's event system, from receiving updates to dispatching events to user handlers. It shows the complete lifecycle of events, filtering mechanisms, and handler execution.

## Event Processing Pipeline

```mermaid
graph TB
    subgraph "Update Reception"
        UPDATE[Telegram Update] --> RECEIVER[Update Receiver]
        RECEIVER --> VALIDATOR[Update Validator]
        VALIDATOR --> SEQUENCER[Sequence Handler]
    end
    
    subgraph "Event Building"
        SEQUENCER --> BUILDER[Event Builder]
        BUILDER --> TYPE_CHECK{Determine Type}
        
        TYPE_CHECK --> NEW_MSG[NewMessage Event]
        TYPE_CHECK --> MSG_EDIT[MessageEdited Event]
        TYPE_CHECK --> MSG_DEL[MessageDeleted Event]
        TYPE_CHECK --> USER_UPD[UserUpdate Event]
        TYPE_CHECK --> CHAT_ACT[ChatAction Event]
        TYPE_CHECK --> CALL_EVT[CallbackQuery Event]
        TYPE_CHECK --> INLINE_EVT[InlineQuery Event]
        TYPE_CHECK --> RAW_EVT[Raw Event]
    end
    
    subgraph "Event Dispatching"
        NEW_MSG --> DISPATCHER[Event Dispatcher]
        MSG_EDIT --> DISPATCHER
        MSG_DEL --> DISPATCHER
        USER_UPD --> DISPATCHER
        CHAT_ACT --> DISPATCHER
        CALL_EVT --> DISPATCHER
        INLINE_EVT --> DISPATCHER
        RAW_EVT --> DISPATCHER
        
        DISPATCHER --> HANDLERS[Handler Registry]
    end
    
    subgraph "Handler Execution"
        HANDLERS --> FILTER[Filter Check]
        FILTER --> PRIORITY[Priority Sort]
        PRIORITY --> EXECUTE[Execute Handlers]
        EXECUTE --> STOP_CHECK{Stop Propagation?}
        
        STOP_CHECK -->|No| NEXT[Next Handler]
        STOP_CHECK -->|Yes| DONE[Complete]
        
        NEXT --> FILTER
    end
```

## Update to Event Conversion

```mermaid
sequenceDiagram
    participant Server as Telegram Server
    participant Client as TelegramClient
    participant Builder as Event Builder
    participant Registry as Event Registry
    participant Handler as User Handler

    Server->>Client: UpdateNewMessage
    Client->>Client: Validate Update
    Client->>Builder: Build Event
    
    Builder->>Builder: Extract Message
    Builder->>Builder: Resolve Entities
    Builder->>Builder: Parse Text/Media
    Builder->>Builder: Create NewMessage Event
    
    Builder-->>Client: NewMessage Event
    
    Client->>Registry: Find Handlers
    Registry->>Registry: Get NewMessage Handlers
    Registry-->>Client: Handler List
    
    loop For each handler
        Client->>Handler: Check Filters
        alt Filters Pass
            Client->>Handler: Execute Handler
            Handler-->>Client: Result
            
            alt Stop Propagation
                Client->>Client: Stop Processing
            else Continue
                Client->>Client: Next Handler
            end
        else Filters Fail
            Client->>Client: Skip Handler
        end
    end
```

## Event Type Hierarchy

```mermaid
graph TB
    subgraph "Event Class Hierarchy"
        EVENT[Event Base Class]
        
        EVENT --> MESSAGE[Message Events]
        EVENT --> USER[User Events]
        EVENT --> CHAT[Chat Events]
        EVENT --> MEDIA[Media Events]
        EVENT --> CALLBACK[Callback Events]
        EVENT --> RAW[Raw Events]
        
        MESSAGE --> NEW_MESSAGE[NewMessage]
        MESSAGE --> MESSAGE_EDITED[MessageEdited]
        MESSAGE --> MESSAGE_DELETED[MessageDeleted]
        MESSAGE --> MESSAGE_READ[MessageRead]
        
        USER --> USER_UPDATE[UserUpdate]
        USER --> USER_STATUS[UserStatus]
        USER --> USER_TYPING[UserTyping]
        
        CHAT --> CHAT_ACTION[ChatAction]
        CHAT --> PARTICIPANT_UPDATE[ParticipantUpdate]
        CHAT --> ADMIN_LOG[AdminLogEvent]
        
        MEDIA --> ALBUM[Album]
        MEDIA --> PHOTO[Photo]
        MEDIA --> VIDEO[Video]
        MEDIA --> DOCUMENT[Document]
        
        CALLBACK --> CALLBACK_QUERY[CallbackQuery]
        CALLBACK --> INLINE_QUERY[InlineQuery]
        CALLBACK --> CHOSEN_INLINE[ChosenInlineResult]
        
        RAW --> UPDATE_SHORT[UpdateShort]
        RAW --> UPDATE_COMBINED[UpdatesCombined]
        RAW --> UPDATE_TOO_LONG[UpdatesTooLong]
    end
```

## Handler Registration Flow

```mermaid
graph LR
    subgraph "Handler Registration"
        DECORATOR[@events.register] --> FUNC[Handler Function]
        FUNC --> ANALYZE[Analyze Signature]
        ANALYZE --> EXTRACT[Extract Event Type]
        EXTRACT --> FILTERS[Extract Filters]
        
        FILTERS --> PATTERN[Pattern Filter]
        FILTERS --> CHATS[Chats Filter]
        FILTERS --> FUNC_FILTER[Function Filter]
        FILTERS --> INCOMING[Incoming Filter]
        FILTERS --> OUTGOING[Outgoing Filter]
        
        subgraph "Registry Storage"
            REGISTRY[Handler Registry]
            EVENT_MAP[Event Type Map]
            HANDLER_LIST[Handler List]
            PRIORITY_QUEUE[Priority Queue]
        end
        
        EXTRACT --> EVENT_MAP
        PATTERN --> HANDLER_LIST
        CHATS --> HANDLER_LIST
        FUNC_FILTER --> HANDLER_LIST
        INCOMING --> HANDLER_LIST
        OUTGOING --> HANDLER_LIST
        
        HANDLER_LIST --> PRIORITY_QUEUE
        EVENT_MAP --> REGISTRY
        PRIORITY_QUEUE --> REGISTRY
    end
```

## Event Filtering System

```mermaid
graph TB
    subgraph "Filter Pipeline"
        EVENT[Incoming Event]
        
        subgraph "Built-in Filters"
            F1{Pattern Match?}
            F2{Chat Match?}
            F3{From User?}
            F4{Is Incoming?}
            F5{Has Media?}
            F6{Is Forward?}
            F7{Is Reply?}
        end
        
        subgraph "Custom Filters"
            CF1{Custom Filter 1}
            CF2{Custom Filter 2}
            CF3{Lambda Filter}
        end
        
        EVENT --> F1
        F1 -->|Pass| F2
        F1 -->|Fail| REJECT1[Reject]
        
        F2 -->|Pass| F3
        F2 -->|Fail| REJECT2[Reject]
        
        F3 -->|Pass| F4
        F3 -->|Fail| REJECT3[Reject]
        
        F4 -->|Pass| F5
        F4 -->|Fail| REJECT4[Reject]
        
        F5 -->|Pass| F6
        F5 -->|Fail| REJECT5[Reject]
        
        F6 -->|Pass| F7
        F6 -->|Fail| REJECT6[Reject]
        
        F7 -->|Pass| CF1
        F7 -->|Fail| REJECT7[Reject]
        
        CF1 -->|Pass| CF2
        CF1 -->|Fail| REJECT8[Reject]
        
        CF2 -->|Pass| CF3
        CF2 -->|Fail| REJECT9[Reject]
        
        CF3 -->|Pass| EXECUTE[Execute Handler]
        CF3 -->|Fail| REJECT10[Reject]
    end
    
    style EXECUTE fill:#4caf50
    style REJECT1 fill:#f44336
    style REJECT2 fill:#f44336
    style REJECT3 fill:#f44336
    style REJECT4 fill:#f44336
    style REJECT5 fill:#f44336
    style REJECT6 fill:#f44336
    style REJECT7 fill:#f44336
    style REJECT8 fill:#f44336
    style REJECT9 fill:#f44336
    style REJECT10 fill:#f44336
```

## Asynchronous Event Handling

```mermaid
sequenceDiagram
    participant Main as Main Loop
    participant Dispatcher as Event Dispatcher
    participant H1 as Handler 1 (async)
    participant H2 as Handler 2 (async)
    participant H3 as Handler 3 (sync)
    participant Executor as Thread Executor

    Main->>Dispatcher: NewMessage Event
    
    Dispatcher->>Dispatcher: Sort handlers by priority
    
    par Async Handler 1
        Dispatcher->>H1: await handler1(event)
        H1-->>Dispatcher: Complete
    and Async Handler 2
        Dispatcher->>H2: await handler2(event)
        H2-->>Dispatcher: Complete
    and Sync Handler 3
        Dispatcher->>Executor: run_in_executor(handler3)
        Executor->>H3: handler3(event)
        H3-->>Executor: Complete
        Executor-->>Dispatcher: Complete
    end
    
    Dispatcher-->>Main: All handlers complete
```

## Event State Management

```mermaid
stateDiagram-v2
    [*] --> Created: Update Received
    
    Created --> Building: Start Building
    Building --> TypeDetection: Detect Event Type
    
    TypeDetection --> MessageEvent: Is Message
    TypeDetection --> UserEvent: Is User Update
    TypeDetection --> ChatEvent: Is Chat Update
    TypeDetection --> RawEvent: Unknown Type
    
    MessageEvent --> Enrichment
    UserEvent --> Enrichment
    ChatEvent --> Enrichment
    RawEvent --> Ready
    
    state Enrichment {
        [*] --> ResolveEntities
        ResolveEntities --> ParseContent
        ParseContent --> AddMetadata
        AddMetadata --> [*]
    }
    
    Enrichment --> Ready: Event Built
    
    Ready --> Dispatching: Start Dispatch
    
    state Dispatching {
        [*] --> FindHandlers
        FindHandlers --> FilterHandlers
        FilterHandlers --> SortByPriority
        SortByPriority --> Execute
        
        state Execute {
            [*] --> Running
            Running --> Success
            Running --> Error
            Success --> [*]
            Error --> [*]
        }
    }
    
    Dispatching --> Completed: All Handlers Done
    Dispatching --> Stopped: Stop Propagation
    
    Completed --> [*]
    Stopped --> [*]
```

## Pattern Matching Flow

```mermaid
graph TB
    subgraph "Pattern Matching System"
        MSG[Message Text: "Hello World!"]
        
        subgraph "Pattern Types"
            P1[Regex Pattern<br/>/hello.*/i]
            P2[String Pattern<br/>"hello"]
            P3[Command Pattern<br/>"/start"]
            P4[Callable Pattern<br/>lambda x: ...]
        end
        
        subgraph "Matching Process"
            CHECK1{Regex Match?}
            CHECK2{String Match?}
            CHECK3{Command Match?}
            CHECK4{Callable Match?}
        end
        
        MSG --> CHECK1
        P1 --> CHECK1
        
        CHECK1 -->|Match| CAPTURE1[Capture Groups]
        CHECK1 -->|No Match| CHECK2
        
        P2 --> CHECK2
        CHECK2 -->|Match| CAPTURE2[Full Match]
        CHECK2 -->|No Match| CHECK3
        
        P3 --> CHECK3
        CHECK3 -->|Match| CAPTURE3[Command Args]
        CHECK3 -->|No Match| CHECK4
        
        P4 --> CHECK4
        CHECK4 -->|True| CAPTURE4[Callable Result]
        CHECK4 -->|False| NO_MATCH[No Pattern Match]
        
        CAPTURE1 --> ATTACH[Attach to Event]
        CAPTURE2 --> ATTACH
        CAPTURE3 --> ATTACH
        CAPTURE4 --> ATTACH
        
        ATTACH --> HANDLER[Execute Handler]
    end
```

## Event Priority System

```mermaid
graph LR
    subgraph "Priority Queue"
        subgraph "Priority Levels"
            P100[Priority 100<br/>System Handlers]
            P50[Priority 50<br/>High Priority]
            P0[Priority 0<br/>Default]
            P_50[Priority -50<br/>Low Priority]
            P_100[Priority -100<br/>Logging]
        end
        
        subgraph "Handler Queue"
            H1[Anti-Spam Handler<br/>Priority: 100]
            H2[Command Handler<br/>Priority: 50]
            H3[Message Logger<br/>Priority: -100]
            H4[Auto Reply<br/>Priority: 0]
            H5[Stats Collector<br/>Priority: -50]
        end
        
        subgraph "Execution Order"
            ORDER[1. Anti-Spam<br/>2. Command<br/>3. Auto Reply<br/>4. Stats<br/>5. Logger]
        end
        
        P100 --> H1
        P50 --> H2
        P0 --> H4
        P_50 --> H5
        P_100 --> H3
        
        H1 --> ORDER
        H2 --> ORDER
        H4 --> ORDER
        H5 --> ORDER
        H3 --> ORDER
    end
```

## Event Bubbling and Cancellation

```mermaid
sequenceDiagram
    participant Event as NewMessage Event
    participant H1 as Handler 1<br/>Priority: 100
    participant H2 as Handler 2<br/>Priority: 50
    participant H3 as Handler 3<br/>Priority: 0
    participant H4 as Handler 4<br/>Priority: -50

    Event->>H1: Process Event
    H1->>H1: Check Conditions
    H1->>Event: Continue (no stop)
    
    Event->>H2: Process Event
    H2->>H2: Process Message
    H2->>Event: event.stop_propagation()
    
    Note over Event,H3: Handler 3 not called
    Note over Event,H4: Handler 4 not called
    
    Event-->>Event: Event handling complete
```

## Album Event Grouping

```mermaid
graph TB
    subgraph "Album Detection"
        M1[Message 1<br/>grouped_id: 123] --> DETECTOR[Album Detector]
        M2[Message 2<br/>grouped_id: 123] --> DETECTOR
        M3[Message 3<br/>grouped_id: 123] --> DETECTOR
        M4[Message 4<br/>grouped_id: 456] --> DETECTOR
        
        DETECTOR --> GROUP1[Album 1<br/>Messages 1,2,3]
        DETECTOR --> GROUP2[Single Message<br/>Message 4]
        
        GROUP1 --> ALBUM_EVENT[Album Event<br/>3 photos]
        GROUP2 --> MSG_EVENT[NewMessage Event]
        
        ALBUM_EVENT --> HANDLER1[Album Handler]
        MSG_EVENT --> HANDLER2[Message Handler]
    end
```

## Error Handling in Events

```mermaid
graph TB
    subgraph "Event Error Handling"
        EVENT[Event Dispatch]
        
        EVENT --> TRY[Try Execute Handler]
        
        TRY --> SUCCESS[Handler Success]
        TRY --> ERROR[Handler Error]
        
        ERROR --> CATCH[Catch Exception]
        
        CATCH --> LOG[Log Error]
        CATCH --> CALLBACK{Error Callback?}
        
        CALLBACK -->|Yes| ERROR_HANDLER[Call Error Handler]
        CALLBACK -->|No| CONTINUE[Continue Next Handler]
        
        ERROR_HANDLER --> HANDLED{Handled?}
        
        HANDLED -->|Yes| CONTINUE
        HANDLED -->|No| PROPAGATE[Propagate Error]
        
        SUCCESS --> NEXT[Next Handler]
        CONTINUE --> NEXT
        
        style ERROR fill:#f44336
        style LOG fill:#ff9800
    end
```

## Event Memory Management

```mermaid
graph LR
    subgraph "Event Lifecycle"
        CREATE[Event Created] --> DISPATCH[Event Dispatched]
        DISPATCH --> PROCESS[Handlers Processing]
        PROCESS --> COMPLETE[Processing Complete]
        COMPLETE --> CLEANUP[Cleanup References]
        CLEANUP --> GC[Garbage Collection]
        
        subgraph "References"
            REF1[Message Reference]
            REF2[Entity Reference]
            REF3[Media Reference]
            REF4[Client Reference]
        end
        
        CREATE --> REF1
        CREATE --> REF2
        CREATE --> REF3
        CREATE --> REF4
        
        CLEANUP -.-> REF1
        CLEANUP -.-> REF2
        CLEANUP -.-> REF3
        
        style CLEANUP fill:#ff9800
        style GC fill:#4caf50
    end
```

## Next Steps

- Continue to [Client Documentation](../client/mixins.md) for implementation details
- Review [Event System](../events/architecture.md) for technical details
- See [Event Types](../events/types.md) for all event types

---
**Navigation:** [← Network Flow](network-flow.md) | [Home](../index.md) | [Up](../index.md) | [Client →](../client/README.md)

---