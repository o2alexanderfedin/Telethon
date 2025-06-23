# Protocol Documentation

---
**Navigation:** [← Request Handling](../network/request-handling.md) | [Home](../index.md) | [MTProto Overview →](mtproto.md)

---

## About This Section

The protocol documentation provides detailed information about the MTProto protocol implementation, including encryption, authorization, and message formatting.

## Contents

### [MTProto Overview](mtproto.md)
- Protocol fundamentals
- Security features
- Protocol versions
- Implementation details

### [Encryption](encryption.md)
- AES-IGE encryption
- RSA public key encryption
- Diffie-Hellman key exchange
- Message key derivation

### [Authorization](authorization.md)
- Authorization flow
- Key generation
- Session creation
- Re-authorization

### [Message Format](message-format.md)
- Message structure
- TL serialization
- Container messages
- Service messages

## Key Concepts

- **End-to-End Security**: Multiple layers of encryption
- **Perfect Forward Secrecy**: DH key exchange for auth keys
- **Message Integrity**: Cryptographic verification of all messages
- **Replay Protection**: Sequence numbers and message IDs

## Protocol Stack

```
┌─────────────────────────┐
│   Application Layer     │
├─────────────────────────┤
│     TL Schema          │
├─────────────────────────┤
│   MTProto Protocol     │
├─────────────────────────┤
│  Transport (TCP/HTTP)   │
└─────────────────────────┘
```

## Next Steps

- Start with [MTProto Overview](mtproto.md) for protocol basics
- Review [Encryption](encryption.md) for security details
- See [API Layer](../api/README.md) for higher-level abstractions

---
**Navigation:** [← Request Handling](../network/request-handling.md) | [Home](../index.md) | [MTProto Overview →](mtproto.md)

---