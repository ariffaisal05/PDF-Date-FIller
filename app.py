import base64
import hashlib
import json
import os
import tempfile
import time
import uuid
from datetime import date

import pymupdf
import streamlit as st
import streamlit.components.v1 as components

from processor import process_pdf
from pdf_operations import merge_pdfs, parse_page_ranges, split_pdf
import analytics

st.set_page_config(page_title="PDF Date Filler", page_icon="📄", layout="centered")
if "analytics_session_id" not in st.session_state:
    st.session_state.analytics_session_id = str(uuid.uuid4())
    if analytics.ready():
        analytics.log_session(st.session_state.analytics_session_id)

if "analytics_view" not in st.session_state:
    st.session_state.analytics_view = False
if "selected_tool" not in st.session_state:
    st.session_state.selected_tool = "Date filler"

header, login = st.columns([5, 1])
with header:
    page_title = "Usage analytics" if st.session_state.analytics_view else {
        "Date filler": "📄 PDF Date Filler",
        "Merge PDFs": "Merge PDFs",
        "Split PDF": "Split PDF",
    }[st.session_state.selected_tool]
    st.title(page_title)
with login:
    if st.session_state.analytics_view:
        if st.button("PDF filler"):
            st.session_state.analytics_view = False
            st.session_state.pop("analytics_authenticated", None)
            st.rerun()
    elif st.button("Admin"):
        st.session_state.analytics_view = True
        st.session_state.pop("analytics_authenticated", None)
        st.rerun()

if st.session_state.analytics_view:
    analytics.show_dashboard()
    st.stop()

st.radio(
    "PDF tool",
    ["Date filler", "Merge PDFs", "Split PDF"],
    horizontal=True,
    key="selected_tool",
    label_visibility="collapsed",
)


def uploads_signature(files, chosen_date):
    digest = hashlib.sha256(chosen_date.isoformat().encode())
    for uploaded in files:
        digest.update(uploaded.name.encode("utf-8", errors="replace"))
        digest.update(uploaded.getvalue())
    return digest.hexdigest()


def make_download_all_html(files):
    # Keep the payload in this browser-side component so one click can initiate
    # a separate PDF download for every successful file (no archive involved).
    payload = [
        {
            "name": item["filename"],
            "data": base64.b64encode(item["data"]).decode("ascii"),
        }
        for item in files
    ]
    payload_json = json.dumps(payload).replace("</", "<\\/")
    return f"""
    <button id="download-all" style="background:#ff4b4b;color:white;border:0;
        border-radius:8px;padding:0.65rem 1rem;font-size:16px;cursor:pointer">
        ⬇️ Download all PDFs
    </button>
    <script>
      const files = {payload_json};
      document.getElementById("download-all").addEventListener("click", () => {{
        for (const file of files) {{
          const raw = atob(file.data);
          const bytes = new Uint8Array(raw.length);
          for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
          const url = URL.createObjectURL(new Blob([bytes], {{type: "application/pdf"}}));
          const link = document.createElement("a");
          link.href = url;
          link.download = file.name;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
        }}
      }});
    </script>
    """


@st.cache_data(show_spinner=False)
def render_pdf_page(pdf_data, page_index):
    with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
        pixmap = doc[page_index].get_pixmap(
            matrix=pymupdf.Matrix(1.5, 1.5), alpha=False
        )
        return pixmap.tobytes("png")


def show_pdf_preview(pdf_data, key):
    """Render one selectable PDF page as an image for broad browser support."""
    with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
        page_count = len(doc)

    if page_count > 1:
        page_number = st.selectbox(
            "Preview page",
            options=range(1, page_count + 1),
            key=f"{key}_page",
        )
    else:
        page_number = 1
        st.caption("Preview · page 1 of 1")

    st.image(
        render_pdf_page(pdf_data, page_number - 1),
        caption=f"Page {page_number} of {page_count}",
        use_container_width=True,
    )


def show_pdf_all_pages(pdf_data):
    """Show every page vertically so the selected PDF can be scrolled through."""
    with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
        page_count = len(doc)
    st.caption(f"Preview · {page_count} page(s)")
    for page_index in range(page_count):
        st.image(
            render_pdf_page(pdf_data, page_index),
            caption=f"Page {page_index + 1} of {page_count}",
            use_container_width=True,
        )


if st.session_state.selected_tool == "Merge PDFs":
    st.write("Combine multiple PDFs in the order you choose.")
    st.caption(
        "Annotations, links, and form fields are copied where supported. "
        "A rewritten PDF may not keep cryptographic signatures valid."
    )
    merge_files = st.file_uploader(
        "Upload PDFs to merge", type=["pdf"], accept_multiple_files=True,
        key="merge_uploads",
    )
    if len(merge_files) < 2:
        st.info("Upload at least two PDF files to merge.")
    else:
        signature = hashlib.sha256()
        for item in merge_files:
            signature.update(item.name.encode("utf-8", errors="replace"))
            signature.update(item.getvalue())
        signature = signature.hexdigest()

        st.caption(f"{len(merge_files)} PDFs ready. Set their order below.")
        merge_order = []
        for position in range(len(merge_files)):
            selected_index = st.selectbox(
                f"PDF at position {position + 1}",
                options=range(len(merge_files)),
                index=position,
                format_func=lambda index: f"{index + 1}. {merge_files[index].name}",
                key=f"merge_order_{signature}_{position}",
            )
            merge_order.append(selected_index)
        result_signature = hashlib.sha256(
            f"{signature}:{','.join(map(str, merge_order))}".encode()
        ).hexdigest()

        if len(set(merge_order)) != len(merge_order):
            st.warning("Choose each PDF exactly once to set the merge order.")
        elif st.button("Merge PDFs", type="primary"):
            started_at = time.perf_counter()
            try:
                merged_data = merge_pdfs(
                    [merge_files[index].getvalue() for index in merge_order]
                )
                st.session_state.merge_result = {
                    "signature": result_signature,
                    "data": merged_data,
                }
                if analytics.ready():
                    analytics.log_operation(
                        st.session_state.analytics_session_id,
                        "merge",
                        len(merge_files),
                        time.perf_counter() - started_at,
                        True,
                    )
            except Exception as error:
                st.session_state.merge_result = {
                    "signature": result_signature,
                    "error": str(error),
                }
                if analytics.ready():
                    analytics.log_operation(
                        st.session_state.analytics_session_id,
                        "merge",
                        len(merge_files),
                        time.perf_counter() - started_at,
                        False,
                    )

        result = st.session_state.get("merge_result", {})
        if result.get("signature") == result_signature:
            if "error" in result:
                st.error(f"Could not merge these PDFs: {result['error']}")
            else:
                st.success("PDFs merged successfully.")
                st.download_button(
                    "Download merged PDF",
                    data=result["data"],
                    file_name="merged.pdf",
                    mime="application/pdf",
                    key=f"download_merged_{result_signature}",
                )
                show_pdf_preview(result["data"], key=f"merged_preview_{result_signature}")
    st.stop()


if st.session_state.selected_tool == "Split PDF":
    st.write("Split one PDF into separate page groups.")
    st.caption(
        "Annotations, links, and form fields are copied where supported. "
        "Links to pages outside a split group may not work, and a rewritten PDF "
        "may not keep cryptographic signatures valid."
    )
    split_file = st.file_uploader(
        "Upload a PDF to split", type=["pdf"], key="split_upload"
    )
    if split_file:
        split_data = split_file.getvalue()
        signature = hashlib.sha256(split_data).hexdigest()
        try:
            with pymupdf.open(stream=split_data, filetype="pdf") as document:
                page_count = len(document)
            if page_count == 0:
                st.error("This PDF has no pages.")
                st.stop()
        except Exception as error:
            st.error(f"Could not read this PDF: {error}")
            st.stop()

        st.caption(f"This PDF has {page_count} pages.")
        split_mode = st.radio(
            "Split method",
            ["Every page separately", "Custom page ranges"],
            horizontal=True,
            key=f"split_mode_{signature}",
        )
        ranges_text = ""
        if split_mode == "Every page separately":
            page_ranges = [(page, page) for page in range(1, page_count + 1)]
            st.caption(f"Creates {page_count} PDF files, one for each page.")
        else:
            ranges_text = st.text_area(
                "One output per line; use a page or inclusive range",
                placeholder="1-3\n4\n5-7",
                key=f"split_ranges_{signature}",
            )
            page_ranges = None
        result_signature = hashlib.sha256(
            f"{signature}:{split_mode}:{ranges_text}".encode()
        ).hexdigest()

        if st.button("Split PDF", type="primary"):
            started_at = time.perf_counter()
            try:
                if page_ranges is None:
                    page_ranges = parse_page_ranges(ranges_text, page_count)
                output_data = split_pdf(split_data, page_ranges)
                stem = os.path.splitext(os.path.basename(split_file.name))[0]
                outputs = []
                for (start, end), data in zip(page_ranges, output_data):
                    label = f"page_{start}" if start == end else f"pages_{start}-{end}"
                    outputs.append({
                        "filename": f"{stem}_{label}.pdf",
                        "data": data,
                    })
                st.session_state.split_result = {
                    "signature": result_signature,
                    "outputs": outputs,
                }
                if analytics.ready():
                    analytics.log_operation(
                        st.session_state.analytics_session_id,
                        "split",
                        1,
                        time.perf_counter() - started_at,
                        True,
                    )
            except Exception as error:
                st.session_state.split_result = {
                    "signature": result_signature,
                    "error": str(error),
                }
                if analytics.ready():
                    analytics.log_operation(
                        st.session_state.analytics_session_id,
                        "split",
                        1,
                        time.perf_counter() - started_at,
                        False,
                    )

        result = st.session_state.get("split_result", {})
        if result.get("signature") == result_signature:
            if "error" in result:
                st.error(f"Could not split this PDF: {result['error']}")
            else:
                st.success(f"Created {len(result['outputs'])} PDF file(s).")
                if result["outputs"]:
                    components.html(
                        make_download_all_html(result["outputs"]),
                        height=58,
                    )
                    st.caption(
                        "Downloads are separate PDF files. Your browser may ask you "
                        "to allow multiple downloads from this page."
                    )
                for index, item in enumerate(result["outputs"]):
                    st.download_button(
                        f"Download {item['filename']}",
                        data=item["data"],
                        file_name=item["filename"],
                        mime="application/pdf",
                        key=f"download_split_{result_signature}_{index}",
                    )
                if result["outputs"]:
                    preview_index = st.selectbox(
                        "Preview split file",
                        options=range(len(result["outputs"])),
                        format_func=lambda index: result["outputs"][index]["filename"],
                        key=f"split_preview_file_{result_signature}",
                    )
                    show_pdf_all_pages(result["outputs"][preview_index]["data"])
    else:
        st.info("Upload one PDF file to split.")
    st.stop()


st.write(
    "Unggah berkas PDF, pilih tanggal, dan sistem akan mengisi label tanggal yang terdeteksi serta menghapus konten PDF interaktif. "
    "Periksa setiap hasil sebelum mengunduhnya."
)
uploaded_files = st.file_uploader(
    "Upload PDF files", type=["pdf"], accept_multiple_files=True, key="date_fill_uploads"
)
selected_date = st.date_input("Date to insert", value=date.today())


if uploaded_files:
    signature = uploads_signature(uploaded_files, selected_date)
    st.caption(f"{len(uploaded_files)} PDF file(s) ready.")

    if st.button("Process PDFs", type="primary"):
        started_at = time.perf_counter()
        processed_files = []
        progress = st.progress(0, text="Starting PDF processing…")

        with tempfile.TemporaryDirectory() as temp_dir:
            for index, uploaded_file in enumerate(uploaded_files):
                input_path = os.path.join(temp_dir, f"input_{index}.pdf")
                output_path = os.path.join(temp_dir, f"output_{index}.pdf")
                stem = os.path.splitext(os.path.basename(uploaded_file.name))[0]
                output_filename = f"{stem}.pdf"

                try:
                    with open(input_path, "wb") as file:
                        file.write(uploaded_file.getvalue())

                    result = process_pdf(input_path, output_path, selected_date)
                    data = None
                    if result["success"]:
                        with open(output_path, "rb") as file:
                            data = file.read()

                    processed_files.append({
                        "source": uploaded_file.name,
                        "filename": output_filename,
                        "result": result,
                        "data": data,
                    })
                except Exception as error:
                    processed_files.append({
                        "source": uploaded_file.name,
                        "filename": output_filename,
                        "result": {
                            "success": False,
                            "message": str(error),
                            "detection_method": "unknown",
                        },
                        "data": None,
                    })

                progress.progress(
                    (index + 1) / len(uploaded_files),
                    text=f"Processed {index + 1} of {len(uploaded_files)} PDFs",
                )
        progress.empty()
        if analytics.ready():
            analytics.log_job(
                st.session_state.analytics_session_id,
                processed_files,
                time.perf_counter() - started_at,
            )
        completed_count = sum(
            item["result"]["success"] for item in processed_files
        )
        st.success(
            f"Processing complete. {completed_count} of "
            f"{len(processed_files)} PDF(s) processed successfully."
        )

        st.session_state.pdf_results = {
            "signature": signature,
            "files": processed_files,
        }

    saved = st.session_state.get("pdf_results")
    if saved and saved["signature"] == signature:
        successful = [item for item in saved["files"] if item["result"]["success"]]
        st.divider()
        st.subheader("Processing results")
        st.caption(f"{len(successful)} of {len(saved['files'])} file(s) processed successfully.")

        for index, item in enumerate(saved["files"]):
            result = item["result"]
            title = f"{item['source']} — {'Ready' if result['success'] else 'Needs attention'}"
            # Keep result panels open so the page selector stays visible after
            # its interaction triggers Streamlit's normal script rerun.
            with st.expander(title, expanded=True):
                if not result["success"]:
                    st.error(result["message"])
                    continue

                st.success("Processed successfully")
                left, right = st.columns(2)
                left.write(f"**Page:** {result['page']}")
                left.write(f"**Labels found:** {result['detected_text']}")
                right.write(f"**Date inserted:** {result['inserted_date']}")
                right.write(f"**Widgets removed:** {result['removed_widgets']}")
                st.write(
                    f"**Annotations removed:** {result['removed_annotations']} · "
                    f"**Links removed:** {result['removed_links']}"
                )
                st.download_button(
                    f"Download {item['filename']}",
                    data=item["data"],
                    file_name=item["filename"],
                    mime="application/pdf",
                    key=f"download_{signature}_{index}",
                )
                show_pdf_preview(
                    item["data"], key=f"pdf_preview_{signature}_{index}"
                )

        if successful:
            st.divider()
            st.subheader("Download all successful PDFs")
            components.html(make_download_all_html(successful), height=58)
            st.caption(
                "Downloads are separate PDF files. Your browser may ask you to "
                "allow multiple downloads from this page."
            )
else:
    st.session_state.pop("pdf_results", None)
