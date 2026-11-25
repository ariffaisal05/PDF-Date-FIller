import pymupdf


CALIBRI_FONT_PATH = "calibri.ttf"
CALIBRI_FONT = pymupdf.Font(fontfile=CALIBRI_FONT_PATH)
STANDARD_A4_WIDTH = 595.2

def add_date_text(
    input_path,
    output_path,
    page_number,
    label_rects,
    old_value_rects,
    date_parts,
    ocr_used=False,
):
    """Replace existing date values, then write the new values by each label."""
    with pymupdf.open(input_path) as doc:
        page = doc[page_number]

        # Redact only the detected old value glyphs; leave labels, punctuation,
        # and surrounding text untouched.
        if old_value_rects:
            if ocr_used:
                # OCR words live in the page image, so text redaction alone
                # cannot erase them. OCR coordinates follow the displayed page
                # orientation; convert them before drawing on rotated pages.
                for old_rect in old_value_rects:
                    old_rect = pymupdf.Rect(old_rect) * page.derotation_matrix
                    cover = pymupdf.Rect(
                        old_rect.x0 - 1,
                        old_rect.y0 - 1,
                        old_rect.x1 + 1,
                        old_rect.y1 + 1,
                    )
                    page.draw_rect(
                        cover, color=None, fill=(1, 1, 1), overlay=True
                    )
            else:
                for old_rect in old_value_rects:
                    redaction = pymupdf.Rect(
                        old_rect.x0 - 0.5,
                        old_rect.y0 - 0.5,
                        old_rect.x1 + 0.5,
                        old_rect.y1 + 0.5,
                    )
                    page.add_redact_annot(
                        redaction, fill=(1, 1, 1), cross_out=False
                    )
                page.apply_redactions(images=0, graphics=0)

        # Redaction can rebuild the page resources, so register Calibri after
        # applying it and before inserting the replacement text.
        page.insert_font(fontname="CalibriDate", fontfile=str(CALIBRI_FONT_PATH))

        for label, value in date_parts.items():
            rect = label_rects.get(label)
            if rect is None or not value:
                continue

            # Keep dates visually at 11 pt. Some scans use pixels as PDF
            # points, so scale to the width of a standard A4 page.
            font_size = 11 * page.rect.width / STANDARD_A4_WIDTH if ocr_used else 11
            if ocr_used:
                # Clear the expected value area even when OCR cannot read the
                # handwriting. Bound the weekday field by the next printed
                # label so this patch cannot cover "tanggal".
                clear_x0 = rect.x1 + 2
                if label == "hari_ini" and "tanggal" in label_rects:
                    clear_x1 = label_rects["tanggal"].x0 - 2
                else:
                    clear_width = CALIBRI_FONT.text_length(
                        str(value), fontsize=font_size
                    ) + 8
                    clear_x1 = rect.x1 + clear_width
                    next_label = {
                        "tanggal": "bulan",
                    }.get(label)
                    if next_label in label_rects:
                        clear_x1 = min(
                            clear_x1, label_rects[next_label].x0 - 2
                        )
                if clear_x1 > clear_x0:
                    clear_rect = pymupdf.Rect(
                        clear_x0,
                        rect.y0 - rect.height * 0.35,
                        clear_x1,
                        rect.y1 + rect.height * 0.35,
                    ) * page.derotation_matrix
                    page.draw_rect(
                        clear_rect,
                        color=None,
                        fill=(1, 1, 1),
                        overlay=True,
                    )

                x_position = rect.x1 + max(6, rect.height * 0.3)
                # The font is capped at 11 pt, so align its baseline from the
                # actual inserted size instead of the taller OCR word box.
                y_position = rect.y1 - font_size * 0.24
                point = pymupdf.Point(x_position, y_position) * page.derotation_matrix
                rotation = (360 - page.rotation) % 360
            else:
                x_position = rect.x1 + 3
                y_position = rect.y1 - rect.height * 0.233
                point = (x_position, y_position)
                rotation = 0
            page.insert_text(
                point,
                str(value),
                fontsize=font_size,
                fontname="CalibriDate",
                color=(0, 0, 0),
                overlay=True,
                rotate=rotation,
            )

        doc.save(output_path, garbage=4, clean=True, deflate=True)
