import requests
import logging

logger = logging.getLogger("DnDAssistant.APIClient")

DND_5E_API_BASE = "https://www.dnd5eapi.co/api/2014"
# Community maintained raw JSON (more comprehensive than SRD)
COMMUNITY_FEATS_URL = (
    "https://raw.githubusercontent.com/BTMorton/dnd-5e-srd/master/json/feats.json"
)


def fetch_feat_from_api(feat_name: str) -> dict:
    """
    Attempts to fetch feat data from multiple sources.
    """
    # 1. Try Official SRD API first
    index = feat_name.lower().replace(" ", "-").replace("'", "")
    url = f"{DND_5E_API_BASE}/feats/{index}"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "name": data.get("name"),
                "description": "\n".join(data.get("desc", [])),
                "source": "SRD (dnd5eapi.co)",
                "raw": data,
            }
    except Exception as e:
        logger.warning(f"Official API failed: {e}")

    # 2. Try Community GitHub JSON
    try:
        response = requests.get(COMMUNITY_FEATS_URL, timeout=5)
        if response.status_code == 200:
            feats = response.json()
            # Search in the list
            for f in feats:
                if f.get("name").lower() == feat_name.lower():
                    # Flatten description if it's a list
                    desc = f.get("description", "")
                    if isinstance(desc, list):
                        desc = "\n".join(desc)
                    return {
                        "name": f.get("name"),
                        "description": desc,
                        "source": "Community SRD (GitHub)",
                        "raw": f,
                    }
    except Exception as e:
        logger.warning(f"Community API failed: {e}")

    return None
