"""
Document Converter and Multi-Format Ingestion Adapter for CodeGraph.
Converts enterprise documentation formats into normalized Markdown:
1. Markdown (.md, .markdown) - Native
2. Plain Text (.txt) - Normalized text
3. HTML / Confluence Wiki Exports (.html, .htm) - Converted via stdlib HTMLParser
4. JSON / Jira Exports (.json) - Converted to PRD/Requirement Markdown
5. PDF (.pdf) & Word (.docx) - Text extraction via native tools/libraries
Zero external dependencies required for core conversions.
"""

import os
import re
import json
import subprocess
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, Any, Optional

SUPPORTED_DOC_EXTENSIONS = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".pdf": "pdf",
    ".docx": "docx"
}


class HTMLToMarkdownParser(HTMLParser):
    """Zero-dependency HTML to Markdown converter using standard library html.parser."""
    def __init__(self):
        super().__init__()
        self.output = []
        self.in_title = False
        self.in_heading = 0
        self.in_list_item = False

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_lower[1])
            self.output.append(f"\n\n{'#' * level} ")
            self.in_heading = level
        elif tag_lower == "p":
            self.output.append("\n\n")
        elif tag_lower == "li":
            self.output.append("\n- ")
            self.in_list_item = True
        elif tag_lower in ("strong", "b"):
            self.output.append("**")
        elif tag_lower in ("em", "i"):
            self.output.append("*")
        elif tag_lower == "code":
            self.output.append("`")
        elif tag_lower in ("br", "hr"):
            self.output.append("\n")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.output.append("\n")
            self.in_heading = 0
        elif tag_lower in ("strong", "b"):
            self.output.append("**")
        elif tag_lower in ("em", "i"):
            self.output.append("*")
        elif tag_lower == "code":
            self.output.append("`")
        elif tag_lower == "li":
            self.in_list_item = False

    def handle_data(self, data):
        self.output.append(data)

    def get_markdown(self) -> str:
        text = "".join(self.output)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


class DocumentConverter:
    @staticmethod
    def to_markdown(file_path: str) -> str:
        """
        Loads and converts any supported document format into normalized Markdown.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            return ""

        ext = path_obj.suffix.lower()

        # 1. Native Markdown & Plain Text
        if ext in (".md", ".markdown", ".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        # 2. HTML / Confluence Export
        if ext in (".html", ".htm"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()
            parser = HTMLToMarkdownParser()
            parser.feed(html_content)
            return parser.get_markdown()

        # 3. JSON / Jira Issues Export
        if ext == ".json":
            return DocumentConverter._convert_jira_json(file_path)

        # 4. PDF (pdftotext / textutil / pypdf)
        if ext == ".pdf":
            return DocumentConverter._convert_pdf(file_path)

        # 5. DOCX (textutil on macOS, pandoc, or python-docx)
        if ext == ".docx":
            return DocumentConverter._convert_docx(file_path)

        # Default fallback
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @staticmethod
    def _convert_jira_json(file_path: str) -> str:
        """Converts Jira issue / Confluence JSON exports into structured PRD markdown."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except Exception:
            return ""

        lines = [f"# PRD: {Path(file_path).stem.replace('-', ' ').title()}\n"]
        lines.append(f"**Document ID:** DOC-{Path(file_path).stem.upper()}\n")
        lines.append("**Status:** APPROVED\n\n## Requirements\n")

        # Support array of Jira issues or single issue object
        issues = data if isinstance(data, list) else data.get("issues", [data])
        for iss in issues:
            key = iss.get("key") or iss.get("id") or "REQ-000"
            fields = iss.get("fields", iss)
            summary = fields.get("summary") or fields.get("title") or "Unnamed Requirement"
            desc = fields.get("description") or "No description provided."
            priority_obj = fields.get("priority", {})
            priority = priority_obj.get("name") if isinstance(priority_obj, dict) else str(priority_obj or "MEDIUM")
            status_obj = fields.get("status", {})
            status = status_obj.get("name") if isinstance(status_obj, dict) else str(status_obj or "IMPLEMENTED")

            lines.append(f"### {key}: {summary}\n")
            lines.append(f"**Priority:** {priority.upper()}\n")
            lines.append(f"**Status:** {status.upper()}\n")
            lines.append(f"**Description:** {desc}\n")

            # Check for acceptance criteria / scenarios
            ac = fields.get("acceptance_criteria") or fields.get("scenarios") or ""
            if ac:
                lines.append("\n**Test Scenarios:**\n")
                if isinstance(ac, list):
                    for idx, s in enumerate(ac, 1):
                        lines.append(f"- **SCEN-{key}-{idx}:** {s}\n")
                else:
                    lines.append(f"- **SCEN-{key}-1:** {ac}\n")
            lines.append("\n")

        return "\n".join(lines)

    @staticmethod
    def _convert_pdf(file_path: str) -> str:
        """Extracts text from PDF via macOS textutil/pdftotext or pypdf if available."""
        # Try pdftotext command line
        try:
            cmd = ["pdftotext", file_path, "-"]
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        except Exception:
            pass

        # Try pypdf if installed
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            return "\n\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception:
            return f"# Document from {Path(file_path).name}\n\n[PDF text extraction requires 'pdftotext' or 'pypdf']"

    @staticmethod
    def _convert_docx(file_path: str) -> str:
        """Extracts text from DOCX via macOS textutil or python-docx."""
        # On macOS, textutil is pre-installed natively in /usr/bin/textutil!
        try:
            cmd = ["textutil", "-convert", "txt", "-stdout", file_path]
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        except Exception:
            pass

        try:
            import docx
            doc = docx.Document(file_path)
            return "\n\n".join([p.text for p in doc.paragraphs if p.text])
        except Exception:
            return f"# Document from {Path(file_path).name}\n\n[DOCX text extraction requires 'textutil' or 'python-docx']"
