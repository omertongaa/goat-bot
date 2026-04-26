"""PDF Generator Service — Converts markdown proposals to polished PDFs.

Uses fpdf2 (pure Python, no system dependencies).
"""

import os
import re
from pathlib import Path
from fpdf import FPDF

BASE_DIR = Path(__file__).parent.parent
DATA_BASE = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))
OUTPUTS_BASE = Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))
OUTPUT_DIR = OUTPUTS_BASE / "proposals"

# Brand colors
ORANGE = (232, 93, 38)
DARK = (26, 26, 46)
GRAY = (136, 136, 136)
WHITE = (255, 255, 255)
LIGHT_BG = (248, 248, 250)


class ProposalPDF(FPDF):
    """Custom PDF class with goat branding."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*GRAY)
            self.cell(0, 10, "goat Agency - Confidential", align="R")
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 10, f"Sayfa {self.page_no()}/{{nb}}", align="C")

    def add_cover(self, title, subtitle="", date=""):
        self.add_page()
        # Orange accent bar
        self.set_fill_color(*ORANGE)
        self.rect(0, 0, 210, 8, "F")
        # Title
        self.set_y(100)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*ORANGE)
        self.multi_cell(0, 14, title, align="C")
        # Subtitle
        if subtitle:
            self.ln(10)
            self.set_font("Helvetica", "", 14)
            self.set_text_color(*GRAY)
            self.multi_cell(0, 8, subtitle, align="C")
        # Date
        if date:
            self.ln(20)
            self.set_font("Helvetica", "", 11)
            self.set_text_color(*GRAY)
            self.cell(0, 8, date, align="C")
        # Bottom bar
        self.set_fill_color(*ORANGE)
        self.rect(0, 289, 210, 8, "F")


def _parse_markdown_blocks(md_text):
    """Parse markdown into structured blocks for PDF rendering."""
    blocks = []
    lines = md_text.split("\n")
    i = 0
    table_rows = []
    in_table = False

    while i < len(lines):
        line = lines[i]

        # Table detection
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # Skip separator rows (---)
            if all(re.match(r'^[-:]+$', c) for c in cells):
                i += 1
                continue
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)
            i += 1
            continue
        elif in_table:
            blocks.append({"type": "table", "rows": table_rows})
            table_rows = []
            in_table = False

        # Headers
        if line.startswith("# "):
            blocks.append({"type": "h1", "text": line[2:].strip()})
        elif line.startswith("## "):
            blocks.append({"type": "h2", "text": line[3:].strip()})
        elif line.startswith("### "):
            blocks.append({"type": "h3", "text": line[4:].strip()})
        # HR
        elif line.strip() in ("---", "***", "___"):
            blocks.append({"type": "hr"})
        # Blockquote
        elif line.strip().startswith("> "):
            blocks.append({"type": "blockquote", "text": line.strip()[2:]})
        # List item
        elif re.match(r'^[\s]*[-*]\s', line):
            text = re.sub(r'^[\s]*[-*]\s', '', line)
            blocks.append({"type": "li", "text": text.strip()})
        elif re.match(r'^[\s]*\d+\.\s', line):
            text = re.sub(r'^[\s]*\d+\.\s', '', line)
            blocks.append({"type": "li", "text": text.strip()})
        # Empty line
        elif line.strip() == "":
            blocks.append({"type": "blank"})
        # Paragraph
        else:
            blocks.append({"type": "p", "text": line.strip()})

        i += 1

    if in_table and table_rows:
        blocks.append({"type": "table", "rows": table_rows})

    return blocks


def _clean_md(text):
    """Strip markdown formatting and problematic unicode for PDF text."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    # Replace unicode chars that Helvetica can't handle
    replacements = {
        '\u2192': '->', '\u2190': '<-', '\u2194': '<->',
        '\u2014': '--', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '-', '\u2026': '...',
        '\u00d7': 'x', '\u2265': '>=', '\u2264': '<=',
        '\u2713': '[x]', '\u2717': '[ ]',
        chr(8226): '-',  # bullet
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Strip any remaining non-latin1 chars
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text


def markdown_to_pdf(markdown_text, output_filename=None, title="Teklif"):
    """Convert markdown text to a styled PDF.

    Returns path to generated PDF, or None on error.
    """
    try:
        pdf = ProposalPDF()
        pdf.alias_nb_pages()

        # Extract title from first H1 if present
        h1_match = re.search(r'^# (.+)$', markdown_text, re.MULTILINE)
        doc_title = h1_match.group(1) if h1_match else title

        # Extract subtitle (first line after title that looks like metadata)
        subtitle_match = re.search(r'^\*\*(.+?)\*\*\s*→\s*\*\*(.+?)\*\*', markdown_text, re.MULTILINE)
        subtitle = ""
        if subtitle_match:
            subtitle = f"{subtitle_match.group(1)}  →  {subtitle_match.group(2)}"

        # Date
        date_match = re.search(r'Tarih:\s*(.+)', markdown_text)
        date_str = date_match.group(1).strip() if date_match else ""

        # Cover page
        pdf.add_cover(_clean_md(doc_title), _clean_md(subtitle), date_str)

        # Content pages
        pdf.add_page()
        blocks = _parse_markdown_blocks(markdown_text)

        for block in blocks:
            btype = block["type"]

            if btype == "h1":
                pdf.ln(8)
                pdf.set_font("Helvetica", "B", 20)
                pdf.set_text_color(*ORANGE)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 10, text)
                # Underline
                pdf.set_draw_color(*ORANGE)
                pdf.set_line_width(0.8)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)

            elif btype == "h2":
                pdf.ln(6)
                pdf.set_font("Helvetica", "B", 15)
                pdf.set_text_color(*DARK)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 8, text)
                pdf.set_draw_color(200, 200, 200)
                pdf.set_line_width(0.3)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(3)

            elif btype == "h3":
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(*ORANGE)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 7, text)
                pdf.ln(2)

            elif btype == "p":
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*DARK)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 6, text)
                pdf.ln(2)

            elif btype == "li":
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*DARK)
                text = _clean_md(block["text"])
                x = pdf.get_x()
                pdf.cell(8, 6, "-", ln=0)
                pdf.multi_cell(0, 6, text)
                pdf.ln(1)

            elif btype == "blockquote":
                pdf.set_fill_color(255, 245, 240)
                pdf.set_draw_color(*ORANGE)
                y = pdf.get_y()
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(100, 100, 100)
                pdf.set_x(15)
                pdf.multi_cell(175, 6, _clean_md(block["text"]), fill=True)
                # Left bar
                pdf.set_line_width(1)
                pdf.line(12, y, 12, pdf.get_y())
                pdf.ln(3)

            elif btype == "hr":
                pdf.ln(4)
                pdf.set_draw_color(200, 200, 200)
                pdf.set_line_width(0.3)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)

            elif btype == "table":
                rows = block["rows"]
                if not rows:
                    continue
                num_cols = len(rows[0])
                col_width = 190 / num_cols

                # Header row
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(*ORANGE)
                pdf.set_text_color(*WHITE)
                for cell in rows[0]:
                    pdf.cell(col_width, 8, _clean_md(cell)[:30], border=0, fill=True)
                pdf.ln()

                # Data rows
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*DARK)
                for ri, row in enumerate(rows[1:]):
                    if ri % 2 == 1:
                        pdf.set_fill_color(*LIGHT_BG)
                    else:
                        pdf.set_fill_color(*WHITE)
                    for cell in row:
                        pdf.cell(col_width, 7, _clean_md(cell)[:30], border=0, fill=True)
                    pdf.ln()
                pdf.ln(3)

            elif btype == "blank":
                pdf.ln(3)

        # Save
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        fname = output_filename or f"proposal_{hash(markdown_text) % 100000}"
        if not fname.endswith(".pdf"):
            fname += ".pdf"
        out_path = OUTPUT_DIR / fname

        pdf.output(str(out_path))
        return str(out_path)

    except Exception as e:
        print(f"PDF generation error: {e}")
        return None


def proposal_file_to_pdf(md_path):
    """Convert an existing markdown proposal file to PDF."""
    path = Path(md_path)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return markdown_to_pdf(content, output_filename=path.stem)


def convert_all_proposals():
    """Convert all existing markdown proposals to PDF. Returns list of paths."""
    proposals_dir = DATA_BASE / "proposals"
    if not proposals_dir.exists():
        return []
    results = []
    for md_file in proposals_dir.glob("*.md"):
        pdf_path = proposal_file_to_pdf(str(md_file))
        if pdf_path:
            results.append(pdf_path)
    return results
