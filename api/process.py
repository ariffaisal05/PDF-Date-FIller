import json
import os
import re
import sys
import tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from processor import process_pdf

MAX_UPLOAD_BYTES = 4 * 1024 * 1024


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        params = parse_qs(urlparse(self.path).query)
        try:
            selected_date = date.fromisoformat(params.get("date", [""])[0])
        except ValueError:
            self._json(400, {"error": "Choose a valid date."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid upload size."})
            return
        if not 0 < content_length <= MAX_UPLOAD_BYTES:
            self._json(413, {"error": "This prototype accepts PDFs up to 4 MB."})
            return

        pdf_data = self.rfile.read(content_length)
        if not pdf_data.startswith(b"%PDF-"):
            self._json(400, {"error": "The uploaded file does not look like a PDF."})
            return

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, "input.pdf")
                output_path = os.path.join(temp_dir, "filled.pdf")
                with open(input_path, "wb") as uploaded_pdf:
                    uploaded_pdf.write(pdf_data)

                result = process_pdf(input_path, output_path, selected_date)
                if not result["success"]:
                    self._json(422, {"error": result["message"]})
                    return

                with open(output_path, "rb") as filled_pdf:
                    output_data = filled_pdf.read()

            if len(output_data) > 4_500_000:
                self._json(
                    413,
                    {"error": "The processed PDF exceeds Vercel's 4.5 MB response limit."},
                )
                return

            name = params.get("filename", ["document.pdf"])[0]
            name = os.path.basename(name)
            stem = os.path.splitext(name)[0] or "document"
            stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "document"
            filename = quote(f"{stem}_dated.pdf")
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header(
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{filename}",
            )
            self.send_header("Content-Length", str(len(output_data)))
            self.end_headers()
            self.wfile.write(output_data)
        except Exception as error:
            self._json(500, {"error": f"Could not process this PDF: {error}"})

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
