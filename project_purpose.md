# D&D Assistant Project Specification

## Project Overview
A comprehensive, AI-powered personal assistant designed for both Dungeons & Dragons (D&D) Players and Dungeon Masters (DMs). The application serves as a dynamic tool for character management, campaign tracking, and AI-assisted content generation.

## Core Features & User Personas

### 1. For the D&D Player
- **Interactive Character Management:** Store, view, and edit character sheets in a dynamic HTML format.
- **PDF Export:** Export characters directly to the standard D&D PDF character sheet format.
- **AI Character Creation:** Generate new characters based on specific user preferences, themes, or archetypes.
- **Smart Build Suggestions:** Receive optimized build and leveling suggestions based on a combination of the character's personality, race, class, and subclass.
- **Automated Progression:** Easily increment character levels with the system automatically recalculating stats, features, and updating the sheet.

### 2. For the Dungeon Master (DM)
- **Campaign Management:** Store, edit, and organize campaign notes and lore in an interactive HTML format.
- **Campaign Book Export:** Export the entire campaign into a beautifully formatted D&D PDF campaign book.
- **Party Integration:** Import player character sheets into the campaign, seamlessly tracking their stats and automatically syncing their level updates.
- **Session Planning & History:** Maintain a structured log of past sessions and use AI to help brainstorm, organize, and set up plot hooks and encounters for the next session based on previous events.
- **Dynamic AI Generation:** Automatically generate story-appropriate NPCs, monsters, and random encounters explicitly tailored to the campaign's current narrative and the party's actual level.

## Technical Architecture
The application will be decoupled into three distinct layers, prioritizing a highly modular and extensible architecture. This ensures that as new ideas emerge (e.g., combat trackers, homebrew rule integrations, loot generators), they can be bolted on seamlessly without rewriting core systems.
1. **Frontend:** The user interface for interacting with characters, campaigns, and AI tools. Designed to support dynamic widgets and future module additions.
2. **Backend:** The core server handling data persistence, business logic, and security. It will expose a flexible, versioned API to easily accommodate future data types.
3. **Agents:** The AI processing layer responsible for generative tasks (character creation, builds, encounters, NPCs). Built with a plug-and-play design so new AI agents and workflows can be added effortlessly.

## Deployment & Infrastructure
- **Portability:** Designed to run seamlessly on a local machine while being structured for easy redeployment to a remote server when needed.
- **Self-Contained:** The system will not rely on any external third-party services (e.g., external databases, auth providers), keeping the infrastructure simple and private.
- **Security:** The only external requirement is the LLM API key, which will be strictly and securely managed within the backend environment.
