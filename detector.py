import re

import pymupdf


DATE_LABELS = {"tanggal", "bulan", "tahun"}


def normalize_text(text):
    """Normalize a PDF word so punctuation and capitalization are ignored."""
    return re.sub(r"[^a-z]", "", text.lower())


def find_date_in_pdf(pdf_path):
    """Find date labels and return their page and text bounds.

    The first page containing a `tanggal` and `bulan` pair on the same line
    is selected. A `tahun` label on that line is included when present.
    Returns `(page_number, labels, detected_text)`, where `labels` maps each
    label to its PyMuPDF rectangle.
    """
    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc):
            found = {label: [] for label in DATE_LABELS}
            for item in page.get_text("words"):
                x0, y0, x1, y1, text = item[:5]
                label = normalize_text(text)
                if label in found:
                    found[label].append(pymupdf.Rect(x0, y0, x1, y1))

            # Pair labels on the same baseline, choosing the closest pair.
            pairs = [
                (tanggal, bulan)
                for tanggal in found["tanggal"]
                for bulan in found["bulan"]
                if bulan.x0 > tanggal.x1
                and abs(tanggal.y0 - bulan.y0) < max(tanggal.height, bulan.height)
            ]
            if not pairs:
                continue

            tanggal, bulan = min(pairs, key=lambda pair: pair[1].x0 - pair[0].x1)
            labels = {"tanggal": tanggal, "bulan": bulan}

            years = [
                year for year in found["tahun"]
                if year.x0 > bulan.x1
                and abs(year.y0 - bulan.y0) < max(year.height, bulan.height)
            ]
            if years:
                labels["tahun"] = min(years, key=lambda year: year.x0 - bulan.x1)

            return page_number, labels, ", ".join(labels)

    return None, None, None
