import pymupdf

from pypdf import PdfReader, PdfWriter


def remove_widgets(doc):
    """
    Remove PDF form widgets while preserving signature appearances.

    Signature widget appearances are flattened into the page first so that
    signatures and QR codes remain visible but are no longer interactive.
    Other widgets are removed as before.

    Removes:
        - Text fields
        - Checkboxes
        - Radio buttons
        - Dropdowns
        - Buttons
    """

    removed = 0

    for page in doc:

        widgets = page.widgets()

        if widgets:

            widgets = list(widgets)

            for widget in widgets:

                rect = pymupdf.Rect(widget.rect)
                has_visible_area = rect.width > 0 and rect.height > 0

                if widget.field_type_string == "Signature" and has_visible_area:

                    # Keep the visible signature/QR artwork, but replace the
                    # clickable signature widget with a high-resolution image.
                    appearance = page.get_pixmap(
                        matrix=pymupdf.Matrix(4, 4),
                        clip=widget.rect,
                        annots=True,
                        alpha=False,
                    )

                    page.insert_image(
                        rect,
                        stream=appearance.tobytes("png"),
                        overlay=True,
                    )

                page.delete_widget(widget)

                removed += 1

    return removed


def remove_annotations(doc):
    """
    Remove PDF annotations.

    Examples:

        - Comments
        - Highlights
        - Sticky notes
        - Text annotations
        - Link annotations
        - Other annotations
    """

    removed = 0

    for page in doc:

        annotations = page.annots()

        if annotations:

            annotations = list(annotations)

            for annotation in annotations:

                # Signatures may be stored as Stamp or Ink annotations.
                # Flatten their own visible appearance before deleting the
                # clickable annotation, preserving transparency for Ink.
                if annotation.type[1] in {"Stamp", "Ink"}:
                    rect = pymupdf.Rect(annotation.rect)
                    if rect.width > 0 and rect.height > 0:
                        if annotation.type[1] == "Ink":
                            appearance = annotation.get_pixmap(
                                matrix=pymupdf.Matrix(4, 4),
                                alpha=True,
                            )
                        else:
                            appearance = page.get_pixmap(
                                matrix=pymupdf.Matrix(4, 4),
                                clip=rect,
                                annots=True,
                                alpha=False,
                            )
                        page.insert_image(
                            rect,
                            stream=appearance.tobytes("png"),
                            overlay=True,
                        )

                page.delete_annot(annotation)

                removed += 1

    return removed


def remove_links(doc):
    """
    Remove PDF links.
    """

    removed = 0

    for page in doc:

        links = page.get_links()

        for link in links:

            try:

                page.delete_link(link)

                removed += 1

            except Exception:

                pass

    return removed


def clean_with_pymupdf(
    input_path,
    output_path
):
    """
    First cleaning stage.

    Removes:

        - Form widgets
        - Annotations
        - Links
    """

    doc = pymupdf.open(input_path)

    widget_count = remove_widgets(doc)

    annotation_count = remove_annotations(doc)

    link_count = remove_links(doc)

    doc.save(
        output_path,
        garbage=4,
        clean=True,
        deflate=True
    )

    doc.close()

    return {
        "widgets": widget_count,
        "annotations": annotation_count,
        "links": link_count,
    }


def remove_pdf_actions(
    input_path,
    output_path
):
    """
    Remove document-level and page-level
    interactive actions.

    Attempts to remove:

        - AcroForm
        - JavaScript
        - OpenAction
        - Page Additional Actions
        - Page annotations
    """

    reader = PdfReader(input_path)

    writer = PdfWriter()

    # --------------------------------------------------------
    # Copy pages
    # --------------------------------------------------------

    for page in reader.pages:

        writer.add_page(page)

    # --------------------------------------------------------
    # Remove AcroForm
    # --------------------------------------------------------

    try:

        root = writer._root_object

        if "/AcroForm" in root:

            del root["/AcroForm"]

    except Exception:

        pass

    # --------------------------------------------------------
    # Remove JavaScript
    # --------------------------------------------------------

    try:

        root = writer._root_object

        if "/Names" in root:

            names = root["/Names"].get_object()

            if "/JavaScript" in names:

                del names["/JavaScript"]

            if len(names) == 0:

                del root["/Names"]

    except Exception:

        pass

    # --------------------------------------------------------
    # Remove OpenAction
    # --------------------------------------------------------

    try:

        root = writer._root_object

        if "/OpenAction" in root:

            del root["/OpenAction"]

    except Exception:

        pass

    # --------------------------------------------------------
    # Remove page-level actions
    # --------------------------------------------------------

    for page in writer.pages:

        try:

            page_obj = page.get_object()

            if "/AA" in page_obj:

                del page_obj["/AA"]

            if "/Annots" in page_obj:

                del page_obj["/Annots"]

        except Exception:

            pass

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    with open(
        output_path,
        "wb"
    ) as file:

        writer.write(file)


def clean_pdf(
    input_path,
    output_path
):
    """
    Complete PDF cleaning pipeline.
    """

    intermediate_pdf = (
        output_path.replace(
            ".pdf",
            "_intermediate.pdf"
        )
    )

    stats = clean_with_pymupdf(
        input_path,
        intermediate_pdf
    )

    remove_pdf_actions(
        intermediate_pdf,
        output_path
    )

    return stats
