import re

import pymupdf

DATE_LABELS = {"tanggal", "bulan", "tahun"}

def normalize_text(text):
    """Normalize a PDF word so punctuation and capitalization are ignored."""
    return re.sub(r"[^a-z]", "", text.lower())


def find_date_in_pdf(pdf_path):
    """Find `Hari ini` and `bulan` on the same line.

    Returns `(page_number, label_rects, detected_text)`. The `hari_ini`
    rectangle covers both words so the day can be inserted after the phrase.
    """
    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc):
            words = []
            for item in page.get_text("words"):
                x0, y0, x1, y1, text = item[:5]
                words.append({
                    "text": normalize_text(text),
                    "rect": pymupdf.Rect(x0, y0, x1, y1),
                    "line": tuple(item[5:7]),
                })

            hari_ini_candidates = []
            hari_words = [word for word in words if word["text"] == "hari"]
            ini_words = [word for word in words if word["text"] == "ini"]

            # Usually extracted as two words; also handle PDFs extracting it
            # as a single word token.
            for word in words:
                if word["text"] == "hariini":
                    hari_ini_candidates.append(word)

            for hari in hari_words:
                for ini in ini_words:
                    gap = ini["rect"].x0 - hari["rect"].x1
                    same_line = hari["line"] == ini["line"]
                    close_words = 0 <= gap <= max(
                        hari["rect"].height, ini["rect"].height
                    )
                    if same_line and close_words:
                        hari_ini_candidates.append({
                            "text": "hariini",
                            "rect": pymupdf.Rect(
                                hari["rect"].x0,
                                min(hari["rect"].y0, ini["rect"].y0),
                                ini["rect"].x1,
                                max(hari["rect"].y1, ini["rect"].y1),
                            ),
                            "line": hari["line"],
                        })

            bulan_candidates = [word for word in words if word["text"] == "bulan"]
            pairs = [
                (hari_ini, bulan)
                for hari_ini in hari_ini_candidates
                for bulan in bulan_candidates
                if hari_ini["line"] == bulan["line"]
                and bulan["rect"].x0 > hari_ini["rect"].x1
            ]
            if not pairs:
                continue

            hari_ini, bulan = min(
                pairs,
                key=lambda pair: pair[1]["rect"].x0 - pair[0]["rect"].x1,
            )
            label_rects = {
                "hari_ini": hari_ini["rect"],
                "bulan": bulan["rect"],
            }
            return page_number, label_rects, "Hari ini, bulan"

    return None, None, None
