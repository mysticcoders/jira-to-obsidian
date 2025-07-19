"""
JIRA client for fetching tickets
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from jira import JIRA
from jira.exceptions import JIRAError

from .config import JiraConfig

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with JIRA."""
    
    def __init__(self, config: JiraConfig):
        """Initialize JIRA client with configuration."""
        self.config = config
        self._client: Optional[JIRA] = None
        
    @property
    def client(self) -> JIRA:
        """Get or create JIRA client instance."""
        if self._client is None:
            self._client = JIRA(
                server=self.config.server,
                basic_auth=(self.config.email, self.config.api_token)
            )
        return self._client
    
    def test_connection(self) -> Dict[str, any]:
        """Test JIRA connection and return status information."""
        try:
            # Try to get server info
            server_info = self.client.server_info()
            
            # Try to get current user
            current_user = self.client.current_user()
            
            # Check if projects are accessible
            accessible_projects = []
            inaccessible_projects = []
            
            for project_key in self.config.projects:
                try:
                    project = self.client.project(project_key)
                    accessible_projects.append({
                        "key": project.key,
                        "name": project.name
                    })
                except JIRAError:
                    inaccessible_projects.append(project_key)
            
            return {
                "connected": True,
                "server_version": server_info.get("version", "Unknown"),
                "server_title": server_info.get("serverTitle", "Unknown"),
                "user": current_user,
                "accessible_projects": accessible_projects,
                "inaccessible_projects": inaccessible_projects
            }
            
        except JIRAError as e:
            logger.error(f"JIRA connection failed: {e}")
            return {
                "connected": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error testing JIRA connection: {e}")
            return {
                "connected": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def get_in_progress_tickets(self) -> List[Dict]:
        """Fetch all in-progress tickets from configured projects."""
        if not self.config.projects:
            return []
        
        # Build JQL query
        project_filter = f"project in ({','.join(self.config.projects)})"
        jql = f'{project_filter} AND status = "In Progress"'
        
        logger.info(f"Fetching tickets with JQL: {jql}")
        
        try:
            issues = self.client.search_issues(
                jql,
                maxResults=100,
                expand='changelog'
            )
            
            tickets = []
            for issue in issues:
                ticket_data = self._extract_ticket_data(issue)
                tickets.append(ticket_data)
            
            logger.info(f"Found {len(tickets)} in-progress tickets")
            return tickets
            
        except JIRAError as e:
            logger.error(f"Error fetching JIRA tickets: {e}")
            raise
    
    def get_all_tickets(self, max_results: Optional[int] = None, order_by: str = "priority DESC", exclude_done: bool = True) -> List[Dict]:
        """
        Fetch all tickets from configured projects with pagination support.
        
        Args:
            max_results: Maximum number of tickets to fetch (None = all tickets)
            order_by: JQL ORDER BY clause (default: "priority DESC")
            exclude_done: If True, exclude tickets with Done status (default: True)
            
        Returns:
            List of ticket dictionaries sorted by the specified order
        """
        if not self.config.projects:
            return []
        
        # Build JQL query
        project_filter = f"project in ({','.join(self.config.projects)})"
        
        if exclude_done:
            # Exclude Done, Resolved, Closed statuses
            jql = f"{project_filter} AND status NOT IN (Done, Resolved, Closed) ORDER BY {order_by}"
        else:
            jql = f"{project_filter} ORDER BY {order_by}"
        
        logger.info(f"Fetching tickets with JQL: {jql}")
        
        try:
            all_tickets = []
            start_at = 0
            batch_size = 50  # JIRA performs better with smaller batches
            
            while True:
                # Fetch a batch of issues
                logger.debug(f"Fetching tickets starting at {start_at}")
                issues = self.client.search_issues(
                    jql,
                    startAt=start_at,
                    maxResults=batch_size,
                    expand='changelog'
                )
                
                # Process this batch
                for issue in issues:
                    ticket_data = self._extract_ticket_data(issue)
                    all_tickets.append(ticket_data)
                
                # Check if we've reached the user-specified limit
                if max_results and len(all_tickets) >= max_results:
                    logger.info(f"Reached max_results limit of {max_results}")
                    return all_tickets[:max_results]
                
                # Check if we have more pages
                if len(issues) < batch_size:
                    break  # No more pages
                
                start_at += batch_size
                logger.info(f"Fetched {len(all_tickets)} tickets so far...")
            
            logger.info(f"Found {len(all_tickets)} total tickets")
            return all_tickets
            
        except JIRAError as e:
            logger.error(f"Error fetching JIRA tickets: {e}")
            raise
    
    def get_updated_tickets(self, since: datetime, exclude_done: bool = True) -> List[Dict]:
        """
        Fetch tickets updated since a specific time.
        
        Args:
            since: Datetime to fetch tickets updated after
            exclude_done: If True, exclude tickets with Done status (default: True)
            
        Returns:
            List of ticket dictionaries updated since the given time
        """
        if not self.config.projects:
            return []
        
        # Build JQL query with date filter
        project_filter = f"project in ({','.join(self.config.projects)})"
        
        # Format datetime for JQL (JIRA expects "yyyy-MM-dd HH:mm")
        since_str = since.strftime("%Y-%m-%d %H:%M")
        date_filter = f'updated >= "{since_str}"'
        
        if exclude_done:
            jql = f"{project_filter} AND {date_filter} AND status NOT IN (Done, Resolved, Closed) ORDER BY updated DESC"
        else:
            jql = f"{project_filter} AND {date_filter} ORDER BY updated DESC"
        
        logger.info(f"Fetching tickets updated since {since_str} with JQL: {jql}")
        
        try:
            all_tickets = []
            start_at = 0
            batch_size = 50
            
            while True:
                # Fetch a batch of issues
                logger.debug(f"Fetching updated tickets starting at {start_at}")
                issues = self.client.search_issues(
                    jql,
                    startAt=start_at,
                    maxResults=batch_size,
                    expand='changelog'
                )
                
                # Process this batch
                for issue in issues:
                    ticket_data = self._extract_ticket_data(issue)
                    all_tickets.append(ticket_data)
                
                # Check if we have more pages
                if len(issues) < batch_size:
                    break  # No more pages
                
                start_at += batch_size
                logger.info(f"Fetched {len(all_tickets)} updated tickets so far...")
            
            logger.info(f"Found {len(all_tickets)} tickets updated since {since_str}")
            return all_tickets
            
        except JIRAError as e:
            logger.error(f"Error fetching updated JIRA tickets: {e}")
            raise
    
    def _extract_ticket_data(self, issue) -> Dict:
        """Extract relevant data from a JIRA issue."""
        fields = issue.fields
        
        data = {
            'key': issue.key,
            'project': issue.fields.project.key,
            'title': fields.summary,
            'description': fields.description or '',
            'assignee': fields.assignee.displayName if fields.assignee else 'Unassigned',
            'assignee_email': getattr(fields.assignee, 'emailAddress', None) if fields.assignee else None,
            'reporter': fields.reporter.displayName if fields.reporter else 'Unknown',
            'reporter_email': getattr(fields.reporter, 'emailAddress', None) if fields.reporter else None,
            'priority': fields.priority.name if fields.priority else 'None',
            'status': fields.status.name,
            'created': fields.created,
            'updated': fields.updated,
        }
        
        # Due date
        if hasattr(fields, 'duedate') and fields.duedate:
            data['due_date'] = fields.duedate
        else:
            data['due_date'] = None
        
        # Story points (custom field - may vary by instance)
        story_points_field = getattr(fields, 'customfield_10016', None)
        data['story_points'] = story_points_field if story_points_field else None
        
        # Sprint information
        sprint_field = getattr(fields, 'customfield_10020', None)
        if sprint_field and len(sprint_field) > 0:
            # Parse sprint info from the string representation
            sprint_info = sprint_field[0]
            if hasattr(sprint_info, 'name'):
                data['sprint'] = sprint_info.name
            else:
                # Try to extract sprint name from string
                sprint_str = str(sprint_info)
                if 'name=' in sprint_str:
                    start = sprint_str.find('name=') + 5
                    end = sprint_str.find(',', start)
                    data['sprint'] = sprint_str[start:end] if end > start else None
                else:
                    data['sprint'] = None
        else:
            data['sprint'] = None
        
        # Get comments
        data['comments'] = self._get_comments(issue)
        
        return data
    
    def _get_comments(self, issue) -> List[Dict]:
        """Get comments for an issue."""
        comments = []
        
        try:
            for comment in self.client.comments(issue):
                comments.append({
                    'author': comment.author.displayName,
                    'created': comment.created,
                    'body': comment.body
                })
        except Exception as e:
            logger.warning(f"Error fetching comments for {issue.key}: {e}")
        
        return comments