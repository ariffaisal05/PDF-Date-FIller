import os
import tempfile

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
        detected_text,
        ocr_used,
    ) = find_date_in_pdf(input_path)

    if page_number is None:

        return {
            "success": False,
            "ocr_used": ocr_used,
            "detection_method": "OCR" if ocr_used else "Text",
            "message": (
                "Could not find Indonesian date labels ('Hari ini' and "
                "'tanggal', with optional 'bulan') or the English label 'Today'."
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
        month_year = (
            f"{indonesian_months[selected_date.month - 1]} "
            f"{selected_date.year}"
        )
        day_and_month = str(selected_date.day)
        if "bulan" not in label_rects:
            day_and_month = f"{day_and_month} {month_year}"

        date_parts = {
            "hari_ini": indonesian_weekdays[selected_date.weekday()],
            "tanggal": day_and_month,
            "bulan": month_year,
        }
        inserted_date = f"{date_parts['hari_ini']}, {date_parts['tanggal']}"
        if "bulan" in label_rects:
            inserted_date += f" {date_parts['bulan']}"

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
            ocr_used=ocr_used,
        )

    # ------------------------------------------------------------
    # Return result
    # ------------------------------------------------------------

    return {
        "success": True,
        "message": (
            "PDF processed successfully (OCR used for scanned page)."
            if ocr_used else "PDF processed successfully."
        ),
        "page": page_number + 1,
        "detected_text": detected_text,
        "ocr_used": ocr_used,
        "detection_method": "OCR" if ocr_used else "Text",
        "inserted_date": inserted_date,
        "removed_widgets": stats["widgets"],
        "removed_annotations": stats["annotations"],
        "removed_links": stats["links"],
    }
