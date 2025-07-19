# JIRA to Obsidian Sync

A Python tool that synchronizes JIRA tickets to your Obsidian vault using the JIRA REST API and Obsidian Local REST API.

## Features

- 🔄 Sync in-progress JIRA tickets to Obsidian notes
- 📝 Rich markdown formatting with metadata, descriptions, and comments
- 🔗 Automatic wiki-linking for assignees and reporters
- 📊 Includes ticket metadata: priority, story points, sprint, dates
- 🔍 Test connections before syncing
- 🎨 Beautiful CLI output with progress indicators
- ⚡ Fast and efficient using UV package manager

## Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- JIRA Cloud account with API access
- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin installed and running

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jira-to-obsidian
   ```

2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

3. Configure your `.env` file with your credentials:
   ```env
   # JIRA Configuration
   JIRA_SERVER=https://your-domain.atlassian.net
   JIRA_EMAIL=your-email@example.com
   JIRA_API_TOKEN=your-jira-api-token
   JIRA_PROJECTS=PROJ1,PROJ2,PROJ3  # Comma-separated list

   # Obsidian Configuration
   OBSIDIAN_API_URL=http://localhost:27123
   OBSIDIAN_API_KEY=your-obsidian-api-key
   OBSIDIAN_FOLDER=JIRA  # Folder within vault for tickets
   ```

## Getting API Tokens

### JIRA API Token
1. Log in to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a name and copy the token

### Obsidian API Key
1. Install the [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin
2. Enable the plugin in Obsidian settings
3. Configure the API key in the plugin settings
4. Make sure the server is running (default port: 27123)

## Usage

You can use either `jira-to-obsidian` or the shorter `j2o` alias for all commands.

### Test Connections

Before syncing, test that both JIRA and Obsidian connections are working:

```bash
uv run j2o test-connections
# or
./run.sh test-connections
```

This will show:
- ✅ JIRA connection status, server version, and accessible projects
- ✅ Obsidian API connection and authentication status
- ❌ Any configuration errors

### Sync All Active Tickets

Sync all tickets (excluding Done/Resolved/Closed) from configured projects:

```bash
uv run j2o sync
# or simply
./run.sh
```

#### Dry Run Mode

To see what would be synced without actually creating/updating files:

```bash
uv run j2o sync --dry-run
# or
uv run j2o sync -n
```

This will show:
- Which tickets would be created or updated
- The full HTTP request details (endpoint, method, headers)
- A preview of the content that would be sent
- File paths where notes would be saved

### Sync Specific Ticket

Sync a single ticket by its key:

```bash
uv run j2o sync --ticket PROJ-123
# or
./run.sh sync --ticket PROJ-123
```

### List JIRA Tickets

List all JIRA tickets (excluding Done/Resolved/Closed) sorted by priority:

```bash
uv run j2o list-jira
# or with specific project
uv run j2o list-jira --project PROJ
```

This displays a color-coded table with:
- Ticket key and summary
- Priority (color-coded from Highest to Lowest)
- Current status
- Assignee

### List Obsidian Notes by Project

List all Obsidian notes for a specific JIRA project:

```bash
uv run j2o list-obsidian
# or with specific project
uv run j2o list-obsidian --project PROJ
```

### Verbose Output

For detailed logging, add the `-v` flag:

```bash
uv run j2o -v sync
```

## Note Format

Each JIRA ticket is saved as a markdown note with the following structure:

```markdown
---
aliases:
  - PROJ-123
assignee: "[[John Doe]]"
reporter: "[[Jane Smith]]"
priority: High
status: In Progress
project: PROJ
key: PROJ-123
story_points: 5
sprint: Sprint 23
created: 2024-01-01 10:00
due_date: 2024-01-15
updated: 2024-01-02 15:30
tags:
  - jira
  - proj
  - in-progress
---

# PROJ-123 Ticket Title

## Description
The ticket description content...

## Comments
### Alice - 2024-01-01 11:00
Comment content...

---
[View in JIRA](https://your-domain.atlassian.net/browse/PROJ-123)
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `JIRA_SERVER` | Your JIRA instance URL | Required |
| `JIRA_EMAIL` | Email for JIRA authentication | Required |
| `JIRA_API_TOKEN` | JIRA API token | Required |
| `JIRA_PROJECTS` | Comma-separated project keys | Required |
| `OBSIDIAN_API_URL` | Obsidian REST API URL | `http://localhost:27123` |
| `OBSIDIAN_API_KEY` | Obsidian API key | Required |
| `OBSIDIAN_FOLDER` | Folder for JIRA tickets | `JIRA` |
| `UPDATE_EXISTING_NOTES` | Update existing notes | `true` |
| `SYNC_INTERVAL_MINUTES` | Sync interval (for automation) | `5` |

## Development

### Running Tests

```bash
uv run pytest
# or with coverage
uv run pytest --cov
```

### Code Formatting

```bash
uv run black src tests
uv run ruff src tests
```

### Project Structure

```
jira-to-obsidian/
├── src/jira_to_obsidian/
│   ├── config.py          # Configuration management
│   ├── jira_client.py     # JIRA API client
│   ├── obsidian_client.py # Obsidian REST API client
│   ├── formatter.py       # Ticket formatting
│   ├── sync.py           # Synchronization logic
│   └── cli.py            # CLI commands
├── tests/                 # Unit tests
├── .env.example          # Environment template
└── pyproject.toml        # Project configuration
```

## Troubleshooting

### Connection Issues

1. **JIRA Connection Failed**
   - Verify your JIRA server URL (should end with `.atlassian.net`)
   - Check API token is valid
   - Ensure your email matches the JIRA account

2. **Obsidian Connection Failed**
   - Make sure Obsidian is running
   - Verify the Local REST API plugin is enabled
   - Check the API URL and port (default: `http://localhost:27123`)
   - Confirm the API key matches the plugin configuration

3. **Projects Not Accessible**
   - Ensure you have read access to the JIRA projects
   - Verify project keys are spelled correctly

### Sync Issues

- **Notes not updating**: Check `UPDATE_EXISTING_NOTES` is set to `true`
- **Folder not found**: The tool will automatically create the folder if needed
- **Missing fields**: Some fields (story points, sprint) may use custom field IDs that vary by JIRA instance

## License

MIT License - see LICENSE file for details