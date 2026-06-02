import hashlib
from backend.core.db import get_db
from backend.repositories.character_repository import CharacterRepository
from backend.repositories.campaign_repository import CampaignRepository
from backend.core.state_manager import get_default_character


def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed():
    db = get_db()
    if db is None:
        print("Error: Could not connect to MongoDB.")
        return

    # 1. Upsert users mitsos and temp_dm
    users_col = db["users"]

    # User Mitsos
    users_col.update_one(
        {"username": "mitsos"},
        {
            "$set": {
                "username": "mitsos",
                "password_hash": hash_pass("1234"),
                "email": "mitsos@phyrexian.forge",
                "name": "Mitsos",
            }
        },
        upsert=True,
    )
    print("User 'mitsos' seeded.")

    # User temp_dm
    users_col.update_one(
        {"username": "temp_dm"},
        {
            "$set": {
                "username": "temp_dm",
                "password_hash": hash_pass("1234"),
                "email": "temp_dm@phyrexian.forge",
                "name": "Temporary DM",
            }
        },
        upsert=True,
    )
    print("User 'temp_dm' seeded.")

    # 2. Seed character for mitsos
    char_repo = CharacterRepository()
    char_id = "mc123"  # short, simple ID that matches filename split logic
    filename = f"mitsos_hero_{char_id}.json"

    char_data = get_default_character()
    char_data["char_id"] = char_id
    char_data["char_name"] = "Mitsos Hero"
    char_data["owner_id"] = "local_user_mitsos"
    char_data["active_campaign"] = "DM Collab Campaign"
    char_data["race"] = "Human"
    char_data["char_class"] = "Fighter"
    char_data["char_level"] = 1
    char_data["dnd_edition"] = "2014 Edition"
    char_data["stats"] = {
        "STR": 16,
        "DEX": 14,
        "CON": 15,
        "INT": 10,
        "WIS": 12,
        "CHA": 8,
    }
    char_data["skills"] = {"Athletics": 5, "Perception": 3}
    char_data["saving_throws"] = ["STR", "CON"]

    char_repo.save(char_data)
    print(f"Character 'Mitsos Hero' seeded for 'mitsos' (filename: {filename}).")

    # 3. Seed campaign for temp_dm
    camp_repo = CampaignRepository()
    campaign_name = "DM Collab Campaign"

    roll_requests = [
        {
            "id": "test_request_id_999",
            "char_filename": filename,
            "char_name": "Mitsos Hero",
            "roll_type": "Perception Check",
            "stat": "Perception",
            "reason": "To notice the hidden trap door in the floor.",
            "status": "pending",
            "result": None,
            "created_at": "2026-06-02 17:58:00",
        }
    ]

    camp_repo.save(
        campaign_name=campaign_name,
        notes="Welcome to the campaign. The dungeon is dangerous!",
        party=[filename],
        dnd_edition="2014 Edition",
        owner_id="local_user_temp_dm",
        roll_requests=roll_requests,
    )
    print(
        f"Campaign 'DM Collab Campaign' seeded for 'temp_dm' with character '{filename}' in the party and a pending roll request."
    )


if __name__ == "__main__":
    seed()
