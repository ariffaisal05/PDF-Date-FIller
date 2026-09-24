import pymupdf


CALIBRI_FONT_PATH = "calibri.ttf"


def add_date_text(input_path, output_path, page_number, label_rects, date_parts):
    """Write date parts immediately after their matching printed labels."""
    with pymupdf.open(input_path) as doc:
        page = doc[page_number]
        page.insert_font(fontname="CalibriDate", fontfile=CALIBRI_FONT_PATH)
        for label, value in date_parts.items():
            rect = label_rects.get(label)
            if rect is None or not value:
                continue

            # The supplied form uses Calibri 11.05 pt. Its text baseline is
            # about 23.3% of the word-box height above the lower edge.
            page.insert_text(
                (rect.x1 + 3, rect.y1 - rect.height * 0.233),
                str(value),
                fontsize=11,
                fontname="CalibriDate",
                color=(0, 0, 0),
                overlay=True,
            )

        doc.save(output_path, garbage=4, clean=True, deflate=True)
