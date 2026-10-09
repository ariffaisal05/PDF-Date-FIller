import pymupdf


CALIBRI_FONT_PATH = "calibri.ttf"

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
                # cannot erase them. Paint over just the detected date glyphs.
                for old_rect in old_value_rects:
                    cover = pymupdf.Rect(
                        old_rect.x0 - 1,
                        old_rect.y0 - 1,
                        old_rect.x1 + 1,
                        old_rect.y1 + 1,
                    ) & page.rect
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

            # The supplied form uses Calibri 11.05 pt. Its text baseline is
            # about 23.3% of the word-box height above the lower edge.
            # OCR page coordinates follow the scan's pixel-sized page. Scale
            # only OCR insertions to the detected printed label height; keep
            # the established 11 pt size for selectable-text PDFs.
            font_size = max(11, rect.height * 0.88) if ocr_used else 11
            if ocr_used:
                x_position = rect.x1 + max(6, rect.height * 0.3)
                y_position = rect.y1 - rect.height * 0.36
            else:
                x_position = rect.x1 + 3
                y_position = rect.y1 - rect.height * 0.233
            page.insert_text(
                (x_position, y_position),
                str(value),
                fontsize=font_size,
                fontname="CalibriDate",
                color=(0, 0, 0),
                overlay=True,
            )

        doc.save(output_path, garbage=4, clean=True, deflate=True)
