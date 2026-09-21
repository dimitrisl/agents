# The DM Arsenal & Worldbuilding Roadmap

This document outlines the proposed roadmap for elevating the DM Workspace from a simple initiative tracker to a complete "Campaign Manager" and "AI Copilot". These features are not yet ticketed but represent the next major evolutionary step for Phyrexian Forge.

## 1. Phase One: The Worldbuilding Foundation
Before the AI can make intelligent suggestions, the system needs to maintain structured state about the world, the lore, and the session history.

### 📖 The Campaign Chronicle (Session Journal)
Currently, campaign notes are a single raw text block. We need to evolve this into a structured **Timeline**.
* **Data Model Idea:** `CampaignLog` (Session Number, In-game Date, Real-world Date, Title, Summary, Key Player Actions).
* **Benefit:** Allows filtering by date and provides structured chronological context to the AI (e.g., "What did the party do in session 4?").

### 🗺️ The Atlas (Location Registry)
A dedicated space to register places the party has visited or will visit.
* **Data Model Idea:** `Location` (Name, Description, Coordinates/Region, Connected NPCs, Current State).
* **Benefit:** The DM can quickly pull up stats for a city, and the AI knows where the party is located.

### 🖼️ The Multimedia Vault
Attach visual and auditory context to Locations or NPCs.
* **Feature:** A gallery system inside the Atlas/NPC cards.
* **Inputs:** Image URLs (maps, character art), YouTube/Spotify links (for quick access to combat/ambient music).
* **Benefit:** One-click environment setting for the DM.

---

## 2. Phase Two: The AI Copilot (Session Prep & Tactics)
Once the Worldbuilding Foundation is in place, we can unleash Gemini to assist the DM proactively.

### 🧠 The Session Forge (Prep Architect)
An AI tool inspired by the "Return of the Lazy Dungeon Master" methodology.
* **Input:** Reads the Campaign Chronicle, Atlas, and Party Character Sheets + a brief DM prompt.
* **Output:** Generates a structured Next-Session plan:
  - **The Strong Start:** A dramatic opening scene.
  - **5 Secrets & Clues:** Bits of lore or plot hooks the party can discover.
  - **3 Potential Encounters:** Balanced based on the party's exact levels and HP.
  - **Key NPCs:** Automatically generated profiles for characters they might meet.
* **Workflow:** The DM reviews the AI output, edits it, and saves it directly to the Campaign Chronicle.

### ⚔️ Smart Encounter Balancer & Tactician
* **Feature:** During combat or prep, the AI analyzes the chosen monsters vs. the Party Roster.
* **Tactics Brief:** Generates a short tactical brief for the DM (e.g., "The party has high AC but low Wisdom saves; use the Mage's *Hold Person* spell early. Spread out to avoid the Sorcerer's *Fireball*.").

### 🧙‍♂️ On-the-Fly NPC & Monster Generator
* **Feature:** A text box in the DM dashboard: *"I need a shady tiefling rogue, CR 4"*.
* **Output:** Instantly generates a full, mathematically correct JSON statblock using the AI and adds it directly to the Initiative Tracker.

### 🎁 Dynamic Loot & Reward Coordinator
* **Feature:** The AI evaluates the Party's current equipment and identifies weaknesses (e.g., "The Paladin hasn't upgraded their armor since level 3").
* **Output:** Auto-generates thematic, balanced Homebrew magic items that perfectly fill the party's gaps and injects them into the current dungeon's loot pool.

### 🎙️ Session Transcription & Auto-Journaling
* **Feature:** DMs who record their sessions (audio) can upload the MP3/WAV file directly to the workspace.
* **Process:** Using Gemini 1.5's native multimodal audio understanding (or Whisper), the system transcribes the session.
* **Output:** Automatically generates a formatted **Session Log** for the Campaign Chronicle, extracts new NPCs met, loot acquired, and locations visited, saving the DM hours of post-session note-taking.

### 🎭 Villain Simulator (Roleplay Sandbox)
* **Feature:** A dedicated chatbot interface where the DM inputs the Big Bad Evil Guy's (BBEG) motives and secrets.
* **Process:** The AI takes on the persona of the *Players*, asking unpredictable questions. The DM roleplays the villain to test out dialogue, find holes in their plot, and get "warmed up" before the real session.

### 🌩️ The "Vibe Shift" (WebSocket Environment Control)
* **Feature:** Because players are connected via WebSockets, the DM acts as the ultimate director.
* **Process:** The DM clicks an environment preset (e.g., "Dragon Lair" or "Tavern").
* **Output:** Instantly changes the CSS theme (colors/backgrounds) on all connected Player clients and triggers ambient background music/SFX on their browsers.

### ⏳ Downtime & Economy Manager
* **Feature:** A tracker that calculates downtime activities between adventures.
* **Process:** Players declare what they are doing (e.g., crafting, running a business, researching). The system crunches the D&D economy math, calculates days passed, gold earned/lost, and outputs the result, removing all accounting from the DM's plate.

---

## 3. Future Enhancements & Resilience

* **UI Integration for Rules Oracle:** The backend already has `ask_rules_oracle` implemented in `rules_router.py`. Future work involves exposing this as an elegant "Rules Lawyer" chat box inside the DM Dashboard so the DM can resolve disputes instantly mid-combat.
* **Lightweight VTT Zone Combat:** A basic grid or abstract zone map where the DM can drag-and-drop player portraits (since they are already uploaded) without needing external tools like Roll20.
* **Offline-First Resilience:** Moving from purely server-state WebSockets to a local-first architecture (e.g., IndexedDB via RxDB). Ensures the character sheets and combat tracker survive intermittent Wi-Fi drops at the physical game table.
* **OAuth2 Integration:** Discord login support, allowing players to join campaigns directly via Discord identity, reducing friction and linking to the most common D&D community platform.
