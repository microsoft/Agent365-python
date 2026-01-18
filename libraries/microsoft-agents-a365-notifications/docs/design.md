# Notifications - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-notifications` package.

## Overview

The notifications package provides agent notification handling and routing capabilities. It enables agents to respond to notifications from various Microsoft 365 channels (email, Word, Excel, PowerPoint) and lifecycle events.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Application                            │
│                   (Microsoft Agents SDK)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AgentNotification                            │
│                                                                  │
│  ┌───────────────────┐  ┌───────────────────┐                   │
│  │ Channel Handlers  │  │ Lifecycle Handlers│                   │
│  │                   │  │                   │                   │
│  │ @on_email         │  │ @on_user_created  │                   │
│  │ @on_word          │  │ @on_user_deleted  │                   │
│  │ @on_excel         │  │ @on_lifecycle     │                   │
│  │ @on_powerpoint    │  │                   │                   │
│  └───────────────────┘  └───────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AgentNotificationActivity                       │
│          (Wraps Activity with notification metadata)             │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### AgentNotification ([agent_notification.py](../microsoft_agents_a365/notifications/agent_notification.py))

The main class for registering notification handlers with an agent application.

```python
from microsoft_agents_a365.notifications import AgentNotification

# Initialize with agent application
notifications = AgentNotification(app)

# Register email notification handler
@notifications.on_email()
async def handle_email(context, state, notification):
    email_ref = notification.email_reference
    print(f"Received email from: {email_ref.sender}")
    print(f"Subject: {email_ref.subject}")

# Register lifecycle event handler
@notifications.on_user_created()
async def handle_user_created(context, state, notification):
    print("New user created!")
```

#### Constructor

```python
def __init__(
    self,
    app: Any,
    known_subchannels: Iterable[str | AgentSubChannel] | None = None,
    known_lifecycle_events: Iterable[str | AgentLifecycleEvent] | None = None,
):
```

**Parameters:**
- `app`: The agent application instance (from Microsoft Agents SDK)
- `known_subchannels`: Optional list of recognized subchannels (defaults to all `AgentSubChannel` values)
- `known_lifecycle_events`: Optional list of recognized lifecycle events (defaults to all `AgentLifecycleEvent` values)

#### Channel Notification Decorators

| Decorator | Subchannel | Description |
|-----------|------------|-------------|
| `@on_email()` | `email` | Handle email notifications |
| `@on_word()` | `word` | Handle Word document notifications |
| `@on_excel()` | `excel` | Handle Excel spreadsheet notifications |
| `@on_powerpoint()` | `powerpoint` | Handle PowerPoint notifications |
| `@on_agent_notification(channel_id)` | Custom | Handle any channel notification |

#### Lifecycle Event Decorators

| Decorator | Event | Description |
|-----------|-------|-------------|
| `@on_lifecycle()` | `*` | Handle all lifecycle events |
| `@on_user_created()` | `usercreated` | Handle user creation events |
| `@on_user_workload_onboarding()` | `userworkloadonboardingupdated` | Handle workload onboarding |
| `@on_user_deleted()` | `userdeleted` | Handle user deletion events |
| `@on_agent_lifecycle_notification(event)` | Custom | Handle specific lifecycle event |

#### Handler Signature

```python
AgentHandler = Callable[[TContext, TState, AgentNotificationActivity], Awaitable[None]]

async def handler(
    context: TurnContext,      # Conversation context
    state: TurnState,          # Turn state
    notification: AgentNotificationActivity  # Notification data
) -> None:
    pass
```

### AgentNotificationActivity ([models/agent_notification_activity.py](../microsoft_agents_a365/notifications/models/agent_notification_activity.py))

Wraps an Activity with convenient access to notification-specific data.

```python
from microsoft_agents_a365.notifications import AgentNotificationActivity

# Inside a handler
notification = AgentNotificationActivity(context.activity)

# Access notification type
if notification.notification_type == NotificationTypes.EMAIL:
    email = notification.email_reference
    print(f"From: {email.sender}")
    print(f"Subject: {email.subject}")

# Access raw activity
raw_activity = notification.activity
```

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `activity` | `Activity` | The underlying Activity object |
| `notification_type` | `NotificationTypes` | Type of notification |
| `email_reference` | `EmailReference` | Email metadata (for email notifications) |
| `wpx_comment` | `WpxComment` | Document comment data |

### AgentSubChannel ([models/agent_subchannel.py](../microsoft_agents_a365/notifications/models/agent_subchannel.py))

Enum of supported notification subchannels.

```python
from microsoft_agents_a365.notifications import AgentSubChannel

class AgentSubChannel(str, Enum):
    EMAIL = "email"
    WORD = "word"
    EXCEL = "excel"
    POWERPOINT = "powerpoint"
    # Additional subchannels...
```

### AgentLifecycleEvent ([models/agent_lifecycle_event.py](../microsoft_agents_a365/notifications/models/agent_lifecycle_event.py))

Enum of supported lifecycle events.

```python
from microsoft_agents_a365.notifications import AgentLifecycleEvent

class AgentLifecycleEvent(str, Enum):
    USERCREATED = "usercreated"
    USERDELETED = "userdeleted"
    USERWORKLOADONBOARDINGUPDATED = "userworkloadonboardingupdated"
    # Additional events...
```

### EmailReference ([models/email_reference.py](../microsoft_agents_a365/notifications/models/email_reference.py))

Data class for email notification metadata.

```python
@dataclass
class EmailReference:
    sender: str | None           # Email sender address
    subject: str | None          # Email subject line
    received_date: str | None    # When email was received
    message_id: str | None       # Unique message identifier
    # Additional email metadata...
```

### EmailResponse ([models/email_response.py](../microsoft_agents_a365/notifications/models/email_response.py))

Data class for email response operations.

```python
@dataclass
class EmailResponse:
    to: list[str]                # Recipients
    subject: str                 # Subject line
    body: str                    # Email body content
    # Additional response fields...
```

### WpxComment ([models/wpx_comment.py](../microsoft_agents_a365/notifications/models/wpx_comment.py))

Data class for Word/PowerPoint/Excel comment notifications.

```python
@dataclass
class WpxComment:
    comment_text: str | None     # Comment content
    author: str | None           # Comment author
    document_url: str | None     # Document location
    # Additional comment metadata...
```

### NotificationTypes ([models/notification_types.py](../microsoft_agents_a365/notifications/models/notification_types.py))

Constants for notification type identifiers.

```python
class NotificationTypes:
    EMAIL = "email"
    AGENT_LIFECYCLE = "agentLifecycle"
    # Additional notification types...
```

## Routing Logic

### Channel Notification Routing

When a notification arrives, the routing logic:

1. Extracts channel and subchannel from `context.activity.channel_id`
2. Normalizes to lowercase for comparison
3. Matches against registered handlers:
   - Channel must match exactly
   - Subchannel `*` matches any subchannel
   - Otherwise subchannel must be in known subchannels and match exactly

```python
def route_selector(context: TurnContext) -> bool:
    ch = context.activity.channel_id
    received_channel = (ch.channel if ch else "").lower()
    received_subchannel = (ch.sub_channel if ch and ch.sub_channel else "").lower()

    if received_channel != registered_channel:
        return False
    if registered_subchannel == "*":
        return True
    if registered_subchannel not in self._known_subchannels:
        return False
    return received_subchannel == registered_subchannel
```

### Lifecycle Event Routing

Lifecycle event routing:

1. Checks channel is `"agents"`
2. Checks activity name is `NotificationTypes.AGENT_LIFECYCLE`
3. Matches against registered lifecycle event or `*` for all events

```python
def route_selector(context: TurnContext) -> bool:
    ch = context.activity.channel_id
    received_channel = (ch.channel if ch else "").lower()

    if received_channel != "agents":
        return False
    if context.activity.name != NotificationTypes.AGENT_LIFECYCLE:
        return False
    if lifecycle_event == "*":
        return True
    return context.activity.value_type in self._known_lifecycle_events
```

## Usage Example

```python
from microsoft_agents.hosting.core import Application
from microsoft_agents_a365.notifications import AgentNotification

# Create agent application
app = Application()

# Initialize notification handling
notifications = AgentNotification(app)

# Handle email notifications
@notifications.on_email()
async def handle_email(context, state, notification):
    email = notification.email_reference

    # Process email content
    summary = await summarize_email(email.subject, context.activity.text)

    # Respond to user
    await context.send_activity(f"Email from {email.sender}: {summary}")

# Handle Word document mentions
@notifications.on_word()
async def handle_word_mention(context, state, notification):
    comment = notification.wpx_comment

    # Process document context
    response = await generate_response(comment.comment_text)

    await context.send_activity(response)

# Handle user onboarding
@notifications.on_user_created()
async def handle_new_user(context, state, notification):
    # Send welcome message
    await context.send_activity("Welcome! I'm your AI assistant.")

# Handle custom notification
@notifications.on_agent_notification(ChannelId(channel="agents", sub_channel="custom"))
async def handle_custom(context, state, notification):
    pass
```

## Design Patterns

### Decorator Pattern

Notification handlers use Python decorators for registration:

```python
@notifications.on_email()
async def handler(context, state, notification):
    pass
```

The decorator:
1. Creates a route selector function
2. Wraps the handler to create `AgentNotificationActivity`
3. Registers the route with the application

### Adapter Pattern

`AgentNotificationActivity` adapts the raw `Activity` object to provide a notification-specific interface:

```python
class AgentNotificationActivity:
    def __init__(self, activity: Activity):
        self._activity = activity

    @property
    def email_reference(self) -> EmailReference:
        # Extract and return email data from activity
```

## File Structure

```
microsoft_agents_a365/notifications/
├── __init__.py                           # Public API exports
├── agent_notification.py                 # Main AgentNotification class
└── models/
    ├── __init__.py
    ├── agent_notification_activity.py    # Activity wrapper
    ├── agent_subchannel.py               # AgentSubChannel enum
    ├── agent_lifecycle_event.py          # AgentLifecycleEvent enum
    ├── email_reference.py                # EmailReference dataclass
    ├── email_response.py                 # EmailResponse dataclass
    ├── notification_types.py             # NotificationTypes constants
    └── wpx_comment.py                    # WpxComment dataclass
```

## Testing

Tests are located in `tests/notifications/`:

```bash
# Run all notification tests
pytest tests/notifications/ -v
```

## Dependencies

- `microsoft-agents-hosting-core` - TurnContext, TurnState, Application types
- `microsoft-agents-activity` - ChannelId type

## Integration Points

The notifications package integrates with:

1. **Microsoft Agents SDK** - Provides the application framework and activity routing
2. **Microsoft 365** - Source of email, document, and lifecycle notifications
3. **Agent application** - Registered handlers process notifications

## Supported Notification Channels

| Channel | Subchannel | Description |
|---------|------------|-------------|
| `agents` | `email` | Email notifications |
| `agents` | `word` | Word document mentions/comments |
| `agents` | `excel` | Excel spreadsheet notifications |
| `agents` | `powerpoint` | PowerPoint notifications |
| `agents` | (lifecycle) | User lifecycle events |
