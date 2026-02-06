"""
FETCH action - make HTTP requests.

Generic HTTP client using only Python standard library (urllib).
"""

from __future__ import annotations

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute
from thoughtflow.actions._http import http_request


class FETCH(ACTION):
    """
    An action that makes HTTP requests.
    
    FETCH provides a generic HTTP client using only Python standard library.
    It supports all HTTP methods, custom headers, request bodies, and
    automatic response parsing.
    
    Args:
        name (str): Unique identifier for this action.
        url (str|callable): Request URL. Supports:
            - str: Static URL with {variable} placeholders
            - callable: Function (memory) -> str for dynamic URLs
        method (str): HTTP method (default: "GET").
        headers (dict): Request headers (values support {variable} placeholders).
        params (dict): Query parameters (appended to URL).
        body (any): Request body (dict auto-serialized to JSON).
        parse (str): Response parsing mode:
            - "auto": Detect from Content-Type (default)
            - "json": Parse as JSON
            - "text": Return as string
            - "bytes": Return raw bytes
        timeout (float): Request timeout in seconds (default: 30).
        retry (int): Number of retry attempts on failure (default: 0).
        retry_delay (float): Delay between retries in seconds (default: 1.0).
        store_as (str): Memory variable for response (default: "{name}_response").
    
    Example:
        >>> from thoughtflow.actions import FETCH
        >>> from thoughtflow import MEMORY
        
        # Simple GET request
        >>> fetch = FETCH(url="https://api.example.com/data")
        >>> memory = fetch(MEMORY())
        >>> result = memory.get_var("fetch_response")
        
        # GET with headers and parameters
        >>> fetch = FETCH(
        ...     url="https://api.example.com/search",
        ...     headers={"Authorization": "Bearer {api_key}"},
        ...     params={"q": "{query}", "limit": 10}
        ... )
        
        # POST with JSON body
        >>> fetch = FETCH(
        ...     url="https://api.example.com/submit",
        ...     method="POST",
        ...     body={"name": "{user_name}", "data": "{payload}"}
        ... )
        
        # With retry logic
        >>> fetch = FETCH(
        ...     url="https://flaky-api.com/data",
        ...     retry=3,
        ...     retry_delay=2.0
        ... )
    """
    
    def __init__(
        self,
        name=None,
        url=None,
        method="GET",
        headers=None,
        params=None,
        body=None,
        parse="auto",
        timeout=30,
        retry=0,
        retry_delay=1.0,
        store_as=None,
    ):
        """
        Initialize a FETCH action.
        
        Args:
            name: Optional name (defaults to "fetch").
            url: Request URL.
            method: HTTP method.
            headers: Request headers.
            params: Query parameters.
            body: Request body.
            parse: Response parsing mode.
            timeout: Request timeout.
            retry: Retry attempts.
            retry_delay: Delay between retries.
            store_as: Memory variable name.
        """
        if url is None:
            raise ValueError("FETCH requires 'url' parameter")
        
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.params = params or {}
        self.body = body
        self.parse = parse
        self.timeout = timeout
        self.retry = retry
        self.retry_delay = retry_delay
        
        name = name or "fetch"
        
        super().__init__(
            name=name,
            fn=self._execute,
            result_key=store_as or "{}_response".format(name),
            description="FETCH: HTTP {} request".format(self.method)
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the FETCH action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override any parameter.
        
        Returns:
            dict: HTTP response with status_code, headers, data, etc.
        """
        import time as time_module
        
        # Get parameters (allow kwargs to override)
        url = kwargs.get('url', self.url)
        method = kwargs.get('method', self.method)
        headers = kwargs.get('headers', self.headers)
        params = kwargs.get('params', self.params)
        body = kwargs.get('body', self.body)
        parse = kwargs.get('parse', self.parse)
        timeout = kwargs.get('timeout', self.timeout)
        retry = kwargs.get('retry', self.retry)
        retry_delay = kwargs.get('retry_delay', self.retry_delay)
        
        # Resolve URL
        url = substitute(url, memory)
        if url is None:
            raise ValueError("FETCH url cannot be None")
        url = str(url)
        
        # Resolve headers
        headers = substitute(headers, memory) or {}
        
        # Resolve params
        params = substitute(params, memory) or {}
        
        # Resolve body
        body = substitute(body, memory)
        
        # Make request with retries
        last_response = None
        attempts = 0
        max_attempts = 1 + retry
        
        while attempts < max_attempts:
            attempts += 1
            
            response = http_request(
                url=url,
                method=method,
                headers=headers,
                params=params,
                data=body,
                timeout=timeout,
                parse_response=parse
            )
            
            last_response = response
            
            # If successful, return immediately
            if response.get("success"):
                return response
            
            # If we have retries left, wait and retry
            if attempts < max_attempts:
                time_module.sleep(retry_delay)
        
        # Return the last response (even if failed)
        return last_response
    
    def to_dict(self):
        """
        Serialize FETCH to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "FETCH"
        base["method"] = self.method
        base["parse"] = self.parse
        base["timeout"] = self.timeout
        base["retry"] = self.retry
        base["retry_delay"] = self.retry_delay
        if not callable(self.url):
            base["url"] = self.url
        if not callable(self.headers):
            base["headers"] = self.headers
        if not callable(self.params):
            base["params"] = self.params
        if not callable(self.body):
            base["body"] = self.body
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct FETCH from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            FETCH: Reconstructed instance.
        """
        fetch = cls(
            name=data.get("name"),
            url=data.get("url"),
            method=data.get("method", "GET"),
            headers=data.get("headers"),
            params=data.get("params"),
            body=data.get("body"),
            parse=data.get("parse", "auto"),
            timeout=data.get("timeout", 30),
            retry=data.get("retry", 0),
            retry_delay=data.get("retry_delay", 1.0),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            fetch.id = data["id"]
        return fetch
    
    def __repr__(self):
        url = "<callable>" if callable(self.url) else repr(self.url)
        return "FETCH(name='{}', method='{}', url={})".format(
            self.name, self.method, url
        )
    
    def __str__(self):
        if callable(self.url):
            return "FETCH {} <dynamic url>".format(self.method)
        return "FETCH {} {}".format(self.method, self.url)
