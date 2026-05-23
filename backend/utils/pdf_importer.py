import logging
import pypdf
import pdfplumber

logger = logging.getLogger("DnDAssistant.PDFImporter")


def extract_text_and_fields_from_pdf(uploaded_pdf) -> str:
    """
    Extracts form fields and visual layout text/tables from a PDF file.
    Returns a unified string representation.
    """
    extracted_text = ""

    # 1. Form Field Extraction (AcroForm + Manual Annotation Scan)
    field_data_found = {}
    try:
        uploaded_pdf.seek(0)
        pdf_reader = pypdf.PdfReader(uploaded_pdf)
        fields = pdf_reader.get_fields()
        if fields:
            for name, data in fields.items():
                val = data.get("/V")
                if val:
                    field_data_found[name] = val

        # Manual scan for widget annotations
        for page in pdf_reader.pages:
            annots = page.get("/Annots")
            if annots:
                for annot in annots:
                    try:
                        obj = annot.get_object()
                        if obj.get("/Subtype") == "/Widget":
                            name = obj.get("/T")
                            val = obj.get("/V")
                            if name and val and name not in field_data_found:
                                field_data_found[name] = val
                    except Exception as e:
                        logger.warning(f"Field extraction error: {e}")
                        continue
    except Exception as e:
        logger.warning(f"Field extraction error: {e}")

    if field_data_found:
        extracted_text += "--- FORM FIELDS ---\n"
        for field_name, val in field_data_found.items():
            extracted_text += f"{field_name}: {val}\n"
        extracted_text += "--- END FORM FIELDS ---\n\n"

    # 2. Enhanced Text Extraction with pdfplumber
    try:
        uploaded_pdf.seek(0)
        with pdfplumber.open(uploaded_pdf) as pdf:
            extracted_text += "--- VISUAL LAYOUT TEXT ---\n"
            for page in pdf.pages:
                page_text = page.extract_text(layout=True)
                if page_text:
                    extracted_text += page_text + "\n"

                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        clean_row = [
                            str(c).replace("\n", " ") if c is not None else ""
                            for c in row
                        ]
                        if any(c.strip() for c in clean_row):
                            extracted_text += " | ".join(clean_row) + "\n"
            extracted_text += "--- END VISUAL LAYOUT TEXT ---\n"
    except Exception as e:
        logger.error(f"pdfplumber failed: {e}")
        try:
            uploaded_pdf.seek(0)
            pdf_reader = pypdf.PdfReader(uploaded_pdf)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception as read_err:
            logger.error(f"Fallback text extraction failed: {read_err}")

    return extracted_text
