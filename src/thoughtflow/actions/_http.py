"""
HTTP utilities for ACTION primitives.

Provides a simple HTTP client using only Python standard library (urllib).
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


# Default User-Agent for requests
DEFAULT_USER_AGENT = "ThoughtFlow/1.0 (Python urllib)"


def http_request(
    url,
    method="GET",
    headers=None,
    data=None,
    params=None,
    timeout=30,
    parse_response="auto",
):
    """
    Make an HTTP request using only urllib (standard library).
    
    Args:
        url: The URL to request.
        method: HTTP method (GET, POST, PUT, DELETE, etc.).
        headers: Dict of request headers.
        data: Request body. Can be:
            - dict: JSON-encoded automatically
            - str: Sent as-is
            - bytes: Sent as-is
        params: Dict of query parameters (appended to URL).
        timeout: Request timeout in seconds.
        parse_response: How to parse response body:
            - "auto": Detect from Content-Type
            - "json": Parse as JSON
            - "text": Return as string
            - "bytes": Return raw bytes
    
    Returns:
        dict: {
            "status_code": int,
            "headers": dict,
            "data": parsed response body,
            "url": final URL (after redirects),
            "elapsed_ms": float,
            "success": bool (True if 2xx status)
        }
    
    Raises:
        Does not raise - errors are captured in the response dict.
    """
    start_time = time.time()
    
    # Build headers
    request_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if headers:
        request_headers.update(headers)
    
    # Add query parameters to URL
    if params:
        url_parts = list(urllib.parse.urlparse(url))
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urllib.parse.urlencode(query)
        url = urllib.parse.urlunparse(url_parts)
    
    # Prepare request body
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = json.dumps(data).encode('utf-8')
            if 'Content-Type' not in request_headers:
                request_headers['Content-Type'] = 'application/json'
        elif isinstance(data, str):
            body = data.encode('utf-8')
        elif isinstance(data, bytes):
            body = data
        else:
            body = str(data).encode('utf-8')
    
    # Create request
    req = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method.upper()
    )
    
    # Create SSL context that allows HTTPS
    ssl_context = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Read response
            response_body = response.read()
            response_headers = dict(response.headers)
            status_code = response.status
            final_url = response.url
            
            # Parse response body
            parsed_data = _parse_response_body(
                response_body,
                response_headers.get('Content-Type', ''),
                parse_response
            )
            
            return {
                "status_code": status_code,
                "headers": response_headers,
                "data": parsed_data,
                "url": final_url,
                "elapsed_ms": round(elapsed_ms, 2),
                "success": 200 <= status_code < 300,
                "error": None
            }
            
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Try to read error response body
        try:
            error_body = e.read()
            error_data = _parse_response_body(error_body, '', parse_response)
        except Exception:
            error_data = None
        
        return {
            "status_code": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "data": error_data,
            "url": url,
            "elapsed_ms": round(elapsed_ms, 2),
            "success": False,
            "error": str(e.reason)
        }
        
    except urllib.error.URLError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "status_code": 0,
            "headers": {},
            "data": None,
            "url": url,
            "elapsed_ms": round(elapsed_ms, 2),
            "success": False,
            "error": str(e.reason)
        }
        
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "status_code": 0,
            "headers": {},
            "data": None,
            "url": url,
            "elapsed_ms": round(elapsed_ms, 2),
            "success": False,
            "error": str(e)
        }


def _parse_response_body(body, content_type, parse_mode):
    """
    Parse response body based on content type or explicit mode.
    
    Args:
        body: Raw response bytes.
        content_type: Content-Type header value.
        parse_mode: Explicit parse mode or "auto".
    
    Returns:
        Parsed body (dict, str, or bytes).
    """
    if parse_mode == "bytes":
        return body
    
    if parse_mode == "text":
        return body.decode('utf-8', errors='replace')
    
    if parse_mode == "json":
        try:
            return json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body.decode('utf-8', errors='replace')
    
    # Auto-detect based on content type
    if parse_mode == "auto":
        content_type_lower = content_type.lower() if content_type else ''
        
        if 'application/json' in content_type_lower:
            try:
                return json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        if 'text/' in content_type_lower or 'application/xml' in content_type_lower:
            return body.decode('utf-8', errors='replace')
        
        # Default to text for unknown types
        try:
            return body.decode('utf-8')
        except UnicodeDecodeError:
            return body
    
    # Unknown mode, return as text
    return body.decode('utf-8', errors='replace')
