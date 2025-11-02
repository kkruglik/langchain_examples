from pydantic import BaseModel, Field


class WriterOutput(BaseModel):
    """Output from the Writer agent containing reasoning and the video script."""

    reasoning: str = Field(
        description="Your thinking process - which angle you chose and why. Explain the newsworthy angle selected and rationale."
    )
    draft: str = Field(
        description="The actual video script - 700-1000 characters. Professional news media style with strong opening hook, clear facts, and journalistic tone."
    )


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
