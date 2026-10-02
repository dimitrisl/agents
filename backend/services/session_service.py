import os
import tempfile
from typing import Any, Dict, List

from fastapi import UploadFile

from backend.core.providers.factory import get_llm_provider


class SessionService:
    def __init__(self):
        self.ai_provider = get_llm_provider()

    async def process_audio_session(
        self, campaign_name: str, session_number: int, audio_file: UploadFile
    ) -> Dict[str, Any]:
        """
        Receives an audio file, streams it to a temp file, uploads it to Gemini,
        and generates a transcribed Session Log + extracted entities.
        """
        if not self.ai_provider.client:
            raise ValueError("Gemini API Key is missing.")

        # Save to temp file
        import uuid

        temp_dir = tempfile.gettempdir()
        file_extension = os.path.splitext(audio_file.filename)[1] or ".mp3"
        temp_file_path = os.path.join(
            temp_dir, f"session_upload_{uuid.uuid4().hex}{file_extension}"
        )

        try:
            with open(temp_file_path, "wb") as f:
                while content := await audio_file.read(1024 * 1024):  # 1MB chunks
                    f.write(content)

            # Upload to Gemini
            gemini_file_id = self.ai_provider.upload_file(temp_file_path)

            prompt = (
                f"You are an AI assistant for a Dungeon Master. Listen to this recording of a D&D session "
                f"(Session #{session_number} of '{campaign_name}').\n"
                "1. Transcribe and summarize the session into a detailed 'Session Log' markdown format (include a title and a narrative summary).\n"
                "2. Extract any newly introduced NPCs, Villains, Factions, Locations, or notable Lore as 'entities'.\n"
                "Return a JSON object matching this schema:\n"
                "{\n"
                "  'title': 'string',\n"
                "  'summary': 'markdown string',\n"
                "  'extracted_entities': [\n"
                "    { 'name': 'string', 'type': 'npc|villain|faction|location|lore', 'content': 'description', 'tags': [] }\n"
                "  ]\n"
                "}"
            )

            # Generate JSON from file
            result = self.ai_provider.generate_json_from_files(
                file_ids=[gemini_file_id], prompt=prompt
            )

            if not result:
                raise ValueError("AI failed to process the audio.")

            return {
                "title": result.get("title", f"Session {session_number} Recap"),
                "summary": result.get("summary", "No summary generated."),
                "extracted_entities": result.get("extracted_entities", []),
                "audio_file_id": gemini_file_id,
            }

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    async def process_text_session(
        self, campaign_name: str, session_number: int, notes: str
    ) -> Dict[str, Any]:
        """
        Receives DM session notes, uploads to Gemini,
        and generates a transcribed Session Log + extracted entities.
        """
        if not self.ai_provider.client:
            raise ValueError("Gemini API Key is missing.")

        prompt = (
            f"You are an AI assistant for a Dungeon Master. Read the following DM notes of a D&D session "
            f"(Session #{session_number} of '{campaign_name}').\n"
            "1. Transform the raw notes into a detailed 'Session Log' markdown format (include a title and a narrative summary).\n"
            "2. Extract any newly introduced NPCs, Villains, Factions, Locations, or notable Lore as 'entities'.\n"
            "3. If an NPC's location is mentioned, include it in 'current_location_id' (just the string name of the location).\n"
            "Return a JSON object matching this schema:\n"
            "{\n"
            "  'title': 'string',\n"
            "  'summary': 'markdown string',\n"
            "  'extracted_entities': [\n"
            "    { 'name': 'string', 'type': 'npc|villain|faction|location|lore', 'content': 'description', 'tags': [], 'current_location_id': 'string|null' }\n"
            "  ]\n"
            "}\n\n"
            f"DM NOTES:\n{notes}"
        )

        result = self.ai_provider.generate_json(prompt=prompt)

        if not result:
            raise ValueError("AI failed to process the session notes.")

        return {
            "title": result.get("title", f"Session {session_number} Recap"),
            "summary": result.get("summary", "No summary generated."),
            "extracted_entities": result.get("extracted_entities", []),
        }

    def generate_session_forge_prep(
        self, past_sessions: List[dict], active_entities: List[dict], dm_ideas: str = ""
    ) -> dict:
        """
        Generates the Lazy DM session prep for the next session.
        """
        if not self.ai_provider.client:
            raise ValueError("Gemini API Key is missing.")

        sessions_context = "\n".join(
            [
                f"Session {s.get('session_number')}: {s.get('title')}\n{s.get('summary')}"
                for s in past_sessions
            ]
        )
        entities_context = "\n".join(
            [f"- {e.get('name')} ({e.get('type')}): {e.get('content')}" for e in active_entities]
        )

        prompt = (
            "You are an expert Dungeon Master using the 'Return of the Lazy Dungeon Master' method.\n"
            "Based on the following past sessions and active entities, generate a prep sheet for the NEXT session.\n\n"
            "PAST SESSIONS:\n"
            f"{sessions_context}\n\n"
            "ACTIVE ENTITIES:\n"
            f"{entities_context}\n\n"
            "Return a JSON object with:\n"
            "{\n"
            "  'strong_start': 'A dramatic opening scene to hook the players.',\n"
            "  'secrets_clues': ['secret 1', 'secret 2', ... (at least 5)],\n"
            "  'encounters': ['potential encounter 1', 'encounter 2', ... (at least 3)],\n"
            "  'key_npcs': ['NPC name and brief role']\n"
            "}"
        )

        result = self.ai_provider.generate_json(prompt=prompt, temperature=0.7)

        if not result:
            raise ValueError("AI failed to generate session prep.")

        return result

    def generate_journey_graph(self, past_sessions: List[dict]) -> dict:
        """
        Analyzes past sessions and returns a chronological path of visited locations.
        """
        if not self.ai_provider.client:
            raise ValueError("Gemini API Key is missing.")

        sessions_context = "\n".join(
            [f"Session {s.get('session_number')}: {s.get('summary')}" for s in past_sessions]
        )

        prompt = (
            "You are an AI assistant for a D&D Campaign.\n"
            "Analyze the following session summaries and reconstruct the EXACT journey of the party "
            "as a chronological sequence of visited locations.\n\n"
            "SESSIONS:\n"
            f"{sessions_context}\n\n"
            "Return a JSON object with this schema:\n"
            "{\n"
            "  'nodes': [\n"
            "    { 'location_name': 'String', 'description': 'What they did there', 'session_number': 1 }\n"
            "  ]\n"
            "}"
        )

        result = self.ai_provider.generate_json(prompt=prompt, temperature=0.3)
        if not result:
            raise ValueError("AI failed to generate journey graph.")

        return result

    def generate_campaign_outlines(self, skeleton_data: dict) -> List[dict]:
        """
        Generates session-by-session outlines based on a campaign skeleton.
        """
        if not self.ai_provider.client:
            raise ValueError("Gemini API Key is missing.")

        prompt = (
            "You are an expert Dungeon Master and storyteller.\n"
            "Given the following campaign skeleton, generate a session-by-session outline that paces the story perfectly "
            f"across EXACTLY {skeleton_data.get('max_sessions')} sessions. Ensure there are no plot holes, the tone is consistent, "
            "and all key milestones and plot twists are logically distributed.\n\n"
            "CAMPAIGN CONCEPT:\n"
            f"{skeleton_data.get('concept')}\n\n"
            "TONE:\n"
            f"{skeleton_data.get('tone')}\n\n"
            "PLOT TWISTS:\n"
            f"{', '.join(skeleton_data.get('plot_twists', []))}\n\n"
            "KEY MILESTONES:\n"
            f"{', '.join(skeleton_data.get('key_milestones', []))}\n\n"
            "Return a JSON object with this schema:\n"
            "{\n"
            "  'outlines': [\n"
            "    {\n"
            "      'session_number': 1,\n"
            "      'main_event': 'string describing the core event',\n"
            "      'required_npcs': ['npc name'],\n"
            "      'location': 'location name',\n"
            "      'plot_hooks': ['hook 1', 'hook 2']\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        result = self.ai_provider.generate_json(prompt=prompt, temperature=0.7)
        if not result or "outlines" not in result:
            raise ValueError("AI failed to generate campaign outlines.")

        return result.get("outlines", [])
