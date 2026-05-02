"""PDF Generator Service — Converts markdown proposals to polished PDFs.

Uses fpdf2 with Unicode font support for Turkish characters.
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
ORANGE_LIGHT = (255, 245, 240)
DARK = (26, 26, 46)
GRAY = (120, 120, 130)
WHITE = (255, 255, 255)
LIGHT_BG = (248, 248, 252)
ACCENT_BAR = (232, 93, 38)

# Unicode TTF fonts (macOS paths)
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC = "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"
FONT_UNICODE = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


def _best_font():
    """Find the best available Unicode font."""
    for f in [FONT_UNICODE, FONT_REGULAR, FONT_BOLD]:
        if Path(f).exists():
            return f
    return None


class ProposalPDF(FPDF):
    """Custom PDF class with goat branding and full Unicode support."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        self._setup_fonts()
        self._on_cover = False

    def accept_page_break(self):
        # Don't auto-break on the cover page
        if self._on_cover:
            return False
        return super().accept_page_break()

    def _setup_fonts(self):
        """Register Unicode fonts."""
        if Path(FONT_REGULAR).exists():
            self.add_font("body", "", FONT_REGULAR)
        if Path(FONT_BOLD).exists():
            self.add_font("body", "B", FONT_BOLD)
        elif Path(FONT_REGULAR).exists():
            self.add_font("body", "B", FONT_REGULAR)
        if Path(FONT_ITALIC).exists():
            self.add_font("body", "BI", FONT_ITALIC)
        # Fallback: use Helvetica if no TTF found
        self._has_unicode = Path(FONT_REGULAR).exists()

    def _font(self, style="", size=10):
        """Set font with Unicode fallback."""
        if self._has_unicode:
            self.set_font("body", style, size)
        else:
            self.set_font("Helvetica", style, size)

    def header(self):
        if self.page_no() > 1:
            # Thin orange line at top
            self.set_draw_color(*ORANGE)
            self.set_line_width(0.5)
            self.line(10, 8, 200, 8)
            # Header text
            self._font("", 7)
            self.set_text_color(*GRAY)
            self.set_y(10)
            self.cell(0, 5, "GOAT Agency  —  Confidential", align="R")
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        # Thin line
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.3)
        self.line(10, self.get_y() - 2, 200, self.get_y() - 2)
        self._font("", 7)
        self.set_text_color(*GRAY)
        self.cell(0, 10, f"Sayfa {self.page_no()}/{{nb}}", align="C")

    def add_cover(self, title, agency="GOAT Agency", client="", date="", cover_image=None):
        self._on_cover = True
        self.add_page()

        # Full-width orange bar at top
        self.set_fill_color(*ORANGE)
        self.rect(0, 0, 210, 12, "F")

        # Title area first, then image as background accent
        y_start = 80
        self.set_y(y_start)

        # Agency name small
        self._font("", 10)
        self.set_text_color(*GRAY)
        self.cell(0, 6, agency.upper(), align="C")
        self.ln(12)

        # Main title
        self._font("B", 32)
        self.set_text_color(*DARK)
        self.multi_cell(0, 16, title, align="C")

        # Divider
        self.ln(8)
        self.set_draw_color(*ORANGE)
        self.set_line_width(1.5)
        self.line(80, self.get_y(), 130, self.get_y())
        self.ln(10)

        # Client name
        if client:
            self._font("", 14)
            self.set_text_color(*ORANGE)
            self.cell(0, 8, client, align="C")
            self.ln(8)

        # Date
        if date:
            self._font("", 11)
            self.set_text_color(*GRAY)
            self.cell(0, 8, date, align="C")

        # Cover image as small accent below content
        if cover_image and Path(cover_image).exists():
            try:
                self.image(cover_image, x=55, y=185, w=100)
            except Exception:
                pass

        # Bottom bar
        self.set_fill_color(*ORANGE)
        self.rect(0, 285, 210, 12, "F")

        # Bottom text — use text() not cell() to avoid triggering page break
        self._font("B", 8)
        self.set_text_color(*WHITE)
        self.text(95, 293, "goatagency.com")
        self._on_cover = False


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
        elif line.strip() in ("---", "***", "___"):
            blocks.append({"type": "hr"})
        elif line.strip().startswith("> "):
            blocks.append({"type": "blockquote", "text": line.strip()[2:]})
        elif re.match(r'^[\s]*[-*]\s', line):
            text = re.sub(r'^[\s]*[-*]\s', '', line)
            blocks.append({"type": "li", "text": text.strip()})
        elif re.match(r'^[\s]*\d+\.\s', line):
            text = re.sub(r'^[\s]*\d+\.\s', '', line)
            blocks.append({"type": "li", "text": text.strip()})
        elif line.strip() == "":
            blocks.append({"type": "blank"})
        else:
            blocks.append({"type": "p", "text": line.strip()})

        i += 1

    if in_table and table_rows:
        blocks.append({"type": "table", "rows": table_rows})

    return blocks


def _clean_md(text):
    """Strip markdown formatting but KEEP Unicode/Turkish characters."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    # Clean up common unicode arrows/dashes to readable alternatives
    text = text.replace('\u2192', '→').replace('\u2014', '—').replace('\u2013', '–')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    return text.strip()


def _clean_proposal_text(text):
    """Remove Claude response artifacts from proposal text."""
    # Remove "Here's the proposal:" type prefixes
    prefixes = [
        r"^Here'?s the proposal:?\s*\n*",
        r"^İşte teklif:?\s*\n*",
        r"^Bu teklifi bir dosyaya kaydetmemi.*$",
        r"^---\s*$",
    ]
    for p in prefixes:
        text = re.sub(p, '', text, flags=re.MULTILINE)
    # Remove leading/trailing whitespace
    return text.strip()


def markdown_to_pdf(markdown_text, output_filename=None, title="İş Teklifi", cover_image=None):
    """Convert markdown text to a styled PDF.

    Returns path to generated PDF, or None on error.
    """
    try:
        # Clean up Claude artifacts
        markdown_text = _clean_proposal_text(markdown_text)

        pdf = ProposalPDF()
        pdf.alias_nb_pages()

        # Extract title from first H1 if present
        h1_match = re.search(r'^# (.+)$', markdown_text, re.MULTILINE)
        doc_title = _clean_md(h1_match.group(1)) if h1_match else title

        # Extract client/agency info
        subtitle_match = re.search(r'(?:GOAT Agency|Maiony)\s*(?:→|->)\s*\*{0,2}(.+?)\*{0,2}\s*$', markdown_text, re.MULTILINE)
        client = _clean_md(subtitle_match.group(1).strip()) if subtitle_match else ""

        # Date
        date_match = re.search(r'Tarih:\s*\*{0,2}(.+?)\*{0,2}\s*$', markdown_text, re.MULTILINE)
        date_str = _clean_md(date_match.group(1).strip()) if date_match else ""
        if not date_str:
            date_match2 = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', markdown_text)
            date_str = date_match2.group(1) if date_match2 else ""

        # Find cover image if not provided
        if not cover_image:
            # Look for a matching proposal cover in creatives
            creatives_dir = BASE_DIR / "outputs" / "creatives"
            if creatives_dir.exists():
                covers = sorted(creatives_dir.glob("proposal_*.png"), reverse=True)
                if covers:
                    cover_image = str(covers[0])

        # Cover page
        pdf.add_cover(doc_title, agency="GOAT Agency", client=client, date=date_str, cover_image=cover_image)

        # Content page
        pdf.add_page()
        blocks = _parse_markdown_blocks(markdown_text)
        # Skip leading blanks and cover metadata (already shown on cover page)
        skip_types = {"blank", "hr"}
        cover_patterns = ["İş Teklifi", "Teklif", "GOAT Agency", "Maiony", "Tarih:", "Hazırlayan:", "→", "->"]
        while blocks:
            b = blocks[0]
            if b["type"] in skip_types:
                blocks.pop(0)
            elif b["type"] == "h1" and any(p in b.get("text", "") for p in ["Teklif"]):
                blocks.pop(0)  # Skip the H1 title (already on cover)
            elif b["type"] == "p" and any(p in b.get("text", "") for p in cover_patterns):
                blocks.pop(0)  # Skip metadata lines
            else:
                break

        for block in blocks:
            btype = block["type"]

            if btype == "h1":
                pdf.ln(8)
                pdf._font("B", 22)
                pdf.set_text_color(*ORANGE)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 11, text)
                # Orange underline
                pdf.set_draw_color(*ORANGE)
                pdf.set_line_width(1)
                pdf.line(10, pdf.get_y() + 1, 80, pdf.get_y() + 1)
                pdf.ln(6)

            elif btype == "h2":
                pdf.ln(6)
                pdf._font("B", 16)
                pdf.set_text_color(*DARK)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 9, text)
                pdf.ln(3)

            elif btype == "h3":
                pdf.ln(4)
                pdf._font("B", 13)
                pdf.set_text_color(*ORANGE)
                text = _clean_md(block["text"])
                pdf.multi_cell(0, 7, text)
                pdf.ln(2)

            elif btype == "p":
                pdf._font("", 10)
                pdf.set_text_color(*DARK)
                text = _clean_md(block["text"])
                if text:
                    pdf.multi_cell(0, 6, text)
                    pdf.ln(2)

            elif btype == "li":
                pdf._font("", 10)
                pdf.set_text_color(*DARK)
                text = _clean_md(block["text"])
                x = pdf.get_x()
                # Orange bullet
                pdf.set_text_color(*ORANGE)
                pdf.cell(6, 6, "•")
                pdf.set_text_color(*DARK)
                pdf.multi_cell(0, 6, text)
                pdf.ln(1)

            elif btype == "blockquote":
                y = pdf.get_y()
                pdf.set_fill_color(*ORANGE_LIGHT)
                pdf._font("", 10)
                pdf.set_text_color(80, 80, 90)
                pdf.set_x(18)
                pdf.multi_cell(172, 6, _clean_md(block["text"]), fill=True)
                # Orange left bar
                pdf.set_draw_color(*ORANGE)
                pdf.set_line_width(2)
                pdf.line(13, y, 13, pdf.get_y())
                pdf.ln(3)

            elif btype == "hr":
                pdf.ln(4)
                pdf.set_draw_color(220, 220, 225)
                pdf.set_line_width(0.3)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)

            elif btype == "table":
                rows = block["rows"]
                if not rows:
                    continue
                num_cols = len(rows[0])

                # Calculate column widths based on content
                col_widths = []
                available = 190
                for ci in range(num_cols):
                    max_len = 0
                    for row in rows:
                        if ci < len(row):
                            max_len = max(max_len, len(row[ci]))
                    col_widths.append(max_len)
                total = sum(col_widths) or 1
                col_widths = [max(30, (w / total) * available) for w in col_widths]
                # Normalize to fit
                scale = available / sum(col_widths)
                col_widths = [w * scale for w in col_widths]

                # Header row
                pdf._font("B", 9)
                pdf.set_fill_color(*ORANGE)
                pdf.set_text_color(*WHITE)
                for ci, cell in enumerate(rows[0]):
                    w = col_widths[ci] if ci < len(col_widths) else 40
                    pdf.cell(w, 8, _clean_md(cell), border=0, fill=True)
                pdf.ln()

                # Data rows
                pdf._font("", 9)
                pdf.set_text_color(*DARK)
                for ri, row in enumerate(rows[1:]):
                    if ri % 2 == 0:
                        pdf.set_fill_color(*LIGHT_BG)
                    else:
                        pdf.set_fill_color(*WHITE)
                    for ci, cell in enumerate(row):
                        w = col_widths[ci] if ci < len(col_widths) else 40
                        text = _clean_md(cell)
                        # Truncate only if really needed
                        max_chars = int(w / 2.2)
                        if len(text) > max_chars:
                            text = text[:max_chars - 1] + "…"
                        pdf.cell(w, 7, text, border=0, fill=True)
                    pdf.ln()
                pdf.ln(4)

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
        import traceback
        traceback.print_exc()
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
