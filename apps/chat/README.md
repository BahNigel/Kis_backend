# Chat Service (Django side)

This app provides the **room metadata + membership + RBAC** layer for the chat system.

- **Django + Postgres** handle:
  - Conversations (rooms),
  - Membership (who is in which room),
  - Per-room settings/policies,
  - Role-based access control (RBAC),
  - Links to higher-level entities (Partners, Communities, Groups, Channels).

- **NestJS + MongoDB** handle:
  - Actual messages,
  - Read receipts,
  - Typing indicators,
  - etc.

Django never stores phone contacts; it only knows platform users and room membership.

---

## Key Models

### Conversations

`chat.models.Conversation` is the universal "room" model.

Important fields:

- `type`: `direct`, `group`, `channel`, `thread`, `system`
- `title`, `description`, `avatar_url`
- `created_by`
- `is_archived`, `is_locked`
- `last_message_at`, `last_message_preview` (denormalized from NestJS)
- `settings`: `ConversationSettings` (1:1)

### Membership

`ConversationMember` links **users** to **conversations**.

Fields:

- `conversation`, `user`
- `base_role`: `owner`, `admin`, `member`, `readonly`
- `display_name` (per-room nickname)
- `notification_level`: `all`, `mentions`, `none`
- `color`: optional UI color
- `is_muted`, `is_blocked`
- `joined_at`, `left_at` (soft delete => history)

To list all members in a conversation:

```python
conversation.memberships.select_related('user')



Settings / Policies
ConversationSettings defines:
send_policy: who can send (all_members, admins_only)
join_policy: invite_only, link_join, open
info_edit_policy: who can edit title/description
subroom_policy: who can create threads/sub-rooms
max_subroom_depth
message_retention_days
allow_reactions, allow_stickers, allow_attachments
These are enforced after role checks in your permission engine.
Threads / Sub-rooms
MessageThreadLink connects:
parent_conversation + parent_message_key (Mongo/Nest message ID),
child_conversation (a separate conversation of type THREAD),
optional parent_thread (for nested threads),
depth.
This allows UI like "Reply in thread / Continue in sub-room".
How it connects to Partners / Communities / Groups / Channels
Higher-level objects live in their own apps:
Partner (partners.models.Partner)
Community (communities.models.Community)
Group (groups.models.Group)
Channel (channels.models.Channel)
Each can have its own backing conversation:
Partner.main_conversation (optional announcement room)
Community.main_conversation (lobby room)
Group.conversation (group chat)
Channel.conversation (broadcast or channel chat)
When you create a Group:
Create a Conversation of type GROUP.
Create a Group and link group.conversation to that Conversation.
Add the group owner as ConversationMember(base_role=OWNER).
Same idea for Channels and Communities.
1:1 Direct Conversations
Concept
A direct conversation is a Conversation with:
type = 'direct'
Exactly two active ConversationMember rows (for the two users).
When a user wants to chat 1:1 with another user, the system should:
Look for an existing direct conversation with both users as active members.
If found, reuse it.
If not found, create a new Conversation(type='direct') and add both members.
API
Endpoint
POST /api/chat/conversations/direct/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "peer_user_id": 42
}
Response
200 OK if an existing direct conversation was found.
201 Created if a new conversation was created.
Example response body:
{
  "id": "e7d8f1c2-1b2c-4d3e-9f3a-123456789abc",
  "type": "direct",
  "title": "",
  "description": "",
  "avatar_url": "",
  "created_by": 7,
  "is_archived": false,
  "is_locked": false,
  "last_message_at": null,
  "last_message_preview": "",
  "created_at": "2025-11-18T10:00:00Z",
  "updated_at": "2025-11-18T10:00:00Z",
  "settings": {
    "send_policy": "all_members",
    "join_policy": "invite_only",
    "info_edit_policy": "admins_only",
    "subroom_policy": "all_members",
    "max_subroom_depth": 8,
    "message_retention_days": null,
    "allow_reactions": true,
    "allow_stickers": true,
    "allow_attachments": true,
    "created_at": "2025-11-18T10:00:00Z",
    "updated_at": "2025-11-18T10:00:00Z"
  },
  "members": [
    {
      "id": 1,
      "user_id": 7,
      "user_username": "alice",
      "base_role": "owner",
      "display_name": "",
      "notification_level": "all",
      "color": "",
      "is_muted": false,
      "is_blocked": false,
      "joined_at": "2025-11-18T10:00:00Z",
      "left_at": null,
      "is_active": true
    },
    {
      "id": 2,
      "user_id": 42,
      "user_username": "bob",
      "base_role": "member",
      "display_name": "",
      "notification_level": "all",
      "color": "",
      "is_muted": false,
      "is_blocked": false,
      "joined_at": "2025-11-18T10:00:00Z",
      "left_at": null,
      "is_active": true
    }
  ]
}
NestJS Messaging Integration
Typical flow:
Client connects to NestJS WebSocket with a JWT.
NestJS verifies the token (via Django introspection or shared JWT secret) and reads:
user_id
When the client wants to send a message:
It includes conversation_id.
NestJS calls a Django endpoint or internal service to check permission:
“Is user X an active member of conversation Y?”
Optional: “Does user X have permission to send messages here?” (use RBAC + ConversationSettings.send_policy).
If allowed:
NestJS writes the message to Mongo,
Updates Conversation.last_message_at and last_message_preview via a small HTTP call to Django (or a message queue).
This keeps responsibilities separated:
Django = rooms, membership, roles, policies.
NestJS = real-time messages.