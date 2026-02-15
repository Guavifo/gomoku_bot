# Gomoku Bot

A real-time Gomoku (Five in a Row) platform with a central game server and two AI bots of different difficulty levels. Players and bots connect over WebSockets to play on a 19x19 board.

## How It Works

```
 [Easy Bot]                              [Normal Bot]
     |                                        |
     +--- WebSocket --->[Game Server]<--- WebSocket ---+
                              |
                          WebSocket
                              |
                        [Web Browser]
                        (spectate/play)
```

**Server** hosts games and manages matchmaking. **Bots** connect as clients, find opponents, and play automatically. **Humans** can spectate or play through the web UI at `http://localhost:8000`.

## Components

### Server (`server/`)

A FastAPI + WebSocket server that orchestrates everything:

- Manages game creation, matchmaking, and move validation on a **19x19 board**
- Places **3 random opening stones** in the center before players take turns
- Tracks player stats and **ELO ratings** in a SQLite database
- Supports **spectators** watching games in real time
- **Force bot matches** via drag-and-drop UI for testing specific matchups
- Saves completed games to text files with full move history
- **60-second move timeout** per turn
- **Game analytics** via `analyze_games.py` — generates statistics on win rates, game lengths, and outcomes

### Easy Bot (`easy_bot/`)

A beginner-level bot using simple threat detection:

1. Win if possible (complete a 4-in-a-row)
2. Block the opponent's 4-in-a-row
3. Extend own 3-in-a-row
4. Block opponent's 3-in-a-row
5. Fall back to center or nearby positions

### Normal Bot (`normal_bot/`)

A stronger bot using pattern-based position scoring:

- Scans all 8 directions around every empty cell
- Assigns weighted scores based on pattern strength (e.g., open threes, blocked fours)
- Prioritizes winning moves (10000+ pts) over building attacks (100+ pts) over development (10+ pts)
- Adds small random values to break ties

## Quick Start

**Prerequisites:** Python 3 with `pip`

### 1. Start the Server

```bash
cd server
pip install -r requirements.txt
python server.py
```

The server runs at `http://localhost:8000`. Open this URL in a browser to spectate or play as a human.

### 2. Launch a Bot

Open a **new terminal** for each bot you want to run:

```bash
cd easy_bot          # or: cd normal_bot
pip install -r requirements.txt
python launcher.py
```

The launcher will walk you through:

1. **Create account** - registers the bot with the server
2. **Run bot** - starts playing games automatically

To pit bots against each other, run both the easy and normal bots in separate terminals. They'll automatically find and play each other.

## Game Rules

| Rule | Detail |
|------|--------|
| Board | 19x19 |
| Opening | 3 stones placed randomly in the center 5x5 area |
| Win condition | 5 or more in a row (horizontal, vertical, or diagonal) |
| Turn timer | 60 seconds per move |
| Rating | ELO system updated after each game |

## Project Structure

```
gomoku_bot/
├── server/
│   ├── server.py           # Game server (FastAPI + WebSocket)
│   ├── requirements.txt
│   └── static/
│       └── index.html      # Web UI for spectating/playing
├── easy_bot/
│   ├── bot.py              # Easy bot strategy
│   ├── launcher.py         # Interactive setup tool
│   ├── config.json         # Saved credentials
│   └── requirements.txt
└── normal_bot/
    ├── bot.py              # Normal bot strategy
    ├── launcher.py         # Interactive setup tool
    ├── config.json         # Saved credentials
    └── requirements.txt
```

## Building Your Own Bot

Want to write a better bot? Here's what it needs to do:

1. **Register** - `POST http://localhost:8000/register?username=mybot&is_bot=true` to get a token
2. **Connect** - Open a WebSocket to `ws://localhost:8000/ws`
3. **Authenticate** - Send `{"type": "authenticate", "token": "your_token"}`
4. **Find a game** - Send `{"type": "create_game"}` or `{"type": "join_game", "game_id": "..."}`
5. **Play moves** - When you receive a `game_update` where it's your turn, send `{"type": "make_move", "game_id": "...", "row": r, "col": c}`
6. **Stay alive** - Reply `{"type": "pong"}` when you receive a `ping`

Use `easy_bot/bot.py` as a starting template and swap in your own `choose_move()` logic.
