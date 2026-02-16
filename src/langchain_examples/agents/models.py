from pydantic import BaseModel, Field


class WriterOutput(BaseModel):
    """Output from the Writer agent containing reasoning and the video script."""

    reasoning: str = Field(description="CHAIN OF THOUGHT: внутренний мыслительный процесс — определение стадии (A/B/C), анализ задачи, план сценария, замечания. Сюда НЕ входит текст сценария.")
    draft: str = Field(description="DRAFT: ПОЛНЫЙ текст видеосценария для устного произнесения + источники в конце. ВЕСЬ сценарий пишется ТОЛЬКО сюда. Поле НЕ может быть пустым.")


class EditorOutput(BaseModel):
    """Output from the Editor agent evaluating script quality."""

    approved: bool = Field(
        description="Whether the script meets professional news media standards: matches user request, strong hook, clarity, proper length (700-1000 chars), and logical structure."
    )
    feedback: str = Field(
        description="If approved: specific reasons why it meets standards. If rejected: specific actionable feedback for improvement (hook strength, clarity, length, structure issues)."
    )


class FactCheckerOutput(BaseModel):
    """Output from the FactChecker agent verifying factual accuracy."""

    approved: bool = Field(
        description="Whether ALL facts in the script come directly from the article without distortion, exaggeration, or external claims."
    )
    feedback: str = Field(
        description="If verified: confirmation that facts are accurate. If issues found: list specific facts not in article, distorted facts, or unsupported claims."
    )


class SupervisorOutput(BaseModel):
    """Supervisor's routing decision."""

    reasoning: str = Field(description="Brief explanation of why this agent should be called next")
    next_agent: str = Field(
        description="The next agent to call: 'researcher', 'swarm', 'writer', 'editor', 'factchecker', or 'finish'"
    )
