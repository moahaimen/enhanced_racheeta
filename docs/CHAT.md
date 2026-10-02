# Chat — Phase 9B

## Scope

Phase 9B adds persistent generic conversations and messages without opening arbitrary user-to-user messaging.

The schema is generic, but the only creation context enabled in this phase is an existing **Reservation**. A patient/provider can open that reservation's conversation; the backend derives participants from the locked reservation and provider profile. The client never chooses account IDs.

Existing recruitment `RecruitmentMessage` remains unchanged.

## Data model

### Conversation

- UUID primary key (BaseModel).
- `context_type` — currently `RESERVATION`.
- `context_id` — reservation UUID.
- `last_sequence` — latest committed message sequence.
- `last_message_at`.
- Unique `(context_type, context_id)`.

No `GenericForeignKey`.

### ConversationParticipant

- conversation.
- account.
- `last_read_sequence`.
- Unique `(conversation, account)`.

### Message

- conversation.
- sender.
- monotonically increasing sequence within the conversation.
- text body, maximum 2000 characters.
- immutable through the application API.
- unique `(conversation, sequence)`.

Django admin is inspection-only for all three models.

## Authorization

Reservation conversation creation:

1. Lock the Reservation.
2. Resolve patient account and current provider-profile account from backend state.
3. Require the actor to be one of those two accounts.
4. Create exactly one conversation and exactly those two participant rows.
5. Never accept participant IDs from the request.

Conversation list, message history, send and read state are scoped through `ConversationParticipant.account = request.user`.

Foreign conversation IDs and nonexistent IDs both return 404.

There is no endpoint to create a generic conversation from arbitrary account IDs, and no message PATCH/PUT/DELETE API.

## Message ordering and concurrency

Sending locks the Conversation row, increments `last_sequence`, creates the Message with that sequence, then updates `last_message_at`.

This serializes concurrent sends and gives a stable per-conversation ordering.

History is bounded by the standard paginator:

- default page size: 20;
- maximum: 100;
- page 1 contains the latest slice;
- messages inside each page are returned chronologically.

## Read state

Read state is sequence-based rather than timestamp-based.

The browser sends:

```json
{"through_sequence": 42}
```

where 42 is the highest message sequence actually rendered by that client.

The backend locks the Conversation and participant, refuses a cursor beyond the conversation's current `last_sequence`, and advances `last_read_sequence` monotonically only to the submitted sequence.

This matters for races: if sequence 43 arrives after the page rendered sequence 42 but before the read receipt reaches the server, sequence 43 remains unread.

Unread counts include only messages from another participant whose sequence is greater than the caller's persisted cursor.

## API

All endpoints are authenticated.

- `POST /api/v1/chat/reservations/{reservation_id}/conversation`
  - backend-derived participants;
  - 201 when created, 200 when already present.
- `GET /api/v1/chat/conversations/`
  - paginated current-account conversations.
- `GET /api/v1/chat/conversations/{conversation_id}/messages/`
  - paginated participant-scoped history.
- `POST /api/v1/chat/conversations/{conversation_id}/messages/`
  - body only: `{"body": "..."}`;
  - text max 2000;
  - sender is server-owned;
  - scoped throttle.
- `POST /api/v1/chat/conversations/{conversation_id}/read/`
  - `{"through_sequence": N}`.
- `GET /api/v1/chat/unread-count/`
  - backend-authoritative total unread message count.

Write serializers reject undeclared client fields.

## Web

Authenticated UI:

- `/messages` — conversation inbox.
- `/messages/:id` — history and text composer.
- header Messages link with backend unread badge.
- patient reservation cards can open the provider conversation.
- provider reservation cards can open the patient conversation.
- Arabic and English strings.

The unread badge refreshes on authenticated pathname navigation and after successful read receipts. No polling is used.

## Explicitly deferred

- FCM/device registration/push delivery — Phase 9C.
- WebSockets/realtime presence/typing indicators.
- Redis.
- Celery/workers.
- attachments/media.
- group chat.
- arbitrary public user-to-user messaging.
- migration or replacement of recruitment `RecruitmentMessage`.
