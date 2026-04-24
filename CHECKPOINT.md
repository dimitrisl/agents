# Project Checkpoint: D&D AI Assistant

## 🎯 Current Status
The core foundation and primary AI features are **fully implemented**! The application now boasts a functional pure-Python UI, clean backend logic separation, persistent data storage, comprehensive logging, and specialized AI Agents for both Players and Dungeon Masters.

## 🛠️ Infrastructure & Architecture
- **Tech Stack:** Python 3.13+, Poetry, Streamlit, Google GenAI SDK.
- **Architecture:** UI logic lives entirely in `main.py`, while AI routing (`ai_client.py`) and data persistence (`storage.py`) live in the `backend/` directory.
- **Code Quality:** Configured `pre-commit` pipeline with `ruff` for linting/formatting. VSCode workspace is strictly bound to the Poetry virtualenv.
- **Logging:** A robust logging system writes debug traces and user actions to both the console and a local `app_debug.log` file.

## ✨ Built Components
### 1. Player Features
- **Editable Dashboard:** Track and freely modify Core Stats (Name, Class, Level, Ability Scores, HP, AC), Skills, Saves, Inventory, Spells, and Features using interactive data grids.
- **AI Build Agent:** Generates custom multiclass/build advice dynamically based on the character's *actual* live stats.
- **AI Complete Character Forge:** A structured wizard that takes your desired Race, Class, Background, Target Level, and any text flavor concept to automatically roll a fully equipped character of *any* level. It forces the LLM to return a highly structured JSON response, instantly equipping skills, weapons, traits, and spell lists.
- **Character Storage:** Save your comprehensive characters to local JSON files (`data/characters/`) and load them back via a dropdown menu.

- **PDF Export Engine:** An integrated `pypdf` module maps your dynamic character state directly onto the official `5E_CharacterSheet_Fillable.pdf`, compiling stats, skills, inventory, and spells into a neatly formatted, downloadable PDF sheet.

### 2. Dungeon Master Features
- **Party Integration:** Automatically tracks the active Player Character and calculates derived stats (e.g., Passive Perception) for the DM.
- **Campaign Logger:** A dedicated notepad for session logs that can be saved and loaded from local `.json` files (`data/campaigns/`).
- **AI Generator Agents:**
  - *Random Encounters:* Dynamically generates setting-appropriate encounters based on custom Party Size, Level, and Location inputs.
  - *NPC Forge:* Generates punchy, formatted NPCs complete with personalities, appearances, and hidden secrets.

## 🚀 Quick Commands
- **Start the UI:** `poetry run streamlit run main.py`
- **Test AI Connection:** `poetry run python tests/test_gemini_connection.py`
- **Format Code:** `poetry run pre-commit run --all-files`

## 🔮 Next Steps
- **Automated Progression:** Implement logic to automatically increment character levels and recalculate stats or recommend new class features.
- **Generic LLM Support (Optional):** Refactor `backend/ai_client.py` using a tool like `litellm` if we ever want to easily swap between Gemini, ChatGPT, or Claude.
