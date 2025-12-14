# codeloom

A lightweight Claude Code terminal interface designed for phones, SSH sessions, and low-bandwidth connections.

## Features

- **Minimal footprint** - Simple ANSI terminal output, no heavy TUI
- **Live streaming** - See AI responses and command outputs as they happen
- **Session management** - Full conversation history with save/load
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

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/new [name]` | Create new session |
| `/list` | List all sessions |
| `/load <id>` | Load a session |
| `/save` | Save current session |
| `/rename <name>` | Rename current session |
| `/delete <id>` | Delete a session |
| `/history` | Show conversation history |
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

## Configuration

Sessions are stored in `~/.config/codeloom/sessions/` as JSON files.

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE)
