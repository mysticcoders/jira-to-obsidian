"""
Formatters for converting JIRA tickets to Obsidian notes
"""

from datetime import datetime
from typing import Dict, List

from dateutil import parser


class TicketFormatter:
    """Format JIRA tickets as Obsidian markdown notes."""
    
    def __init__(self, jira_server: str):
        """Initialize formatter with JIRA server URL."""
        self.jira_server = jira_server.rstrip("/")
    
    def format_note(self, ticket: Dict) -> tuple[str, str]:
        """
        Format ticket data as Obsidian markdown note.
        
        Returns:
            Tuple of (note_title, note_content)
        """
        note_title = self._format_title(ticket)
        note_content = self._format_content(ticket)
        
        return note_title, note_content
    
    def _format_title(self, ticket: Dict) -> str:
        """Format the note title."""
        # Sanitize title to avoid filesystem issues
        safe_title = ticket['title']
        
        # Replace problematic characters
        replacements = {
            '/': '-',      # Forward slash would create subdirectories
            '\\': '-',     # Backslash could cause issues
            ':': '-',      # Colon is problematic on Windows
            '*': '-',      # Asterisk is not allowed in filenames
            '?': '-',      # Question mark is not allowed
            '"': "'",      # Double quotes not allowed
            '<': '-',      # Less than not allowed
            '>': '-',      # Greater than not allowed
            '|': '-',      # Pipe not allowed
            '\n': ' ',     # Newlines replaced with space
            '\r': ' ',     # Carriage returns replaced with space
            '\t': ' ',     # Tabs replaced with space
        }
        
        for old_char, new_char in replacements.items():
            safe_title = safe_title.replace(old_char, new_char)
        
        # Remove any double spaces that might have been created
        while '  ' in safe_title:
            safe_title = safe_title.replace('  ', ' ')
        
        # Trim whitespace
        safe_title = safe_title.strip()
        
        return f"{ticket['project']}-{ticket['key'].split('-')[1]} {safe_title}"
    
    def _format_content(self, ticket: Dict) -> str:
        """Format the note content."""
        title = self._format_title(ticket)
        sections = []
        
        # YAML frontmatter
        frontmatter = self._format_yaml_frontmatter(ticket)
        sections.append(frontmatter)
        
        # Header
        sections.append(f"# {title}")
        
        # Description section
        description = self._format_description(ticket)
        sections.append("## Description")
        sections.append(description)
        
        # Comments section
        comments = self._format_comments(ticket.get('comments', []))
        if comments:
            sections.append("## Comments")
            sections.append(comments)
        
        # Footer with JIRA link
        sections.append(self._format_footer(ticket))
        
        return '\n\n'.join(sections)
    
    def _format_yaml_frontmatter(self, ticket: Dict) -> str:
        """Format metadata as YAML frontmatter."""
        lines = ["---"]
        
        # Aliases - allows linking with [[PROJ-123]]
        lines.append(f"aliases:")
        lines.append(f"  - {ticket['key']}")
        
        # Basic metadata
        # Add wikilinks for assignee and reporter if they're actual people
        assignee = ticket['assignee']
        if assignee not in ['Unassigned', 'Unknown', '']:
            assignee = f'"[[{assignee}]]"'
        lines.append(f"assignee: {assignee}")
        
        reporter = ticket['reporter']
        if reporter not in ['Unassigned', 'Unknown', '']:
            reporter = f'"[[{reporter}]]"'
        lines.append(f"reporter: {reporter}")
        lines.append(f"priority: {ticket['priority']}")
        lines.append(f"status: {ticket['status']}")
        lines.append(f"project: {ticket['project']}")
        lines.append(f"key: {ticket['key']}")
        
        # Optional metadata
        if ticket.get('story_points') is not None:
            lines.append(f"story_points: {ticket['story_points']}")
        
        if ticket.get('sprint'):
            lines.append(f"sprint: {ticket['sprint']}")
        
        # Dates
        lines.append(f"created: {self._format_date(ticket['created'])}")
        
        if ticket.get('due_date'):
            lines.append(f"due_date: {ticket['due_date']}")
            
        lines.append(f"updated: {self._format_date(ticket['updated'])}")
        
        # Tags for Obsidian
        lines.append(f"tags:")
        lines.append(f"  - jira")
        lines.append(f"  - {ticket['project'].lower()}")
        lines.append(f"  - {ticket['status'].lower().replace(' ', '-')}")
        
        lines.append("---")
        
        return '\n'.join(lines)
    
    def _format_metadata(self, ticket: Dict) -> str:
        """Format the metadata section."""
        lines = []
        
        # Basic metadata
        lines.append(f"- **Assignee**: [[{ticket['assignee']}]]")
        lines.append(f"- **Reporter**: [[{ticket['reporter']}]]")
        lines.append(f"- **Priority**: {ticket['priority']}")
        lines.append(f"- **Status**: {ticket['status']}")
        
        # Optional metadata
        if ticket.get('story_points'):
            lines.append(f"- **Story Points**: {ticket['story_points']}")
        
        if ticket.get('sprint'):
            lines.append(f"- **Sprint**: {ticket['sprint']}")
        
        # Dates
        lines.append(f"- **Created**: {self._format_date(ticket['created'])}")
        
        if ticket.get('due_date'):
            lines.append(f"- **Due Date**: {ticket['due_date']}")
        
        lines.append(f"- **Last Updated**: {self._format_date(ticket['updated'])}")
        
        return '\n'.join(lines)
    
    def _format_description(self, ticket: Dict) -> str:
        """Format the description section."""
        description = ticket.get('description', '').strip()
        
        if not description:
            return "*No description provided*"
        
        # Convert JIRA formatting to Markdown if needed
        description = self._convert_jira_to_markdown(description)
        
        return description
    
    def _format_comments(self, comments: List[Dict]) -> str:
        """Format the comments section."""
        if not comments:
            return ""
        
        formatted_comments = []
        
        for comment in comments:
            date = self._format_date(comment['created'])
            author = comment['author']
            body = self._convert_jira_to_markdown(comment['body'])
            
            formatted_comments.append(f"### {author} - {date}\n\n{body}")
        
        return '\n\n'.join(formatted_comments)
    
    def _format_footer(self, ticket: Dict) -> str:
        """Format the footer with JIRA link."""
        return f"---\n[View in JIRA]({self.jira_server}/browse/{ticket['key']})"
    
    def _format_date(self, date_str: str) -> str:
        """Format date string for display."""
        try:
            date = parser.parse(date_str)
            return date.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return date_str
    
    def _convert_jira_to_markdown(self, text: str) -> str:
        """Convert JIRA wiki markup to Markdown (basic conversion)."""
        if not text:
            return ""
        
        # Basic conversions
        conversions = {
            # Headers
            'h1. ': '# ',
            'h2. ': '## ',
            'h3. ': '### ',
            'h4. ': '#### ',
            'h5. ': '##### ',
            'h6. ': '###### ',
            # Text formatting
            '*bold*': '**bold**',
            '_italic_': '*italic*',
            '+underline+': '<u>underline</u>',
            '-strikethrough-': '~~strikethrough~~',
            # Lists
            '* ': '- ',
            '# ': '1. ',
            # Code
            '{code}': '```',
            '{code:': '```',
            '{noformat}': '```',
        }
        
        result = text
        for jira_format, markdown_format in conversions.items():
            result = result.replace(jira_format, markdown_format)
        
        return result