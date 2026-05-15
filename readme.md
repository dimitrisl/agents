# 🩸 Phyrexian Forge
> *"All will be one."*

**Phyrexian Forge** is a premium, AI-powered specialized tool for **Dungeons & Dragons (5e & 5.5e)**. It serves as a bio-mechanical forge for character creation, strategic optimization, and campaign management, powered by Google's Gemini LLM.

---

## ✨ Features

### 🗡️ For the Player
- **AI Character Forge:** Generate fully equipped, thematic heroes from a simple text concept.
- **🖼️ Dynamic Portrait Generation:** Automatically generated, high-quality character portraits based on your hero's race, class, alignment, and backstory (powered by Pollinations.ai).
- **🎲 Interactive Dice Roller:** Integrated dice mechanics with support for automated attack and damage rolls using your character's real-time modifiers.
- **📖 AI Playstyle Guide:** On-demand generation of a comprehensive strategic guide (Combat & Roleplay) tailored to your specific build and level.
- **Dual Edition Support (5.5e Ready):** Seamlessly toggle between **D&D 2014** and **2024 Revision (5.5e)** rulesets.
- **Character Vault:** Manage, view, and persist your characters with deep integration for stats, alignment, and features.
- **Premium PDF Export:** Export your character to a standard 5e fillable PDF, featuring automated proficiency marks and character portraits.

### 🏰 For the Dungeon Master
- **DM Quick Forge:** Rapidly generate NPCs and monsters to populate your world.
- **Campaign Workspace:** Track session logs, plot hooks, and active campaign developments with AI assistance.
- **Party Tracking & Initiative:** Monitor the entire party's stats from a centralized dashboard and track combat turns with a built-in initiative system.
- **Static Rules Engine:** Level-up features and class/feat lookups are powered by a rigorous, local JSON knowledge base (for both 2014 & 2024 rulesets) to guarantee perfectly accurate progression without AI hallucinations.

---

## 🎨 Aesthetics & UI
- **Bio-mechanical Design:** High-contrast dark theme with a custom Phyrexian aesthetic.
- **Segmented Control Navigation:** Modern, pill-shaped navigation for a faster, premium workflow.
- **Custom AI Logo:** Iconic Cyber-D20 branding integrated with Phyrexian lore.

---

## 🛠️ Tech Stack
- **Dependency Management:** [Poetry](https://python-poetry.org/)
- **Frontend:** [Streamlit](https://streamlit.io/) (Styled with Custom CSS & Segmented Controls)
- **AI Engine:** [Google GenAI SDK](https://pypi.org/project/google-genai/) (Gemini Flash/Pro models)
- **Image Generation:** [Pollinations.ai](https://pollinations.ai/)
- **Data Architecture:** Repository Pattern (`CharacterRepository`, `RulesRepository`) handling static JSON local storage.
- **PDF Engine:** `pypdf`, `reportlab`
- **Quality Control:** `pre-commit`, `ruff`

---

## 🏗️ Architecture

```mermaid
graph TB
    subgraph UI["🖥️ Streamlit UI Layer"]
        MAIN["main.py<br/><i>Entry Point & Router</i>"]
        PD["player_dashboard.py<br/><i>Character Sheet, Dice, Combat</i>"]
        DM["dm_workspace.py<br/><i>Encounters, NPCs, Campaigns</i>"]
        SV["settings_view.py<br/><i>Config & Preferences</i>"]
    end

    subgraph SERVICES["⚙️ Backend Services"]
        FORGE["forge_service.py<br/><i>AI Character Generation<br/>Level Up Analysis</i>"]
        MECH["mechanics_service.py<br/><i>HP, AC, Saves, Weapons<br/>stat sync engine</i>"]
        RULES["rules_service.py<br/><i>AI Rules Oracle<br/>Build Validation</i>"]
        DMS["dm_service.py<br/><i>Encounters, NPCs<br/>Session Prep</i>"]
    end

    subgraph SUPPORT["🔧 Support Modules"]
        DICE["dice.py<br/><i>Dice Parser & Roller</i>"]
        SCHEMAS["schemas.py<br/><i>Pydantic Models</i>"]
        STATE["state_manager.py<br/><i>Session State</i>"]
        PDF["pdf_exporter.py<br/><i>PDF Character Sheets</i>"]
        IMG["image_utils.py<br/><i>Portrait Generation</i>"]
        AI["ai_client.py<br/><i>Gemini API Wrapper</i>"]
    end

    subgraph REPOS["🗄️ Repositories"]
        CHAR_REPO["CharacterRepository<br/><i>CRUD for Characters</i>"]
        CAMP_REPO["CampaignRepository<br/><i>CRUD for Campaigns</i>"]
        RULES_REPO["RulesRepository<br/><i>Classes, Feats, Items</i>"]
    end

    subgraph DATA["💾 Local JSON Storage"]
        CHARS[("data/characters/")]
        CAMPS[("data/campaigns/")]
        CLASSES[("data/rules/classes/")]
        FEATS[("data/rules/feats_*.json")]
        ITEMS[("data/rules/items.json")]
    end

    subgraph EXTERNAL["☁️ External APIs"]
        GEMINI["Google Gemini<br/><i>LLM (Flash/Pro)</i>"]
        POLL["Pollinations.ai<br/><i>Image Generation</i>"]
    end

    %% UI routing
    MAIN --> PD & DM & SV

    %% Views → Services
    PD --> FORGE & MECH & DICE & PDF & IMG
    DM --> DMS & RULES
    PD --> RULES

    %% Views → State
    PD --> STATE
    DM --> STATE

    %% Services → AI
    FORGE --> AI
    RULES --> AI
    DMS --> AI
    AI --> GEMINI

    %% Services → Repos
    FORGE --> RULES_REPO
    MECH --> RULES_REPO
    RULES --> RULES_REPO

    %% Services → Schemas
    FORGE --> SCHEMAS
    RULES --> SCHEMAS
    DMS --> SCHEMAS
    MECH --> SCHEMAS

    %% Services internal
    FORGE --> MECH

    %% Repos → Data
    CHAR_REPO --> CHARS
    CAMP_REPO --> CAMPS
    RULES_REPO --> CLASSES & FEATS & ITEMS

    %% Storage facade
    STATE --> CHAR_REPO & CAMP_REPO

    %% Image
    IMG --> POLL

    %% Styling
    classDef ui fill:#1a1a2e,stroke:#ff4b4b,color:#fff
    classDef service fill:#16213e,stroke:#d4af37,color:#fff
    classDef support fill:#0f3460,stroke:#53a8b6,color:#fff
    classDef repo fill:#1b1b2f,stroke:#e94560,color:#fff
    classDef data fill:#2d2d44,stroke:#888,color:#ccc
    classDef ext fill:#0d0d1a,stroke:#7b68ee,color:#fff

    class MAIN,PD,DM,SV ui
    class FORGE,MECH,RULES,DMS service
    class DICE,SCHEMAS,STATE,PDF,IMG,AI support
    class CHAR_REPO,CAMP_REPO,RULES_REPO repo
    class CHARS,CAMPS,CLASSES,FEATS,ITEMS data
    class GEMINI,POLL ext
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.13+**
- **Poetry**
- **Google Gemini API Key** (Available at [Google AI Studio](https://aistudio.google.com/))

### 2. Installation
```bash
git clone https://github.com/dimitrisl/agents.git
cd agents
poetry install
```

### 3. Environment Setup
Copy `.env_example` to `.env` and add your `GEMINI_API_KEY`.

### 4. Run
```bash
poetry run streamlit run main.py
```

---

## 🧪 Development
- **Tests:** `poetry run pytest tests/ -v`
- **Pre-commit Hooks:** `poetry run pre-commit install`
- **Linting & Formatting:** `poetry run pre-commit run --all-files`
