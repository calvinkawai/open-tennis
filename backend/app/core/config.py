from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the backend POC."""

    google_api_key: str | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-2.5-flash", validation_alias="GEMINI_MODEL"
    )
    embedding_model: str = Field(
        default="gemini-embedding-2", validation_alias="EMBEDDING_MODEL"
    )
    chroma_db_path: Path = Field(
        default=BACKEND_DIR / "data" / "chroma_db", validation_alias="CHROMA_DB_PATH"
    )
    chroma_collection_name: str = Field(
        default="tennis_tutorial_sections", validation_alias="CHROMA_COLLECTION_NAME"
    )
    sqlite_database_path: Path = Field(
        default=BACKEND_DIR / "data" / "database.db",
        validation_alias="SQLITE_DATABASE_PATH",
    )
    retrieval_k: int = Field(default=4, validation_alias="RETRIEVAL_K")
    retrieval_fetch_k: int = Field(default=12, validation_alias="RETRIEVAL_FETCH_K")
    conversation_max_turns: int = Field(
        default=4, validation_alias="CONVERSATION_MAX_TURNS"
    )
    reflection_light_retrieval_k: int = Field(
        default=3, validation_alias="REFLECTION_LIGHT_RETRIEVAL_K"
    )
    llm_timeout_seconds: float = Field(
        default=30, gt=0, le=120, validation_alias="LLM_TIMEOUT_SECONDS"
    )
    llm_max_retries: int = Field(
        default=1, ge=0, le=3, validation_alias="LLM_MAX_RETRIES"
    )
    llm_max_output_tokens: int = Field(
        default=4096, ge=256, le=16384, validation_alias="LLM_MAX_OUTPUT_TOKENS"
    )
    agent_enabled: bool = Field(default=False, validation_alias="AGENT_ENABLED")
    allow_personal_model_context: bool = Field(
        default=False, validation_alias="ALLOW_PERSONAL_MODEL_CONTEXT"
    )
    agent_max_input_characters: int = Field(
        default=50000, ge=2000, le=150000, validation_alias="AGENT_MAX_INPUT_CHARACTERS"
    )
    owner_username: str = Field(default="owner", min_length=1, validation_alias="OWNER_USERNAME")
    owner_password: str | None = Field(default=None, validation_alias="OWNER_PASSWORD")
    tutorial_path: Path = Field(default=BACKEND_DIR / "data" / "tutorial", validation_alias="TUTORIAL_PATH")
    semantic_index_enabled: bool = Field(default=False, validation_alias="SEMANTIC_INDEX_ENABLED")
    wiki_index_path: Path = Field(default=BACKEND_DIR / "data" / "wiki_index", validation_alias="WIKI_INDEX_PATH")
    public_origin: str | None = Field(default=None, validation_alias="PUBLIC_ORIGIN")

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        allow_inf_nan=False,
    )

    @field_validator(
        "chroma_db_path", "sqlite_database_path",
        "tutorial_path", "wiki_index_path", mode="after"
    )
    @classmethod
    def resolve_backend_relative_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return BACKEND_DIR / value

    @property
    def google_genai_api_key(self) -> str:
        api_key = self.google_api_key or self.gemini_api_key
        if not api_key:
            raise RuntimeError(
                "Gemini API key is missing. Set GOOGLE_API_KEY or GEMINI_API_KEY."
            )
        return api_key

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_database_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
