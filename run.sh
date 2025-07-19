#!/bin/bash
# Run the JIRA to Obsidian sync using UV

# Default to sync command if no arguments provided
if [ $# -eq 0 ]; then
    uv run jira-to-obsidian sync
else
    uv run jira-to-obsidian "$@"
fi