import re

import pymupdf


SAME_LINE_TOLERANCE = 8
INDONESIAN_WEEKDAYS = {
    "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu"
}
INDONESIAN_MONTHS = {
    "januari", "februari", "maret", "april", "mei", "juni",
    "juli", "agustus", "september", "oktober", "november", "desember",
}
ENGLISH_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
}
ENGLISH_MONTHS = {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}


def normalize_text(text):
    """Normalize words and numeric date values, ignoring punctuation."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_date_in_pdf(pdf_path):
    """Find Indonesian date markers or the English `Today` marker.

    PDF line metadata can split words that visually share a line, so the
    Indonesian detector compares vertical positions instead of internal line
    IDs. English dates are anchored immediately after `Today`. Returns
    `(page_number, label_rects, old_value_rects, detected_text)`.
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
                # English forms place the complete date after the marker
                # "today,". Detect and clear any existing date tokens there.
                today_candidates = [
                    rect for text, rect in words if text == "today"
                ]
                for today in today_candidates:
                    following = sorted(
                        (
                            (text, rect)
                            for text, rect in words
                            if rect.x0 >= today.x1
                            and abs(rect.y0 - today.y0) < SAME_LINE_TOLERANCE
                        ),
                        key=lambda item: item[1].x0,
                    )
                    old_value_rects = []
                    date_started = False
                    for text, rect in following:
                        is_day = text.isdigit() and 1 <= int(text) <= 31
                        is_year = bool(re.fullmatch(r"(?:19|20)\d{2}", text))
                        if (
                            text in ENGLISH_WEEKDAYS
                            or text in ENGLISH_MONTHS
                            or is_day
                            or is_year
                        ):
                            old_value_rects.append(rect)
                            date_started = True
                        elif not text:
                            # Standalone punctuation may separate date parts.
                            continue
                        elif date_started:
                            break
                        else:
                            break

                    return page_number, {"today": today}, old_value_rects, "Today"

                continue

            hari_ini, tanggal, bulan = min(
                triples,
                key=lambda triple: (
                    triple[1].x0 - triple[0].x1
                    + triple[2].x0 - triple[1].x1
                ),
            )

            old_value_rects = []

            def right_of(anchor, stop=None):
                return sorted(
                    (
                        (text, rect)
                        for text, rect in words
                        if rect.x0 >= anchor.x1
                        and abs(rect.y0 - anchor.y0) < SAME_LINE_TOLERANCE
                        and (stop is None or rect.x1 < stop.x0)
                    ),
                    key=lambda item: item[1].x0,
                )

            # Remove a previously inserted weekday (current format) or a
            # numeric day left by an earlier version from after "Hari ini".
            for text, rect in right_of(hari_ini, tanggal):
                is_numeric_day = text.isdigit() and 1 <= int(text) <= 31
                if text in INDONESIAN_WEEKDAYS or is_numeric_day:
                    old_value_rects.append(rect)

            # Remove the previous day value after "tanggal".
            for text, rect in right_of(tanggal, bulan):
                if text.isdigit() and 1 <= int(text) <= 31:
                    old_value_rects.append(rect)

            # Remove an existing Indonesian month and adjacent year after
            # "bulan", including dates inserted by this processor earlier.
            month_area = right_of(bulan)
            month_tokens = [
                (text, rect)
                for text, rect in month_area
                if text in INDONESIAN_MONTHS
            ]
            if month_tokens:
                # Prior runs can leave multiple values overlapped. Remove all
                # recognized month/year tokens before the next comma on this
                # line, where the following sentence begins.
                commas = [
                    rect for text, rect in month_area
                    if not text and rect.x0 > month_tokens[0][1].x1
                ]
                stop_x = min((rect.x0 for rect in commas), default=None)
                for text, rect in month_area:
                    in_date_area = stop_x is None or rect.x0 < stop_x
                    if in_date_area and (
                        text in INDONESIAN_MONTHS
                        or re.fullmatch(r"(?:19|20)\d{2}", text)
                    ):
                        old_value_rects.append(rect)

            # Older revisions wrote the year after a printed "tahun" label.
            year_labels = [rect for text, rect in words if text == "tahun"]
            for year_label in year_labels:
                years = [
                    (text, rect)
                    for text, rect in right_of(year_label)
                    if re.fullmatch(r"(?:19|20)\d{2}", text)
                ]
                old_value_rects.extend(rect for _, rect in years)

            # A year after `bulan` and after a printed `tahun` label can be
            # discovered by both cleanup rules; only redact it once.
            unique_old_value_rects = []
            seen_rects = set()
            for rect in old_value_rects:
                key = tuple(round(value, 2) for value in rect)
                if key not in seen_rects:
                    seen_rects.add(key)
                    unique_old_value_rects.append(rect)

            return page_number, {
                "hari_ini": hari_ini,
                "tanggal": tanggal,
                "bulan": bulan,
            }, unique_old_value_rects, "Hari ini, tanggal, bulan"

    return None, None, None, None
