from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..tools.scrapers import scrape_article
from .models import EditorOutput, FactCheckerOutput, WriterOutput
from .prompts import EDITOR_PROMPT, FACTCHECKER_PROMPT, WRITER_PROMPT
from .state import PipelineState

tools = [scrape_article]
tools_by_name = {tool.name: tool for tool in tools}

# writer_llm = create_agent("openai:gpt-5-mini", temperature=0.7, tools=tools)

writer_llm = ChatOpenAI(model="gpt-5-mini", temperature=0.7)
writer_llm = writer_llm.bind_tools(tools)

editor_llm = ChatOpenAI(model="gpt-5-mini", temperature=0.3)
editor_llm = editor_llm.with_structured_output(EditorOutput)

factchecker_llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
factchecker_llm = factchecker_llm.with_structured_output(FactCheckerOutput)


def user_input_node(state: PipelineState) -> dict:
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


def writer_agent(state: PipelineState) -> dict:
    """Generate script from article."""
    print(f"Writer: iteration {state['iteration']}")

    messages = [SystemMessage(content=WRITER_PROMPT)] + state["messages"]

    if state["article_content"]:
        article_text = "\n\n--- Additional Source ---\n".join(state["article_content"])
        messages.append(HumanMessage(content=f"Article:\n{article_text}"))

    tool_result = None

    while True:
        response = writer_llm.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                print(f"→ Tool call: {tool_call['name']} with args {tool_call['args']}")
                tool = tools_by_name[tool_call["name"]]
                tool_result = tool.invoke(tool_call["args"])

                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))

            continue

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
            "article_content": [tool_result] if tool_result else [],
        }


def editor_agent(state: PipelineState) -> dict:
    """Review script for quality."""
    print("Editor: reviewing script")

    article_text = "\n\n--- Additional Source ---\n".join(state["article_content"]) if state["article_content"] else ""

    prompt = ChatPromptTemplate(
        [
            ("system", EDITOR_PROMPT),
            ("placeholder", "{messages}"),
            ("human", "Article: {article_text}\n\nScript to review:\n{draft}"),
        ]
    )

    chain = prompt | editor_llm

    response: EditorOutput = chain.invoke(
        {
            "article_text": article_text,
            "draft": state["drafts"][-1],
            "messages": state["messages"],
        }
    )

    feedback_message = AIMessage(content=response.feedback, name="editor")

    if response.approved:
        return {"messages": [feedback_message], "editor_approved": True}
    else:
        return {"messages": [feedback_message], "editor_approved": False}


def factchecker_agent(state: PipelineState) -> dict:
    """Check facts in script."""
    print("FactChecker: verifying facts")

    article_text = "\n\n--- Additional Source ---\n".join(state["article_content"]) if state["article_content"] else ""

    prompt = ChatPromptTemplate(
        [
            ("system", FACTCHECKER_PROMPT),
            ("placeholder", "{messages}"),
            ("human", "Article: {article_text}\n\nScript to verify:\n{draft}"),
        ]
    )

    chain = prompt | factchecker_llm

    response: FactCheckerOutput = chain.invoke(
        {
            "article_text": article_text,
            "draft": state["drafts"][-1],
            "messages": state["messages"],
        }
    )

    feedback_message = AIMessage(content=response.feedback, name="factchecker")

    if response.approved:
        return {"messages": [feedback_message], "factchecker_approved": True}
    else:
        return {"messages": [feedback_message], "factchecker_approved": False}
