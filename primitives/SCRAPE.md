# SCRAPE

> Fetch a webpage and extract its content as text, markdown, links, tables, or a structured JSON object.

## Philosophy

Once an agent finds a URL (from SEARCH, from a user, or from its own reasoning), it needs to read the page. SCRAPE turns any URL into usable content using only the Python standard library. There are no browser dependencies, no headless Chrome, no Selenium. The HTML is fetched with `urllib` and parsed with `html.parser`, making SCRAPE lightweight enough for Lambda or any minimal runtime.

SCRAPE offers six extraction modes because different tasks need different representations of the same page. A summarization task needs clean text. A research agent needs structured markdown that preserves headings and emphasis. A link-analysis task needs just the links. A data pipeline needs tables. An indexing pipeline needs everything at once, organized into a standardized JSON object. All six modes use the same fetch-and-clean pipeline, and the developer picks the one that fits the job.

Boilerplate removal (nav bars, footers, ads, script tags) is on by default. It is not perfect -- no regex-based cleaner can match a full DOM-aware readability algorithm -- but it handles the common cases well and is fast. When precision matters, the developer can pass `clean=False` and do their own preprocessing, or pass a custom callable as the extraction mode.

## How It Works

SCRAPE is constructed with a URL and an extraction mode. On invocation, the URL is resolved (supporting `{variable}` placeholders), the page is fetched via HTTP GET, and the HTML is optionally cleaned of boilerplate elements. The cleaned HTML is then passed to the extractor matching the chosen mode.

Under the hood, five `HTMLParser` subclasses handle the different extraction concerns:

- `_TextExtractor` -- extracts visible text, skipping script/style/head content, and adding line breaks at block element boundaries.
- `_LinkExtractor` -- collects all `<a>` tags as `{text, url}` dicts, resolving relative URLs against the page's base URL.
- `_TableExtractor` -- collects `<table>` data as lists of lists (rows of cells).
- `_MarkdownExtractor` -- converts HTML to clean markdown: headings, bold/italic, links, images, lists, code blocks, blockquotes, tables, and horizontal rules. This is the most complex extractor and is designed to degrade gracefully on malformed HTML.
- `_MetadataExtractor` -- collects page metadata: `<title>`, `<meta>` description/author/date, `<time>` datetime, headings, and images.

The `"structured"` mode runs all of these extractors on the same HTML and combines their outputs into a single JSON dict.

### Structured Output Schema

```
{
    "url": "https://example.com/article",
    "title": "Page Title",
    "description": "Meta description",
    "author": "Author Name",
    "date_published": "2026-03-01",
    "content_markdown": "# Page Title\n\nArticle content...",
    "content_text": "Page Title Article content...",
    "headings": ["Page Title", "Section 1", "Section 2"],
    "links": [{"text": "Link text", "url": "https://..."}, ...],
    "images": [{"alt": "Photo", "src": "https://..."}, ...],
    "word_count": 1234,
    "timestamp": "2026-03-13T12:00:00Z"
}
```

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `url` | Page URL to scrape. Supports `{variable}` placeholders or a callable `(memory) -> str`. |
| `extract` | Extraction mode: `"text"` (default), `"html"`, `"links"`, `"tables"`, `"markdown"`, `"structured"`, or a callable `(html, url) -> result`. |
| `clean` | Remove boilerplate (nav, header, footer, aside, script, style) before extraction. Default: `True`. Applies to text, links, markdown, and structured modes. |
| `timeout` | Request timeout in seconds (default: 30). |
| `user_agent` | Custom User-Agent header. Default: ThoughtFlow identifier. |
| `store_as` | Memory variable name for the result (default: `"{name}_content"`). |
| `name` | Identifier for the action (default: `"scrape"`). |

## Usage

```python
from thoughtflow.actions import SCRAPE
from thoughtflow import MEMORY

# Extract plain text
scrape = SCRAPE(url="https://example.com/article")
memory = scrape(MEMORY())
text = memory.get_var("scrape_content")

# Convert to markdown (preserves headings, links, emphasis)
scrape = SCRAPE(url="https://example.com/article", extract="markdown")
memory = scrape(MEMORY())
markdown = memory.get_var("scrape_content")

# Full structured extraction (JSON)
scrape = SCRAPE(url="https://example.com/article", extract="structured")
memory = scrape(MEMORY())
data = memory.get_var("scrape_content")
print(data["title"])
print(data["word_count"])
print(len(data["links"]))

# Extract just the links
scrape = SCRAPE(url="https://example.com", extract="links")
memory = scrape(MEMORY())
links = memory.get_var("scrape_content")
for link in links:
    print(link["text"], "->", link["url"])

# Custom extraction with a callable
scrape = SCRAPE(
    url="https://example.com",
    extract=lambda html, url: html.count("<a"),
)
```

### Combining SEARCH and SCRAPE

A common pattern is to search for URLs and then scrape the top results:

```python
from thoughtflow.actions import SEARCH, SCRAPE
from thoughtflow import MEMORY

memory = MEMORY()

# Step 1: Search
search = SEARCH(query="Python best practices", provider="brave", max_results=3)
memory = search(memory)
results = memory.get_var("search_results")

# Step 2: Scrape the top result
top_url = results["results"][0]["url"]
scrape = SCRAPE(url=top_url, extract="structured")
memory = scrape(memory)
page_data = memory.get_var("scrape_content")
```

## Relationship to Other Primitives

- **ACTION**: SCRAPE is a subclass of ACTION. It inherits memory integration, error handling, execution tracking, and serialization.
- **SEARCH**: SEARCH finds URLs; SCRAPE reads them. These two actions form a natural pair for research workflows.
- **FETCH**: FETCH is a generic HTTP client for any API. SCRAPE is specialized for HTML pages: it fetches and then extracts content. Use FETCH for JSON APIs; use SCRAPE for web pages.
- **TOOL**: To let an LLM decide when to scrape, wrap SCRAPE in a TOOL.
- **MEMORY**: The URL can reference memory variables. Extracted content is stored in memory at the configured key.

## Considerations for Future Development

- JavaScript rendering: some pages require JS to produce content. A future mode could use a headless browser (as an optional dependency) for these cases.
- Readability-style extraction: a more sophisticated algorithm (similar to Mozilla's Readability) that identifies the main content area rather than relying on boilerplate-stripping regex.
- PDF and document extraction: extend SCRAPE to handle non-HTML content types (PDF, DOCX) by detecting Content-Type and dispatching to appropriate parsers.
- Caching: store fetched HTML to avoid redundant requests for the same URL.
- Robots.txt compliance: optionally respect robots.txt directives.
- Rate limiting and politeness delays for crawling multiple pages.
