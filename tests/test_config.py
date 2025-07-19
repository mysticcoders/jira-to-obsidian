"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from jira_to_obsidian.config import Config, JiraConfig, ObsidianConfig


class TestJiraConfig:
    """Test JiraConfig class."""
    
    def test_from_env_with_all_values(self):
        """Test creating JiraConfig from environment with all values."""
        env_vars = {
            "JIRA_SERVER": "https://test.atlassian.net",
            "JIRA_EMAIL": "test@example.com",
            "JIRA_API_TOKEN": "test-token",
            "JIRA_PROJECTS": "PROJ1,PROJ2,PROJ3"
        }
        
        with patch.dict(os.environ, env_vars):
            config = JiraConfig.from_env()
            
        assert config.server == "https://test.atlassian.net"
        assert config.email == "test@example.com"
        assert config.api_token == "test-token"
        assert config.projects == ["PROJ1", "PROJ2", "PROJ3"]
    
    def test_from_env_strips_trailing_slash(self):
        """Test that trailing slash is stripped from server URL."""
        with patch.dict(os.environ, {"JIRA_SERVER": "https://test.atlassian.net/"}):
            config = JiraConfig.from_env()
            
        assert config.server == "https://test.atlassian.net"
    
    def test_validate_with_valid_config(self):
        """Test validation with valid configuration."""
        config = JiraConfig(
            server="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            projects=["PROJ1"]
        )
        
        errors = config.validate()
        assert len(errors) == 0
    
    def test_validate_with_missing_values(self):
        """Test validation with missing values."""
        config = JiraConfig(server="", email="", api_token="", projects=[])
        
        errors = config.validate()
        assert len(errors) == 4
        assert "JIRA_SERVER is required" in errors
        assert "JIRA_EMAIL is required" in errors
        assert "JIRA_API_TOKEN is required" in errors
        assert "JIRA_PROJECTS is required (comma-separated list)" in errors


class TestObsidianConfig:
    """Test ObsidianConfig class."""
    
    def test_from_env_with_defaults(self):
        """Test creating ObsidianConfig with default values."""
        env_vars = {
            "OBSIDIAN_API_KEY": "test-key"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = ObsidianConfig.from_env()
            
        assert config.api_url == "http://localhost:27123"
        assert config.api_key == "test-key"
        assert config.folder == "JIRA"
        assert config.update_existing is True
    
    def test_from_env_with_custom_values(self):
        """Test creating ObsidianConfig with custom values."""
        env_vars = {
            "OBSIDIAN_API_URL": "http://custom:8080/",
            "OBSIDIAN_API_KEY": "test-key",
            "OBSIDIAN_FOLDER": "Tickets",
            "UPDATE_EXISTING_NOTES": "false"
        }
        
        with patch.dict(os.environ, env_vars):
            config = ObsidianConfig.from_env()
            
        assert config.api_url == "http://custom:8080"
        assert config.folder == "Tickets"
        assert config.update_existing is False
    
    def test_validate_with_valid_config(self):
        """Test validation with valid configuration."""
        config = ObsidianConfig(
            api_url="http://localhost:27123",
            api_key="test-key",
            folder="JIRA",
            update_existing=True
        )
        
        errors = config.validate()
        assert len(errors) == 0
    
    def test_validate_with_missing_values(self):
        """Test validation with missing values."""
        config = ObsidianConfig(
            api_url="http://localhost:27123",
            api_key="",
            folder="JIRA",
            update_existing=True
        )
        
        errors = config.validate()
        assert len(errors) == 1
        assert "OBSIDIAN_API_KEY is required" in errors


class TestConfig:
    """Test Config class."""
    
    def test_from_env_loads_dotenv(self):
        """Test that from_env loads .env file."""
        with patch('jira_to_obsidian.config.load_dotenv') as mock_load:
            with patch.dict(os.environ, {
                "JIRA_SERVER": "https://test.atlassian.net",
                "JIRA_EMAIL": "test@example.com",
                "JIRA_API_TOKEN": "token",
                "JIRA_PROJECTS": "PROJ1",
                "OBSIDIAN_API_KEY": "key"
            }):
                Config.from_env()
                
        mock_load.assert_called_once()
    
    def test_validate_combines_errors(self):
        """Test that validate combines errors from all configs."""
        config = Config(
            jira=JiraConfig(server="", email="", api_token="", projects=[]),
            obsidian=ObsidianConfig(
                api_url="http://localhost:27123",
                api_key="",
                folder="JIRA",
                update_existing=True
            ),
            sync_interval_minutes=5
        )
        
        errors = config.validate()
        assert len(errors) == 5  # 4 from JIRA + 1 from Obsidian
    
    def test_validate_sync_interval(self):
        """Test validation of sync interval."""
        config = Config(
            jira=JiraConfig(
                server="https://test.atlassian.net",
                email="test@example.com",
                api_token="token",
                projects=["PROJ1"]
            ),
            obsidian=ObsidianConfig(
                api_url="http://localhost:27123",
                api_key="key",
                folder="JIRA",
                update_existing=True
            ),
            sync_interval_minutes=0
        )
        
        errors = config.validate()
        assert len(errors) == 1
        assert "SYNC_INTERVAL_MINUTES must be at least 1" in errors