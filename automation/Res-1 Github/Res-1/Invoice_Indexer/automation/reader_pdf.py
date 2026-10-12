"""Render a PDF's pages to PNG bytes with Poppler (via pdf2image). This is the
ONLY file that touches Poppler. 200 DPI, at most 3 pages (see the spec)."""
import io


def render_pdf(pdf_path, dpi=200, max_pages=3, poppler_path=None, _convert=None):
    """Up to `max_pages` pages of `pdf_path` as a list of PNG byte-strings.
    `_convert` defaults to pdf2image.convert_from_path; tests inject a fake so
    they need no Poppler installed."""
    if _convert is None:
        from pdf2image import convert_from_path as _convert

    pages = _convert(pdf_path, dpi=dpi, first_page=1, last_page=max_pages,
                     poppler_path=poppler_path)

    png_bytes = []
    for page in pages[:max_pages]:
        buffer = io.BytesIO()
        page.save(buffer, format="PNG")
        png_bytes.append(buffer.getvalue())
    return png_bytes
