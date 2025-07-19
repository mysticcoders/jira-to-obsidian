"""
State persistence for JIRA to Obsidian sync
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from dateutil import parser

logger = logging.getLogger(__name__)


class SyncState:
    """Manages sync state persistence for incremental updates."""
    
    def __init__(self, state_file: str = None):
        """Initialize state manager."""
        if state_file is None:
            # Default to user's home directory
            home = Path.home()
            state_dir = home / ".jira_to_obsidian"
            state_dir.mkdir(exist_ok=True)
            self.state_file = state_dir / "sync_state.json"
        else:
            self.state_file = Path(state_file)
        
        self._state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from file or return empty state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file}")
                return state
            except Exception as e:
                logger.warning(f"Failed to load state file: {e}. Starting fresh.")
                return self._empty_state()
        else:
            logger.debug("No state file found. Starting fresh.")
            return self._empty_state()
    
    def _empty_state(self) -> Dict:
        """Return an empty state structure."""
        return {
            "last_sync": None,
            "tickets": {},
            "version": "1.0"
        }
    
    def save(self):
        """Save current state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self._state, f, indent=2, default=str)
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last successful sync time."""
        last_sync = self._state.get("last_sync")
        if last_sync:
            try:
                return parser.parse(last_sync)
            except Exception as e:
                logger.warning(f"Invalid last_sync time: {e}")
                return None
        return None
    
    def set_last_sync_time(self, sync_time: datetime = None):
        """Update the last sync time."""
        if sync_time is None:
            sync_time = datetime.utcnow()
        self._state["last_sync"] = sync_time.isoformat()
    
    def get_ticket_state(self, ticket_key: str) -> Optional[Dict]:
        """Get stored state for a ticket."""
        return self._state["tickets"].get(ticket_key)
    
    def update_ticket_state(self, ticket_key: str, updated: str, file_path: str):
        """Update state for a ticket."""
        self._state["tickets"][ticket_key] = {
            "updated": updated,
            "file_path": file_path,
            "last_synced": datetime.utcnow().isoformat()
        }
    
    def remove_ticket_state(self, ticket_key: str):
        """Remove a ticket from state (e.g., if deleted)."""
        self._state["tickets"].pop(ticket_key, None)
    
    def is_ticket_updated(self, ticket_key: str, updated: str) -> bool:
        """Check if a ticket has been updated since last sync."""
        stored = self.get_ticket_state(ticket_key)
        if not stored:
            return True  # New ticket
        
        # Compare update times
        try:
            stored_time = parser.parse(stored["updated"])
            current_time = parser.parse(updated)
            return current_time > stored_time
        except Exception as e:
            logger.warning(f"Error comparing times for {ticket_key}: {e}")
            return True  # Assume updated if we can't compare
    
    def get_all_tracked_tickets(self) -> Dict[str, Dict]:
        """Get all tickets being tracked."""
        return self._state["tickets"].copy()
    
    def clear(self):
        """Clear all state (useful for --full sync)."""
        self._state = self._empty_state()
        logger.info("Cleared sync state")