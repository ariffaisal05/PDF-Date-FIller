"""PDF merge and split operations, independent from date filling and cleaning."""

import pymupdf


def _open_pdf(data):
    document = pymupdf.open(stream=data, filetype="pdf")
    if document.needs_pass:
        document.close()
        raise ValueError("This PDF is password-protected. Remove its password and try again.")
    return document


def merge_pdfs(pdf_data):
    """Merge PDFs in the given order, copying supported interactive objects."""
    merged = pymupdf.open()
    sources = []
    try:
        for data in pdf_data:
            source = _open_pdf(data)
            sources.append(source)
            merged.insert_pdf(source, links=True, annots=True, widgets=True)
        if not merged.page_count:
            raise ValueError("Upload at least one PDF with a page.")
        return merged.tobytes(deflate=True, garbage=3)
    finally:
        merged.close()
        for source in sources:
            source.close()


def parse_page_ranges(text, page_count):
    """Parse one 1-based page or inclusive range per line."""
    ranges = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = line.split("-")
        if len(parts) > 2 or any(not part.strip().isdigit() for part in parts):
            raise ValueError(f"Line {line_number}: enter a page number or range, such as 2-5.")
        start = int(parts[0].strip())
        end = int(parts[-1].strip())
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"Line {line_number}: pages must be between 1 and {page_count}.")
        ranges.append((start, end))

    if not ranges:
        raise ValueError("Enter at least one page number or range.")

    used_pages = set()
    for start, end in ranges:
        pages = set(range(start, end + 1))
        if used_pages & pages:
            raise ValueError("Page ranges cannot overlap.")
        used_pages.update(pages)
    return ranges


def split_pdf(data, page_ranges):
    """Return one PDF per inclusive 1-based page range."""
    source = _open_pdf(data)
    outputs = []
    try:
        for start, end in page_ranges:
            output = pymupdf.open()
            try:
                output.insert_pdf(
                    source,
                    from_page=start - 1,
                    to_page=end - 1,
                    links=True,
                    annots=True,
                    widgets=True,
                )
                outputs.append(output.tobytes(deflate=True, garbage=3))
            finally:
                output.close()
        return outputs
    finally:
        source.close()
