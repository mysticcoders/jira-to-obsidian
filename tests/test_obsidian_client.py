"""Tests for Obsidian client module."""

from unittest.mock import Mock, patch

import pytest
import requests
import responses

from jira_to_obsidian.config import ObsidianConfig
from jira_to_obsidian.obsidian_client import ObsidianClient


class TestObsidianClient:
    """Test ObsidianClient class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ObsidianConfig(
            api_url="http://localhost:27123",
            api_key="test-key",
            folder="JIRA",
            update_existing=True
        )
    
    @pytest.fixture
    def client(self, config):
        """Create client instance."""
        return ObsidianClient(config)
    
    @responses.activate
    def test_test_connection_success(self, client):
        """Test successful connection test."""
        # Mock listing files in root
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/",
            json={"files": []},
            status=200
        )
        
        # Mock folder check response
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/JIRA/",
            status=200
        )
        
        result = client.test_connection()
        
        assert result["connected"] is True
        assert result["authenticated"] is True
        assert result["folder_exists"] is True
        assert result["folder_path"] == "JIRA"
    
    @responses.activate
    def test_test_connection_unauthorized(self, client):
        """Test connection with invalid API key."""
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/",
            status=401
        )
        
        result = client.test_connection()
        
        assert result["connected"] is True
        assert result["authenticated"] is False
        assert result["error"] == "Invalid API key"
    
    def test_test_connection_no_server(self, client):
        """Test connection when server is not running."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            result = client.test_connection()
            
        assert result["connected"] is False
        assert "Cannot connect to Obsidian REST API" in result["error"]
    
    @responses.activate
    def test_note_exists_true(self, client):
        """Test checking if note exists (exists)."""
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/JIRA/test.md",
            status=200
        )
        
        exists = client.note_exists("JIRA/test.md")
        assert exists is True
    
    @responses.activate
    def test_note_exists_false(self, client):
        """Test checking if note exists (doesn't exist)."""
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/JIRA/test.md",
            status=404
        )
        
        exists = client.note_exists("JIRA/test.md")
        assert exists is False
    
    @responses.activate
    def test_save_note_create(self, client):
        """Test creating a new note."""
        responses.add(
            responses.PUT,
            "http://localhost:27123/vault/JIRA/test.md",
            status=201
        )
        
        success = client.save_note("JIRA/test.md", "# Test Content")
        assert success is True
    
    @responses.activate
    def test_save_note_update(self, client):
        """Test updating an existing note."""
        responses.add(
            responses.PUT,
            "http://localhost:27123/vault/JIRA/test.md",
            status=200
        )
        
        success = client.save_note("JIRA/test.md", "# Updated Content")
        assert success is True
    
    @responses.activate
    def test_save_note_failure(self, client):
        """Test failed note save."""
        responses.add(
            responses.PUT,
            "http://localhost:27123/vault/JIRA/test.md",
            status=500,
            body="Internal Server Error"
        )
        
        success = client.save_note("JIRA/test.md", "# Content")
        assert success is False
    
    @responses.activate
    def test_get_note_content(self, client):
        """Test getting note content."""
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/JIRA/test.md",
            body="# Test Note\nContent here",
            status=200,
            content_type="text/markdown"
        )
        
        content = client.get_note_content("JIRA/test.md")
        assert content == "# Test Note\nContent here"
    
    @responses.activate
    def test_get_note_content_not_found(self, client):
        """Test getting content of non-existent note."""
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/JIRA/test.md",
            status=404
        )
        
        content = client.get_note_content("JIRA/test.md")
        assert content is None
    
    @responses.activate
    def test_delete_note_success(self, client):
        """Test successful note deletion."""
        responses.add(
            responses.DELETE,
            "http://localhost:27123/vault/JIRA/test.md",
            status=204
        )
        
        success = client.delete_note("JIRA/test.md")
        assert success is True
    
    @responses.activate
    def test_create_folder_if_needed(self, client):
        """Test creating folder when it doesn't exist."""
        # Mock folder check - doesn't exist
        responses.add(
            responses.GET,
            "http://localhost:27123/vault/JIRA/",
            status=404
        )
        
        # Mock creating README file
        responses.add(
            responses.PUT,
            "http://localhost:27123/vault/JIRA/README.md",
            status=201
        )
        
        client.create_folder_if_needed()
        
        # Verify README was created
        assert len(responses.calls) == 2
        assert responses.calls[1].request.url.endswith("JIRA/README.md")
    
    def test_headers_include_auth(self, client):
        """Test that headers include authorization."""
        assert client.headers["Authorization"] == "Bearer test-key"
        assert client.headers["Content-Type"] == "application/json"