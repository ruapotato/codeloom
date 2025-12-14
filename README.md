# codeloom

A lightweight Claude Code terminal interface designed for phones, SSH sessions, and low-bandwidth connections.

## Features

- **Minimal footprint** - Simple ANSI terminal output, no heavy TUI
- **Live streaming** - See AI responses and command outputs as they happen
- **Session management** - Full conversation history with save/load
- **Profile system** - Persistent system prompts and notes
- **Interrupt support** - Ctrl+C to stop generation
- **Tool visibility** - See file reads, writes, bash commands, and their outputs

## Requirements

- Python 3.8+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and configured

## Installation

```bash
git clone https://github.com/yourusername/codeloom.git
cd codeloom
./install.sh
```

Options:
- `./install.sh` - Install to ~/.local/bin (user)
- `./install.sh --system` - Install to /usr/local/bin (system-wide)
- `./install.sh --uninstall` - Remove codeloom

## Usage

```bash
codeloom                    # Start new session
codeloom -s SESSION_ID      # Resume a session
codeloom -l                 # List all sessions
```

## Commands

### Session Commands
| Command | Description |
|---------|-------------|
| `/new [name]` | Create new session |
| `/list` | List all sessions |
| `/load <id>` | Load a session |
| `/save` | Save current session |
| `/rename <name>` | Rename current session |
| `/delete <id>` | Delete a session |
| `/history` | Show conversation history |

### Profile Commands
| Command | Description |
|---------|-------------|
| `/profile [name]` | Show current or switch to profile |
| `/profiles` | List all profiles |
| `/prompt [text]` | Show or set system prompt |
| `/note <text>` | Add a persistent note |
| `/notes` | List all notes |
| `/note del <n>` | Delete note by number |
| `/clearnotes` | Clear all notes |

### Process Commands
| Command | Description |
|---------|-------------|
| `/run <cmd>` | Run command in background |
| `/ps` | List all processes (`/ps -r` for running only) |
| `/output <id>` | Show process output (alias: `/out`) |
| `/kill <id>` | Kill a running process |
| `/pclean` | Remove finished processes from list |

### Other
| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/clear` | Clear screen |
| `/quit` | Exit |

## How It Works

codeloom wraps Claude Code's headless mode (`claude -p`) with streaming JSON output. This provides:

1. **Live output** - Text streams as Claude types
2. **Tool visibility** - Shows when Claude reads/writes files or runs commands
3. **Command output** - Displays bash command results in real-time
4. **Session persistence** - All conversations saved to `~/.config/codeloom/sessions/`

## Output Indicators

When Claude uses tools, you'll see:

```
📝 Writing /path/to/file.py (42 lines)
→ File created successfully

✏️  Editing /path/to/file.py
→ File updated

$ ls -la
→ total 24
→ drwxr-xr-x 2 user user 4096 ...

📖 Reading /path/to/file.py
→ [file contents]

🔍 Grep pattern
→ [search results]
```

## Profiles

Profiles let you customize how Claude behaves with persistent system prompts and notes.

```bash
# Create and switch to a new profile
/profile coding

# Set a system prompt
/prompt You are a senior Python developer. Prefer simple solutions.

# Add persistent notes (always included in context)
/note Project uses FastAPI and SQLAlchemy
/note Follow PEP8 style guidelines
/note Tests are in tests/ directory

# View current profile
/profile

# List all profiles
/profiles
```

The prompt shows your current path and profile: `~/myproject:coding >`

## Background Processes

Run long-running commands (servers, builds, tests) in the background and check on them later:

```bash
# Start a dev server in background
/run npm run dev

# List all processes
/ps

# View output of a process
/output abc123

# Kill a running process
/kill abc123

# Clean up finished processes
/pclean
```

Running processes are automatically tracked and their status is included in Claude's context, so Claude knows what's running.

## Configuration

- Sessions: `~/.config/codeloom/sessions/`
- Profiles: `~/.config/codeloom/profiles/`
- Processes: `~/.config/codeloom/processes/`

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE)
