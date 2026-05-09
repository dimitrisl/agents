# 🩸 Phyrexian Forge: Project Suggestions

Following a comprehensive review of the **Phyrexian Forge** codebase, here are prioritized suggestions for architectural improvements, new features, and quality enhancements.

---

## 🛠️ 1. Architectural Improvements

### PDF Field Abstraction
The mapping of character data to PDF form fields in `backend/pdf_exporter.py` is currently hardcoded.
- **Suggestion:** Extract this mapping into a configuration file (e.g., `data/pdf_mappings.json`).
- **Benefit:** Simplifies support for multiple character sheet templates (e.g., 2014 vs. 2024 editions) without modifying Python logic.

### Caching Strategy
Frequent Streamlit reruns can lead to unnecessary API calls and latency.
- **Suggestion:** Implement `@st.cache_data` in `backend/ai_client.py` for methods like `query_rules` or `get_flash_model`.
- **Benefit:** Reduces API costs and improves UI responsiveness.

### Centralized Prompt Management
Prompts are currently embedded within `ai_client.py`.
- **Suggestion:** Move prompts into a dedicated `backend/prompts.py` file or external templates.
- **Benefit:** Facilitates "prompt engineering" and versioning without cluttering core logic.

---

## 🏹 2. Enhanced Feature Set

### Integrated Portrait Generation
- **Suggestion:** Integrate an image generation API (DALL-E 3 or Imagen) to generate "Phyrexian-styled" portraits directly from the character concept.
- **Benefit:** Provides a more "premium" and visually complete character creation experience.

### Interactive Initiative Tracker
- **Suggestion:** Expand the DM workspace with a real-time initiative tracker that manages HP, conditions (e.g., "Prone"), and turn order.
- **Benefit:** Increases the utility of the "Dungeon Master View" for active session management.

### Rule Comparison Tool
- **Suggestion:** Add a tool to explicitly compare changes between the 2014 and 2024 rulesets using the AI.
- **Benefit:** Helps players and DMs transition to the 5.5e Revision smoothly.

---

## 🧪 3. Quality Assurance & DX

### Automated Testing Suite
- **Suggestion:** Add a `tests/` directory using `pytest`.
- **Benefit:** Ensures core mechanics (calculations, AI parsing) remain stable as the project grows.

### Robust Schema Validation (Pydantic)
- **Suggestion:** Use **Pydantic** models to define character and encounter schemas.
- **Benefit:** Provides strict validation for AI-generated JSON and better IDE support.

---

## 🎨 4. UI/UX Polishing

### Themed Markdown Rendering
- **Suggestion:** Use custom CSS to style the AI-generated markdown (Oracle answers, Playstyle guides) to match the dark, bio-mechanical aesthetic.
- **Benefit:** Creates a more immersive "Phyrexian" user experience.

### Character Export Preview
- **Suggestion:** Display a data summary or "preview card" in Streamlit before the user downloads the PDF.
- **Benefit:** Allows users to verify AI Forge results before committing to a download.
