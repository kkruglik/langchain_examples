from langchain_openai import ChatOpenAI

from langchain_examples.config import agents_config, settings

from ..tools.scrapers import analyze_script, scrape_article, web_search
from .models import SupervisorOutput, WriterOutput

editor_tools = [analyze_script]
factchecker_tools = [web_search]
researcher_tools = [web_search, scrape_article]
all_tools = editor_tools + factchecker_tools + researcher_tools
tools_by_name = {tool.name: tool for tool in all_tools}

writer_llm = ChatOpenAI(
    model=agents_config.writer.model,
    temperature=agents_config.writer.temperature,
    api_key=settings.openai_api_key,
)
writer_llm = writer_llm.with_structured_output(WriterOutput)

editor_llm = ChatOpenAI(
    model=agents_config.editor.model,
    temperature=agents_config.editor.temperature,
    api_key=settings.openai_api_key,
)
editor_llm = editor_llm.bind_tools(editor_tools)

factchecker_llm = ChatOpenAI(
    model=agents_config.factchecker.model,
    temperature=agents_config.factchecker.temperature,
    api_key=settings.openai_api_key,
)
factchecker_llm = factchecker_llm.bind_tools(factchecker_tools)

supervisor_llm = ChatOpenAI(
    model=agents_config.supervisor.model,
    temperature=agents_config.supervisor.temperature,
    api_key=settings.openai_api_key,
)
supervisor_llm = supervisor_llm.with_structured_output(SupervisorOutput)

researcher_llm = ChatOpenAI(
    model=agents_config.researcher.model,
    temperature=agents_config.researcher.temperature,
    api_key=settings.openai_api_key,
)
researcher_llm = researcher_llm.bind_tools(researcher_tools)

swarm_writer_llm = ChatOpenAI(
    model=agents_config.swarm_writer.model,
    temperature=agents_config.swarm_writer.temperature,
    api_key=settings.openai_api_key,
)
