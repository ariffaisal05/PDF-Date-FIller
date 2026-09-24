import base64
import hashlib
import json
import os
import tempfile
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from pdf_processor.processor import process_pdf


st.set_page_config(page_title="PDF Date Filler", page_icon="📄", layout="centered")
st.title("📄 PDF Date Filler")
st.write(
    "Upload PDFs, choose a date, and the system will fill the detected date "
    "labels and remove interactive PDF content. Review each result before downloading."
)

uploaded_files = st.file_uploader(
    "Upload PDF files", type=["pdf"], accept_multiple_files=True
)
selected_date = st.date_input("Date to insert", value=date.today())


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


if uploaded_files:
    signature = uploads_signature(uploaded_files, selected_date)
    st.caption(f"{len(uploaded_files)} PDF file(s) ready.")

    if st.button("Process PDFs", type="primary"):
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
                        "result": {"success": False, "message": str(error)},
                        "data": None,
                    })

                progress.progress(
                    (index + 1) / len(uploaded_files),
                    text=f"Processed {index + 1} of {len(uploaded_files)} PDFs",
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
            with st.expander(title, expanded=not result["success"]):
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
                encoded = base64.b64encode(item["data"]).decode("ascii")
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{encoded}" '
                    'width="100%" height="600" style="border:1px solid #ddd; '
                    'border-radius:8px"></iframe>',
                    unsafe_allow_html=True,
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
