"""Saves pipeline outputs as DOCX files and collects image paths."""
from pathlib import Path

import pypandoc


def _save_docx(path: Path, content: str) -> None:
    lines = content.splitlines()
    cleaned = "\n".join("" if line.strip() == "---" else line for line in lines)
    pypandoc.convert_text(cleaned, "docx", format="markdown-yaml_metadata_block", outputfile=str(path))


def save_artifacts(result: dict) -> list[str]:
    """Save pipeline outputs as DOCX files + collect image paths. Returns file paths to upload."""
    run_dir = Path(result["run_dir"])
    paths = []

    if result.get("research_output"):
        p = run_dir / "research.docx"
        _save_docx(p, result["research_output"])
        paths.append(str(p))

    if result.get("swarm_output"):
        p = run_dir / "swarm.docx"
        _save_docx(p, result["swarm_output"])
        paths.append(str(p))

    if result.get("drafts"):
        p = run_dir / "script.docx"
        _save_docx(p, result["drafts"][-1])
        paths.append(str(p))

    paths.extend(result.get("image_paths", []))
    return paths
