"""
NOTIFY action - send asynchronous notifications.

Supports console, webhook, and email (via smtplib) using only standard library.
"""

from __future__ import annotations

import json
import os

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute
from thoughtflow.actions._http import http_request


class NOTIFY(ACTION):
    """
    An action that sends asynchronous notifications.
    
    NOTIFY supports multiple notification methods:
    - console: Print with [NOTIFY] prefix
    - webhook: HTTP POST to a URL
    - email: Send via SMTP (standard library smtplib)
    
    Args:
        name (str): Unique identifier for this action.
        method (str|callable): Notification method:
            - "console": Print to stdout (default)
            - "webhook": POST to webhook URL
            - "email": Send via SMTP
            - callable: Custom handler (recipient, subject, body, config) -> bool
        recipient (str): Who receives the notification:
            - console: ignored
            - webhook: URL to POST to
            - email: recipient email address
        subject (str): Subject/title (for email, optional for others).
        body (str|callable): Message content with {variable} placeholders.
        config (dict): Method-specific configuration:
            - email: {smtp_host, smtp_port, smtp_user, smtp_pass, from_addr}
        on_fail (str): Failure behavior:
            - "log": Log error and continue (default)
            - "raise": Raise exception
            - "ignore": Silently continue
    
    Example:
        >>> from thoughtflow.actions import NOTIFY
        >>> from thoughtflow import MEMORY
        
        # Console notification
        >>> notify = NOTIFY(
        ...     method="console",
        ...     body="Task completed: {task_name}"
        ... )
        >>> memory = notify(MEMORY())
        [NOTIFY] Task completed: example_task
        
        # Webhook notification
        >>> notify = NOTIFY(
        ...     method="webhook",
        ...     recipient="https://hooks.slack.com/services/...",
        ...     body={"text": "Agent completed task: {task_name}"}
        ... )
        
        # Email notification
        >>> notify = NOTIFY(
        ...     method="email",
        ...     recipient="admin@example.com",
        ...     subject="Agent Alert",
        ...     body="Task {task_name} finished with status: {status}",
        ...     config={
        ...         "smtp_host": "smtp.gmail.com",
        ...         "smtp_port": 587,
        ...         "smtp_user": "agent@example.com",
        ...         "smtp_pass": os.environ["SMTP_PASSWORD"],
        ...         "from_addr": "agent@example.com"
        ...     }
        ... )
    """
    
    def __init__(
        self,
        name=None,
        method="console",
        recipient=None,
        subject="",
        body="",
        config=None,
        on_fail="log",
    ):
        """
        Initialize a NOTIFY action.
        
        Args:
            name: Optional name (defaults to "notify").
            method: Notification method.
            recipient: Notification recipient.
            subject: Subject/title.
            body: Message content.
            config: Method-specific config.
            on_fail: Failure behavior.
        """
        self.method = method
        self.recipient = recipient
        self.subject = subject
        self.body = body
        self.config = config or {}
        self.on_fail = on_fail
        
        super().__init__(
            name=name or "notify",
            fn=self._execute,
            description="NOTIFY: Send {} notification".format(
                method if isinstance(method, str) else "custom"
            )
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the NOTIFY action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override parameters.
        
        Returns:
            dict: {status: "sent" or "failed", method: str, ...}
        """
        # Get parameters
        method = kwargs.get('method', self.method)
        recipient = kwargs.get('recipient', self.recipient)
        subject = kwargs.get('subject', self.subject)
        body = kwargs.get('body', self.body)
        config = kwargs.get('config', self.config)
        on_fail = kwargs.get('on_fail', self.on_fail)
        
        # Resolve dynamic values
        recipient = substitute(recipient, memory)
        subject = substitute(subject, memory)
        body = substitute(body, memory)
        config = substitute(config, memory) or {}
        
        try:
            # Dispatch to method handler
            if callable(method):
                success = method(recipient, subject, body, config)
            elif method == "console":
                success = self._notify_console(body)
            elif method == "webhook":
                success = self._notify_webhook(recipient, subject, body, config)
            elif method == "email":
                success = self._notify_email(recipient, subject, body, config)
            else:
                raise ValueError("Unknown notification method: {}".format(method))
            
            return {
                "status": "sent" if success else "failed",
                "method": method if isinstance(method, str) else "custom",
                "recipient": recipient
            }
            
        except Exception as e:
            return self._handle_failure(e, method, recipient, on_fail, memory)
    
    def _notify_console(self, body):
        """
        Print notification to console.
        
        Args:
            body: Message content.
        
        Returns:
            bool: Always True.
        """
        print("[NOTIFY] {}".format(body))
        return True
    
    def _notify_webhook(self, url, subject, body, config):
        """
        Send notification via webhook (HTTP POST).
        
        Args:
            url: Webhook URL.
            subject: Subject (added to payload if present).
            body: Message body (can be str or dict).
            config: Additional config (headers, etc.).
        
        Returns:
            bool: True if request succeeded.
        """
        if not url:
            raise ValueError("Webhook notification requires 'recipient' URL")
        
        # Prepare payload
        if isinstance(body, dict):
            payload = body
            if subject:
                payload["subject"] = subject
        else:
            payload = {"text": str(body)}
            if subject:
                payload["subject"] = subject
        
        # Custom headers
        headers = config.get("headers", {})
        
        response = http_request(
            url=url,
            method="POST",
            headers=headers,
            data=payload,
            timeout=config.get("timeout", 30)
        )
        
        return response.get("success", False)
    
    def _notify_email(self, recipient, subject, body, config):
        """
        Send notification via email (SMTP).
        
        Uses standard library smtplib.
        
        Args:
            recipient: Email address.
            subject: Email subject.
            body: Email body.
            config: SMTP configuration.
        
        Returns:
            bool: True if email sent successfully.
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        if not recipient:
            raise ValueError("Email notification requires 'recipient' address")
        
        # Get SMTP config (from config dict or environment)
        smtp_host = config.get("smtp_host") or os.environ.get("SMTP_HOST", "localhost")
        smtp_port = config.get("smtp_port") or int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = config.get("smtp_user") or os.environ.get("SMTP_USER")
        smtp_pass = config.get("smtp_pass") or os.environ.get("SMTP_PASS")
        from_addr = config.get("from_addr") or smtp_user or "noreply@localhost"
        use_tls = config.get("use_tls", True)
        
        # Build email
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = recipient
        msg["Subject"] = subject or "Notification"
        msg.attach(MIMEText(str(body), "plain"))
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return True
    
    def _handle_failure(self, error, method, recipient, on_fail, memory):
        """
        Handle notification failure.
        
        Args:
            error: Exception that occurred.
            method: Notification method.
            recipient: Intended recipient.
            on_fail: Failure behavior.
            memory: MEMORY instance.
        
        Returns:
            dict: Failure result.
        
        Raises:
            Exception: If on_fail="raise".
        """
        result = {
            "status": "failed",
            "method": method if isinstance(method, str) else "custom",
            "recipient": recipient,
            "error": str(error)
        }
        
        if on_fail == "raise":
            raise error
        
        if on_fail == "log":
            if hasattr(memory, 'add_log'):
                memory.add_log("NOTIFY failed: {}".format(str(error)))
        
        # on_fail == "ignore" - just return the result
        return result
    
    def to_dict(self):
        """
        Serialize NOTIFY to dictionary.
        
        Note: Custom method handlers and sensitive config are not serialized.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "NOTIFY"
        base["on_fail"] = self.on_fail
        if not callable(self.method):
            base["method"] = self.method
        if not callable(self.recipient):
            base["recipient"] = self.recipient
        if not callable(self.subject):
            base["subject"] = self.subject
        if not callable(self.body):
            base["body"] = self.body
        # Note: config with credentials is NOT serialized for security
        return base
    
    @classmethod
    def from_dict(cls, data, config=None, method=None, **kwargs):
        """
        Reconstruct NOTIFY from dictionary.
        
        Args:
            data: Dictionary representation.
            config: SMTP/webhook config (for security, not stored in dict).
            method: Custom method handler if needed.
            **kwargs: Ignored.
        
        Returns:
            NOTIFY: Reconstructed instance.
        """
        notify = cls(
            name=data.get("name"),
            method=method or data.get("method", "console"),
            recipient=data.get("recipient"),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            config=config or {},
            on_fail=data.get("on_fail", "log")
        )
        if data.get("id"):
            notify.id = data["id"]
        return notify
    
    def __repr__(self):
        method = "<callable>" if callable(self.method) else self.method
        return "NOTIFY(name='{}', method='{}', recipient='{}')".format(
            self.name, method, self.recipient or "<none>"
        )
    
    def __str__(self):
        method = "<custom>" if callable(self.method) else self.method
        if self.recipient:
            return "NOTIFY [{}] -> {}".format(method, self.recipient)
        return "NOTIFY [{}]".format(method)
