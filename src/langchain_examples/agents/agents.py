from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..tools.scrapers import scrape_article
from .models import EditorOutput, FactCheckerOutput
from .prompts import EDITOR_PROMPT, FACTCHECKER_PROMPT, WRITER_PROMPT
from .state import PipelineState

tools = [scrape_article]
tools_by_name = {tool.name: tool for tool in tools}

writer_llm = ChatOpenAI(model="gpt-5-mini", temperature=0.7)
writer_llm = writer_llm.bind_tools(tools)

editor_llm = ChatOpenAI(model="gpt-5-mini", temperature=0.3)
editor_llm = editor_llm.with_structured_output(EditorOutput)

factchecker_llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
factchecker_llm = factchecker_llm.with_structured_output(FactCheckerOutput)


def tool_node(state: PipelineState) -> dict:
    """Performs the tool call and updates article content."""

    result_messages = []
    new_article_content = []

    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])

        result_messages.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
        new_article_content.append(observation)

    return {"messages": result_messages, "article_content": new_article_content}


def user_node(state: PipelineState) -> dict:
    """Get user input."""
    if state["drafts"]:
        print("Here is the last draft:")
        print(state["drafts"][-1])
        user_input = input("Write your feedback or 'exit' to exit: ")
    else:
        print("Enter task or write 'exit' to exit:")
        user_input = input("User: ")
    if user_input.lower() in ["exit", "quit", "stop", "bye", "done"]:
        return {"user_approved": True}
    return {
        "messages": [HumanMessage(content=user_input)],
        "editor_approved": False,
        "factchecker_approved": False,
    }


def writer_node(state: PipelineState) -> dict:
    """Generate script from article."""
    print(f"Writer: iteration {state['iteration']}")

    prompt = ChatPromptTemplate([("system", WRITER_PROMPT), ("placeholder", "{messages}")])
    chain = prompt | writer_llm

    response = chain.invoke({"messages": state["messages"]})

    if response.tool_calls:
        print(f"→ Writer wants to call tools: {[tc['name'] for tc in response.tool_calls]}")
        return {
            "messages": [response],
        }

    content = response.content
    script = ""

    if "REASONING:" in content and "SCRIPT:" in content:
        parts = content.split("SCRIPT:")
        script = parts[1].strip()
    else:
        script = content

    writer_message = AIMessage(content=response.content, name="writer")

    return {
        "messages": [writer_message],
        "drafts": [script],
        "iteration": state["iteration"] + 1,
    }


def editor_node(state: PipelineState) -> dict:
    """Review script for quality."""
    print("Editor: reviewing script")

    messages = [m for m in state["messages"] if getattr(m, "name", None) != "factchecker"]

    prompt = ChatPromptTemplate(
        [
            ("system", EDITOR_PROMPT),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | editor_llm

    response: EditorOutput = chain.invoke(
        {
            "messages": messages,
        }
    )

    feedback_message = AIMessage(content=response.feedback, name="editor")

    if response.approved:
        return {"messages": [feedback_message], "editor_approved": True}
    else:
        return {"messages": [feedback_message], "editor_approved": False}


def factchecker_node(state: PipelineState) -> dict:
    """Check facts in script."""
    print("FactChecker: verifying facts")

    messages = [
        m for m in state["messages"] if not isinstance(m, HumanMessage) and getattr(m, "name", None) != "editor"
    ]

    prompt = ChatPromptTemplate(
        [
            ("system", FACTCHECKER_PROMPT),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | factchecker_llm

    response: FactCheckerOutput = chain.invoke(
        {
            "messages": messages,
        }
    )

    feedback_message = AIMessage(content=response.feedback, name="factchecker")

    if response.approved:
        return {"messages": [feedback_message], "factchecker_approved": True}
    else:
        return {"messages": [feedback_message], "factchecker_approved": False}
