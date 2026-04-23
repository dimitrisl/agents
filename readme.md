# 🎲 D&D AI Assistant

A comprehensive, AI-powered personal assistant designed for both **Dungeons & Dragons Players** and **Dungeon Masters (DMs)**. This application serves as a dynamic tool for character management, campaign tracking, and AI-assisted content generation using Google's Gemini LLM.

## ✨ Features

### 🗡️ For the Player
- **Character Dashboard:** Manage and view your character's stats and abilities.
- **AI Build Suggestions:** Receive optimized class and leveling suggestions based on your character's personality and current stats.
- *(Coming Soon)* **Automated Progression:** Easily increment character levels with the system automatically recalculating stats and features.
- *(Coming Soon)* **PDF Export:** Export your characters to a standard D&D PDF format.

### 🏰 For the Dungeon Master
- **Campaign Workspace:** Track session logs and active campaign notes.
- **AI Encounter Generator:** Dynamically generate story-appropriate NPCs, monsters, and random encounters tailored to your party's level.
- *(Coming Soon)* **Campaign Book Export:** Export the entire campaign into a beautifully formatted D&D PDF.

---

## 🛠️ Tech Stack
- **Environment & Dependency Management:** [Poetry](https://python-poetry.org/)
- **UI Framework:** [Streamlit](https://streamlit.io/) (Pure Python, zero-Javascript frontend)
- **AI Integration:** [Google GenAI SDK](https://pypi.org/project/google-genai/) (Gemini 2.5 Flash)
- **Code Quality:** `pre-commit`, `ruff`

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.13+**
- **Poetry** installed on your system.
- A **Google Gemini API Key**. You can get one for free at [Google AI Studio](https://aistudio.google.com/).

### 2. Installation
Clone the repository and install the dependencies using Poetry:

```bash
git clone https://github.com/dimitrisl/agents.git
cd agents

# Install dependencies and create the virtual environment
poetry install
```

### 3. Environment Variables
Copy the `.env_example` file to create a `.env` file:
```bash
cp .env_example .env
```
Open `.env` and add your Gemini API Key:
```env
GEMINI_API_KEY=your_actual_api_key_here
```

### 4. Running the Application
To launch the Streamlit dashboard, run:
```bash
poetry run streamlit run main.py
```
This will automatically open the web UI in your default browser at `http://localhost:8501`.

---

## 🧪 Testing & Development

**Test API Connectivity:**
To verify that your Gemini API key is working correctly:
```bash
poetry run python tests/test_gemini_connection.py
```

**Code Quality (Pre-commit & Ruff):**
This project uses `ruff` for extremely fast linting and formatting. Ensure hooks are installed:
```bash
poetry run pre-commit install
```
To manually run the formatting and lint checks on all files:
```bash
poetry run pre-commit run --all-files
```
