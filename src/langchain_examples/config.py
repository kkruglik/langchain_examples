import os
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
DEFAULT_CONFIG = "config/base-openai-mini.yaml"


class ModelProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelConfig(BaseModel):
    name: str
    temperature: float
    provider: ModelProvider
    max_tokens: int | None = None
    max_retries: int = 2


class AgentConfig(BaseModel):
    """Config for individual agent. Loaded from YAML."""

    prompt_path: str = ""
    model: ModelConfig

    @cached_property
    def prompt(self) -> str:
        """Load prompt from file. Cached after first access."""
        if not self.prompt_path:
            return ""
        path = CONFIG_DIR / self.prompt_path
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()


class AgentsConfig(BaseModel):
    """All agent configs. Nested under 'agents' key in YAML."""

    supervisor: AgentConfig
    writer: AgentConfig
    editor: AgentConfig
    factchecker: AgentConfig
    researcher: AgentConfig
    swarm_writer: AgentConfig


class Config(BaseSettings):
    """Main config. Env vars for secrets, YAML for agent settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        yaml_file=os.getenv("CONFIG_FILE", DEFAULT_CONFIG),
        extra="ignore",
    )

    openai_api_key: Annotated[str | None, Field(default=None, alias="OPENAI_API_KEY")]
    anthropic_api_key: Annotated[str | None, Field(default=None, alias="ANTHROPIC_API_KEY")]
    google_api_key: Annotated[str | None, Field(default=None, alias="GOOGLE_API_KEY")]
    agents: AgentsConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


settings = Config()  # type: ignore[call-arg]
agents_config = settings.agents
