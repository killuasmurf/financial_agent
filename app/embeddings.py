from functools import lru_cache
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings
from pydantic import SecretStr


@lru_cache(maxsize=1)
def get_embeddings_model() -> GoogleGenerativeAIEmbeddings:
    """Create the embedding client only when document work is requested."""
    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2-preview",
        api_key=(
            SecretStr(settings.GOOGLE_API_KEY)
            if settings.GOOGLE_API_KEY is not None
            else None
        ),
    )