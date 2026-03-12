from langchain_examples.config import agents_config, settings

from ..tools.scrapers import scrape_article, web_search, search_verstka_texts
from .builder import build_agent
from .models import EditorOutput, SupervisorOutput, WriterOutput

factchecker_tools = [web_search]
researcher_tools = [web_search, scrape_article, search_verstka_texts]
all_tools = factchecker_tools + researcher_tools
tools_by_name = {tool.name: tool for tool in all_tools}

writer_llm = build_agent(agents_config.writer, settings).with_structured_output(WriterOutput)
editor_llm = build_agent(agents_config.editor, settings).with_structured_output(EditorOutput)
factchecker_llm = build_agent(agents_config.factchecker, settings).bind_tools(factchecker_tools)
supervisor_llm = build_agent(agents_config.supervisor, settings).with_structured_output(SupervisorOutput)
researcher_llm = build_agent(agents_config.researcher, settings).bind_tools(researcher_tools)
swarm_writer_llm = build_agent(agents_config.swarm_writer, settings)
