from pydantic import BaseModel, Field


class WriterOutput(BaseModel):
    """Output from the Writer agent containing reasoning and the video script."""

    reasoning: str = Field(
        description="Мыслительный процесс: определение стадии (A/B/C), анализ брифа, план сценария (хук, блоки, закрытие), самопроверка по чеклисту. Не содержит текст сценария."
    )
    draft: str = Field(
        description="Полный текст видеосценария для устного произнесения. Только разговорный текст без рассуждений, заголовков и пометок. В конце — список источников [1] URL. Не может быть пустым."
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


class ImagePrompt(BaseModel):
    """A single image generation request."""

    label: str = Field(description="Short snake_case filename label, e.g. 'cover', 'protest_scene', 'chip_closeup'.")
    prompt: str = Field(description="Full descriptive image prompt in English. A narrative paragraph, not a keyword list. Max 480 tokens.")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio for this image. Default '16:9'. Use '9:16' for vertical, '1:1' for square.")


class ImagePromptsOutput(BaseModel):
    """Structured output from the illustrator LLM."""

    images: list[ImagePrompt] = Field(description="One entry per image to generate. Count and labels are determined by the user request and script content.")
