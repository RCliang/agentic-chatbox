from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chatbox"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/chatbox"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "sk-placeholder"
    llm_default_model: str = "gpt-4"
    milvus_uri: str = "http://localhost:19530"
    milvus_user: str = ""
    milvus_password: str = ""

    # Embedding model (falls back to LLM settings if not set)
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    # MCP web search service
    mcp_websearch_url: str = ""
    mcp_websearch_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def effective_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.llm_base_url

    @property
    def effective_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.llm_api_key

    @property
    def effective_embedding_model(self) -> str:
        return self.embedding_model or self.llm_default_model


settings = Settings()
