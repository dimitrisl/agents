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
graph LR
    %% Layer 1: UI
    subgraph UI ["🖥️ USER INTERFACE"]
        direction TB
        MAIN["<b>main.py</b><br/>Router & Entry"]
        PD["<b>player_dashboard.py</b><br/>Player Hub"]
        DM["<b>dm_workspace.py</b><br/>DM Tools"]
        SV["<b>settings_view.py</b><br/>Preferences"]
    end

    %% Layer 2: Core Logic
    subgraph CORE ["🔧 CORE & STATE"]
        direction TB
        AI["<b>core.ai_client</b><br/>Gemini Bridge"]
        STATE["<b>core.state_manager</b><br/>Session State"]
        STORAGE["<b>core.storage</b><br/>Domain Facade"]
        SCHEMAS["<b>core.schemas</b><br/>Data Models"]
        PROMPTS["<b>core.prompts</b><br/>AI Templates"]
    end

    %% Layer 3: Services
    subgraph SERVICES ["⚙️ SERVICES"]
        direction TB
        FORGE["<b>services.forge</b><br/>Character AI"]
        MECH["<b>services.mechanics</b><br/>Stat Engine"]
        RULES["<b>services.rules</b><br/>Rules Oracle"]
        DMS["<b>services.dm_service</b><br/>Campaign AI"]
    end

    %% Layer 4: Infrastructure & Data
    subgraph INFRA ["🛠️ UTILS & REPOS"]
        direction TB
        REPOS["<b>repositories</b><br/>Persistence Logic"]
        PDF["<b>utils.pdf_exporter</b><br/>PDF Gen"]
        IMG["<b>utils.image_utils</b><br/>Art Gen"]
        DICE["<b>utils.dice</b><br/>Dice Engine"]
        JSON[("<b>Local Files</b><br/>JSON Storage")]
    end

    %% Layer 5: External
    subgraph EXTERNAL ["☁️ CLOUD"]
        GEMINI["<b>Google Gemini</b><br/>LLM API"]
        POLL["<b>Pollinations.ai</b><br/>Image API"]
    end

    %% Routing
    MAIN --> PD & DM & SV

    %% UI to Services & Utils
    PD --> FORGE & MECH & RULES
    PD --> PDF & IMG & DICE
    DM --> DMS & RULES

    %% Cross-cutting Core
    PD & DM --> STATE
    STATE & SERVICES --> STORAGE
    STORAGE --> REPOS
    REPOS --> JSON

    %% AI Chain
    SERVICES --> AI
    AI --> GEMINI
    IMG --> POLL

    %% Styling
    classDef ui fill:#2d1a1a,stroke:#ff4b4b,stroke-width:2px,color:#fff
    classDef core fill:#1a2d2d,stroke:#53a8b6,stroke-width:2px,color:#fff
    classDef service fill:#1a1a2d,stroke:#d4af37,stroke-width:2px,color:#fff
    classDef infra fill:#1d1d1d,stroke:#888,stroke-width:1px,color:#ccc
    classDef data fill:#2d1a2d,stroke:#e94560,stroke-width:2px,color:#fff
    classDef ext fill:#111,stroke:#7b68ee,stroke-width:2px,color:#fff

    class MAIN,PD,DM,SV ui
    class AI,STATE,STORAGE,SCHEMAS,PROMPTS core
    class FORGE,MECH,RULES,DMS service
    class REPOS,PDF,IMG,DICE,JSON infra
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
