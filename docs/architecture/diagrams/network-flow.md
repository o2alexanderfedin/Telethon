# Network Flow

---
**Navigation:** [← Client Structure](client-structure.md) | [Home](../index.md) | [Up](../index.md) | [Event Flow →](event-flow.md)

---

## Overview

This document visualizes the network communication flow in Telethon, showing how data moves between the client and Telegram servers, including request/response cycles, connection management, and protocol handling.

## Request/Response Flow

```mermaid
sequenceDiagram
    participant App as Application
    participant Client as TelegramClient
    participant Queue as Request Queue
    participant Sender as MTProtoSender
    participant Conn as Connection
    participant Transport as Transport Layer
    participant Server as Telegram Server

    App->>Client: send_message("Hello")
    Client->>Client: Build TL Request
    Client->>Queue: Queue Request
    
    Queue->>Sender: Get Request
    Sender->>Sender: Assign msg_id
    Sender->>Sender: Calculate msg_key
    Sender->>Sender: Encrypt with AES-IGE
    Sender->>Sender: Add headers
    
    Sender->>Conn: Send encrypted data
    Conn->>Transport: Frame data
    Transport->>Server: TCP/HTTP send
    
    Server-->>Transport: Encrypted response
    Transport-->>Conn: Extract frame
    Conn-->>Sender: Encrypted data
    
    Sender->>Sender: Verify headers
    Sender->>Sender: Decrypt with AES-IGE
    Sender->>Sender: Verify msg_key
    Sender->>Sender: Parse TL response
    
    Sender-->>Client: Response object
    Client-->>App: Message sent
```

## Connection Establishment

```mermaid
graph TB
    subgraph "Connection Process"
        START[Start] --> CHECK_CONN[Check Existing Connection]
        
        CHECK_CONN -->|Exists| VALIDATE[Validate Connection]
        CHECK_CONN -->|None| CREATE[Create Connection]
        
        VALIDATE -->|Valid| READY[Connection Ready]
        VALIDATE -->|Invalid| CLOSE[Close Connection]
        
        CLOSE --> CREATE
        
        CREATE --> SELECT_DC[Select Data Center]
        SELECT_DC --> RESOLVE[Resolve DC Address]
        RESOLVE --> CHOOSE_TRANSPORT[Choose Transport]
        
        subgraph "Transport Selection"
            CHOOSE_TRANSPORT --> TCP_CHECK{TCP Available?}
            TCP_CHECK -->|Yes| TCP_MODE[Select TCP Mode]
            TCP_CHECK -->|No| HTTP_MODE[Use HTTP]
            
            TCP_MODE --> ABRIDGED[TCP Abridged]
            TCP_MODE --> INTERMEDIATE[TCP Intermediate]
            TCP_MODE --> FULL[TCP Full]
            TCP_MODE --> OBFUSCATED[TCP Obfuscated]
        end
        
        ABRIDGED --> CONNECT
        INTERMEDIATE --> CONNECT
        FULL --> CONNECT
        OBFUSCATED --> CONNECT
        HTTP_MODE --> CONNECT
        
        CONNECT[Establish Connection] --> AUTH_CHECK{Has Auth Key?}
        
        AUTH_CHECK -->|Yes| READY
        AUTH_CHECK -->|No| DH_EXCHANGE[DH Exchange]
        
        DH_EXCHANGE --> GEN_NONCE[Generate Nonces]
        GEN_NONCE --> REQ_PQ[Request PQ]
        REQ_PQ --> FACTOR[Factor PQ]
        FACTOR --> REQ_DH[Request DH Params]
        REQ_DH --> GEN_KEY[Generate Auth Key]
        GEN_KEY --> READY
    end
```

## MTProto Message Flow

```mermaid
graph LR
    subgraph "Outgoing Message"
        MSG[Message] --> SERIALIZE[Serialize to TL]
        SERIALIZE --> ADD_SALT[Add Salt]
        ADD_SALT --> ADD_SESSION[Add Session ID]
        ADD_SESSION --> ADD_SEQ[Add Sequence]
        ADD_SEQ --> CALC_KEY[Calculate msg_key]
        CALC_KEY --> ENCRYPT[Encrypt Payload]
        ENCRYPT --> ADD_AUTH[Add auth_key_id]
        ADD_AUTH --> SEND[Send to Network]
    end
    
    subgraph "Incoming Message"
        RECV[Receive from Network] --> CHECK_AUTH[Check auth_key_id]
        CHECK_AUTH --> EXTRACT_KEY[Extract msg_key]
        EXTRACT_KEY --> DECRYPT[Decrypt Payload]
        DECRYPT --> VERIFY_KEY[Verify msg_key]
        VERIFY_KEY --> CHECK_SEQ[Check Sequence]
        CHECK_SEQ --> CHECK_TIME[Check Time]
        CHECK_TIME --> DESERIALIZE[Deserialize TL]
        DESERIALIZE --> PROCESS[Process Message]
    end
```

## Parallel Request Handling

```mermaid
graph TB
    subgraph "Request Multiplexing"
        R1[Request 1] --> Q[Request Queue]
        R2[Request 2] --> Q
        R3[Request 3] --> Q
        R4[Request 4] --> Q
        
        Q --> BATCH[Batch Processor]
        
        BATCH --> C1[Container 1<br/>R1 + R2]
        BATCH --> C2[Container 2<br/>R3 + R4]
        
        C1 --> SEND1[Send Container 1]
        C2 --> SEND2[Send Container 2]
        
        SEND1 --> NET[Network]
        SEND2 --> NET
        
        NET --> RECV1[Receive Response 1]
        NET --> RECV2[Receive Response 2]
        
        RECV1 --> UNPACK1[Unpack Container 1]
        RECV2 --> UNPACK2[Unpack Container 2]
        
        UNPACK1 --> RESP1[Response 1]
        UNPACK1 --> RESP2[Response 2]
        UNPACK2 --> RESP3[Response 3]
        UNPACK2 --> RESP4[Response 4]
    end
```

## Update Delivery

```mermaid
sequenceDiagram
    participant Server as Telegram Server
    participant Conn as Connection
    participant Sender as MTProtoSender
    participant Handler as Update Handler
    participant Queue as Update Queue
    participant App as Application

    Note over Server,App: Push Updates (Server-initiated)
    
    Server->>Conn: Push Update
    Conn->>Sender: Encrypted Update
    Sender->>Sender: Decrypt & Parse
    
    alt Update in sequence
        Sender->>Handler: Process Update
        Handler->>Queue: Queue Update
        Queue->>App: Dispatch Event
    else Update has gap
        Sender->>Handler: Gap Detected
        Handler->>Server: Request Missing Updates
        Server-->>Handler: Missing Updates
        Handler->>Queue: Queue All Updates
        Queue->>App: Dispatch Events in Order
    end
    
    Note over Server,App: Poll Updates (Client-initiated)
    
    loop Every N seconds
        Sender->>Server: GetUpdates/GetDifference
        Server-->>Sender: Updates Array
        Sender->>Handler: Process Updates
        Handler->>Queue: Queue Updates
        Queue->>App: Dispatch Events
    end
```

## Network Error Recovery

```mermaid
stateDiagram-v2
    [*] --> Connected: Initial Connection
    
    Connected --> Sending: Send Request
    Sending --> Waiting: Request Sent
    
    Waiting --> Received: Response OK
    Waiting --> NetworkError: Timeout/Error
    Waiting --> BadMessage: Bad MSG
    
    Received --> [*]: Success
    
    NetworkError --> Reconnecting: Auto Reconnect
    BadMessage --> ResendWithNew: Update Salt/Time
    
    Reconnecting --> Connected: Reconnected
    Reconnecting --> Disconnected: Max Retries
    
    ResendWithNew --> Sending: Resend
    
    Disconnected --> [*]: Give Up
    
    state NetworkError {
        [*] --> CheckType
        CheckType --> TimeoutError: Timeout
        CheckType --> ConnectionLost: Lost Conn
        CheckType --> ConnectionReset: Reset
    }
```

## Data Center Migration

```mermaid
sequenceDiagram
    participant Client
    participant DC1 as DC 1 (Current)
    participant DC2 as DC 2 (Target)
    participant Session

    Client->>DC1: Request File/User
    DC1-->>Client: FILE_MIGRATE_2 Error
    
    Client->>Session: Get DC2 Auth Key
    
    alt Has Auth Key for DC2
        Client->>DC2: Reuse Auth Key
    else No Auth Key
        Client->>DC2: Connect
        Client->>DC2: DH Exchange
        DC2-->>Client: New Auth Key
        Client->>Session: Save DC2 Auth Key
    end
    
    Client->>DC2: Export Authorization
    DC2-->>Client: Authorization Exported
    
    Client->>DC2: Retry Original Request
    DC2-->>Client: Success
    
    Client->>Session: Update DC Info
```

## Connection Pooling

```mermaid
graph TB
    subgraph "Connection Pool Architecture"
        CLIENT[TelegramClient]
        
        subgraph "Main DC Pool"
            MAIN1[Connection 1<br/>Messages]
            MAIN2[Connection 2<br/>Updates]
            MAIN3[Connection 3<br/>General]
        end
        
        subgraph "Media DC Pool"
            MEDIA1[DC2 Connection<br/>Downloads]
            MEDIA2[DC3 Connection<br/>Uploads]
            MEDIA3[DC4 Connection<br/>CDN]
        end
        
        subgraph "Pool Manager"
            MANAGER[Connection Manager]
            SELECTOR[Connection Selector]
            HEALTH[Health Monitor]
        end
        
        CLIENT --> MANAGER
        
        MANAGER --> SELECTOR
        SELECTOR --> MAIN1
        SELECTOR --> MAIN2
        SELECTOR --> MAIN3
        SELECTOR --> MEDIA1
        SELECTOR --> MEDIA2
        SELECTOR --> MEDIA3
        
        HEALTH --> MAIN1
        HEALTH --> MAIN2
        HEALTH --> MAIN3
        HEALTH --> MEDIA1
        HEALTH --> MEDIA2
        HEALTH --> MEDIA3
    end
```

## Request Priority Queue

```mermaid
graph TB
    subgraph "Priority Queue System"
        subgraph "Incoming Requests"
            R1[Auth Request<br/>Priority: Critical]
            R2[Message Send<br/>Priority: High]
            R3[Get History<br/>Priority: Normal]
            R4[Get Participants<br/>Priority: Low]
            R5[File Download<br/>Priority: Low]
        end
        
        subgraph "Priority Queues"
            Q1[Critical Queue]
            Q2[High Queue]
            Q3[Normal Queue]
            Q4[Low Queue]
        end
        
        subgraph "Scheduler"
            SCHED[Request Scheduler]
            RATE[Rate Limiter]
        end
        
        R1 --> Q1
        R2 --> Q2
        R3 --> Q3
        R4 --> Q4
        R5 --> Q4
        
        Q1 --> SCHED
        Q2 --> SCHED
        Q3 --> SCHED
        Q4 --> SCHED
        
        SCHED --> RATE
        RATE --> SEND[Send to Network]
    end
    
    style Q1 fill:#ff6b6b
    style Q2 fill:#feca57
    style Q3 fill:#48dbfb
    style Q4 fill:#1dd1a1
```

## Acknowledgment System

```mermaid
sequenceDiagram
    participant Client
    participant Sender as MTProtoSender
    participant Server
    participant AckQueue as Ack Queue

    Client->>Sender: Send Message (msg_id: 123)
    Sender->>Server: Encrypted Message
    Sender->>AckQueue: Track msg_id: 123
    
    Note over Sender: Continue sending other messages
    
    Server-->>Sender: Message Received
    Server-->>Sender: Ack for msg_id: 123
    
    Sender->>AckQueue: Remove msg_id: 123
    
    Note over Sender: Batch acknowledgments
    
    loop Every 30 seconds
        AckQueue->>Sender: Pending Acks
        Sender->>Server: msgs_ack([124, 125, 126])
    end
    
    Note over Sender: Handle missing acks
    
    alt No ack received
        AckQueue->>Sender: msg_id: 127 not acked
        Sender->>Sender: Check timeout
        Sender->>Server: Resend msg_id: 127
    end
```

## Network Statistics

```mermaid
graph LR
    subgraph "Network Monitoring"
        subgraph "Metrics Collection"
            SENT[Bytes Sent]
            RECV[Bytes Received]
            LATENCY[Latency]
            ERRORS[Error Count]
            RETRIES[Retry Count]
        end
        
        subgraph "Statistics"
            AVG_LATENCY[Avg Latency: 45ms]
            THROUGHPUT[Throughput: 2.5 MB/s]
            ERROR_RATE[Error Rate: 0.1%]
            UPTIME[Uptime: 99.9%]
        end
        
        subgraph "Actions"
            OPTIMIZE[Optimize Routes]
            SWITCH_DC[Switch DC]
            ADJUST_TIMEOUT[Adjust Timeouts]
            CHANGE_MODE[Change Transport]
        end
        
        SENT --> AVG_LATENCY
        RECV --> THROUGHPUT
        LATENCY --> AVG_LATENCY
        ERRORS --> ERROR_RATE
        RETRIES --> ERROR_RATE
        
        AVG_LATENCY --> OPTIMIZE
        THROUGHPUT --> ADJUST_TIMEOUT
        ERROR_RATE --> SWITCH_DC
        UPTIME --> CHANGE_MODE
    end
```

## Flood Control

```mermaid
graph TB
    subgraph "Flood Control System"
        REQ[Incoming Request]
        
        CHECK{Check Rate Limit}
        
        REQ --> CHECK
        
        CHECK -->|Under Limit| SEND[Send Request]
        CHECK -->|Over Limit| QUEUE[Queue Request]
        
        SEND --> RESPONSE{Server Response}
        
        RESPONSE -->|Success| DONE[Complete]
        RESPONSE -->|Flood Wait| WAIT[Wait N Seconds]
        
        WAIT --> DELAY[Delay Queue]
        QUEUE --> DELAY
        
        DELAY --> SCHEDULER[Rate Scheduler]
        
        SCHEDULER --> BUCKET[Token Bucket]
        
        BUCKET -->|Token Available| SEND
        BUCKET -->|No Token| WAIT_TOKEN[Wait for Token]
        
        WAIT_TOKEN --> BUCKET
    end
    
    style WAIT fill:#ff6b6b
    style DELAY fill:#feca57
```

## Transport Layer Details

```mermaid
graph TB
    subgraph "Transport Protocols"
        subgraph "TCP Abridged"
            A1[Length: 1-3 bytes]
            A2[Payload: Variable]
            A3[No CRC]
        end
        
        subgraph "TCP Intermediate"
            I1[Length: 4 bytes]
            I2[Payload: Variable]
            I3[No CRC]
        end
        
        subgraph "TCP Full"
            F1[Length: 4 bytes]
            F2[Sequence: 4 bytes]
            F3[Payload: Variable]
            F4[CRC32: 4 bytes]
        end
        
        subgraph "HTTP"
            H1[POST Request]
            H2[Content-Type: application/x-gzip]
            H3[Gzipped Payload]
        end
        
        subgraph "Obfuscated"
            O1[Random Padding: 64 bytes]
            O2[Encrypted Header]
            O3[Standard Protocol Inside]
        end
    end
```

## Connection State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: Initialize
    
    Idle --> Connecting: connect()
    
    Connecting --> HandshakeWait: TCP Connected
    Connecting --> Failed: Connection Error
    
    HandshakeWait --> Authenticating: Handshake OK
    HandshakeWait --> Failed: Handshake Error
    
    Authenticating --> Ready: Auth Success
    Authenticating --> Unauthorized: Auth Failed
    
    Unauthorized --> Authenticating: retry_auth()
    
    Ready --> Sending: send_request()
    Ready --> Receiving: receive_update()
    
    Sending --> Ready: Send Complete
    Receiving --> Ready: Process Complete
    
    Ready --> Reconnecting: Connection Lost
    Failed --> Reconnecting: auto_reconnect
    
    Reconnecting --> Connecting: Retry
    Reconnecting --> Disconnected: Max Retries
    
    Ready --> Disconnecting: disconnect()
    Disconnecting --> Disconnected: Cleanup Done
    
    Disconnected --> [*]
```

## Next Steps

- Continue to [Event Flow](event-flow.md) for event system visualization
- Review [Network Layer](../network/mtproto-sender.md) for implementation details
- See [Protocol Documentation](../protocol/mtproto.md) for protocol specifics

---
**Navigation:** [← Client Structure](client-structure.md) | [Home](../index.md) | [Up](../index.md) | [Event Flow →](event-flow.md)

---