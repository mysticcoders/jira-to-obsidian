"""Tests for formatter module."""

from datetime import datetime

import pytest

from jira_to_obsidian.formatter import TicketFormatter


class TestTicketFormatter:
    """Test TicketFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """Create a formatter instance."""
        return TicketFormatter("https://test.atlassian.net")
    
    @pytest.fixture
    def sample_ticket(self):
        """Create a sample ticket."""
        return {
            "key": "PROJ-123",
            "project": "PROJ",
            "title": "Sample ticket title",
            "description": "This is a sample description",
            "assignee": "John Doe",
            "reporter": "Jane Smith",
            "priority": "High",
            "status": "In Progress",
            "created": "2024-01-01T10:00:00+00:00",
            "updated": "2024-01-02T15:30:00+00:00",
            "due_date": "2024-01-15",
            "story_points": 5,
            "sprint": "Sprint 23",
            "comments": [
                {
                    "author": "Alice",
                    "created": "2024-01-01T11:00:00+00:00",
                    "body": "This is a comment"
                }
            ]
        }
    
    def test_format_title(self, formatter, sample_ticket):
        """Test formatting note title."""
        title = formatter._format_title(sample_ticket)
        assert title == "PROJ-123 Sample ticket title"
    
    def test_format_title_with_problematic_characters(self, formatter):
        """Test formatting note title with characters that need sanitization."""
        ticket = {
            "key": "PROJ-456",
            "project": "PROJ",
            "title": "Fix bug in module/component: What's wrong? <Test>"
        }
        
        title = formatter._format_title(ticket)
        # Forward slash, colon, question mark, and angle brackets should be replaced
        assert title == "PROJ-456 Fix bug in module-component- What's wrong- -Test-"
        
        # Test with multiple slashes
        ticket['title'] = "Update docs/readme/guide"
        title = formatter._format_title(ticket)
        assert title == "PROJ-456 Update docs-readme-guide"
        
        # Test with newlines and tabs
        ticket['title'] = "Fix\nbug\twith\rspaces"
        title = formatter._format_title(ticket)
        assert title == "PROJ-456 Fix bug with spaces"
    
    def test_format_note_structure(self, formatter, sample_ticket):
        """Test that format_note returns correct structure."""
        title, content = formatter.format_note(sample_ticket)
        
        assert title == "PROJ-123 Sample ticket title"
        assert "# PROJ-123 Sample ticket title" in content
        assert "## Metadata" in content
        assert "## Description" in content
        assert "## Comments" in content
        assert "[View in JIRA]" in content
    
    def test_format_yaml_frontmatter(self, formatter, sample_ticket):
        """Test YAML frontmatter formatting."""
        frontmatter = formatter._format_yaml_frontmatter(sample_ticket)
        
        assert 'aliases:\n  - PROJ-123' in frontmatter
        assert 'assignee: "[[John Doe]]"' in frontmatter
        assert 'reporter: "[[Jane Smith]]"' in frontmatter
        assert 'priority: High' in frontmatter
        assert 'status: In Progress' in frontmatter
        assert 'story_points: 5' in frontmatter
        assert 'sprint: Sprint 23' in frontmatter
        assert 'due_date: 2024-01-15' in frontmatter
        
    def test_format_yaml_frontmatter_unassigned(self, formatter):
        """Test YAML frontmatter with unassigned/unknown values."""
        ticket = {
            'key': 'PROJ-456',
            'project': 'PROJ',
            'assignee': 'Unassigned',
            'reporter': 'Unknown',
            'priority': 'Low',
            'status': 'To Do',
            'created': '2024-01-01T10:00:00+00:00',
            'updated': '2024-01-01T10:00:00+00:00'
        }
        
        frontmatter = formatter._format_yaml_frontmatter(ticket)
        
        # Should not have wikilinks for Unassigned/Unknown
        assert 'assignee: Unassigned' in frontmatter
        assert 'reporter: Unknown' in frontmatter
        assert 'assignee: "[[Unassigned]]"' not in frontmatter
        assert 'reporter: "[[Unknown]]"' not in frontmatter
    
    def test_format_metadata_optional_fields(self, formatter):
        """Test metadata formatting with missing optional fields."""
        ticket = {
            "key": "PROJ-123",
            "project": "PROJ",
            "title": "Title",
            "assignee": "John",
            "reporter": "Jane",
            "priority": "Low",
            "status": "In Progress",
            "created": "2024-01-01T10:00:00+00:00",
            "updated": "2024-01-01T10:00:00+00:00"
        }
        
        metadata = formatter._format_metadata(ticket)
        
        assert "Story Points" not in metadata
        assert "Sprint" not in metadata
        assert "Due Date" not in metadata
    
    def test_format_empty_description(self, formatter):
        """Test formatting empty description."""
        ticket = {"description": ""}
        description = formatter._format_description(ticket)
        assert description == "*No description provided*"
    
    def test_format_comments(self, formatter, sample_ticket):
        """Test comment formatting."""
        comments = formatter._format_comments(sample_ticket["comments"])
        
        assert "### Alice - 2024-01-01 11:00" in comments
        assert "This is a comment" in comments
    
    def test_format_empty_comments(self, formatter):
        """Test formatting empty comments list."""
        comments = formatter._format_comments([])
        assert comments == ""
    
    def test_format_footer(self, formatter, sample_ticket):
        """Test footer formatting."""
        footer = formatter._format_footer(sample_ticket)
        assert footer == "---\n[View in JIRA](https://test.atlassian.net/browse/PROJ-123)"
    
    def test_convert_jira_to_markdown(self, formatter):
        """Test JIRA wiki to Markdown conversion."""
        jira_text = """h1. Header 1
h2. Header 2
*bold text*
_italic text_
+underlined+
-strikethrough-
* List item 1
* List item 2
# Numbered item
{code}
some code
{code}"""
        
        result = formatter._convert_jira_to_markdown(jira_text)
        
        assert "# Header 1" in result
        assert "## Header 2" in result
        assert "**bold text**" in result
        assert "*italic text*" in result
        assert "<u>underlined</u>" in result
        assert "~~strikethrough~~" in result
        assert "- List item 1" in result
        assert "1. Numbered item" in result
        assert "```" in result
    
    def test_format_date(self, formatter):
        """Test date formatting."""
        date_str = "2024-01-01T15:30:45+00:00"
        formatted = formatter._format_date(date_str)
        assert formatted == "2024-01-01 15:30"
    
    def test_format_invalid_date(self, formatter):
        """Test formatting invalid date returns original."""
        invalid_date = "not-a-date"
        formatted = formatter._format_date(invalid_date)
        assert formatted == "not-a-date"