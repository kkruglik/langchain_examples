from google import genai
from google.genai import types as genai_types
from langchain_core.language_models import BaseChatModel
from langsmith import traceable

from langchain_examples.config import AgentConfig, Config, ModelProvider


def build_agent(agent_config: AgentConfig, config: Config) -> BaseChatModel:
    model_config = agent_config.model

    match model_config.provider:
        case ModelProvider.OPENAI:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_config.name,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                max_retries=model_config.max_retries,
                api_key=config.openai_api_key,
            )

        case ModelProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_config.name,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                max_retries=model_config.max_retries,
                api_key=config.anthropic_api_key,
            )

        case ModelProvider.GOOGLE:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model_config.name,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                max_retries=model_config.max_retries,
                api_key=config.google_api_key,
            )

        case _:
            raise ValueError(f"Unsupported model provider: {model_config.provider}. Select one of: {ModelProvider}")


@traceable(run_type="llm", name="generate_image")
def generate_image(model: str, prompt: str, aspect_ratio: str, api_key: str | None) -> bytes:
    """Generate a single image and return raw bytes. Dispatches on model name."""
    client = genai.Client(api_key=api_key)

    if "imagen" in model.lower():
        result = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=genai_types.GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio),
        )
        return result.generated_images[0].image.image_bytes

    if "gemini" in model.lower():
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=genai_types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        for part in response.parts:
            if part.inline_data is not None:
                return part.inline_data.data
        raise ValueError(f"Gemini model {model} returned no image data")

    raise ValueError(f"Unsupported image model: {model}")
