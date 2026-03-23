from langchain_examples.config import agents_config, settings

from langchain_examples.agents.builder import build_agent
from langchain_examples.agents.models import EditorOutput, ImagePromptsOutput, WriterOutput
from langchain_examples.tools.agent_tools import scrape_article, search_verstka_texts, web_search_tavily

factchecker_tools = [web_search_tavily]
researcher_tools = [web_search_tavily, scrape_article, search_verstka_texts]
all_tools = factchecker_tools + researcher_tools
tools_by_name = {tool.name: tool for tool in all_tools}

writer_llm = build_agent(agents_config.writer, settings).with_structured_output(WriterOutput)
editor_llm = build_agent(agents_config.editor, settings).with_structured_output(EditorOutput)
factchecker_llm = build_agent(agents_config.factchecker, settings).bind_tools(factchecker_tools)
researcher_llm = build_agent(agents_config.researcher, settings).bind_tools(researcher_tools)
swarm_writer_llm = build_agent(agents_config.swarm_writer, settings)
illustrator_llm = build_agent(agents_config.illustrator, settings).with_structured_output(ImagePromptsOutput)
