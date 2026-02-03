from langchain_examples.agents.utils import filter_messages
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

from langchain_examples.agents.agents import (
    editor_llm,
    factchecker_llm,
    researcher_llm,
    supervisor_llm,
    swarm_writer_llm,
    tools_by_name,
    writer_llm,
)
from langchain_examples.agents.state import PipelineState
from langchain_examples.config import agents_config
from langchain_examples.display import (
    processing,
    show_agent_output,
    show_draft,
    show_routing,
    show_tool_call,
    show_user_prompt,
)
from langchain_examples.logging import get_logger
from langchain_examples.tools.scrapers import scrape_article, scrape_telegram_post

from .models import SupervisorOutput, WriterOutput

logger = get_logger(__name__)


def track_transition(state: PipelineState, current_node: str) -> dict[str, int]:
    """Track node transition and return updated transitions dict."""
    transitions = dict(state.get("node_transitions") or {})
    last = state.get("last_agent", "")

    if last:
        key = f"{last}→{current_node}"
        transitions[key] = transitions.get(key, 0) + 1
        logger.debug("Transition: %s (count: %d)", key, transitions[key])

    return transitions


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
    transitions = track_transition(state, "tools")
    result_messages = []

    for tool_call in state["messages"][-1].tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        show_tool_call(tool_name, tool_args)

        tool = tools_by_name[tool_name]
        with processing("tool"):
            observation = tool.invoke(tool_args)

        result_messages.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))

    return {"messages": result_messages, "node_transitions": transitions}


def user_node(state: PipelineState) -> dict:
    """Get user input - text content, feedback, or message with URLs."""
    transitions = track_transition(state, "user")
    has_drafts = bool(state["drafts"])

    if has_drafts:
        show_draft(state["drafts"][-1], state["iteration"])

    user_input = show_user_prompt(has_drafts)

    if user_input.lower() in ["exit", "quit", "stop", "bye", "done"]:
        return {"user_approved": True, "node_transitions": transitions}

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
        "node_transitions": transitions,
        "last_agent": "user",
    }


def writer_node(state: PipelineState) -> dict:
    """Generate script from article."""
    transitions = track_transition(state, "writer")
    logger.info("Writer: iteration %d", state["iteration"])

    messages = filter_messages(
        state["messages"],
        [
            {"agent": "human", "count": 1},
            {"agent": "researcher", "count": 1},
            {"agent": "swarm", "count": 1},
            {"agent": "writer", "count": 2},
            {"agent": "editor", "count": 2},
            {"agent": "factchecker", "count": 1},
        ],
    )

    logger.debug(f"Filtered messages: {messages}")

    prompt = ChatPromptTemplate([("system", agents_config.writer.prompt), ("placeholder", "{messages}")])
    chain = prompt | writer_llm

    with processing("writer"):
        response: WriterOutput = chain.invoke({"messages": messages})

    show_agent_output("writer", response.reasoning)

    new_iteration = state["iteration"] + 1
    show_draft(response.draft, new_iteration)

    writer_message = AIMessage(content=f"{response.reasoning}\n\n---\n\n{response.draft}", name="writer")

    return {
        "messages": [writer_message],
        "drafts": [response.draft],
        "iteration": new_iteration,
        "node_transitions": transitions,
        "last_agent": "writer",
    }


def editor_node(state: PipelineState) -> dict:
    """Review script for quality."""
    transitions = track_transition(state, "editor")
    logger.info("Editor: reviewing script")

    messages = filter_messages(
        state["messages"],
        [
            {"agent": "human", "count": 1},
            {"agent": "writer", "count": 2},
            {"agent": "editor", "count": 1},
        ],
    )

    prompt = ChatPromptTemplate(
        [
            ("system", agents_config.editor.prompt),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | editor_llm

    with processing("editor"):
        response = chain.invoke({"messages": messages})

    if response.tool_calls:
        response = AIMessage(content=response.content, tool_calls=response.tool_calls, name="editor")
        logger.info("Editor wants to call tools: %s", [tc["name"] for tc in response.tool_calls])
        return {"messages": [response], "last_agent": "editor", "node_transitions": transitions}

    content = response.content
    approved = "APPROVED" in content.upper() and "REJECTED" not in content.upper()

    feedback_message = AIMessage(content=content, name="editor")
    show_agent_output("editor", content, approved=approved)

    return {
        "messages": [feedback_message],
        "editor_approved": approved,
        "node_transitions": transitions,
        "last_agent": "editor",
    }


def factchecker_node(state: PipelineState) -> dict:
    """Check facts in script."""
    transitions = track_transition(state, "factchecker")
    logger.info("FactChecker: verifying facts")

    messages = []

    # Article content (source of truth) - not in message history
    if state["article_content"]:
        article_text = "\n\n---\n\n".join(state["article_content"])
        messages.append(SystemMessage(content=f"Source article to verify facts against:\n\n{article_text}"))

    messages.extend(
        filter_messages(
            state["messages"],
            [
                {"agent": "writer", "count": 1},
                {"agent": "factchecker", "count": 1},
            ],
        )
    )

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
        response = AIMessage(content=response.content, tool_calls=response.tool_calls, name="factchecker")
        logger.info("FactChecker wants to call tools: %s", [tc["name"] for tc in response.tool_calls])
        return {"messages": [response], "last_agent": "factchecker", "node_transitions": transitions}

    content = response.content
    approved = "APPROVED" in content.upper() and "REJECTED" not in content.upper()

    feedback_message = AIMessage(content=content, name="factchecker")
    show_agent_output("factchecker", content, approved=approved)

    return {
        "messages": [feedback_message],
        "factchecker_approved": approved,
        "node_transitions": transitions,
        "last_agent": "factchecker",
    }


def supervisor_node(state: PipelineState) -> dict:
    """Supervisor decides which agent to call next."""
    transitions = track_transition(state, "supervisor")
    logger.info("Supervisor: analyzing state and deciding next step...")

    if state["iteration"] >= 20:
        logger.warning("Supervisor: max iterations reached, finishing")
        return {
            "messages": [AIMessage(content="Max iterations reached. Finishing with current draft.", name="supervisor")],
            "next_agent": "finish",
            "node_transitions": transitions,
            "last_agent": "supervisor",
        }

    state_info = (
        f"Current state: iteration={state['iteration']}, "
        f"editor_approved={state['editor_approved']}, "
        f"factchecker_approved={state['factchecker_approved']}, "
        f"node_transitions={state.get('node_transitions', {})}"
    )

    messages = [SystemMessage(content=state_info), state["messages"][-1]]

    prompt = ChatPromptTemplate([("system", agents_config.supervisor.prompt), ("placeholder", "{messages}")])
    chain = prompt | supervisor_llm

    with processing("supervisor"):
        response: SupervisorOutput = chain.invoke({"messages": messages})

    show_agent_output("supervisor", response.reasoning)
    show_routing("supervisor", response.next_agent)

    return {
        "messages": [AIMessage(content=response.reasoning, name="supervisor")],
        "next_agent": response.next_agent,
        "node_transitions": transitions,
        "last_agent": "supervisor",
    }


def researcher_node(state: PipelineState) -> dict:
    """Research the topic before writing begins."""
    transitions = track_transition(state, "researcher")
    logger.info("Researcher: gathering context and angles")

    messages = list(state["messages"])

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
        response = AIMessage(content=response.content, tool_calls=response.tool_calls, name="researcher")
        logger.info("Researcher wants to call tools: %s", [tc["name"] for tc in response.tool_calls])
        return {
            "messages": [response],
            "last_agent": "researcher",
            "node_transitions": transitions,
        }

    research_message = AIMessage(content=response.content, name="researcher")
    show_agent_output("researcher", response.content)

    return {
        "messages": [research_message],
        "node_transitions": transitions,
        "last_agent": "researcher",
    }


SWARM_ANGLES = ["HUMOR", "DRAMA", "HISTORY REFERENCES"]


def swarm_node(state: PipelineState) -> dict:
    """Run swarm writers once, summarize into one message."""
    transitions = track_transition(state, "swarm")
    logger.info("Swarm: brainstorming %d angles", len(SWARM_ANGLES))

    base_messages = list(state["messages"])

    if state["article_content"]:
        article_text = "\n\n---\n\n".join(state["article_content"])
        base_messages.insert(
            0,
            SystemMessage(content=f"Article content:\n\n{article_text}"),
        )

    prompt = ChatPromptTemplate([("system", agents_config.swarm_writer.prompt), ("placeholder", "{messages}")])
    chain = prompt | swarm_writer_llm

    # Single round: each writer generates ideas from their angle
    drafts = []
    for i, angle in enumerate(SWARM_ANGLES):
        logger.info("Swarm: angle %s", angle)

        swarm_messages = base_messages + [
            HumanMessage(content=f"Your assigned angle is: {angle}. Write your ideas/draft now.")
        ]

        with processing("swarm"):
            response = chain.invoke({"messages": swarm_messages})

        drafts.append(f"## {angle}\n{response.content}")
        logger.info("Swarm: %s completed", angle)

    # Combine all into one message
    combined = "\n\n---\n\n".join(drafts)
    swarm_message = AIMessage(content=combined, name="swarm")
    show_agent_output("swarm", combined)

    return {
        "messages": [swarm_message],
        "node_transitions": transitions,
        "last_agent": "swarm",
    }
