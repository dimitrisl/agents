#!/usr/bin/env python3
from dotenv import load_dotenv
from backend.repositories.character_repository import CharacterRepository
from backend.services.forge_service import process_character_update
from backend.core.state_manager import get_default_character
import pprint


def main():
    load_dotenv()
    repo = CharacterRepository()

    print("=== D&D AI Assistant Debugger CLI ===")
    print("1. List all characters in MongoDB")
    print("2. Inspect a character's weapons")
    print("3. Test weapon damage formula edit parsing")
    print("4. Exit")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        chars = repo.list_all()
        print(f"\nFound {len(chars)} characters:")
        for c in chars:
            print(f"- {c}")

    elif choice == "2":
        char_file = input(
            "Enter character filename (e.g., verso_399d4e7b.json): "
        ).strip()
        char_data = repo.load(char_file)
        if not char_data:
            print("Character not found.")
            return
        print(f"\nWeapons for {char_data.get('char_name')}:")
        pprint.pprint(char_data.get("weapons", []))

    elif choice == "3":
        char_file = input(
            "Enter character filename to test (default: verso_399d4e7b.json): "
        ).strip()
        if not char_file:
            char_file = "verso_399d4e7b.json"

        char_data = repo.load(char_file)
        if not char_data:
            print("Character not found. Using default empty character.")
            char_data = get_default_character()

        print("\nOriginal weapons state:")
        pprint.pprint(char_data.get("weapons", []))

        if not char_data.get("weapons"):
            print("No weapons found on character to edit.")
            return

        print("\nSelect a weapon index to edit:")
        for idx, w in enumerate(char_data["weapons"]):
            print(f"[{idx}] {w.get('name')} (Current Damage: {w.get('damage')})")

        try:
            idx_to_edit = int(input("Index: ").strip())
        except ValueError:
            print("Invalid index.")
            return

        if idx_to_edit < 0 or idx_to_edit >= len(char_data["weapons"]):
            print("Index out of range.")
            return

        new_dmg = input("Enter new Damage Formula (e.g. 2d6 + 5 fire): ").strip()

        # Construct deltas simulating streamlit's data_editor
        weapon_deltas = {"edited_rows": {str(idx_to_edit): {"damage": new_dmg}}}

        print("\nProcessing update...")
        try:
            updated_char = process_character_update(
                char_data, weapon_deltas=weapon_deltas
            )
            print("\nUpdated weapon details after parsing and calculations:")
            pprint.pprint(updated_char["weapons"][idx_to_edit])

            save_choice = input("\nSave changes to MongoDB? (y/n): ").strip().lower()
            if save_choice == "y":
                success = repo.save(updated_char)
                if success:
                    print("Successfully saved to database!")
                else:
                    print("Failed to save character schema validation failed.")
        except Exception:
            import traceback

            traceback.print_exc()

    else:
        print("Exiting.")


if __name__ == "__main__":
    main()
