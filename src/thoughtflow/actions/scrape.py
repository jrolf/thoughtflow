"""
SCRAPE action - fetch and extract content from web pages.

Uses only Python standard library (urllib, html.parser).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute
from thoughtflow.actions._http import http_request


class _TextExtractor(HTMLParser):
    """
    HTML parser that extracts visible text content.
    
    Filters out script, style, and other non-visible elements.
    """
    
    SKIP_TAGS = {'script', 'style', 'head', 'meta', 'link', 'noscript', 'iframe'}
    BLOCK_TAGS = {'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                  'li', 'tr', 'td', 'th', 'blockquote', 'pre', 'hr'}
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_depth = 0
        self.current_tag = None
    
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()
        if self.current_tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif self.current_tag in self.BLOCK_TAGS and self.text_parts:
            self.text_parts.append('\n')
    
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in self.BLOCK_TAGS:
            self.text_parts.append('\n')
    
    def handle_data(self, data):
        if self.skip_depth == 0:
            text = data.strip()
            if text:
                self.text_parts.append(text)
    
    def get_text(self):
        # Join and clean up whitespace
        text = ' '.join(self.text_parts)
        # Collapse multiple newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)
        # Collapse multiple spaces
        text = re.sub(r' +', ' ', text)
        return text.strip()


class _LinkExtractor(HTMLParser):
    """
    HTML parser that extracts all links.
    """
    
    def __init__(self, base_url=""):
        super().__init__()
        self.links = []
        self.base_url = base_url
        self.current_href = None
        self.current_text = []
    
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            attrs_dict = dict(attrs)
            self.current_href = attrs_dict.get('href', '')
            self.current_text = []
    
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.current_href:
            text = ' '.join(self.current_text).strip()
            # Resolve relative URLs
            href = self.current_href
            if href and not href.startswith(('http://', 'https://', '//')):
                if href.startswith('/'):
                    # Absolute path
                    from urllib.parse import urlparse
                    parsed = urlparse(self.base_url)
                    href = "{}://{}{}".format(parsed.scheme, parsed.netloc, href)
                else:
                    # Relative path
                    href = self.base_url.rsplit('/', 1)[0] + '/' + href
            self.links.append({"text": text, "url": href})
            self.current_href = None
            self.current_text = []
    
    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data.strip())


class _TableExtractor(HTMLParser):
    """
    HTML parser that extracts tables as lists of lists.
    """
    
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = []
        self.in_cell = False
    
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'table':
            self.current_table = []
        elif tag == 'tr' and self.current_table is not None:
            self.current_row = []
        elif tag in ('td', 'th') and self.current_row is not None:
            self.current_cell = []
            self.in_cell = True
    
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'table' and self.current_table is not None:
            if self.current_table:  # Only add non-empty tables
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag == 'tr' and self.current_row is not None:
            if self.current_row:  # Only add non-empty rows
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag in ('td', 'th') and self.in_cell:
            text = ' '.join(self.current_cell).strip()
            self.current_row.append(text)
            self.in_cell = False
    
    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data.strip())


class SCRAPE(ACTION):
    """
    An action that fetches and extracts content from web pages.
    
    SCRAPE downloads a webpage and extracts content in various formats
    using only Python standard library.
    
    Args:
        name (str): Unique identifier for this action.
        url (str|callable): Page URL with optional {variable} placeholders.
        extract (str|callable): Extraction mode:
            - "text": Clean text content (default)
            - "html": Raw HTML
            - "links": All links as [{text, url}, ...]
            - "tables": Tables as list of lists
            - callable: Custom extractor (html, url) -> extracted
        clean (bool): Remove boilerplate (nav, ads) - basic cleaning (default: True).
        timeout (float): Request timeout in seconds (default: 30).
        user_agent (str): Custom User-Agent header.
        store_as (str): Memory variable for content (default: "{name}_content").
    
    Example:
        >>> from thoughtflow.actions import SCRAPE
        >>> from thoughtflow import MEMORY
        
        # Extract text from webpage
        >>> scrape = SCRAPE(url="https://example.com/article")
        >>> memory = scrape(MEMORY())
        >>> text = memory.get_var("scrape_content")
        
        # Extract all links
        >>> scrape = SCRAPE(
        ...     url="https://example.com",
        ...     extract="links"
        ... )
        
        # Extract tables
        >>> scrape = SCRAPE(
        ...     url="https://example.com/data",
        ...     extract="tables"
        ... )
        
        # Get raw HTML
        >>> scrape = SCRAPE(
        ...     url="https://example.com",
        ...     extract="html"
        ... )
        
        # Custom extraction
        >>> scrape = SCRAPE(
        ...     url="https://example.com",
        ...     extract=lambda html, url: custom_parser(html)
        ... )
    """
    
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (compatible; ThoughtFlow/1.0; +https://github.com/thoughtflow)"
    )
    
    def __init__(
        self,
        name=None,
        url=None,
        extract="text",
        clean=True,
        timeout=30,
        user_agent=None,
        store_as=None,
    ):
        """
        Initialize a SCRAPE action.
        
        Args:
            name: Optional name (defaults to "scrape").
            url: Page URL to scrape.
            extract: Extraction mode.
            clean: Whether to clean boilerplate.
            timeout: Request timeout.
            user_agent: Custom User-Agent.
            store_as: Memory variable name.
        """
        if url is None:
            raise ValueError("SCRAPE requires 'url' parameter")
        
        self.url = url
        self.extract = extract
        self.clean = clean
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        
        name = name or "scrape"
        
        super().__init__(
            name=name,
            fn=self._execute,
            result_key=store_as or "{}_content".format(name),
            description="SCRAPE: Extract content from webpage"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the SCRAPE action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override parameters.
        
        Returns:
            Extracted content (format depends on extract mode).
        """
        # Get parameters
        url = kwargs.get('url', self.url)
        extract = kwargs.get('extract', self.extract)
        clean = kwargs.get('clean', self.clean)
        
        # Resolve URL
        url = substitute(url, memory)
        if not url:
            raise ValueError("SCRAPE url cannot be empty")
        url = str(url)
        
        # Fetch the page
        response = http_request(
            url=url,
            method="GET",
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            parse_response="text"
        )
        
        if not response.get("success"):
            return {
                "error": response.get("error"),
                "status_code": response.get("status_code"),
                "url": url
            }
        
        html = response.get("data", "")
        
        # Clean HTML if requested
        if clean and extract in ("text", "links"):
            html = self._clean_html(html)
        
        # Extract content
        return self._extract_content(html, url, extract)
    
    def _clean_html(self, html):
        """
        Basic HTML cleaning to remove common boilerplate elements.
        
        Args:
            html: Raw HTML string.
        
        Returns:
            Cleaned HTML string.
        """
        # Remove common boilerplate elements
        patterns = [
            r'<nav[^>]*>.*?</nav>',
            r'<header[^>]*>.*?</header>',
            r'<footer[^>]*>.*?</footer>',
            r'<aside[^>]*>.*?</aside>',
            r'<script[^>]*>.*?</script>',
            r'<style[^>]*>.*?</style>',
            r'<noscript[^>]*>.*?</noscript>',
            r'<!--.*?-->',
        ]
        
        for pattern in patterns:
            html = re.sub(pattern, '', html, flags=re.DOTALL | re.IGNORECASE)
        
        return html
    
    def _extract_content(self, html, url, extract):
        """
        Extract content from HTML based on mode.
        
        Args:
            html: HTML string.
            url: Original URL (for resolving relative links).
            extract: Extraction mode.
        
        Returns:
            Extracted content.
        """
        if callable(extract):
            return extract(html, url)
        
        if extract == "html":
            return html
        
        if extract == "text":
            extractor = _TextExtractor()
            try:
                extractor.feed(html)
            except Exception:
                # If parsing fails, do basic text extraction
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
            return extractor.get_text()
        
        if extract == "links":
            extractor = _LinkExtractor(base_url=url)
            try:
                extractor.feed(html)
            except Exception:
                return []
            return extractor.links
        
        if extract == "tables":
            extractor = _TableExtractor()
            try:
                extractor.feed(html)
            except Exception:
                return []
            return extractor.tables
        
        # Unknown mode, return raw HTML
        return html
    
    def to_dict(self):
        """
        Serialize SCRAPE to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "SCRAPE"
        base["clean"] = self.clean
        base["timeout"] = self.timeout
        base["user_agent"] = self.user_agent
        if not callable(self.url):
            base["url"] = self.url
        if not callable(self.extract):
            base["extract"] = self.extract
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct SCRAPE from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            SCRAPE: Reconstructed instance.
        """
        scrape = cls(
            name=data.get("name"),
            url=data.get("url"),
            extract=data.get("extract", "text"),
            clean=data.get("clean", True),
            timeout=data.get("timeout", 30),
            user_agent=data.get("user_agent"),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            scrape.id = data["id"]
        return scrape
    
    def __repr__(self):
        url = "<callable>" if callable(self.url) else repr(self.url)
        return "SCRAPE(name='{}', url={}, extract='{}')".format(
            self.name, url, self.extract if not callable(self.extract) else "<callable>"
        )
    
    def __str__(self):
        if callable(self.url):
            return "SCRAPE <dynamic url>"
        return "SCRAPE: {}".format(self.url)
