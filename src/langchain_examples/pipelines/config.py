from pathlib import Path
from typing import Annotated
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
DEFAULT_CONFIG = "config/base-rag-pipeline.yaml"


class SplitterConfig(BaseSettings):
    chunk_size: Annotated[int, Field(default=1000)]
    chunk_overlap: Annotated[int, Field(default=200)]


class QdrantConfig(BaseSettings):
    collection_name: Annotated[str, Field(default="default")]
    k_results: Annotated[int, Field(default=5)]
    url: Annotated[str, Field(default="http://localhost:6333")]
    vector_size: Annotated[int, Field(default=1536)]
    distance: Annotated[str, Field(default="Cosine")]


class RagPipelineConfig(BaseSettings):
    openai_api_key: Annotated[str | None, Field(default=None, alias="OPENAI_API_KEY")]
    embedding_model: Annotated[str, Field(default="text-embedding-3-small")]
    collection_path: Annotated[str, Field(default="data/verstka/")]
    batch_size: Annotated[int, Field(default=2000)]

    splitter: SplitterConfig
    qdrant: QdrantConfig

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        yaml_file=DEFAULT_CONFIG,
        extra="ignore",
    )

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


config = RagPipelineConfig()  # type: ignore[call-arg]
