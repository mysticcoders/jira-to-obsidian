"""
Main synchronization logic for JIRA to Obsidian
"""

import logging
from datetime import datetime
from typing import Dict, List

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.console import Console

from .config import Config
from .formatter import TicketFormatter
from .jira_client import JiraClient
from .obsidian_client import ObsidianClient
from .state import SyncState

logger = logging.getLogger(__name__)
console = Console()


class JiraObsidianSync:
    """Main synchronization class."""
    
    def __init__(self, config: Config):
        """Initialize sync with configuration."""
        self.config = config
        self.jira_client = JiraClient(config.jira)
        self.obsidian_client = ObsidianClient(config.obsidian)
        self.formatter = TicketFormatter(config.jira.server)
        self.state = SyncState()
    
    def test_connections(self) -> Dict[str, Dict]:
        """Test both JIRA and Obsidian connections."""
        return {
            "jira": self.jira_client.test_connection(),
            "obsidian": self.obsidian_client.test_connection()
        }
    
    def sync(self, dry_run: bool = False, full_sync: bool = False) -> Dict[str, any]:
        """
        Perform the synchronization.
        
        Args:
            dry_run: If True, show what would be done without actually doing it
            full_sync: If True, perform a full sync ignoring state
            
        Returns:
            Dictionary with sync results
        """
        results = {
            "success": False,
            "tickets_found": 0,
            "notes_created": 0,
            "notes_updated": 0,
            "errors": [],
            "dry_run": dry_run,
            "dry_run_actions": []
        }
        
        try:
            # Ensure Obsidian folder exists (skip in dry run)
            if not dry_run:
                self.obsidian_client.create_folder_if_needed()
            
            # Get all non-done tickets
            # Determine which tickets to fetch based on sync mode
            if full_sync:
                # Clear state for full sync
                self.state.clear()
                logger.info("Performing full sync - fetching all non-done tickets from JIRA...")
                
                # Use progress indicator for fetching
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True
                ) as progress:
                    task = progress.add_task("Fetching all tickets from JIRA...", total=None)
                    tickets = self.jira_client.get_all_tickets(exclude_done=True)
                    progress.update(task, completed=100)
            else:
                # Incremental sync - only fetch updated tickets
                last_sync = self.state.get_last_sync_time()
                
                if last_sync is None:
                    # First sync ever - do a full sync
                    logger.info("No previous sync found - performing initial full sync...")
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True
                    ) as progress:
                        task = progress.add_task("Fetching all tickets from JIRA...", total=None)
                        tickets = self.jira_client.get_all_tickets(exclude_done=True)
                        progress.update(task, completed=100)
                else:
                    # Fetch only updated tickets
                    logger.info(f"Fetching tickets updated since {last_sync.strftime('%Y-%m-%d %H:%M')}...")
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True
                    ) as progress:
                        task = progress.add_task("Fetching updated tickets from JIRA...", total=None)
                        tickets = self.jira_client.get_updated_tickets(since=last_sync, exclude_done=True)
                        progress.update(task, completed=100)
            
            results["tickets_found"] = len(tickets)
            
            if not tickets:
                logger.info("No active tickets found")
                results["success"] = True
                return results
            
            # Process each ticket with progress bar
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task(
                    f"Processing {len(tickets)} tickets...", 
                    total=len(tickets)
                )
                
                for ticket in tickets:
                    try:
                        self._process_ticket(ticket, results, dry_run)
                        progress.update(task, advance=1)
                    except Exception as e:
                        error_msg = f"Error processing ticket {ticket['key']}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
                        progress.update(task, advance=1)
            
            results["success"] = len(results["errors"]) == 0
            
            # During incremental sync, check for tickets that may have moved to Done
            if not full_sync and not dry_run and results["success"]:
                # Get all currently tracked tickets
                tracked_tickets = self.state.get_all_tracked_tickets()
                processed_keys = {ticket['key'] for ticket in tickets}
                
                # Find tickets that were not in the update but are still tracked
                potentially_done_keys = set(tracked_tickets.keys()) - processed_keys
                
                if potentially_done_keys:
                    logger.info(f"Checking {len(potentially_done_keys)} tickets that may have moved to Done status...")
                    
                    # We could optionally check these tickets individually or just note them
                    # For now, we'll keep them in state but log them
                    for key in potentially_done_keys:
                        logger.debug(f"Ticket {key} was not in recent updates - may be Done or unchanged")
            
            # Update sync state if successful and not in dry run mode
            if results["success"] and not dry_run:
                self.state.set_last_sync_time()
                self.state.save()
                logger.info("Updated sync state")
            
        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results
    
    def _process_ticket(self, ticket: Dict, results: Dict, dry_run: bool = False):
        """Process a single ticket."""
        # Format the note
        note_title, note_content = self.formatter.format_note(ticket)
        note_path = f"{self.config.obsidian.folder}/{note_title}.md"
        
        # Look for existing note by ticket key
        existing_note_path = None
        if not dry_run:
            existing_note_path = self.obsidian_client.find_note_by_ticket_key(ticket['key'])
        
        # Determine if this is an update or create
        exists = existing_note_path is not None
        needs_rename = exists and existing_note_path != note_path
        
        if exists and not self.config.obsidian.update_existing:
            logger.info(f"Skipping existing note: {ticket['key']}")
            return
        
        if dry_run:
            # In dry run mode, just record what would be done
            action = "UPDATE" if exists else "CREATE"
            if needs_rename:
                action = "UPDATE + RENAME"
            
            dry_run_info = {
                "action": action,
                "ticket": ticket['key'],
                "file_path": note_path,
                "old_file_path": existing_note_path if needs_rename else None,
                "api_endpoint": f"{self.config.obsidian.api_url}/vault/{note_path}",
                "http_method": "PUT",
                "headers": {
                    "Authorization": "Bearer [REDACTED]",
                    "Content-Type": "text/markdown"
                },
                "content_preview": note_content[:500] + "..." if len(note_content) > 500 else note_content,
                "content_length": len(note_content)
            }
            
            results["dry_run_actions"].append(dry_run_info)
            
            if exists:
                results["notes_updated"] += 1
                if needs_rename:
                    logger.info(f"[DRY RUN] Would rename and update note: {existing_note_path} -> {note_path}")
                else:
                    logger.info(f"[DRY RUN] Would update note: {note_title}")
            else:
                results["notes_created"] += 1
                logger.info(f"[DRY RUN] Would create note: {note_title}")
        else:
            # Handle the actual save/rename operations
            success = False
            
            if needs_rename:
                # First update the content at the existing path
                if self.obsidian_client.save_note(existing_note_path, note_content):
                    # Then rename to the new path
                    success = self.obsidian_client.rename_note(existing_note_path, note_path)
                    if success:
                        logger.info(f"Renamed and updated note: {existing_note_path} -> {note_path}")
                    else:
                        error_msg = f"Failed to rename note from {existing_note_path} to {note_path}"
                        results["errors"].append(error_msg)
                else:
                    error_msg = f"Failed to update note content before rename: {existing_note_path}"
                    results["errors"].append(error_msg)
            else:
                # Just save the note (create or update without rename)
                success = self.obsidian_client.save_note(note_path, note_content)
                
            if success:
                if exists:
                    results["notes_updated"] += 1
                    logger.info(f"Updated note: {note_title}")
                else:
                    results["notes_created"] += 1
                    logger.info(f"Created note: {note_title}")
                
                # Update state with ticket info
                self.state.update_ticket_state(
                    ticket['key'],
                    ticket['updated'],
                    note_path
                )
            elif not needs_rename:  # Don't double-log rename errors
                error_msg = f"Failed to save note: {note_title}"
                results["errors"].append(error_msg)
    
    def sync_single_ticket(self, ticket_key: str) -> Dict[str, any]:
        """Sync a single ticket by key."""
        results = {
            "success": False,
            "ticket_found": False,
            "note_created": False,
            "note_updated": False,
            "error": None
        }
        
        try:
            # Fetch the specific ticket
            jql = f'key = "{ticket_key}"'
            issues = self.jira_client.client.search_issues(jql, maxResults=1)
            
            if not issues:
                results["error"] = f"Ticket {ticket_key} not found"
                return results
            
            results["ticket_found"] = True
            
            # Extract ticket data
            ticket = self.jira_client._extract_ticket_data(issues[0])
            
            # Process the ticket
            note_title, note_content = self.formatter.format_note(ticket)
            note_path = f"{self.config.obsidian.folder}/{note_title}.md"
            
            exists = self.obsidian_client.note_exists(note_path)
            success = self.obsidian_client.save_note(note_path, note_content)
            
            if success:
                results["success"] = True
                if exists:
                    results["note_updated"] = True
                else:
                    results["note_created"] = True
            else:
                results["error"] = "Failed to save note to Obsidian"
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Error syncing ticket {ticket_key}: {e}")
        
        return results