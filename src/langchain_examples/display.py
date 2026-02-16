from contextlib import contextmanager

from prompt_toolkit import prompt as pt_prompt
from rich.console import Console
from rich.panel import Panel

console = Console()


def _prompt_continuation(width, line_number, wrap_count):
    """Format line continuation for multiline input."""
    return "> "


AGENT_LABELS = {
    "writer": "Writer is drafting...",
    "editor": "Editor is reviewing...",
    "factchecker": "FactChecker is verifying...",
    "supervisor": "Supervisor is deciding...",
    "researcher": "Researcher is investigating...",
    "swarm": "Swarm Writers are drafting...",
    "scraping": "Scraping URL...",
    "tool": "Executing tool...",
}


@contextmanager
def processing(agent: str):
    """Show spinner while agent is processing."""
    label = AGENT_LABELS.get(agent, f"{agent} is processing...")
    with console.status(f"[bold cyan]{label}[/bold cyan]", spinner="dots"):
        yield


def show_agent_output(agent: str, content: str | list, approved: bool | None = None) -> None:
    """Display agent output in a styled panel."""
    if isinstance(content, list):
        content = "\n".join(str(part) for part in content)
    colors = {
        "writer": "blue",
        "editor": "yellow",
        "factchecker": "magenta",
        "supervisor": "cyan",
        "researcher": "green",
        "swarm": "bright_blue",
    }
    color = colors.get(agent, "white")

    title = agent.capitalize()
    if approved is not None:
        status = "[green]Approved[/green]" if approved else "[red]Rejected[/red]"
        title = f"{title} - {status}"

    console.print(Panel(content, title=title, border_style=color))


def show_draft(draft: str, iteration: int) -> None:
    """Display current draft."""
    console.print(Panel(draft, title=f"Draft v{iteration}", border_style="blue"))


def show_final_script(script: str) -> None:
    """Display final script."""
    console.print()
    console.print(Panel(script, title="Final Script", border_style="green", padding=(1, 2)))


def show_user_prompt(has_drafts: bool) -> str:
    """Show prompt and get multiline user input. Esc→Enter to submit."""
    hint = "Esc → Enter to submit, 'exit' to quit"
    if has_drafts:
        console.print(f"[bold]Your feedback[/bold] ({hint}):")
    else:
        console.print(f"[bold]Enter text or paste URL[/bold] ({hint}):")

    try:
        result = pt_prompt(
            "> ",
            multiline=True,
            prompt_continuation=_prompt_continuation,
        )
        return result.strip()
    except (EOFError, KeyboardInterrupt):
        return "exit"


def show_scraping(url: str) -> None:
    """Show scraping status."""
    console.print(f"[dim]Scraping: {url}[/dim]")


def show_info(message: str) -> None:
    """Show info message."""
    console.print(f"[dim]{message}[/dim]")


def show_error(message: str) -> None:
    """Show error message."""
    console.print(f"[red]{message}[/red]")


def show_routing(from_agent: str, to_agent: str) -> None:
    """Show routing decision."""
    console.print(f"[dim]{from_agent} -> {to_agent}[/dim]")


def show_tool_call(tool_name: str, args: dict) -> None:
    """Show tool being called."""
    args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
    console.print(f"[dim]Tool: {tool_name}({args_str})[/dim]")


def show_node_stats(transitions: dict[str, int]) -> None:
    """Display node transition statistics."""
    if not transitions:
        return

    console.print()
    console.print(Panel.fit("[bold]Node Communication Stats[/bold]", border_style="cyan"))

    # Sort by count (descending), then by name
    sorted_transitions = sorted(transitions.items(), key=lambda x: (-x[1], x[0]))

    for edge, count in sorted_transitions:
        console.print(f"  {edge}: [bold]{count}[/bold]")

    total = sum(transitions.values())
    console.print(f"\n  [dim]Total transitions: {total}[/dim]")


def show_config(config_file: str, agents_config) -> None:
    """Display loaded config summary to console."""
    console.print()
    console.print(f"[bold cyan]Config:[/bold cyan] {config_file}")
    console.print()

    for agent_name in ["supervisor", "writer", "editor", "factchecker", "researcher", "swarm_writer"]:
        agent_cfg = getattr(agents_config, agent_name)
        model = agent_cfg.model
        console.print(
            f"  [bold]{agent_name:<15}[/bold] "
            f"model=[green]{model.provider}:{model.name}[/green] "
            f"temp={model.temperature} "
            f"prompt=[dim]{agent_cfg.prompt_path or 'none'}[/dim]"
        )

    console.print()


def show_previous_state(state_values: dict) -> None:
    """Display previous run state when resuming."""
    console.print()
    console.rule("[bold cyan]PREVIOUS RUN STATE[/bold cyan]")

    # Show last draft
    if state_values.get("drafts"):
        last_draft = state_values["drafts"][-1]
        if len(last_draft) > 1000:
            last_draft = last_draft[:1000] + "..."
        console.print(Panel(last_draft, title="📝 Last Draft", border_style="blue"))

    # Show last messages
    if state_values.get("messages"):
        console.print("\n[bold]💬 Last 3 Messages:[/bold]")
        for msg in state_values["messages"][-3:]:
            name = getattr(msg, "name", None) or msg.__class__.__name__
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            console.print(f"  [bold]{name}:[/bold] {content}\n")

    # Show status
    console.print(f"[dim]Iteration: {state_values.get('iteration', 0)}[/dim]")

    editor = state_values.get("editor_approved", False)
    factchecker = state_values.get("factchecker_approved", False)
    editor_status = "[green]✓[/green]" if editor else "[red]✗[/red]"
    factchecker_status = "[green]✓[/green]" if factchecker else "[red]✗[/red]"
    console.print(f"[dim]Editor: {editor_status}  Factchecker: {factchecker_status}[/dim]")

    console.rule()
