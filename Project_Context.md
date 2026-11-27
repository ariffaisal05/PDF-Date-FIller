I’m working on a PDF utility web app built with Streamlit. This is the original version, before the separate Vercel experiment. Keep improvements in this Streamlit project and don’t mix in Vercel-specific code.

### What the app does

- Date filler: Users upload PDFs, and the app detects date labels and writes updated dates into the document.
  - Indonesian documents use labels such as “Hari ini” and “tanggal.” “Hari ini” gets the weekday, and the date label gets the day, month, and year. “Bulan” may be absent; the date is still written after “tanggal.”
  - English documents use “Today” and receive an English date such as “8 October 2026.”
  - It supports both text-based PDFs and scanned/image PDFs using OCR.
  - When revising a date that is already filled in, the old date should be removed or covered before writing the new one.
  - There has been careful tuning of OCR output position, vertical alignment, and font size. Preserve the text-label detector’s existing size and position when adjusting OCR output.
- Interactive PDF content: The date-filler path removes clickability from interactive elements while trying to preserve visible signatures and QR codes. Avoid flattening or editing that makes signatures disappear or creates unexpected signing indicators.
- Merge PDFs: Combines uploaded PDFs without routing them through the date-filler or interactive-content cleanup path.
- Split PDFs: Splits a PDF into user-selected files, previews each split file across its pages, and offers a “download all” action.
- Analytics: An admin-only dashboard tracks usage and job types. The public landing flow remains the regular PDF tool; admin access is through a login button. Analytics are stored privately rather than exposed in GitHub.

### Existing user preferences

- Prioritize correctness of PDF processing before redesigning the UI.
- Make focused changes and preserve behaviors that are already working.
- Keep analytics secrets out of source control.
- Ask before making broad architectural changes, but make reasonable implementation choices for focused fixes.

### How to start

First inspect the current branch and files to confirm you’re in the Streamlit/original project, not the Vercel version. Then summarize the architecture and current state before changing code.