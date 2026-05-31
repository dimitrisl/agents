# Phyrexian Forge: Product Vision & Roadmap

## 🎯 The Core Vision
A modern, AI-powered toolkit designed 50-50 for both Players and Dungeon Masters. It aims to eliminate the friction of learning rules and preparing sessions, allowing groups to focus on the story and the fun of tabletop RPGs.

Currently focused on D&D 5e / 5.5e (2024), but built with a long-term architecture that can eventually pivot to become completely **TTRPG-agnostic** to avoid legal/copyright issues.

---

## ⭐ The "Killer" Features

### For Players (Especially Beginners)
- **Zero-Friction Character Creation:** Generate fully playable characters for 5e/5.5e instantly via AI, without needing to own or read the rulebooks.
- **Smart Dashboard:** An intuitive sheet that calculates everything automatically and explains abilities in plain language.

### For Dungeon Masters
- **AI Session Prep:** The LLM acts as a co-DM. It reads the adventure module, remembers the party's past actions, and merges them with the DM's fresh ideas to generate the next session's notes.
- **Campaign Digitization:** Upload a module PDF and instantly extract the story, lore, and NPCs into the Vault.
- **Combat & Initiative Tracker:** A fast, visual tracker that manages the math so the DM can manage the narrative.

---

## 🗺️ Roadmap to "v1.0" (The 'Friends & Family' Release)
This phase focuses on making the Streamlit app robust enough for live, in-person play without needing to touch the code.

- [x] **Performance & Speed:** Optimize UI to prevent lag or freezing during combat (e.g. Damage/Heal callbacks).
- [x] **Discord Auth:** Allow easy login for players without managing passwords.
- [x] **Module & NPC Parsing:** Fix and refine the extraction of adventure modules and NPCs so they load reliably into the system.
- [x] **Image Management:** Ensure player and NPC portraits populate correctly in all views (player dashboard, initiative tracker, party dashboard). Add the ability to manually upload or set custom portraits via URL or file upload — both on the player sheet and per-combatant in the Initiative Tracker.
- [x] **Manual NPC Creation:** Allow the DM to manually add characters to the NPC Vault (beyond just what the parser extracts).
- [x] **Table-Ready UX:** Polish the interface so it flows naturally during a live, in-person session.

---

## 🚀 The Future (Post v1.0)
- **Tech Stack Migration:** Move away from Streamlit to a modern JavaScript framework (e.g., React/Next.js/Vite) to allow for **native-feeling mobile support**, which is critical for players at a physical table.
- **System Agnosticism:** Strip out hardcoded D&D mechanics and create a generic AI rules-engine to avoid copyright strikes and support multiple systems (Pathfinder, Call of Cthulhu, custom homebrew).
