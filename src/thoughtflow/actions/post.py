"""
POST action - send data to external services.

A convenience wrapper around FETCH with sensible defaults for POST requests.
"""

from __future__ import annotations

from thoughtflow.actions.fetch import FETCH
from thoughtflow.actions._substitution import substitute


class POST(FETCH):
    """
    An action that sends data to external services via HTTP POST.
    
    POST is a convenience wrapper around FETCH with sensible defaults
    for sending data. It automatically sets the method to POST and
    provides a cleaner interface for common use cases like webhooks.
    
    Args:
        name (str): Unique identifier for this action.
        url (str|callable): Request URL with optional {variable} placeholders.
        data (any|callable): Payload to send. Can be:
            - dict: Serialized to JSON automatically
            - str: Sent as-is
            - callable: Function (memory) -> data
        headers (dict): Request headers.
        format (str): Payload format:
            - "json": JSON encoding (default)
            - "form": URL-encoded form data
            - "raw": Send as-is
        timeout (float): Request timeout in seconds (default: 30).
        store_as (str): Memory variable for response.
    
    Example:
        >>> from thoughtflow.actions import POST
        >>> from thoughtflow import MEMORY
        
        # Simple webhook
        >>> post = POST(
        ...     url="https://hooks.example.com/trigger",
        ...     data={"event": "complete", "status": "success"}
        ... )
        >>> memory = post(MEMORY())
        
        # Dynamic data from memory
        >>> post = POST(
        ...     url="https://api.example.com/submit",
        ...     data=lambda m: {
        ...         "result": m.get_var("result"),
        ...         "timestamp": m.get_var("timestamp")
        ...     }
        ... )
        
        # With authentication
        >>> post = POST(
        ...     url="https://api.example.com/data",
        ...     data={"query": "{user_query}"},
        ...     headers={"Authorization": "Bearer {api_token}"}
        ... )
    """
    
    def __init__(
        self,
        name=None,
        url=None,
        data=None,
        headers=None,
        format="json",
        timeout=30,
        store_as=None,
    ):
        """
        Initialize a POST action.
        
        Args:
            name: Optional name (defaults to "post").
            url: Request URL.
            data: Payload to send.
            headers: Request headers.
            format: Payload format.
            timeout: Request timeout.
            store_as: Memory variable name.
        """
        self.data = data
        self.format = format
        
        # Prepare headers based on format
        request_headers = headers.copy() if headers else {}
        if format == "json" and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        elif format == "form" and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        super().__init__(
            name=name or "post",
            url=url,
            method="POST",
            headers=request_headers,
            body=data,
            timeout=timeout,
            store_as=store_as
        )
        
        # Update description
        self.description = "POST: Send data to URL"
    
    def _execute(self, memory, **kwargs):
        """
        Execute the POST action.
        
        Handles format-specific encoding before calling parent.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override parameters.
        
        Returns:
            dict: HTTP response.
        """
        import urllib.parse
        
        # Get data (from kwargs or self)
        data = kwargs.get('data', self.data)
        format_type = kwargs.get('format', self.format)
        
        # Resolve data
        data = substitute(data, memory)
        
        # Encode based on format
        if format_type == "form" and isinstance(data, dict):
            # URL-encode for form data
            kwargs['body'] = urllib.parse.urlencode(data)
        else:
            # JSON or raw - let parent handle it
            kwargs['body'] = data
        
        return super()._execute(memory, **kwargs)
    
    def to_dict(self):
        """
        Serialize POST to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "POST"
        base["format"] = self.format
        if not callable(self.data):
            base["data"] = self.data
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct POST from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            POST: Reconstructed instance.
        """
        post = cls(
            name=data.get("name"),
            url=data.get("url"),
            data=data.get("data") or data.get("body"),
            headers=data.get("headers"),
            format=data.get("format", "json"),
            timeout=data.get("timeout", 30),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            post.id = data["id"]
        return post
    
    def __repr__(self):
        url = "<callable>" if callable(self.url) else repr(self.url)
        return "POST(name='{}', url={}, format='{}')".format(
            self.name, url, self.format
        )
    
    def __str__(self):
        if callable(self.url):
            return "POST <dynamic url>"
        return "POST {}".format(self.url)
