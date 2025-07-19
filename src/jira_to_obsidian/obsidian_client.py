"""
Obsidian client for managing notes via REST API
"""

import json
import logging
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from requests.exceptions import ConnectionError, RequestException

from .config import ObsidianConfig

logger = logging.getLogger(__name__)


class ObsidianClient:
    """Client for interacting with Obsidian via REST API."""
    
    def __init__(self, config: ObsidianConfig):
        """Initialize Obsidian client with configuration."""
        self.config = config
        self.headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_connection(self) -> Dict[str, any]:
        """Test Obsidian connection and return status information."""
        try:
            # Test with a simple request to list files in root
            response = requests.get(
                f"{self.config.api_url}/vault/",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                # Try to check if our folder exists
                folder_response = requests.get(
                    f"{self.config.api_url}/vault/{quote(self.config.folder)}/",
                    headers=self.headers,
                    timeout=5
                )
                
                folder_exists = folder_response.status_code == 200
                
                return {
                    "connected": True,
                    "authenticated": True,
                    "folder_exists": folder_exists,
                    "folder_path": self.config.folder
                }
            elif response.status_code == 401:
                return {
                    "connected": True,
                    "authenticated": False,
                    "error": "Invalid API key"
                }
            else:
                return {
                    "connected": True,
                    "authenticated": False,
                    "error": f"Unexpected status code: {response.status_code}"
                }
                
        except ConnectionError:
            return {
                "connected": False,
                "error": "Cannot connect to Obsidian REST API. Make sure the plugin is installed and running."
            }
        except Exception as e:
            logger.error(f"Unexpected error testing Obsidian connection: {e}")
            return {
                "connected": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def note_exists(self, note_path: str) -> bool:
        """Check if a note exists at the given path."""
        try:
            response = requests.get(
                f"{self.config.api_url}/vault/{quote(note_path)}",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except RequestException:
            return False
    
    def create_folder_if_needed(self):
        """Create the configured folder if it doesn't exist."""
        folder_path = self.config.folder
        
        try:
            # Check if folder exists by listing its contents
            response = requests.get(
                f"{self.config.api_url}/vault/{quote(folder_path)}/",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 404:
                # Create folder by creating a README file in it
                readme_path = f"{folder_path}/README.md"
                content = f"# {folder_path}\n\nThis folder contains synchronized JIRA tickets."
                
                response = requests.put(
                    f"{self.config.api_url}/vault/{quote(readme_path)}",
                    headers={
                        'Authorization': f'Bearer {self.config.api_key}',
                        'Content-Type': 'text/markdown'
                    },
                    data=content.encode('utf-8'),
                    timeout=10
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Created folder: {folder_path}")
                else:
                    logger.error(f"Failed to create folder: {response.status_code}")
                    
        except RequestException as e:
            logger.error(f"Error creating folder: {e}")
    
    def save_note(self, note_path: str, content: str) -> bool:
        """Save or update a note at the given path."""
        try:
            # The API expects the content as the request body, not JSON
            response = requests.put(
                f"{self.config.api_url}/vault/{quote(note_path)}",
                headers={
                    'Authorization': f'Bearer {self.config.api_key}',
                    'Content-Type': 'text/markdown'
                },
                data=content.encode('utf-8'),
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"Successfully saved note: {note_path}")
                return True
            else:
                logger.error(
                    f"Failed to save note {note_path}: "
                    f"{response.status_code} - {response.text}"
                )
                return False
                
        except RequestException as e:
            logger.error(f"Error saving note {note_path}: {e}")
            return False
    
    def get_note_content(self, note_path: str) -> Optional[str]:
        """Get the content of a note."""
        try:
            response = requests.get(
                f"{self.config.api_url}/vault/{quote(note_path)}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                # The API returns the content directly as text
                return response.text
            else:
                return None
                
        except RequestException as e:
            logger.error(f"Error reading note {note_path}: {e}")
            return None
    
    def delete_note(self, note_path: str) -> bool:
        """Delete a note at the given path."""
        try:
            response = requests.delete(
                f"{self.config.api_url}/vault/{quote(note_path)}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Successfully deleted note: {note_path}")
                return True
            else:
                logger.error(
                    f"Failed to delete note {note_path}: "
                    f"{response.status_code} - {response.text}"
                )
                return False
                
        except RequestException as e:
            logger.error(f"Error deleting note {note_path}: {e}")
            return False
    
    def find_note_by_ticket_key(self, ticket_key: str) -> Optional[str]:
        """
        Find an existing note by ticket key prefix.
        
        Args:
            ticket_key: The JIRA ticket key (e.g., "PROJ-123")
            
        Returns:
            Full path to the existing note, or None if not found
        """
        notes = self.list_notes()
        
        # Look for notes that start with the ticket key
        for note in notes:
            # Extract just the filename without path
            filename = note['name']
            # Check if filename starts with ticket key followed by space
            if filename.startswith(f"{ticket_key} "):
                return note['path']
        
        return None
    
    def rename_note(self, old_path: str, new_path: str) -> bool:
        """
        Rename a note by creating it at new path and deleting old one.
        
        Args:
            old_path: Current path of the note
            new_path: New path for the note
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First, get the content of the old note
            content = self.get_note_content(old_path)
            if content is None:
                logger.error(f"Cannot read note to rename: {old_path}")
                return False
            
            # Create the note at the new path
            if not self.save_note(new_path, content):
                logger.error(f"Failed to create note at new path: {new_path}")
                return False
            
            # Delete the old note
            if not self.delete_note(old_path):
                logger.error(f"Failed to delete old note: {old_path}")
                # Try to clean up the new note since rename failed
                self.delete_note(new_path)
                return False
            
            logger.info(f"Successfully renamed note from {old_path} to {new_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error renaming note: {e}")
            return False
    
    def list_notes(self, folder_path: Optional[str] = None) -> List[Dict[str, str]]:
        """
        List all notes in a folder.
        
        Args:
            folder_path: Path to folder (default: configured folder)
            
        Returns:
            List of dictionaries with 'name' and 'path' keys
        """
        if folder_path is None:
            folder_path = self.config.folder
            
        try:
            response = requests.get(
                f"{self.config.api_url}/vault/{quote(folder_path)}/",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                # Parse the response - it should contain a list of files
                data = response.json()
                notes = []
                
                # The API returns a files array
                for item in data.get('files', []):
                    # Only include markdown files
                    if isinstance(item, str) and item.endswith('.md'):
                        notes.append({
                            'name': item,
                            'path': f"{folder_path}/{item}"
                        })
                    elif isinstance(item, dict) and 'name' in item:
                        # Handle different response format
                        if item['name'].endswith('.md'):
                            notes.append({
                                'name': item['name'],
                                'path': f"{folder_path}/{item['name']}"
                            })
                
                return sorted(notes, key=lambda x: x['name'])
            elif response.status_code == 404:
                logger.warning(f"Folder {folder_path} not found")
                return []
            else:
                logger.error(f"Failed to list notes in {folder_path}: {response.status_code}")
                return []
                
        except RequestException as e:
            logger.error(f"Error listing notes in {folder_path}: {e}")
            return []