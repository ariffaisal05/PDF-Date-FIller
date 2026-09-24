import os
import tempfile

from .detector import find_date_in_pdf
from .cleaner import clean_pdf
from .writer import add_date_text


def process_pdf(
    input_path,
    output_path,
    selected_date
):

    # ------------------------------------------------------------
    # Convert selected date to Indonesian text
    # ------------------------------------------------------------

    indonesian_months = [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember"
    ]

    date_parts = {
        "tanggal": str(selected_date.day),
        "bulan": indonesian_months[selected_date.month - 1],
        "tahun": str(selected_date.year),
    }

    # ------------------------------------------------------------
    # Detect date area
    # ------------------------------------------------------------

    (
        page_number,
        label_rects,
        detected_text
    ) = find_date_in_pdf(input_path)

    if page_number is None:

        return {
            "success": False,
            "message": (
                "Could not find 'tanggal' and 'bulan' "
                "on the same line in the PDF."
            )
        }

    # ------------------------------------------------------------
    # Create temporary directory
    # ------------------------------------------------------------

    with tempfile.TemporaryDirectory() as temp_dir:

        cleaned_pdf = os.path.join(
            temp_dir,
            "cleaned.pdf"
        )

        # --------------------------------------------------------
        # Remove existing interactive content
        # --------------------------------------------------------

        stats = clean_pdf(
            input_path,
            cleaned_pdf
        )

        # --------------------------------------------------------
        # Write selected date onto PDF
        # --------------------------------------------------------

        add_date_text(
            cleaned_pdf,
            output_path,
            page_number,
            label_rects,
            {
                label: date_parts[label]
                for label in label_rects
            }
        )

    # ------------------------------------------------------------
    # Return result
    # ------------------------------------------------------------

    return {
        "success": True,
        "message": (
            "PDF processed successfully."
        ),
        "page": page_number + 1,
        "detected_text": detected_text,
        "inserted_date": " ".join(
            date_parts[label] for label in label_rects
        ),
        "removed_widgets": stats["widgets"],
        "removed_annotations": stats["annotations"],
        "removed_links": stats["links"],
    }
