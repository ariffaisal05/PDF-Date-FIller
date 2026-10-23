# Vercel prototype

This branch adds a minimal upload, fill, and download flow using a static page
and a Vercel Python Function. It reuses the existing PDF processor.

## Deploy

Create a separate Vercel project from this repository. Set its production branch
to `Vercel_version` and leave the project root at the repository root. Keep the
existing Streamlit deployment on its current project and branch.

## Current limits

- Uploads are capped at 4 MB to stay below Vercel Function's 4.5 MB request
  body limit.
- `packages.txt` installs Tesseract on Streamlit Community Cloud, but Vercel
  does not use that file. Text-based PDFs can use the existing detector. Scanned
  PDFs still need a Tesseract runtime packaged for Vercel or a separate OCR
  backend before this prototype can support them.
- Vercel's Python runtime is currently in beta.
