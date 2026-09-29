import re

import pymupdf

SAME_LINE_TOLERANCE = 8

def normalize_text(text):
    """Normalize a PDF word so punctuation and capitalization are ignored."""
    return re.sub(r"[^a-z]", "", text.lower())


def find_date_in_pdf(pdf_path):
    """Find `Hari ini`, `tanggal`, and `bulan` by visible text positions.

    PDF line metadata can split words that visually share a line, so the
    detector compares their vertical positions instead of internal line IDs.
    Returns `(page_number, label_rects, detected_text)`.
    """
    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc):
            words = []
            for item in page.get_text("words"):
                x0, y0, x1, y1, text = item[:5]
                words.append((normalize_text(text), pymupdf.Rect(x0, y0, x1, y1)))

            hari_words = [rect for text, rect in words if text == "hari"]
            ini_words = [rect for text, rect in words if text == "ini"]
            hari_ini_candidates = [
                rect for text, rect in words if text == "hariini"
            ]

            for hari in hari_words:
                for ini in ini_words:
                    gap = ini.x0 - hari.x1
                    same_line = abs(hari.y0 - ini.y0) < SAME_LINE_TOLERANCE
                    close_words = 0 <= gap <= max(hari.height, ini.height)
                    if same_line and close_words:
                        hari_ini_candidates.append(pymupdf.Rect(
                            hari.x0,
                            min(hari.y0, ini.y0),
                            ini.x1,
                            max(hari.y1, ini.y1),
                        ))

            tanggal_candidates = [rect for text, rect in words if text == "tanggal"]
            bulan_candidates = [rect for text, rect in words if text == "bulan"]
            triples = [
                (hari_ini, tanggal, bulan)
                for hari_ini in hari_ini_candidates
                for tanggal in tanggal_candidates
                for bulan in bulan_candidates
                if hari_ini.x1 < tanggal.x0 < bulan.x0
                and tanggal.x1 < bulan.x0
                and abs(hari_ini.y0 - tanggal.y0) < SAME_LINE_TOLERANCE
                and abs(tanggal.y0 - bulan.y0) < SAME_LINE_TOLERANCE
            ]
            if not triples:
                continue

            hari_ini, tanggal, bulan = min(
                triples,
                key=lambda triple: (
                    triple[1].x0 - triple[0].x1
                    + triple[2].x0 - triple[1].x1
                ),
            )
            return page_number, {
                "hari_ini": hari_ini,
                "tanggal": tanggal,
                "bulan": bulan,
            }, "Hari ini, tanggal, bulan"

    return None, None, None
