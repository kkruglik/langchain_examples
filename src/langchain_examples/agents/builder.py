from langchain_core.language_models import BaseChatModel

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
