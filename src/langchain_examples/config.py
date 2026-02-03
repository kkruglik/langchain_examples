from functools import cached_property
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class AgentConfig(BaseModel):
    """Config for individual agent. Loaded from YAML."""

    model: str = "gpt-5-mini"
    temperature: float = 0.3
    prompt_path: str = ""

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

    supervisor: AgentConfig = AgentConfig(temperature=0.3)
    writer: AgentConfig = AgentConfig(temperature=0.7)
    editor: AgentConfig = AgentConfig(temperature=0.5)
    factchecker: AgentConfig = AgentConfig(temperature=0.2)
    researcher: AgentConfig = AgentConfig(temperature=0.3)
    swarm_writer: AgentConfig = AgentConfig(temperature=0.8)


class Config(BaseSettings):
    """Main config. Env vars for secrets, YAML for agent settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        yaml_file="config/base.yaml",
        extra="ignore",
    )

    openai_api_key: Annotated[str, Field(alias="OPENAI_API_KEY")]
    agents: AgentsConfig = AgentsConfig()

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
