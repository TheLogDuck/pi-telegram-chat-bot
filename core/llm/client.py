# GenAI client initialization and authentication management.
# Designed to be lightweight and stateless to keep RAM usage under 150 MB.
import os
from google import genai
from core.logger import setup_logger

logger = setup_logger("llm.client")


def get_gemini_client() -> genai.Client:
    """Instantiates the Google GenAI client using the configured API key.

    We avoid storing persistent heavy state in memory. The client object
    is lightweight and delegates async network calls efficiently.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not defined in the environment.")
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    # Return configured Google GenAI client
    return genai.Client(api_key=api_key)
