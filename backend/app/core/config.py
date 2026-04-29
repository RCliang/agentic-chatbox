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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
