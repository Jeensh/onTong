"""Application configuration via environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # FastAPI
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8001

    # Frontend (CORS)
    frontend_url: str = "http://localhost:3000"

    # LLM — format: "provider/model" (e.g. "openai/gpt-4o-mini", "ollama/llama3")
    # Supported providers: openai, anthropic, ollama, google, azure, groq, deepseek
    litellm_model: str = "ollama/llama3"
    litellm_api_key: str = ""       # Generic fallback API key
    anthropic_api_key: str = ""     # ANTHROPIC_API_KEY
    google_api_key: str = ""        # GOOGLE_API_KEY (Gemini)
    groq_api_key: str = ""          # GROQ_API_KEY
    azure_endpoint: str = ""        # AZURE_OPENAI_ENDPOINT
    azure_api_key: str = ""         # AZURE_OPENAI_API_KEY
    azure_api_version: str = "2024-12-01-preview"
    deepseek_api_key: str = ""      # DEEPSEEK_API_KEY
    ollama_host: str = "http://localhost:11434"

    # Embedding — "default" uses ChromaDB built-in, "openai" uses OpenAI API
    embedding_provider: str = "default"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chromadb_collection: str = "ontong_wiki"

    # Langfuse
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    enable_langfuse_monitor: bool = False

    # Search
    enable_reranker: bool = True  # LLM-based reranking of search results

    # Auth
    auth_provider: str = "noop"  # "noop" | future: "oidc", "ldap", "saml", etc.

    # Wiki storage — "local" or "nas"
    storage_backend: str = "local"
    wiki_dir: Path = Path(__file__).resolve().parent.parent.parent / "wiki"
    nas_wiki_dir: str = ""  # NAS mount path (used when storage_backend=nas)

    # Neo4j (Section 2 - Modeling)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ontong_dev"

    # Redis (optional — falls back to in-memory if not configured)
    redis_url: str = ""  # e.g. redis://localhost:6379/0

    # Ollama
    ollama_num_parallel: int = 4  # Max parallel LLM requests (Ollama)
    llm_semaphore_limit: int = 8  # Max concurrent LLM calls across all agents

    # Server
    uvicorn_workers: int = 4  # Number of uvicorn workers (production)

    # Monitoring
    log_dir: str = ".logs"
    enable_local_monitor: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
