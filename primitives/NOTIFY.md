# NOTIFY

> Asynchronous notification primitive for console, webhook, and email.

## Philosophy

Agents sometimes need to alert someone without blocking: task completion, errors, or status updates. NOTIFY is the fire-and-forget primitive for that. Unlike SAY, which is synchronous and in-conversation, NOTIFY sends a message and continues. The recipient might be a human watching the console, a Slack webhook, or an email inbox.

NOTIFY supports three built-in methods—console, webhook, email—and a callable for custom handlers. All use only the standard library: console prints with a `[NOTIFY]` prefix; webhook uses the shared `_http.http_request` helper; email uses `smtplib`. Configurable failure handling (log, raise, ignore) lets you choose how strict to be when a notification fails. Credentials are never serialized; SMTP and webhook config are passed at runtime or via environment variables.

## How It Works

NOTIFY is constructed with a method, recipient, subject, body, and optional config. On execution, `{variable}` placeholders in recipient, subject, and body are resolved from memory. The method is dispatched: console prints the body; webhook POSTs a JSON payload (body as `text` or as dict) to the recipient URL; email builds a MIME message and sends via SMTP with TLS.

SMTP config can come from the `config` dict or environment: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `from_addr`. TLS is used by default. If any method raises, `on_fail` controls the outcome: `"log"` adds an error to memory and returns a failure dict; `"raise"` re-raises; `"ignore"` returns the failure dict and continues.

The return value is a dict: `{"status": "sent"|"failed", "method": str, "recipient": str}`. On failure, the dict also includes `"error": str`. Serialization via `to_dict`/`from_dict` excludes credentials and callable handlers for security.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `method` | Notification method: `"console"` (default), `"webhook"`, `"email"`, or callable `(recipient, subject, body, config) -> bool`. |
| `recipient` | Who receives the notification. Console: ignored. Webhook: URL. Email: address. Supports `{variable}`. |
| `subject` | Subject/title. For email, the subject line. For webhook, added to payload. Supports `{variable}`. |
| `body` | Message content. Str or dict (for webhook). Supports `{variable}`. |
| `config` | Method-specific config. Email: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_pass`, `from_addr`, `use_tls`. Webhook: `headers`, `timeout`. |
| `name` | Identifier for this action (default: `"notify"`). |
| `on_fail` | Failure behavior: `"log"` (default), `"raise"`, or `"ignore"`. |

## Usage

```python
from thoughtflow.actions import NOTIFY
from thoughtflow import MEMORY

# Console notification
notify = NOTIFY(
    method="console",
    body="Task completed: {task_name}"
)
memory = MEMORY()
memory.set_var("task_name", "example_task")
memory = notify(memory)
# [NOTIFY] Task completed: example_task

# Webhook notification (e.g. Slack)
notify = NOTIFY(
    method="webhook",
    recipient="https://hooks.slack.com/services/...",
    body={"text": "Agent completed task: {task_name}"}
)

# Email notification
notify = NOTIFY(
    method="email",
    recipient="admin@example.com",
    subject="Agent Alert",
    body="Task {task_name} finished with status: {status}",
    config={
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "agent@example.com",
        "smtp_pass": os.environ["SMTP_PASSWORD"],
        "from_addr": "agent@example.com"
    }
)

# Strict failure handling
notify = NOTIFY(
    method="webhook",
    recipient="{webhook_url}",
    body="Critical error",
    on_fail="raise"
)
```

## Relationship to Other Primitives

- **ACTION**: NOTIFY is a subclass of ACTION. It inherits memory integration, execution tracking, and serialization (credentials excluded).
- **SAY**: SAY is synchronous, in-conversation output. NOTIFY is async, fire-and-forget. Use SAY when the user is waiting; use NOTIFY when you are alerting in the background.
- **POST / FETCH**: NOTIFY uses the same HTTP helper for webhooks. POST is the general "send data" primitive; NOTIFY is specialized for notifications with multiple delivery methods.
- **MEMORY**: Recipient, subject, and body support `{variable}` substitution. On `on_fail="log"`, errors are added via `memory.add_log`.
- **WORKFLOW**: NOTIFY is a common final step in workflows (e.g. notify on success or failure).

## Considerations for Future Development

- Additional methods: SMS, push notifications, in-app alerts.
- Batching: collect multiple notifications and send in one call.
- Rate limiting for webhooks and email to avoid provider throttling.
- Retry with backoff for transient delivery failures.
- Template system for body (e.g. Jinja-style) when body is complex.
