"""
Quick test to verify AI client connection
"""
from config.ai_client import ai_client


def test_ai_connection():
    """Test basic AI client functionality"""
    print("Testing AI Client Connection...")
    print(f"Base URL: https://ai.megallm.io/v1")
    print(f"Available models: {ai_client.models}")

    # Test simple completion
    print("\nTesting simple completion with Claude Haiku...")

    try:
        response = ai_client.client.chat.completions.create(
            model=ai_client.models["fast"],
            messages=[
                {"role": "user", "content": "Say 'Hello from Claude!' and nothing else."}
            ],
            max_tokens=20
        )

        print(f"✅ Success! Response: {response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_ai_connection()
