# 🛠️ Subsystem: Backend Utilities (`backend/utils/`)

## 📌 Overview
The `backend/utils/` package contains low-level helpers, mathematical formulas, dice mechanics, PDF generation engines, and filesystem security filters.

---

## 🔑 Key Modules

| Module | Responsibility |
| :--- | :--- |
| [`path_safety.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/path_safety.py) | **Security:** Provides `safe_path(filepath, scope="portraits"|"uploads")` to guarantee that file access stays within allowed directories, preventing path traversal attacks (`../`). |
| [`dnd_math.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/dnd_math.py) | Fundamental math formulas: ability score modifier calculation `floor((score - 10) / 2)` and proficiency bonus scaling by level. |
| [`dice.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/dice.py) | Dice rolling engine: parses complex expressions (e.g. `2d6 + 1d4 + 3`), handles Advantage/Disadvantage, and evaluates critical hits. |
| [`pdf_exporter.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/pdf_exporter.py) | Fills official D&D character sheet PDF form fields from `CharacterSchema` using ReportLab / PyPDF. |
| [`pdf_importer.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/pdf_importer.py) | Extracts AcroForm fields, annotations, visual layout text, and tables from uploaded PDF character sheets using `pdfplumber` and `pypdf`. |
| [`image_utils.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/image_utils.py) | Character portrait image processing, secure filename generation (`{char_id}.png`), and thumbnail generation. |
| [`homebrew_pdf.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/homebrew_pdf.py) | Compiles custom items and spell cards into printable PDF handouts. |
| [`api_client.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/utils/api_client.py) | HTTP client wrapper for third-party network communications. |
