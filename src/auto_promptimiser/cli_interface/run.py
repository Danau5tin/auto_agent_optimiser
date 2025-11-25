"""
CLI v2: Checks for eval callback and project_breakdown before allowing optimisation.
"""

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from auto_promptimiser.agent.local_tools.local_bash_executor import LocalBashExecutor
from auto_promptimiser.agent.local_tools.local_file_manager import LocalFileManager
from auto_promptimiser.agent.optimiser_agent import OptimiserAgent
from auto_promptimiser.core.project_breakdown import load_project_breakdown
from auto_promptimiser.storage.eval_storage_nosql import NoSQLEvalStorage
from auto_promptimiser.storage.message_storage_nosql import NoSQLMessageStorage

app = typer.Typer(
    name="auto-promptimiser",
    help="CLI agent for analyzing and optimizing AI agent implementations",
    add_completion=False,
)
console = Console()


def find_python_files(root_dir: Path) -> list[Path]:
    """Find all Python files in the project, excluding common ignore patterns."""
    ignore_dirs = {'.venv', 'venv', '__pycache__', '.git', 'node_modules', '.pytest_cache', 'dist', 'build', '.eggs'}

    python_files = []
    for path in root_dir.rglob('*.py'):
        if not any(parent.name in ignore_dirs for parent in path.parents):
            python_files.append(path)

    return sorted(python_files)


def find_eval_callback(root_dir: Path) -> Path | None:
    """Find eval callback file by looking for files with 'eval' in the name."""
    python_files = find_python_files(root_dir)

    for py_file in python_files:
        # Look for files with 'eval' in the name (case insensitive)
        if 'eval' in py_file.name.lower():
            return py_file

    return None


def scan_and_display_files(root_dir: Path) -> list[Path]:
    """Scan for Python files and display them in a table."""
    with console.status("[bold green]Scanning for Python files...", spinner="dots"):
        python_files = find_python_files(root_dir)

    if not python_files:
        console.print("[yellow]No Python files found.[/yellow]\n")
        return []

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan", no_wrap=False)

    for py_file in python_files:
        try:
            relative_path = py_file.relative_to(root_dir)
        except ValueError:
            relative_path = py_file
        table.add_row(str(relative_path))

    console.print(f"\n[bold green]Found {len(python_files)} Python file(s):[/bold green]")
    console.print(table)
    console.print()

    return python_files


def check_prerequisites(root_dir: Path) -> tuple[bool, Path | None, Path | None]:
    """
    Check if both eval callback and project_breakdown exist.

    Returns:
        (ready, eval_file, breakdown_file) where ready is True if both files exist
    """
    breakdown_file = root_dir / "project_breakdown.yaml"
    eval_file = find_eval_callback(root_dir)

    breakdown_exists = breakdown_file.exists()
    eval_exists = eval_file is not None

    return (breakdown_exists and eval_exists, eval_file, breakdown_file if breakdown_exists else None)


def load_eval_callback(eval_file: Path):
    """
    Dynamically load the eval_callback function from the provided Python file.

    Looks for a function named 'eval_callback' in the module.
    """
    try:
        # Load the module dynamically
        spec = importlib.util.spec_from_file_location("eval_module", eval_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec from {eval_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules["eval_module"] = module
        spec.loader.exec_module(module)

        # Look for eval_callback function
        if not hasattr(module, "eval_callback"):
            raise AttributeError(f"Module {eval_file} does not contain 'eval_callback' function")

        return module.eval_callback
    except Exception as e:
        console.print(f"[bold red]Error loading eval callback:[/bold red] {e}")
        raise


def interactive():
    root_dir = Path.cwd()

    # Show warning that this CLI is not ready for use
    console.print(Panel.fit(
        "[bold red]WARNING: NOT READY FOR USE[/bold red]\n\n"
        "This CLI is a proof-of-concept demonstrating what the future of this\n"
        "project could look like. The interface exists but has not been fully\n"
        "tested or validated for real-world use.\n\n"
        "See the README for details on the project's current status.",
        border_style="red",
        title="[bold red]Proof of Concept[/bold red]"
    ))
    console.print()

    console.print(Panel.fit(
        f"[bold cyan]Auto-Promptimiser Interactive Mode[/bold cyan]\n"
        f"Project root: [yellow]{root_dir}[/yellow]",
        border_style="cyan"
    ))

    while True:
        # Check prerequisites
        ready, eval_file, breakdown_file = check_prerequisites(root_dir)

        console.print()

        # Display status of prerequisites
        if breakdown_file:
            console.print("[bold green]✓[/bold green] Found [cyan]project_breakdown[/cyan]")
        else:
            console.print("[bold red]✗[/bold red] Missing [cyan]project_breakdown[/cyan]")

        if eval_file:
            try:
                relative_eval = eval_file.relative_to(root_dir)
            except ValueError:
                relative_eval = eval_file
            console.print(f"[bold green]✓[/bold green] Found eval callback: [cyan]{relative_eval}[/cyan]")
        else:
            console.print("[bold red]✗[/bold red] No eval callback found (looking for files with 'eval' in name)")

        console.print()

        # Build menu choices based on prerequisites
        if ready:
            choices = [
                "Run optimisation",
                "Re-scan project",
                "Exit"
            ]
        else:
            choices = [
                "Re-scan project",
                "Exit"
            ]

        choice = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=questionary.Style([
                ('highlighted', 'fg:cyan bold'),
                ('pointer', 'fg:cyan bold'),
            ])
        ).ask()

        if choice == "Exit" or choice is None:
            console.print("\n[bold green]Goodbye![/bold green]")
            raise typer.Exit(0)

        elif choice == "Re-scan project":
            console.print()
            scan_and_display_files(root_dir)

        elif choice == "Run optimisation" and ready and eval_file is not None:
            console.print("\n[bold yellow]Starting optimisation...[/bold yellow]")
            console.print(f"Using eval callback: [cyan]{eval_file.relative_to(root_dir)}[/cyan]")
            console.print("Using breakdown: [cyan]project_breakdown.yaml[/cyan]\n")

            try:
                # Load the eval callback from the detected file
                eval_callback = load_eval_callback(eval_file)

                breakdown_path = root_dir / "project_breakdown.yaml"
                project_breakdown = load_project_breakdown(breakdown_path)

                # Instantiate storage and optimizer agent
                eval_storage = NoSQLEvalStorage(db_path=str(root_dir / "eval_results.json"))
                message_storage = NoSQLMessageStorage(db_path=str(root_dir / "message_history.json"))
                file_manager = LocalFileManager(root_dir=root_dir)
                bash_executor = LocalBashExecutor(root_dir=root_dir)

                opt_agent = OptimiserAgent(
                    eval_storage=eval_storage,
                    message_storage=message_storage,
                    file_manager=file_manager,
                    bash_executor=bash_executor,
                    eval_callback=eval_callback,
                    project_breakdown=project_breakdown,
                )

                # Run the optimisation (it's async)
                console.print("[bold green]Running optimisation...[/bold green]\n")
                asyncio.run(opt_agent.optimise())

                console.print("\n[bold green]optimisation complete![/bold green]\n")

                # Close the storage connection
                eval_storage.close()
                message_storage.close()

                # End session
                break

            except Exception as e:
                console.print(f"\n[bold red]Error during optimisation:[/bold red] {e}\n")
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]\n")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Auto-Promptimiser CLI v2 - Interactive agent for analyzing and optimizing AI agent implementations.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    if ctx.invoked_subcommand is None:
        interactive()


if __name__ == "__main__":
    app()
