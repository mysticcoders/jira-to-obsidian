"""
Configuration management for JIRA to Obsidian sync
"""

import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv


@dataclass
class JiraConfig:
    """JIRA configuration settings."""
    
    server: str
    email: str
    api_token: str
    projects: List[str]
    
    @classmethod
    def from_env(cls) -> "JiraConfig":
        """Create JiraConfig from environment variables."""
        server = os.getenv("JIRA_SERVER", "").rstrip("/")
        email = os.getenv("JIRA_EMAIL", "")
        api_token = os.getenv("JIRA_API_TOKEN", "")
        projects = [
            p.strip() 
            for p in os.getenv("JIRA_PROJECTS", "").split(",") 
            if p.strip()
        ]
        
        return cls(
            server=server,
            email=email,
            api_token=api_token,
            projects=projects
        )
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.server:
            errors.append("JIRA_SERVER is required")
        if not self.email:
            errors.append("JIRA_EMAIL is required")
        if not self.api_token:
            errors.append("JIRA_API_TOKEN is required")
        if not self.projects:
            errors.append("JIRA_PROJECTS is required (comma-separated list)")
            
        return errors


@dataclass
class ObsidianConfig:
    """Obsidian configuration settings."""
    
    api_url: str
    api_key: str
    folder: str
    update_existing: bool
    
    @classmethod
    def from_env(cls) -> "ObsidianConfig":
        """Create ObsidianConfig from environment variables."""
        return cls(
            api_url=os.getenv("OBSIDIAN_API_URL", "http://localhost:27123").rstrip("/"),
            api_key=os.getenv("OBSIDIAN_API_KEY", ""),
            folder=os.getenv("OBSIDIAN_FOLDER", "JIRA"),
            update_existing=os.getenv("UPDATE_EXISTING_NOTES", "true").lower() == "true"
        )
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.api_key:
            errors.append("OBSIDIAN_API_KEY is required")
            
        return errors


@dataclass
class Config:
    """Complete application configuration."""
    
    jira: JiraConfig
    obsidian: ObsidianConfig
    sync_interval_minutes: int
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create Config from environment variables."""
        load_dotenv()
        
        return cls(
            jira=JiraConfig.from_env(),
            obsidian=ObsidianConfig.from_env(),
            sync_interval_minutes=int(os.getenv("SYNC_INTERVAL_MINUTES", "5"))
        )
    
    def validate(self) -> List[str]:
        """Validate all configuration and return list of errors."""
        errors = []
        errors.extend(self.jira.validate())
        errors.extend(self.obsidian.validate())
        
        if self.sync_interval_minutes < 1:
            errors.append("SYNC_INTERVAL_MINUTES must be at least 1")
            
        return errors