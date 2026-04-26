"""
Modern PDF Generation Utilities for Deep Research Workflow

2025 Best Practices:
- Full markdown parsing with extensions
- Proper URL handling with numbered references
- Image support with automatic downloading
- Table formatting and other markdown features
- WeasyPrint for professional PDF generation
"""

import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import markdown
from bs4 import BeautifulSoup

import platform
if platform.system() == "Darwin":
    os.environ['PKG_CONFIG_PATH'] = "/opt/homebrew/lib/pkgconfig"
    os.environ['LDFLAGS'] = "-L/opt/homebrew/lib"
    os.environ['CPPFLAGS'] = "-I/opt/homebrew/include"
    os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = "/opt/homebrew/lib:/usr/lib"

class URLReference:
    """Represents a URL reference with title and number"""

    def __init__(self, url: str, title: str = "", number: int = 1):
        self.url = url
        self.title = title or self._extract_domain(url)
        self.number = number

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "") or url
        except:
            return url

    def __str__(self):
        return f"[{self.number}] {self.title}: {self.url}"


class ModernPDFGenerator:
    """Modern PDF generator with full markdown support"""

    def __init__(self):
        self.url_references: Dict[str, URLReference] = {}
        self.reference_counter = 1

    def _preprocess_markdown(self, content: str) -> str:
        """Normalize markdown so block-level elements are properly separated.

        LLM output often lacks blank lines before headings, lists, and blockquotes.
        The Python markdown library requires blank lines to recognize block boundaries.
        """
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # Strip wrapping code fences if the model wrapped the entire response
        stripped = content.strip()
        if stripped.startswith('```') and stripped.endswith('```'):
            lines = stripped.split('\n')
            if lines[0].strip().startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            content = '\n'.join(lines)

        lines = content.split('\n')
        result = []

        for i, line in enumerate(lines):
            stripped_line = line.strip()

            if i > 0 and result:
                prev_stripped = result[-1].strip()
                if prev_stripped != '':
                    needs_blank = False

                    # Current line is a heading
                    if re.match(r'^#{1,6}\s', stripped_line):
                        needs_blank = True
                    # Current line starts a list (prev line is NOT a list item)
                    elif re.match(r'^[-*+]\s', stripped_line) and not re.match(r'^[-*+]\s', prev_stripped):
                        needs_blank = True
                    elif re.match(r'^\d+\.\s', stripped_line) and not re.match(r'^\d+\.\s', prev_stripped):
                        needs_blank = True
                    # Current line is a blockquote start
                    elif stripped_line.startswith('>') and not prev_stripped.startswith('>'):
                        needs_blank = True
                    # Current line is a table row start
                    elif re.match(r'^\|', stripped_line) and not re.match(r'^\|', prev_stripped):
                        needs_blank = True

                    if needs_blank:
                        result.append('')

            result.append(line)

        return '\n'.join(result)

    def save_research_to_pdf(
        self,
        research_content: str,
        query: str = "Research Report",
        output_dir: str = "reports",
        filename: str = None,
    ) -> str:
        """
        Save research content to a professionally formatted PDF.

        Args:
            research_content: The research text to save (markdown format)
            query: Original research query for the title
            output_dir: Directory to save the PDF
            filename: Custom filename (optional)

        Returns:
            str: Path to the saved PDF file
        """
        # Create output directory
        output_dir = os.path.expanduser(output_dir)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = (
                "".join(c for c in query[:50] if c.isalnum() or c in (" ", "-", "_"))
                .strip()
                .replace(" ", "_")
            )
            filename = f"research_report_{safe_query}_{timestamp}.pdf"

        if not filename.endswith(".pdf"):
            filename += ".pdf"

        filepath = os.path.join(output_dir, filename)

        # Parse markdown and extract URLs
        html_content, references = self._markdown_to_html_with_references(
            research_content
        )

        # Create complete HTML document
        full_html = self._create_html_document(html_content, query, references)

        # Generate PDF (lazy import so agency can start without WeasyPrint system libs)
        try:
            from weasyprint import CSS, HTML
        except OSError as e:
            raise RuntimeError(
                "PDF generation requires WeasyPrint system libraries (Pango, Cairo). "
                "On macOS install with: brew install pango cairo gdk-pixbuf libffi. "
                "See https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
            ) from e
        html_doc = HTML(string=full_html)
        css = CSS(string=self._get_modern_css())
        with tempfile.TemporaryDirectory() as temp_dir:
            html_doc.write_pdf(filepath, stylesheets=[css])
        return filepath

    def _markdown_to_html_with_references(
        self, content: str
    ) -> Tuple[str, List[URLReference]]:
        """Convert markdown to HTML while extracting URL references"""

        # Initialize markdown processor with extensions
        md = markdown.Markdown(
            extensions=[
                "tables",
                "toc",
                "codehilite",
                "fenced_code",
                "attr_list",
                "def_list",
                "footnotes",
                "smarty",
                "sane_lists",
            ],
            extension_configs={
                "codehilite": {"css_class": "highlight", "use_pygments": True},
                "toc": {"permalink": False, "title": "Table of Contents"},
            },
        )

        # Preprocess markdown to ensure proper block-level separation
        normalized_content = self._preprocess_markdown(content)

        # Extract and replace URLs with numbered references
        processed_content = self._process_urls_in_markdown(normalized_content)

        # Convert to HTML
        html = md.convert(processed_content)

        # Enhance HTML with BeautifulSoup
        html = self._enhance_html_with_bs4(html)

        return html, list(self.url_references.values())

    def _process_urls_in_markdown(self, content: str) -> str:
        """Process URLs in markdown content and create numbered references"""

        # Reset references for each document
        self.url_references = {}
        self.reference_counter = 1

        # Pattern to match markdown links [text](url)
        link_pattern = r"\[([^\]]*)\]\(([^)]+)\)"

        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2)

            # Skip internal links (anchors)
            if url.startswith("#"):
                return match.group(0)

            # Add to references if not already present
            if url not in self.url_references:
                self.url_references[url] = URLReference(
                    url=url,
                    title=link_text or self._extract_domain_from_url(url),
                    number=self.reference_counter,
                )
                self.reference_counter += 1

            ref = self.url_references[url]
            # Simple approach: just show reference number
            return f"[{ref.number}]"

        # Replace all markdown links
        processed = re.sub(link_pattern, replace_link, content)

        # Handle bare URLs that aren't already processed
        url_pattern = r'(?<!\[)\b(?:https?://|www\.)[^\s<>"\[\]]+(?!\])'

        def replace_bare_url(match):
            url = match.group(0)
            if url not in self.url_references:
                self.url_references[url] = URLReference(
                    url=url,
                    title=self._extract_domain_from_url(url),
                    number=self.reference_counter,
                )
                self.reference_counter += 1

            ref = self.url_references[url]
            return f"[{ref.number}]"

        processed = re.sub(url_pattern, replace_bare_url, processed)

        return processed

    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except:
            return url

    def _enhance_html_with_bs4(self, html: str) -> str:
        """Enhance HTML with BeautifulSoup for better formatting"""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Add classes to elements for better styling
            for table in soup.find_all("table"):
                table["class"] = table.get("class", []) + ["research-table"]
            for blockquote in soup.find_all("blockquote"):
                blockquote["class"] = blockquote.get("class", []) + ["research-quote"]
            for pre in soup.find_all("pre"):
                pre["class"] = pre.get("class", []) + ["research-code"]

            return str(soup)
        except Exception as e:
            logging.warning(f"HTML enhancement failed: {e}")
            return html

    def _create_html_document(
        self, content: str, query: str, references: List[URLReference]
    ) -> str:
        """Create complete HTML document with header, content, and references"""

        # Create references section
        references_html = ""
        if references:
            references_html = "<div class='references'><h2>References</h2><ol class='references-list'>"
            for ref in sorted(references, key=lambda x: x.number):
                references_html += f"<li><strong>{ref.title}</strong><br/><a href='{ref.url}'>{ref.url}</a></li>"
            references_html += "</ol></div>"

        # Generate timestamp
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        # Create complete HTML
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Deep Research Report</title>
        </head>
        <body>
            <div class="document">
                <header class="document-header">
                    <h1 class="document-title">Deep Research Report</h1>
                    <p class="document-query"><strong>Query:</strong> {query}</p>
                    <p class="document-timestamp">Generated on {timestamp}</p>
                </header>
                <main class="document-content">{content}</main>
                {references_html}
            </div>
        </body>
        </html>
        """

    def _get_modern_css(self) -> str:
        """Get modern CSS styles for professional PDF formatting"""
        return """
        @page { size: A4; margin: 2cm; }
        body { font-family: Georgia, serif; font-size: 11pt; line-height: 1.6; color: #2c3e50; }
        .document-header { text-align: center; margin-bottom: 2cm; padding-bottom: 1cm; border-bottom: 2px solid #3498db; }
        .document-title { font-size: 24pt; color: #2c3e50; margin-bottom: 0.5cm; }
        .document-query { font-size: 14pt; color: #34495e; margin-bottom: 0.3cm; }
        .document-timestamp { font-size: 12pt; color: #7f8c8d; font-style: italic; }
        .document-content { margin-bottom: 2cm; }
        h1, h2, h3, h4, h5, h6 { color: #2c3e50; margin-top: 1.5em; margin-bottom: 0.5em; }
        h1 { font-size: 20pt; } h2 { font-size: 16pt; } h3 { font-size: 14pt; }
        p { margin-bottom: 1em; text-align: justify; }
        ul, ol { margin-bottom: 1em; padding-left: 1.5em; }
        .research-table { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 10pt; }
        .research-table th, .research-table td { border: 1px solid #bdc3c7; padding: 0.5em; text-align: left; }
        .research-table th { background-color: #ecf0f1; font-weight: bold; }
        .research-table tr:nth-child(even) { background-color: #f8f9fa; }
        .research-quote { border-left: 4px solid #3498db; padding-left: 1em; margin: 1em 0; font-style: italic; color: #34495e; }
        .research-code { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px; padding: 1em; font-family: monospace; font-size: 9pt; }
        code { background-color: #f8f9fa; padding: 0.2em 0.4em; border-radius: 3px; font-family: monospace; font-size: 9pt; }
        .references { margin-top: 2cm; padding-top: 1cm; border-top: 1px solid #bdc3c7; }
        .references h2 { color: #2c3e50; font-size: 16pt; margin-bottom: 1em; }
        .references-list { font-size: 10pt; line-height: 1.4; }
        .references-list li { margin-bottom: 0.8em; padding-bottom: 0.5em; border-bottom: 1px solid #ecf0f1; }
        .references-list a { color: #3498db; text-decoration: none; word-break: break-all; }
        """


# Create a single instance for use throughout the application
pdf_generator = ModernPDFGenerator()


def save_research_to_pdf(
    research_content: str,
    query: str = "Research Report",
    output_dir: str = "reports",
    filename: str = None,
) -> str:
    """
    Save research content to a professionally formatted PDF.

    Args:
        research_content: The research text to save (markdown format)
        query: Original research query for the title
        output_dir: Directory to save the PDF (default: 'reports')
        filename: Custom filename (optional, auto-generated if not provided)

    Returns:
        str: Path to the saved PDF file
    """
    return pdf_generator.save_research_to_pdf(
        research_content=research_content,
        query=query,
        output_dir=output_dir,
        filename=filename,
    )
