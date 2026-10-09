import pymupdf


CALIBRI_FONT_PATH = "calibri.ttf"

def add_date_text(
    input_path,
    output_path,
    page_number,
    label_rects,
    old_value_rects,
    date_parts,
    scanned_page=False,
):
    """Replace existing date values, then write the new values by each label."""
    with pymupdf.open(input_path) as doc:
        page = doc[page_number]

        # Redact only the detected old value glyphs; leave labels, punctuation,
        # and surrounding text untouched.
        if old_value_rects:
            if scanned_page:
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
            page.insert_text(
                (rect.x1 + 3, rect.y1 - rect.height * 0.233),
                str(value),
                fontsize=11,
                fontname="CalibriDate",
                color=(0, 0, 0),
                overlay=True,
            )

        doc.save(output_path, garbage=4, clean=True, deflate=True)
