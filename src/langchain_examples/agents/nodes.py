import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed

from langsmith import traceable
from langchain_examples.agents.utils import filter_messages
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

from langchain_examples.agents.agents import (
    editor_llm,
    factchecker_llm,
    researcher_llm,
    swarm_writer_llm,
    tools_by_name,
    writer_llm,
)
from langchain_examples.agents.state import PipelineState
from langchain_examples.display import (
    processing,
    show_agent_output,
    show_draft,
    show_tool_call,
    show_user_prompt,
)
from langchain_examples.logging import get_logger
from langchain_examples.agents.utils import analyze_script
from langchain_examples.tools.agent_tools import scrape_article, scrape_telegram_post

from .models import EditorOutput, WriterOutput
from ..config import agents_config

logger = get_logger(__name__)


def _ensure_str(content) -> str:
    """Normalize LLM response content to string. Gemini can return content as:
    - str (normal)
    - list of str/dict parts (multi-part response)
    - dict with 'text' key
    Grounding metadata dicts (with 'signature'/'extras') are filtered out."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "text" in content:
            return content["text"]
        if "signature" in content or "extras" in content:
            return ""
        return str(content)
    if isinstance(content, list):
        parts = []
        for part in content:
            text = _ensure_str(part)
            if text:
                parts.append(text)
        result = "\n".join(parts)
        if not result:
            logger.warning(
                "_ensure_str: all %d parts filtered out, types: %s", len(content), [type(p).__name__ for p in content]
            )
        return result
    return str(content)


def _log_state(state: PipelineState, node_name: str) -> None:
    """Log current state snapshot for debugging."""
    logger.debug(
        "[%s] State: iteration=%d, editor_approved=%s, factchecker_approved=%s, "
        "total_messages=%d, total_drafts=%d, last_agent=%s",
        node_name,
        state["iteration"],
        state["editor_approved"],
        state["factchecker_approved"],
        len(state["messages"]),
        len(state["drafts"]),
        state.get("last_agent", "none"),
    )


def _log_messages(messages: list, node_name: str) -> None:
    """Log full messages that agent will receive."""
    logger.debug("[%s] %d messages:", node_name, len(messages))
    for i, msg in enumerate(messages):
        name = getattr(msg, "name", None) or type(msg).__name__
        tool_calls = getattr(msg, "tool_calls", None)
        logger.debug(
            "[%s] [%d] %s | tool_calls=%s | content_type=%s | content=%s",
            node_name,
            i,
            name,
            [tc["name"] for tc in tool_calls] if tool_calls else None,
            type(msg.content).__name__,
            repr(msg.content)[:1000],
        )


URL_PATTERN = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:"
    r"t\.me/[^\s<>\"{}|\\^`\[\]]+"
    r"|"
    r"[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}"
    r"[^\s<>\"{}|\\^`\[\]]*"
    r")"
)


def normalize_url(url: str) -> str:
    """Add https:// if missing."""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def tool_node(state: PipelineState) -> dict:
    """Execute tool calls and return results as messages."""
    _log_state(state, "tools")
    tool_calls = state["messages"][-1].tool_calls
    logger.debug(
        "[tools] %d tool calls from %s: %s", len(tool_calls), state.get("last_agent"), [tc["name"] for tc in tool_calls]
    )
    result_messages = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        show_tool_call(tool_name, tool_args)

        tool = tools_by_name[tool_name]
        with processing("tool"):
            observation = tool.invoke(tool_args)

        result_messages.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))

    return {"messages": result_messages}


def user_node(state: PipelineState) -> dict:
    """Get user input - text content, feedback, or message with URLs."""
    _log_state(state, "user")
    has_drafts = bool(state["drafts"])

    if has_drafts:
        show_draft(state["drafts"][-1], state["iteration"])

    user_input = show_user_prompt(has_drafts)

    if user_input.lower() in ["exit", "quit", "stop", "bye", "done"]:
        return {"user_approved": True}

    article_content = []
    urls = URL_PATTERN.findall(user_input)

    if urls:
        for url in urls:
            normalized = normalize_url(url)
            with processing("scraping"):
                if "t.me/" in normalized:
                    result = scrape_telegram_post.invoke({"url": normalized})
                else:
                    result = scrape_article.invoke({"url": normalized})
            article_content.append(result)

    # First iteration without URLs - text is the content
    if not has_drafts and not urls:
        article_content.append(user_input)

    return {
        "messages": [HumanMessage(content=user_input)],
        "article_content": article_content,
        "editor_approved": False,
        "factchecker_approved": False,
        "editor_iteration": 0,
        "factchecker_iteration": 0,
        "last_agent": "user",
    }


@traceable(name="writer", run_type="chain", metadata={**agents_config.writer.model_dump()})
def writer_node(state: PipelineState) -> dict:
    """Generate script from article."""
    _log_state(state, "writer")
    logger.info("Writer: iteration %d", state["iteration"])

    if state["last_agent"] == "editor":
        messages = filter_messages(
            state["messages"],
            [
                {"agent": "human", "count": 1},
                {"agent": "researcher", "count": 1},
                {"agent": "swarm", "count": 1},
                {"agent": "writer", "count": 5},
                {"agent": "editor", "count": 5},
            ],
        )

    elif state["last_agent"] == "factchecker":
        messages = filter_messages(
            state["messages"],
            [
                {"agent": "human", "count": 1},
                {"agent": "writer", "count": 5},
                {"agent": "factchecker", "count": 5},
            ],
        )

    else:
        messages = filter_messages(
            state["messages"],
            [
                {"agent": "human", "count": 1},
                {"agent": "researcher", "count": 1},
                {"agent": "swarm", "count": 1},
            ],
        )

    if state["article_content"]:
        article_text = "\n\n---\n\n".join(state["article_content"])
        messages.insert(0, SystemMessage(content=f"Article content (already scraped by user):\n\n{article_text}"))

    _log_messages(messages, "writer")

    prompt = ChatPromptTemplate([("system", agents_config.writer.prompt), ("placeholder", "{messages}")])
    chain = prompt | writer_llm

    with processing("writer"):
        response: WriterOutput = chain.invoke({"messages": messages})

    show_agent_output("writer", response.reasoning)

    new_iteration = state["iteration"] + 1
    show_draft(response.draft, new_iteration)

    writer_message = AIMessage(content=response.draft, name="writer")

    return {
        "messages": [writer_message],
        "drafts": [response.draft],
        "iteration": new_iteration,
        "last_agent": "writer",
    }


@traceable(name="editor", run_type="chain", metadata={**agents_config.editor.model_dump()})
def editor_node(state: PipelineState) -> dict:
    """Review script for quality."""
    _log_state(state, "editor")
    logger.info("Editor: reviewing script")

    messages = filter_messages(
        state["messages"],
        [
            {"agent": "human", "count": 1},
            {"agent": "writer", "count": 2},
            {"agent": "editor", "count": 1},
        ],
    )

    if state["drafts"]:
        metrics = analyze_script(state["drafts"][-1])
        metrics_msg = (
            f"Script metrics: {metrics['characters']} characters, {metrics['words']} words, "
            f"estimated speaking time {metrics['speaking_time_formatted']} ({metrics['speaking_time_seconds']}s)"
        )
        messages.insert(0, SystemMessage(content=metrics_msg))
        logger.debug("[editor] %s", metrics_msg)

    _log_messages(messages, "editor")

    prompt = ChatPromptTemplate(
        [
            ("system", agents_config.editor.prompt),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | editor_llm

    with processing("editor"):
        response: EditorOutput = chain.invoke({"messages": messages})

    logger.debug("[editor] Verdict: approved=%s, feedback_length=%d", response.approved, len(response.feedback))

    feedback_message = AIMessage(content=response.feedback, name="editor")
    show_agent_output("editor", response.feedback, approved=response.approved)

    return {
        "messages": [feedback_message],
        "editor_approved": response.approved,
        "editor_iteration": state.get("editor_iteration", 0) + 1,
        "last_agent": "editor",
    }


@traceable(name="factchecker", run_type="chain", metadata={**agents_config.factchecker.model_dump()})
def factchecker_node(state: PipelineState) -> dict:
    """Check facts in script."""
    _log_state(state, "factchecker")
    logger.info("FactChecker: verifying facts")

    messages = []

    if state["article_content"]:
        article_text = "\n\n---\n\n".join(state["article_content"])
        messages.append(SystemMessage(content=f"Source article to verify facts against:\n\n{article_text}"))
        logger.debug(
            "[factchecker] Article content: %d sources, total %d chars",
            len(state["article_content"]),
            len(article_text),
        )

    filtered = filter_messages(
        state["messages"],
        [
            {"agent": "human", "count": 1},
            {"agent": "writer", "count": 1},
            {"agent": "researcher", "count": 1},
            {"agent": "factchecker", "count": 20},
        ],
    )
    messages.extend(filtered)

    _log_messages(messages, "factchecker")

    prompt = ChatPromptTemplate(
        [
            ("system", agents_config.factchecker.prompt),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | factchecker_llm

    with processing("factchecker"):
        response = chain.invoke({"messages": messages})

    if response.tool_calls:
        response = AIMessage(content=_ensure_str(response.content), tool_calls=response.tool_calls, name="factchecker")
        logger.info("FactChecker wants to call tools: %s", [tc["name"] for tc in response.tool_calls])
        return {"messages": [response], "last_agent": "factchecker"}

    content = _ensure_str(response.content)
    approved = "APPROVED" in content.upper() and "REJECTED" not in content.upper()
    logger.debug("[factchecker] Verdict: %s, content_length=%d", "APPROVED" if approved else "REJECTED", len(content))

    feedback_message = AIMessage(content=content, name="factchecker")
    show_agent_output("factchecker", content, approved=approved)

    return {
        "messages": [feedback_message],
        "factchecker_approved": approved,
        "factchecker_iteration": state.get("factchecker_iteration", 0) + 1,
        "last_agent": "factchecker",
    }


@traceable(name="researcher", run_type="chain", metadata={**agents_config.researcher.model_dump()})
def researcher_node(state: PipelineState) -> dict:
    """Research the topic before writing begins."""
    _log_state(state, "researcher")
    logger.info("Researcher: gathering context and angles")

    messages = list(state["messages"])
    logger.debug(
        "[researcher] Input messages: %d, article_content: %d sources", len(messages), len(state["article_content"])
    )

    if state["article_content"]:
        article_text = "\n\n---\n\n".join(state["article_content"])
        messages.insert(
            0,
            SystemMessage(content=f"Article content (already scraped by user):\n\n{article_text}"),
        )

    prompt = ChatPromptTemplate([("system", agents_config.researcher.prompt), ("placeholder", "{messages}")])
    chain = prompt | researcher_llm

    with processing("researcher"):
        response = chain.invoke({"messages": messages})

    if response.tool_calls:
        response = AIMessage(content=_ensure_str(response.content), tool_calls=response.tool_calls, name="researcher")
        logger.info("Researcher wants to call tools: %s", [tc["name"] for tc in response.tool_calls])
        return {
            "messages": [response],
            "last_agent": "researcher",
        }

    content = _ensure_str(response.content)
    research_message = AIMessage(content=content, name="researcher")
    show_agent_output("researcher", content)

    return {
        "messages": [research_message],
        "last_agent": "researcher",
        "research_output": content,
    }


SWARM_ANGLES = ["HUMOR", "DRAMA", "HISTORY REFERENCES"]

SWARM_SUMMARIZE_PROMPT = """Ты — редактор креативного отдела. Тебе дали сырые идеи от трёх креативщиков (HUMOR, DRAMA, HISTORY REFERENCES).

Твоя задача — сохранить все ценные идеи и собрать их в структурированный документ с буллетами.

Правила:
- Убирай только дубли и откровенно слабые идеи — всё остальное оставляй
- Группируй по смыслу, НЕ по углам
- Каждый буллет — 1-3 предложения, сохраняй детали и нюансы
- Итого 12-20 буллетов
- Формулируй чётко, без воды, но не обрезай смысл ради краткости
- Сохраняй отсылки, метафоры и сильные фразы дословно

Формат ответа:

**Лучшие идеи и находки:**

- [идея/находка]
- [идея/находка]
...

**Сильные формулировки:**

- [фраза или метафора]
- [фраза или метафора]
...

**Лучшие отсылки:**

- [отсылка и почему она работает]
..."""


@traceable(name="swarm_writer", run_type="chain", metadata={**agents_config.swarm_writer.model_dump()})
def swarm_writer_node(state: PipelineState) -> dict:
    """Run swarm writers once, summarize best ideas into bullets."""
    _log_state(state, "swarm")
    logger.info("Swarm: brainstorming %d angles", len(SWARM_ANGLES))

    base_messages = []

    if state["article_content"]:
        article_text = "\n\n---\n\n".join(state["article_content"])
        base_messages.append(SystemMessage(content=f"Article content:\n\n{article_text}"))

    if state.get("research_output"):
        base_messages.append(HumanMessage(content=f"Research:\n\n{state['research_output']}"))

    prompt = ChatPromptTemplate([("system", agents_config.swarm_writer.prompt), ("placeholder", "{messages}")])
    chain = prompt | swarm_writer_llm

    def run_angle(angle: str) -> tuple[str, str]:
        messages = base_messages + [HumanMessage(content=f"Your assigned angle is: {angle}. Write your ideas/draft now.")]
        response = chain.invoke({"messages": messages})
        return angle, _ensure_str(response.content)

    drafts_map = {}
    with ThreadPoolExecutor(max_workers=len(SWARM_ANGLES)) as executor:
        futures = {executor.submit(contextvars.copy_context().run, run_angle, angle): angle for angle in SWARM_ANGLES}
        for future in as_completed(futures):
            angle, content = future.result()
            drafts_map[angle] = content
            logger.info("Swarm: %s completed", angle)

    drafts = [f"## {angle}\n{drafts_map[angle]}" for angle in SWARM_ANGLES]

    combined_raw = "\n\n---\n\n".join(drafts)
    logger.info("Swarm: summarizing %d angles into best ideas", len(SWARM_ANGLES))

    summarize_messages = [
        SystemMessage(content=SWARM_SUMMARIZE_PROMPT),
        HumanMessage(content=f"Вот сырые идеи от креативщиков:\n\n{combined_raw}"),
    ]

    with processing("swarm"):
        summary_response = swarm_writer_llm.invoke(summarize_messages)

    summary = _ensure_str(summary_response.content)
    logger.info("Swarm: summary ready, %d chars", len(summary))

    swarm_message = AIMessage(content=summary, name="swarm")
    show_agent_output("swarm", summary)

    return {
        "messages": [swarm_message],
        "last_agent": "swarm",
        "swarm_output": summary,
    }
