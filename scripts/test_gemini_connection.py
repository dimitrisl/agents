import os
from dotenv import load_dotenv
from google import genai

# Load environment variables from the .env file
load_dotenv()


def test_connection():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY is not set. Please add it to your .env file.")
        return

    print("🔄 Initializing Gemini client...")
    try:
        # Initialize the client. It automatically picks up GEMINI_API_KEY from the environment.
        client = genai.Client()

        print("🔍 Searching for available Flash models...")
        models = list(client.models.list())

        # Find all available flash models
        flash_models = [m.name for m in models if "flash" in m.name.lower()]

        if not flash_models:
            print(
                "❌ No Flash models found. Here are the models you do have access to:"
            )
            for m in models[:5]:
                print(f" - {m.name}")
            return

        # Select the first available flash model
        model_to_use = flash_models[0]
        # The library sometimes prefers the name without the "models/" prefix
        if model_to_use.startswith("models/"):
            model_to_use = model_to_use[7:]

        print(f"📨 Sending a test prompt to Gemini (using {model_to_use})...")
        response = client.models.generate_content(
            model=model_to_use,
            contents='Reply with exactly "Connection successful!" and nothing else.',
        )

        print("\n✅ --- Response from Gemini ---")
        print(response.text.strip())
        print("------------------------------")
        print(
            f"\n🎉 Success! You are connected to the Gemini API using {model_to_use}."
        )

    except Exception as e:
        print(f"\n❌ Failed to connect to Gemini API. Error details:\n{e}")


if __name__ == "__main__":
    test_connection()
