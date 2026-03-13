"""
SCRAPE action - fetch and extract content from web pages.

Uses only Python standard library (urllib, html.parser).
Supports text, HTML, links, tables, markdown, and structured extraction modes.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute
from thoughtflow.actions._http import http_request


# =========================================================================
# HTML Extractors
# =========================================================================


class _TextExtractor(HTMLParser):
    """
    HTML parser that extracts visible text content.

    Filters out script, style, and other non-visible elements.
    Correctly handles void elements (meta, link, br, hr, img, input)
    which never produce end tags and should not affect skip depth.
    """

    SKIP_TAGS = {
        'script', 'style', 'head', 'noscript', 'iframe',
    }
    # Void elements are self-closing -- they never have a matching end tag,
    # so we must not increment skip_depth for them.
    VOID_SKIP_TAGS = {'meta', 'link'}
    BLOCK_TAGS = {
        'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'li', 'tr', 'td', 'th', 'blockquote', 'pre', 'hr',
    }

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
        """Return cleaned text from parsed HTML."""
        text = ' '.join(self.text_parts)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()


class _LinkExtractor(HTMLParser):
    """
    HTML parser that extracts all links as {text, url} dicts.
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
            href = self._resolve_url(self.current_href)
            self.links.append({"text": text, "url": href})
            self.current_href = None
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data.strip())

    def _resolve_url(self, href):
        """Resolve relative URLs against the base URL."""
        if not href or href.startswith(('http://', 'https://', '//')):
            return href
        if href.startswith('/'):
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            return "{}://{}{}".format(parsed.scheme, parsed.netloc, href)
        return self.base_url.rsplit('/', 1)[0] + '/' + href


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
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag == 'tr' and self.current_row is not None:
            if self.current_row:
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag in ('td', 'th') and self.in_cell:
            text = ' '.join(self.current_cell).strip()
            self.current_row.append(text)
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data.strip())


class _MetadataExtractor(HTMLParser):
    """
    HTML parser that extracts page metadata: title, description, author,
    published date, and images.

    Collects information from <title>, <meta>, <time>, <h1>, and <img> tags.
    """

    def __init__(self, base_url=""):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.description = ""
        self.author = ""
        self.date_published = ""
        self.images = []
        self.headings = []

        # Internal parsing state
        self._in_title = False
        self._title_parts = []
        self._in_heading = False
        self._heading_parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)

        if tag in ('script', 'style'):
            self._skip_depth += 1
            return

        if tag == 'title':
            self._in_title = True
            self._title_parts = []

        elif tag == 'meta':
            self._handle_meta(attrs_dict)

        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._in_heading = True
            self._heading_parts = []

        elif tag == 'time':
            dt = attrs_dict.get('datetime', '')
            if dt and not self.date_published:
                self.date_published = dt

        elif tag == 'img':
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', '')
            if src:
                self.images.append({"alt": alt, "src": src})

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in ('script', 'style'):
            self._skip_depth = max(0, self._skip_depth - 1)
            return

        if tag == 'title':
            self._in_title = False
            if not self.title:
                self.title = ' '.join(self._title_parts).strip()

        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._in_heading = False
            heading_text = ' '.join(self._heading_parts).strip()
            if heading_text:
                self.headings.append(heading_text)
                # Use first h1 as fallback title
                if tag == 'h1' and not self.title:
                    self.title = heading_text

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._in_title:
            self._title_parts.append(data.strip())
        if self._in_heading:
            self._heading_parts.append(data.strip())

    def _handle_meta(self, attrs):
        """Process a <meta> tag for description, author, and date fields."""
        name = (attrs.get('name') or attrs.get('property') or '').lower()
        content = attrs.get('content', '')

        if not content:
            return

        if name in ('description', 'og:description') and not self.description:
            self.description = content

        elif name in ('author', 'article:author') and not self.author:
            self.author = content

        elif name in (
            'article:published_time',
            'og:updated_time',
            'date',
            'publish_date',
        ) and not self.date_published:
            self.date_published = content


class _MarkdownExtractor(HTMLParser):
    """
    HTML parser that converts HTML into clean, readable Markdown.

    Handles headings, paragraphs, bold/italic, links, images, lists,
    code blocks, blockquotes, tables, and horizontal rules. Designed to
    degrade gracefully on malformed or deeply nested HTML.
    """

    SKIP_TAGS = {
        'script', 'style', 'head', 'noscript', 'iframe',
    }
    HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    HEADING_PREFIX = {
        'h1': '# ', 'h2': '## ', 'h3': '### ',
        'h4': '#### ', 'h5': '##### ', 'h6': '###### ',
    }

    def __init__(self):
        super().__init__()
        self._output = []
        self._skip_depth = 0

        # Inline formatting state
        self._link_href = None
        self._link_text = []
        self._in_bold = False
        self._in_italic = False
        self._in_code = False
        self._in_pre = False

        # Block state
        self._in_heading = None
        self._heading_parts = []
        self._in_blockquote = False
        self._in_li = False
        self._list_stack = []

        # Table state
        self._in_table = False
        self._table_rows = []
        self._current_row = []
        self._current_cell = []
        self._in_cell = False
        self._header_row_seen = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)

        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return

        if tag in self.HEADING_TAGS:
            self._in_heading = tag
            self._heading_parts = []

        elif tag == 'p':
            self._ensure_blank_line()

        elif tag == 'br':
            self._output.append('  \n')

        elif tag == 'hr':
            self._ensure_blank_line()
            self._output.append('---\n\n')

        elif tag in ('strong', 'b'):
            self._in_bold = True
            self._output.append('**')

        elif tag in ('em', 'i'):
            self._in_italic = True
            self._output.append('*')

        elif tag == 'a':
            self._link_href = attrs_dict.get('href', '')
            self._link_text = []

        elif tag == 'img':
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', '')
            if src:
                self._output.append('![{}]({})'.format(alt, src))

        elif tag == 'pre':
            self._in_pre = True
            self._ensure_blank_line()
            self._output.append('```\n')

        elif tag == 'code':
            if not self._in_pre:
                self._in_code = True
                self._output.append('`')

        elif tag == 'blockquote':
            self._in_blockquote = True
            self._ensure_blank_line()

        elif tag == 'ul':
            self._list_stack.append('ul')
            self._ensure_newline()

        elif tag == 'ol':
            self._list_stack.append('ol')
            self._ensure_newline()

        elif tag == 'li':
            self._in_li = True
            indent = '  ' * max(0, len(self._list_stack) - 1)
            if self._list_stack and self._list_stack[-1] == 'ol':
                self._output.append('{}1. '.format(indent))
            else:
                self._output.append('{}- '.format(indent))

        elif tag == 'table':
            self._in_table = True
            self._table_rows = []
            self._header_row_seen = False
            self._ensure_blank_line()

        elif tag == 'tr':
            self._current_row = []

        elif tag in ('td', 'th'):
            self._current_cell = []
            self._in_cell = True

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return

        if tag in self.HEADING_TAGS and self._in_heading == tag:
            prefix = self.HEADING_PREFIX.get(tag, '# ')
            text = ''.join(self._heading_parts).strip()
            self._ensure_blank_line()
            self._output.append('{}{}\n\n'.format(prefix, text))
            self._in_heading = None

        elif tag == 'p':
            self._output.append('\n\n')

        elif tag in ('strong', 'b') and self._in_bold:
            self._in_bold = False
            self._output.append('**')

        elif tag in ('em', 'i') and self._in_italic:
            self._in_italic = False
            self._output.append('*')

        elif tag == 'a' and self._link_href is not None:
            text = ''.join(self._link_text).strip()
            href = self._link_href
            self._output.append('[{}]({})'.format(text, href))
            self._link_href = None
            self._link_text = []

        elif tag == 'pre':
            self._in_pre = False
            self._output.append('\n```\n\n')

        elif tag == 'code' and self._in_code:
            self._in_code = False
            self._output.append('`')

        elif tag == 'blockquote':
            self._in_blockquote = False
            self._output.append('\n')

        elif tag in ('ul', 'ol'):
            if self._list_stack:
                self._list_stack.pop()
            self._output.append('\n')

        elif tag == 'li':
            self._in_li = False
            self._output.append('\n')

        elif tag in ('td', 'th'):
            if self._in_cell:
                cell_text = ''.join(self._current_cell).strip()
                self._current_row.append(cell_text)
                self._in_cell = False

        elif tag == 'tr':
            if self._current_row:
                self._table_rows.append(self._current_row)

        elif tag == 'table':
            self._flush_table()
            self._in_table = False

    def handle_data(self, data):
        if self._skip_depth > 0:
            return

        # Route text into the right collector
        if self._in_cell:
            self._current_cell.append(data)
            return

        if self._in_heading is not None:
            self._heading_parts.append(data)
            return

        if self._link_href is not None:
            self._link_text.append(data)
            return

        text = data
        if not self._in_pre:
            text = re.sub(r'\s+', ' ', text)
            if not text.strip():
                return

        if self._in_blockquote:
            for line in text.split('\n'):
                stripped = line.strip()
                if stripped:
                    self._output.append('> {}\n'.format(stripped))
        else:
            self._output.append(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_blank_line(self):
        """Make sure the output ends with a blank line (double newline)."""
        current = ''.join(self._output)
        if current and not current.endswith('\n\n'):
            if current.endswith('\n'):
                self._output.append('\n')
            else:
                self._output.append('\n\n')

    def _ensure_newline(self):
        """Make sure the output ends with at least one newline."""
        current = ''.join(self._output)
        if current and not current.endswith('\n'):
            self._output.append('\n')

    def _flush_table(self):
        """Convert collected table rows into a pipe-delimited markdown table."""
        if not self._table_rows:
            return

        # Determine column count from the widest row
        col_count = max(len(row) for row in self._table_rows)

        for i, row in enumerate(self._table_rows):
            # Pad short rows
            while len(row) < col_count:
                row.append('')
            self._output.append('| {} |\n'.format(' | '.join(row)))

            # Insert separator after the first row (header)
            if i == 0:
                sep = '| {} |'.format(' | '.join('---' for _ in row))
                self._output.append(sep + '\n')

        self._output.append('\n')

    def get_markdown(self):
        """
        Return the final markdown string, cleaned up.

        Collapses excessive blank lines and trims leading/trailing whitespace.
        """
        raw = ''.join(self._output)
        # Collapse runs of 3+ newlines into 2
        cleaned = re.sub(r'\n{3,}', '\n\n', raw)
        return cleaned.strip()


# =========================================================================
# SCRAPE ACTION
# =========================================================================


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
            - "markdown": Content converted to clean Markdown
            - "structured": Standardized JSON with all extracted components
            - callable: Custom extractor ``(html, url) -> extracted``
        clean (bool): Remove boilerplate (nav, footer, ads) before extraction
            (default: True). Applies to text, links, markdown, and structured
            modes.
        timeout (float): Request timeout in seconds (default: 30).
        user_agent (str): Custom User-Agent header.
        store_as (str): Memory variable for content (default: "{name}_content").

    Example:
        >>> from thoughtflow.actions import SCRAPE
        >>> from thoughtflow import MEMORY

        # Extract text
        >>> scrape = SCRAPE(url="https://example.com")
        >>> memory = scrape(MEMORY())
        >>> text = memory.get_var("scrape_content")

        # Convert page to Markdown
        >>> scrape = SCRAPE(
        ...     url="https://example.com",
        ...     extract="markdown",
        ... )

        # Full structured extraction (JSON)
        >>> scrape = SCRAPE(
        ...     url="https://example.com",
        ...     extract="structured",
        ... )

    Returns:
        Extracted content. The type depends on the extraction mode:
        - "text" / "html" / "markdown": str
        - "links": list of dicts
        - "tables": list of lists
        - "structured": dict with standardized fields
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (compatible; ThoughtFlow/1.0; "
        "+https://github.com/thoughtflow)"
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
            extract: Extraction mode string or callable.
            clean: Whether to clean boilerplate before extraction.
            timeout: Request timeout in seconds.
            user_agent: Custom User-Agent header.
            store_as: Memory variable name for the result.
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

        Fetches the page, optionally cleans boilerplate, then dispatches
        to the requested extraction mode.

        Args:
            memory: MEMORY instance.
            **kwargs: Can override 'url', 'extract', 'clean'.

        Returns:
            Extracted content (format depends on extract mode).
        """
        url = kwargs.get('url', self.url)
        extract = kwargs.get('extract', self.extract)
        clean = kwargs.get('clean', self.clean)

        url = substitute(url, memory)
        if not url:
            raise ValueError("SCRAPE url cannot be empty")
        url = str(url)

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
                "url": url,
            }

        html = response.get("data", "")

        # Modes that benefit from boilerplate removal
        cleanable_modes = ("text", "links", "markdown", "structured")
        if clean and extract in cleanable_modes:
            html = self._clean_html(html)

        return self._extract_content(html, url, extract)

    # ------------------------------------------------------------------
    # HTML cleaning
    # ------------------------------------------------------------------

    def _clean_html(self, html):
        """
        Basic HTML cleaning to remove common boilerplate elements.

        Strips nav, header, footer, aside, script, style, noscript tags
        and HTML comments.

        Args:
            html: Raw HTML string.

        Returns:
            Cleaned HTML string.
        """
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

    # ------------------------------------------------------------------
    # Extraction dispatch
    # ------------------------------------------------------------------

    def _extract_content(self, html, url, extract):
        """
        Extract content from HTML based on the requested mode.

        Args:
            html: HTML string (possibly already cleaned).
            url: Original URL (for resolving relative links).
            extract: Extraction mode string or callable.

        Returns:
            Extracted content in the requested format.
        """
        if callable(extract):
            return extract(html, url)

        if extract == "html":
            return html

        if extract == "text":
            return self._extract_text(html)

        if extract == "links":
            return self._extract_links(html, url)

        if extract == "tables":
            return self._extract_tables(html)

        if extract == "markdown":
            return self._extract_markdown(html)

        if extract == "structured":
            return self._extract_structured(html, url)

        # Unknown mode -- return raw HTML as a safe fallback
        return html

    # ------------------------------------------------------------------
    # Individual extractors
    # ------------------------------------------------------------------

    def _extract_text(self, html):
        """Extract visible text from HTML."""
        extractor = _TextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        return extractor.get_text()

    def _extract_links(self, html, url):
        """Extract all links from HTML."""
        extractor = _LinkExtractor(base_url=url)
        try:
            extractor.feed(html)
        except Exception:
            return []
        return extractor.links

    def _extract_tables(self, html):
        """Extract tables from HTML as lists of lists."""
        extractor = _TableExtractor()
        try:
            extractor.feed(html)
        except Exception:
            return []
        return extractor.tables

    def _extract_markdown(self, html):
        """
        Convert HTML to clean Markdown.

        Uses the _MarkdownExtractor parser to produce readable Markdown
        with headings, links, bold/italic, lists, code blocks, blockquotes,
        tables, and images.

        Args:
            html: HTML string.

        Returns:
            Markdown string.
        """
        extractor = _MarkdownExtractor()
        try:
            extractor.feed(html)
        except Exception:
            # Graceful degradation: strip tags and return plain text
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        return extractor.get_markdown()

    def _extract_structured(self, html, url):
        """
        Extract all components into a standardized JSON dict.

        Combines metadata extraction (title, description, author, date),
        markdown conversion, plain text, headings, links, images, and
        word count into a single response object.

        Args:
            html: HTML string.
            url: Original URL.

        Returns:
            dict: Structured extraction result with standardized keys.
        """
        from datetime import datetime, timezone

        # Metadata (title, description, author, date, headings, images)
        meta = _MetadataExtractor(base_url=url)
        try:
            meta.feed(html)
        except Exception:
            pass

        # Markdown conversion
        markdown_content = self._extract_markdown(html)

        # Plain text
        text_content = self._extract_text(html)

        # Links
        links = self._extract_links(html, url)

        # Word count from the text content
        words = text_content.split()
        word_count = len(words)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return {
            "url": url,
            "title": meta.title,
            "description": meta.description,
            "author": meta.author,
            "date_published": meta.date_published or None,
            "content_markdown": markdown_content,
            "content_text": text_content,
            "headings": meta.headings,
            "links": links,
            "images": meta.images,
            "word_count": word_count,
            "timestamp": now,
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

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
        ext = "<callable>" if callable(self.extract) else self.extract
        return "SCRAPE(name='{}', url={}, extract='{}')".format(
            self.name, url, ext
        )

    def __str__(self):
        if callable(self.url):
            return "SCRAPE <dynamic url>"
        return "SCRAPE: {}".format(self.url)
