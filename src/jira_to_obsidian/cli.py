"""
CLI entry points for JIRA to Obsidian sync
"""

import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from .config import Config
from .jira_client import JiraClient
from .obsidian_client import ObsidianClient
from .sync import JiraObsidianSync

# Set up rich console
console = Console()

# Configure logging with rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool):
    """Set up logging based on verbosity."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose: bool):
    """JIRA to Obsidian sync tool."""
    setup_logging(verbose)


@cli.command()
def test_connections():
    """Test connections to JIRA and Obsidian."""
    console.print("\n[bold]Testing connections...[/bold]\n")
    
    # Load configuration
    try:
        config = Config.from_env()
        
        # Validate configuration
        errors = config.validate()
        if errors:
            console.print("[red]Configuration errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print("\n[yellow]Please check your .env file[/yellow]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        sys.exit(1)
    
    # Test connections
    try:
        sync = JiraObsidianSync(config)
        results = sync.test_connections()
        
        # Display JIRA results
        jira_results = results["jira"]
        if jira_results["connected"]:
            jira_panel = Panel(
                f"[green]✓ Connected[/green]\n"
                f"Server: {jira_results.get('server_title', 'Unknown')}\n"
                f"Version: {jira_results.get('server_version', 'Unknown')}\n"
                f"User: {jira_results.get('user', 'Unknown')}\n\n"
                f"Accessible projects: {', '.join([p['key'] for p in jira_results.get('accessible_projects', [])])}\n"
                f"Inaccessible projects: {', '.join(jira_results.get('inaccessible_projects', []))}",
                title="[bold green]JIRA Connection[/bold green]",
                border_style="green"
            )
        else:
            jira_panel = Panel(
                f"[red]✗ Connection Failed[/red]\n"
                f"Error: {jira_results.get('error', 'Unknown error')}",
                title="[bold red]JIRA Connection[/bold red]",
                border_style="red"
            )
        console.print(jira_panel)
        
        # Display Obsidian results
        obsidian_results = results["obsidian"]
        if obsidian_results["connected"]:
            if obsidian_results.get("authenticated", False):
                obsidian_panel = Panel(
                    f"[green]✓ Connected and Authenticated[/green]\n"
                    f"API Version: {obsidian_results.get('api_version', 'Unknown')}\n"
                    f"Folder exists: {'Yes' if obsidian_results.get('folder_exists', False) else 'No'}\n"
                    f"Folder path: {obsidian_results.get('folder_path', 'Unknown')}",
                    title="[bold green]Obsidian Connection[/bold green]",
                    border_style="green"
                )
            else:
                obsidian_panel = Panel(
                    f"[yellow]⚠ Connected but not authenticated[/yellow]\n"
                    f"Error: {obsidian_results.get('error', 'Unknown error')}",
                    title="[bold yellow]Obsidian Connection[/bold yellow]",
                    border_style="yellow"
                )
        else:
            obsidian_panel = Panel(
                f"[red]✗ Connection Failed[/red]\n"
                f"Error: {obsidian_results.get('error', 'Unknown error')}",
                title="[bold red]Obsidian Connection[/bold red]",
                border_style="red"
            )
        console.print(obsidian_panel)
        
        # Overall status
        if jira_results["connected"] and obsidian_results["connected"] and obsidian_results.get("authenticated", False):
            console.print("\n[bold green]✅ All connections successful![/bold green]")
            sys.exit(0)
        else:
            console.print("\n[bold red]❌ Some connections failed. Please check your configuration.[/bold red]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', help='Filter by specific project key (e.g., PROJ)')
def list_jira(project: str):
    """List all JIRA tickets sorted by priority (excluding Done/Resolved/Closed)."""
    # Load configuration
    try:
        config = Config.from_env()
        
        # Validate configuration
        errors = config.validate()
        if errors:
            console.print("[red]Configuration errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print("\n[yellow]Please check your .env file[/yellow]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        sys.exit(1)
    
    try:
        # Create JIRA client
        jira_client = JiraClient(config.jira)
        
        # If project specified, temporarily override the projects list
        original_projects = None
        if project:
            original_projects = config.jira.projects
            config.jira.projects = [project]
            console.print(f"\n[bold]Fetching JIRA tickets for project {project} sorted by priority...[/bold]\n")
        else:
            console.print("\n[bold]Fetching JIRA tickets sorted by priority...[/bold]\n")
        
        # Get all tickets (excluding done)
        tickets = jira_client.get_all_tickets(exclude_done=True)
        
        # Restore original projects if we overrode them
        if original_projects:
            config.jira.projects = original_projects
        
        if not tickets:
            console.print("[yellow]No tickets found in configured projects[/yellow]")
            return
        
        # Create table
        table = Table(title=f"JIRA Tickets ({len(tickets)} total)")
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Priority", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Assignee", style="green")
        table.add_column("Summary", style="white")
        
        # Priority colors
        priority_colors = {
            "Highest": "red",
            "High": "bright_red",
            "Medium": "yellow",
            "Low": "green",
            "Lowest": "bright_green"
        }
        
        for ticket in tickets:
            priority = ticket.get('priority', 'None')
            priority_color = priority_colors.get(priority, "white")
            
            table.add_row(
                ticket['key'],
                f"[{priority_color}]{priority}[/{priority_color}]",
                ticket['status'],
                ticket.get('assignee', 'Unassigned'),
                ticket['title'][:80] + "..." if len(ticket['title']) > 80 else ticket['title']
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"\n[red]Failed to fetch tickets: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', help='Filter by specific project key (e.g., PROJ)')
def list_obsidian(project: str):
    """List all Obsidian notes for JIRA tickets."""
    # Load configuration
    try:
        config = Config.from_env()
        
        # Validate configuration
        errors = config.validate()
        if errors:
            console.print("[red]Configuration errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print("\n[yellow]Please check your .env file[/yellow]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        sys.exit(1)
    
    try:
        # Create Obsidian client
        obsidian_client = ObsidianClient(config.obsidian)
        
        if project:
            console.print(f"\n[bold]Fetching Obsidian notes for project {project}...[/bold]\n")
        else:
            console.print(f"\n[bold]Fetching all Obsidian notes in {config.obsidian.folder} folder...[/bold]\n")
        
        # List all notes in the configured folder
        notes = obsidian_client.list_notes()
        
        # Filter notes by project if specified
        if project:
            project_notes = []
            for note in notes:
                # Check if note name starts with project key
                if note['name'].startswith(f"{project}-"):
                    project_notes.append(note)
        else:
            # Show all notes
            project_notes = notes
        
        if not project_notes:
            if project:
                console.print(f"[yellow]No notes found for project {project}[/yellow]")
            else:
                console.print(f"[yellow]No notes found in {config.obsidian.folder} folder[/yellow]")
            return
        
        # Sort by ticket number
        def extract_ticket_number(note_name):
            try:
                # Extract number from format "PROJ-123 Title.md"
                parts = note_name.split('-')
                if len(parts) >= 2:
                    number_part = parts[1].split(' ')[0]
                    return int(number_part)
            except:
                return 0
            return 0
        
        project_notes.sort(key=lambda x: extract_ticket_number(x['name']))
        
        # Create table
        if project:
            table = Table(title=f"Obsidian Notes for Project {project} ({len(project_notes)} total)")
        else:
            table = Table(title=f"All Obsidian Notes ({len(project_notes)} total)")
        table.add_column("Ticket", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Path", style="dim")
        
        for note in project_notes:
            # Extract ticket key and title from filename
            name = note['name']
            if name.endswith('.md'):
                name = name[:-3]
            
            # Try to split into ticket and title
            parts = name.split(' ', 1)
            if len(parts) == 2:
                ticket_key = parts[0]
                title = parts[1]
            else:
                ticket_key = name
                title = ""
            
            table.add_row(
                ticket_key,
                title[:60] + "..." if len(title) > 60 else title,
                note['path']
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"\n[red]Failed to fetch notes: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--ticket', '-t', help='Sync a specific ticket by key (e.g., PROJ-123)')
@click.option('--dry-run', '-n', is_flag=True, help='Show what would be done without actually doing it')
@click.option('--full', '-f', is_flag=True, help='Perform a full sync, ignoring last sync state')
def sync(ticket: str, dry_run: bool, full: bool):
    """Sync JIRA tickets to Obsidian."""
    # Load configuration
    try:
        config = Config.from_env()
        
        # Validate configuration
        errors = config.validate()
        if errors:
            console.print("[red]Configuration errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print("\n[yellow]Please check your .env file[/yellow]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        sys.exit(1)
    
    # Create sync instance
    sync_instance = JiraObsidianSync(config)
    
    try:
        if ticket:
            # Sync single ticket
            console.print(f"\n[bold]Syncing ticket {ticket}...[/bold]\n")
            results = sync_instance.sync_single_ticket(ticket)
            
            if results["success"]:
                if results["note_created"]:
                    console.print(f"[green]✅ Created note for {ticket}[/green]")
                elif results["note_updated"]:
                    console.print(f"[green]✅ Updated note for {ticket}[/green]")
            else:
                console.print(f"[red]❌ Failed to sync {ticket}: {results.get('error', 'Unknown error')}[/red]")
                sys.exit(1)
        else:
            # Sync all tickets
            if dry_run:
                console.print("\n[bold yellow]Starting JIRA to Obsidian sync (DRY RUN)...[/bold yellow]\n")
            else:
                if full:
                    console.print("\n[bold]Starting JIRA to Obsidian FULL sync...[/bold]\n")
                else:
                    console.print("\n[bold]Starting JIRA to Obsidian incremental sync...[/bold]\n")
            
            results = sync_instance.sync(dry_run=dry_run, full_sync=full)
            
            # Display results
            table = Table(title="Sync Results" + (" (DRY RUN)" if dry_run else ""))
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Tickets Found", str(results["tickets_found"]))
            table.add_row("Notes Created", str(results["notes_created"]))
            table.add_row("Notes Updated", str(results["notes_updated"]))
            table.add_row("Errors", str(len(results["errors"])))
            
            console.print(table)
            
            # In dry run mode, show what would be done
            if dry_run and results.get("dry_run_actions"):
                console.print("\n[bold yellow]DRY RUN - The following actions would be performed:[/bold yellow]\n")
                
                for action in results["dry_run_actions"]:
                    # Create a panel for each action
                    panel_content = f"[cyan]Action:[/cyan] {action['action']}\n"
                    panel_content += f"[cyan]File Path:[/cyan] {action['file_path']}\n"
                    
                    # Show old file path if this is a rename
                    if action.get('old_file_path'):
                        panel_content += f"[cyan]Old File Path:[/cyan] {action['old_file_path']}\n"
                    
                    panel_content += f"[cyan]HTTP Method:[/cyan] {action['http_method']}\n"
                    panel_content += f"[cyan]API Endpoint:[/cyan] {action['api_endpoint']}\n"
                    panel_content += f"[cyan]Content Length:[/cyan] {action['content_length']} bytes\n"
                    panel_content += f"\n[cyan]Headers:[/cyan]\n"
                    for header, value in action['headers'].items():
                        panel_content += f"  {header}: {value}\n"
                    panel_content += f"\n[cyan]Content Preview:[/cyan]\n"
                    panel_content += f"{action['content_preview']}"
                    
                    panel = Panel(
                        panel_content,
                        title=f"[bold]{action['ticket']}[/bold]",
                        border_style="yellow"
                    )
                    console.print(panel)
                    console.print("")  # Add spacing between panels
            
            if results["errors"]:
                console.print("\n[red]Errors encountered:[/red]")
                for error in results["errors"]:
                    console.print(f"  • {error}")
            
            if results["success"]:
                if dry_run:
                    console.print("\n[bold yellow]✅ Dry run completed successfully![/bold yellow]")
                else:
                    console.print("\n[bold green]✅ Sync completed successfully![/bold green]")
            else:
                console.print("\n[bold red]❌ Sync completed with errors[/bold red]")
                sys.exit(1)
                
    except Exception as e:
        console.print(f"\n[red]Sync failed: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()