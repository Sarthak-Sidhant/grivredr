"""
Interactive Terminal UI for Grivredr Training
Provides a user-friendly interface for training web scrapers with real-time progress tracking
"""

import asyncio
import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich.markdown import Markdown
    from rich import box
    from rich.live import Live
    from rich.logging import RichHandler

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' package not installed. Install with: pip install rich")

from config.settings import settings, AIProvider, BrowserType, TaskType, ModelConfig
from config.multi_provider_client import ai_client
from agents.orchestrator import Orchestrator
from loguru import logger


# Global state for TUI
class TUIState:
    """Manages TUI state and progress tracking"""

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.current_session: Optional[Dict[str, Any]] = None
        self.progress_tasks: Dict[str, TaskID] = {}
        self.training_log: List[Dict[str, Any]] = []
        self.current_phase = "idle"
        self.error_display: List[Dict[str, Any]] = []
        self.status_updates: List[str] = []

    def log(self, message: str, level: str = "info"):
        """Log a message to the training log"""
        self.training_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
            }
        )
        self.status_updates.append(f"[{level.upper()}] {message}")
        if len(self.status_updates) > 20:
            self.status_updates.pop(0)

    def add_error(self, error: str, phase: str, details: Optional[str] = None):
        """Add an error to display"""
        self.error_display.append(
            {
                "timestamp": datetime.now().isoformat(),
                "phase": phase,
                "error": error,
                "details": details,
            }
        )

    def clear_errors(self):
        """Clear error display"""
        self.error_display.clear()


state = TUIState()


class GrivredrTUI:
    """Interactive TUI for Grivredr training"""

    def __init__(self):
        if not RICH_AVAILABLE:
            print(
                "Error: rich package required for TUI. Install with: pip install rich"
            )
            sys.exit(1)

        self.console = Console()
        self.layout = Layout()
        self.setup_layout()

    def setup_layout(self):
        """Setup the TUI layout"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        self.layout["main"].split_row(
            Layout(name="progress", ratio=2), Layout(name="info", ratio=1)
        )

    def show_header(self, title: str = "Grivredr - AI-Powered Web Scraper Trainer"):
        """Show header"""
        header = Panel(Text(title, style="bold cyan"), box=box.DOUBLE, style="blue")
        self.layout["header"].update(header)

    def show_progress_panel(self, phase: str, current_step: str, progress: float):
        """Show progress panel with live updates"""
        progress_panel = Panel(
            f"[yellow]Phase:[/yellow] {phase}\n"
            f"[cyan]Current Step:[/cyan] {current_step}\n"
            f"[green]Progress:[/green] {progress:.1f}%",
            title="Training Progress",
            box=box.ROUNDED,
        )
        self.layout["progress"].update(progress_panel)

    def show_info_panel(self, info: Dict[str, Any]):
        """Show info panel with session details"""
        info_text = f"""
[yellow]Portal:[/yellow] {info.get("portal", "N/A")}
[cyan]District:[/cyan] {info.get("district", "N/A")}
[blue]URL:[/blue] {info.get("url", "N/A")}
[magenta]Model:[/magenta] {info.get("model", "N/A")}
[green]Browser:[/green] {info.get("browser", "N/A")}

[yellow]AI Providers:[/yellow]
"""
        for provider in info.get("providers", []):
            info_text += f"  • {provider}\n"

        info_panel = Panel(info_text.strip(), title="Session Info", box=box.ROUNDED)
        self.layout["info"].update(info_panel)

    def show_log_panel(self):
        """Show recent log entries"""
        if not state.status_updates:
            log_text = "No activity yet"
        else:
            log_text = "\n".join(state.status_updates[-10:])

        log_panel = Panel(
            log_text, title="Recent Activity", box=box.ROUNDED, border_style="dim"
        )
        self.layout["footer"].update(log_panel)

    def update_display(
        self,
        phase: str = "idle",
        current_step: str = "",
        progress: float = 0.0,
        session_info: Optional[Dict[str, Any]] = None,
    ):
        """Update the entire display"""
        self.show_header()
        self.show_progress_panel(phase, current_step, progress)
        if session_info:
            self.show_info_panel(session_info)
        self.show_log_panel()

    def welcome_screen(self) -> bool:
        """Show welcome screen and confirm to continue"""
        self.console.clear()

        welcome_text = """
[bold cyan]╔══════════════════════════════════════════════════════════╗
║                                                            ║
║        [bold yellow]Grivredr - AI Web Scraper Generator[/bold yellow]         ║
║                                                            ║
║  Train web scrapers using AI in minutes, not hours        ║
║                                                            ║
╚══════════════════════════════════════════════════════════╝[/bold cyan]

[bold white]Features:[/bold white]
  • Multiple AI Providers (Anthropic, OpenAI, Gemini, OpenRouter)
  • Granular Model Selection per Task
  • Browser Selection (Chromium, Firefox, WebKit)
  • Real-time Progress Tracking
  • Self-Healing Scrapers
  • Zero Ongoing AI Costs After Training

[bold yellow]Press Enter to continue or Ctrl+C to exit[/bold yellow]
"""

        self.console.print(Markdown(welcome_text))

        try:
            input()
            return True
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Goodbye![/yellow]")
            return False

    def select_ai_providers(self) -> List[AIProvider]:
        """Select AI providers to use"""
        self.console.clear()
        self.console.print("\n[bold cyan]Select AI Providers[/bold cyan]")
        self.console.print(
            "You can use multiple providers for redundancy or cost optimization.\n"
        )

        available_providers = [
            AIProvider.ANTHROPIC,
            AIProvider.OPENAI,
            AIProvider.GEMINI,
            AIProvider.OPENROUTER,
        ]

        selected_providers = []
        for provider in available_providers:
            has_key = settings.get_api_key_for_provider(provider) is not None
            status = "[green]✓[/green]" if has_key else "[red]✗[/red]"

            if Confirm.ask(
                f"{status} Use {provider.value}?", default=True if has_key else False
            ):
                selected_providers.append(provider)

        if not selected_providers:
            self.console.print(
                "\n[red]Error: At least one AI provider must be selected![/red]"
            )
            return self.select_ai_providers()

        return selected_providers

    def configure_task_models(self) -> Dict[TaskType, ModelConfig]:
        """Configure models for each task type"""
        self.console.clear()
        self.console.print("\n[bold cyan]Configure Models per Task[/bold cyan]")
        self.console.print(
            "Different tasks can use different AI models for optimal cost/performance.\n"
        )

        task_configs = {}

        for task_type in TaskType:
            self.console.print(
                f"\n[yellow]Task: {task_type.value.replace('_', ' ').title()}[/yellow]"
            )

            # Select provider
            providers = ai_client.list_available_providers()
            if not providers:
                self.console.print("[red]No AI providers available![/red]")
                continue

            provider = providers[0]  # Default to first available
            if len(providers) > 1:
                provider_str = Prompt.ask(
                    "Select provider",
                    choices=[p.value for p in providers],
                    default=providers[0].value,
                )
                provider = AIProvider(provider_str)

            # Select model based on provider
            model = Prompt.ask(
                "Enter model name", default=self._get_default_model(provider, task_type)
            )

            # Temperature
            temp = float(
                Prompt.ask(
                    "Temperature (0.0 - 1.0)",
                    default=str(self._get_default_temperature(task_type)),
                )
            )

            task_configs[task_type] = ModelConfig(
                provider=provider,
                model_name=model,
                temperature=temp,
                max_tokens=4096 if task_type == TaskType.CODE_GENERATION else 2048,
            )

        return task_configs

    def select_browser(self) -> BrowserType:
        """Select browser type"""
        self.console.clear()
        self.console.print("\n[bold cyan]Select Browser[/bold cyan]")

        browser = Prompt.ask(
            "Which browser should be used for automation?",
            choices=[bt.value for bt in BrowserType],
            default=BrowserType.CHROMIUM.value,
        )

        headless = Confirm.ask("Run browser in headless mode?", default=True)

        settings.browser.browser_type = BrowserType(browser)
        settings.browser.headless = headless

        return settings.browser.browser_type

    def get_training_config(self) -> Dict[str, Any]:
        """Get training configuration from user"""
        self.console.clear()
        self.console.print("\n[bold cyan]Training Configuration[/bold cyan]\n")

        config = {
            "portal": Prompt.ask("Portal name", default="my_portal"),
            "district": Prompt.ask("District name", default="my_district"),
            "url": Prompt.ask("Form URL (leave empty to search)", default=""),
            "description": Prompt.ask("Description (optional)", default=""),
        }

        # Select AI providers
        config["providers"] = self.select_ai_providers()

        # Configure models
        config["task_models"] = self.configure_task_models()

        # Select browser
        config["browser"] = self.select_browser()

        # Advanced options
        if Confirm.ask("Configure advanced options?", default=False):
            config["max_retries"] = int(Prompt.ask("Max retries", default="3"))
            config["validation_enabled"] = Confirm.ask(
                "Enable validation?", default=True
            )
            config["save_screenshots"] = Confirm.ask("Save screenshots?", default=True)
        else:
            config["max_retries"] = 3
            config["validation_enabled"] = True
            config["save_screenshots"] = True

        return config

    def show_config_summary(self, config: Dict[str, Any]) -> bool:
        """Show configuration summary and confirm"""
        self.console.clear()
        self.console.print("\n[bold cyan]Configuration Summary[/bold cyan]\n")

        table = Table(title="Training Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Portal", config.get("portal", "N/A"))
        table.add_row("District", config.get("district", "N/A"))
        table.add_row("URL", config.get("url", "Not specified"))
        table.add_row("Browser", config.get("browser", "N/A"))
        table.add_row(
            "AI Providers", ", ".join([p.value for p in config.get("providers", [])])
        )
        table.add_row("Max Retries", str(config.get("max_retries", 3)))
        table.add_row("Validation", "Yes" if config.get("validation_enabled") else "No")
        table.add_row("Screenshots", "Yes" if config.get("save_screenshots") else "No")

        self.console.print(table)

        return Confirm.ask(
            "\n[yellow]Start training with this configuration?[/yellow]", default=True
        )

    async def run_training(self, config: Dict[str, Any]):
        """Run training with live progress updates"""
        self.console.clear()

        # Apply configuration
        for task, model_config in config["task_models"].items():
            settings.update_task_model(task, model_config)

        state.current_session = {
            "config": config,
            "started_at": datetime.now().isoformat(),
            "status": "running",
        }

        session_info = {
            "portal": config["portal"],
            "district": config["district"],
            "url": config["url"],
            "model": config["task_models"][TaskType.CODE_GENERATION].model_name,
            "browser": config["browser"],
            "providers": [p.value for p in config["providers"]],
        }

        # Use Live display for real-time updates
        with Live(self.layout, refresh_per_second=4, screen=False) as live:
            self.update_display(
                phase="Initializing",
                current_step="Starting training session",
                progress=0.0,
                session_info=session_info,
            )

            try:
                # Create orchestrator with callbacks
                orchestrator = Orchestrator()

                # Setup callbacks for progress updates
                self._setup_orchestrator_callbacks(orchestrator)

                state.log("Starting training session", "info")

                # Run training
                result = await orchestrator.train_municipality(
                    url=config["url"] if config["url"] else "",
                    municipality=config["portal"],
                )

                state.current_session["completed_at"] = datetime.now().isoformat()
                state.current_session["status"] = "completed"
                state.current_session["result"] = result

                self.update_display(
                    phase="Completed",
                    current_step="Training finished",
                    progress=100.0,
                    session_info=session_info,
                )

                state.log(f"Training completed: {result}", "info")

            except Exception as e:
                state.current_session["status"] = "failed"
                state.current_session["error"] = str(e)
                state.add_error(str(e), "Training", traceback.format_exc())

                self.update_display(
                    phase="Failed",
                    current_step=f"Error: {str(e)}",
                    progress=0.0,
                    session_info=session_info,
                )

                state.log(f"Training failed: {e}", "error")

        # Show final results
        self.show_training_results()

    def _setup_orchestrator_callbacks(self, orchestrator):
        """Setup callbacks for orchestrator to update TUI"""

        async def on_phase_start(phase_name: str, phase_num: int, total_phases: int):
            state.current_phase = phase_name
            progress = (phase_num - 1) / total_phases * 100
            state.log(f"Starting phase: {phase_name}", "info")

        async def on_phase_complete(phase_name: str, result: Dict[str, Any]):
            state.log(f"Completed phase: {phase_name}", "info")

        async def on_agent_action(agent_name: str, action: Any):
            state.log(f"{agent_name}: {action.description[:50]}...", "debug")

        async def on_error(phase: str, error: str, details: Optional[str] = None):
            state.add_error(error, phase, details)
            state.log(f"Error in {phase}: {error}", "error")

        orchestrator.on_phase_start = on_phase_start
        orchestrator.on_phase_complete = on_phase_complete
        orchestrator.on_agent_action = on_agent_action
        orchestrator.on_error = on_error

    def show_training_results(self):
        """Show final training results"""
        self.console.clear()
        self.console.print("\n[bold cyan]Training Results[/bold cyan]\n")

        if not state.current_session:
            self.console.print("[yellow]No training session available[/yellow]")
            return

        session = state.current_session

        if session.get("status") == "completed":
            self.console.print("[green]✓ Training completed successfully![/green]\n")

            result = session.get("result", {})

            # Show summary
            table = Table(title="Training Summary", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Status", "[green]Success[/green]")
            table.add_row("Duration", str(session.get("duration", "N/A")))
            table.add_row("Total Attempts", str(result.get("total_attempts", 0)))
            table.add_row("Confidence Score", str(result.get("confidence", 0)))

            self.console.print(table)

            # Show output location
            output_path = result.get("output_path")
            if output_path:
                self.console.print(f"\n[cyan]Generated scraper saved to:[/cyan]")
                self.console.print(f"  [white]{output_path}[/white]")

        else:
            self.console.print("[red]✗ Training failed[/red]\n")

            error = session.get("error", "Unknown error")
            self.console.print(f"[red]Error:[/red] {error}\n")

            # Show error details
            if state.error_display:
                error_table = Table(title="Error Details", box=box.ROUNDED)
                error_table.add_column("Phase", style="cyan")
                error_table.add_column("Error", style="red")
                error_table.add_column("Details", style="white")

                for err in state.error_display[-5:]:  # Show last 5 errors
                    error_table.add_row(
                        err["phase"], err["error"][:50], (err["details"] or "")[:50]
                    )

                self.console.print(error_table)

        # Show log
        if state.training_log:
            self.console.print("\n[bold cyan]Training Log[/bold cyan]\n")
            for log_entry in state.training_log[-10:]:
                level = log_entry["level"]
                msg = log_entry["message"]
                color = (
                    "green"
                    if level == "info"
                    else "yellow"
                    if level == "warning"
                    else "red"
                )
                self.console.print(f"[{color}]{level.upper()}[/color]: {msg}")

    def _get_default_model(self, provider: AIProvider, task_type: TaskType) -> str:
        """Get default model for provider and task type"""
        defaults = {
            AIProvider.ANTHROPIC: {
                TaskType.FORM_DISCOVERY: "claude-sonnet-4.5",
                TaskType.JS_ANALYSIS: "claude-sonnet-4.5",
                TaskType.TESTING: "claude-sonnet-4.5",
                TaskType.CODE_GENERATION: "claude-opus-4",
                TaskType.VALIDATION: "claude-sonnet-4.5",
                TaskType.HEALING: "claude-opus-4",
            },
            AIProvider.OPENAI: {
                TaskType.FORM_DISCOVERY: "gpt-4",
                TaskType.JS_ANALYSIS: "gpt-4",
                TaskType.TESTING: "gpt-4",
                TaskType.CODE_GENERATION: "gpt-4-turbo",
                TaskType.VALIDATION: "gpt-4",
                TaskType.HEALING: "gpt-4-turbo",
            },
            AIProvider.GEMINI: {
                TaskType.FORM_DISCOVERY: "gemini-pro",
                TaskType.JS_ANALYSIS: "gemini-pro",
                TaskType.TESTING: "gemini-pro",
                TaskType.CODE_GENERATION: "gemini-ultra",
                TaskType.VALIDATION: "gemini-pro",
                TaskType.HEALING: "gemini-ultra",
            },
            AIProvider.OPENROUTER: {
                TaskType.FORM_DISCOVERY: "anthropic/claude-sonnet-4.5",
                TaskType.JS_ANALYSIS: "anthropic/claude-sonnet-4.5",
                TaskType.TESTING: "anthropic/claude-sonnet-4.5",
                TaskType.CODE_GENERATION: "anthropic/claude-opus-4",
                TaskType.VALIDATION: "anthropic/claude-sonnet-4.5",
                TaskType.HEALING: "anthropic/claude-opus-4",
            },
        }
        return defaults.get(provider, {}).get(task_type, "default-model")

    def _get_default_temperature(self, task_type: TaskType) -> float:
        """Get default temperature for task type"""
        defaults = {
            TaskType.FORM_DISCOVERY: 0.5,
            TaskType.JS_ANALYSIS: 0.3,
            TaskType.TESTING: 0.4,
            TaskType.CODE_GENERATION: 0.2,
            TaskType.VALIDATION: 0.3,
            TaskType.HEALING: 0.2,
        }
        return defaults.get(task_type, 0.5)


async def main():
    """Main entry point for TUI"""
    tui = GrivredrTUI()

    # Show welcome screen
    if not tui.welcome_screen():
        return

    # Get configuration
    config = tui.get_training_config()

    # Show summary and confirm
    if not tui.show_config_summary(config):
        print("Training cancelled.")
        return

    # Run training
    await tui.run_training(config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[yellow]Training cancelled by user[/yellow]")
    except Exception as e:
        print(f"\n[red]Fatal error: {e}[/red]")
        import traceback

        traceback.print_exc()
