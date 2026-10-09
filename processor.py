import os
import tempfile

import pymupdf

from detector import find_date_in_pdf
from cleaner import clean_pdf
from writer import add_date_text


def process_pdf(
    input_path,
    output_path,
    selected_date
):

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
    indonesian_weekdays = [
        "Senin",
        "Selasa",
        "Rabu",
        "Kamis",
        "Jumat",
        "Sabtu",
        "Minggu",
    ]

    # ------------------------------------------------------------
    # Detect date area
    # ------------------------------------------------------------

    (
        page_number,
        label_rects,
        old_value_rects,
        detected_text
    ) = find_date_in_pdf(input_path)

    scanned_page = False
    if page_number is not None:
        with pymupdf.open(input_path) as source_doc:
            scanned_page = not bool(source_doc[page_number].get_text().strip())

    if page_number is None:

        return {
            "success": False,
            "message": (
                "Could not find either the Indonesian date labels "
                "('Hari ini', 'tanggal', 'bulan') or the English label 'Today'."
            )
        }

    if "today" in label_rects:
        english_months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        date_parts = {
            "today": (
                f"{selected_date.day} "
                f"{english_months[selected_date.month - 1]} "
                f"{selected_date.year}"
            )
        }
        inserted_date = date_parts["today"]
    else:
        date_parts = {
            "hari_ini": indonesian_weekdays[selected_date.weekday()],
            "tanggal": str(selected_date.day),
            "bulan": (
                f"{indonesian_months[selected_date.month - 1]} "
                f"{selected_date.year}"
            ),
        }
        inserted_date = (
            f"{date_parts['hari_ini']}, {date_parts['tanggal']} "
            f"{date_parts['bulan']}"
        )

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
            old_value_rects,
            {
                label: date_parts[label]
                for label in label_rects
            },
            scanned_page=scanned_page,
        )

    # ------------------------------------------------------------
    # Return result
    # ------------------------------------------------------------

    return {
        "success": True,
        "message": (
            "PDF processed successfully (OCR used for scanned page)."
            if scanned_page else "PDF processed successfully."
        ),
        "page": page_number + 1,
        "detected_text": detected_text,
        "inserted_date": inserted_date,
        "removed_widgets": stats["widgets"],
        "removed_annotations": stats["annotations"],
        "removed_links": stats["links"],
    }
