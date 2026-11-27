from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The repo root holds the three LLM_* values the challenge template asks for.
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"), extra="ignore", env_ignore_empty=True
    )

    database_url: str = "postgresql+asyncpg://trustroom:trustroom@localhost:5433/trustroom"
    test_database_url: str | None = (
        "postgresql+asyncpg://trustroom:trustroom@localhost:5433/trustroom_test"
    )

    llm_base_url: str
    llm_api_key: SecretStr
    llm_name: str
    llm_name_fast: str | None = None  # None: the fast model is `llm_name` too
    apertus_timeout_seconds: float = 60
    apertus_max_retries: int = 2
    apertus_json_schema_supported: bool = False

    # The e-banking's API, as this server reaches it. Never taken from the browser.
    banking_api_url: str = "http://localhost:8000/api"
    banking_timeout_seconds: float = 10

    # Web search leaves the bank's environment, so it is off until a key is set.
    tavily_base_url: str = "https://api.tavily.com"
    tavily_api_key: SecretStr = SecretStr("")

    # Writes from other origins are refused.
    app_origin: str = "http://localhost:3000"

    log_llm_content: bool = False
    llm_log_path: str | None = "logs/llm.jsonl"  # None: log to stdout (deployment)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # values come from env
