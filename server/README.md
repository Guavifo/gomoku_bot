# Gomoku Server

A FastAPI-based Gomoku server for the educational hackathon. This server manages games, handles WebSocket connections from bots and human players, tracks ELO ratings, and provides a web interface for human play and spectating.

## Features

- **Real-time multiplayer** via WebSockets
- **ELO rating system** with adaptive K-factors
- **Game variants**: Randomized 3-stone opening to reduce first-player advantage
- **Spectator mode**: Watch any active game in real-time
- **Leaderboard**: Track player rankings and statistics
- **Web UI**: Play as a human or spectate games through your browser
- **Game history**: All games saved to text files with full move history

## Quick Start

### 1. Set Up Virtual Environment (Recommended)

**Windows:**
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# You should see (.venv) in your prompt
```

**Linux/Mac:**
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# You should see (.venv) in your prompt
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Server

```bash
python server.py
```

The server will start and display:
```
[SERVER] Gomoku server started
[SERVER] Server running at: http://0.0.0.0:8765
[SERVER] Local access: http://localhost:8765
[SERVER] WebSocket endpoint: ws://0.0.0.0:8765/ws
[SERVER] Board size: 19x19
[SERVER] Move timeout: 60s
[SERVER] Heartbeat interval: 10s
```

### 4. Access the Web UI

Open your browser and go to:
```
http://localhost:8765
```

**To access from other computers on your network:**
1. Find your server's IP address:
   - Windows: `ipconfig`
   - Linux/Mac: `hostname -I`
2. Use that IP: `http://192.168.x.x:8765`

### Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

## For Human Players

1. Open http://localhost:8765 in your browser
2. Enter a username (leave token empty to register)
3. Click "Connect"
4. Create a game or join an existing one
5. Play by clicking on the board

## For Bot Developers

See the separate `gomoku-bot-template` repository for:
- Starter bot code
- API documentation
- How to connect and play

## HTTP API

### POST /register
Register a new user and get a token.

**Parameters:**
- `username` (string): 3-20 characters, alphanumeric with underscores
- `is_bot` (boolean, optional): Set to `true` for bots, default `false`

**Response:**
```json
{
  "username": "alice",
  "token": "a3f5e8d2-4b1c-4a9e-8f2d-1c5b3a7e9d4f"
}
```

### GET /leaderboard
Get the current leaderboard sorted by ELO.

**Response:**
```json
{
  "leaderboard": [
    {
      "username": "alice",
      "elo": 1050,
      "games_played": 10,
      "wins": 6,
      "losses": 4,
      "win_rate": 60.0,
      "is_bot": false
    },
    ...
  ]
}
```

## WebSocket API

### Connection Flow
1. Connect to `ws://localhost:8765/ws`
2. Send authentication message
3. Receive confirmation
4. Send game commands

### Message Types

#### Client → Server

**authenticate**
```json
{
  "type": "authenticate",
  "token": "your-token-here"
}
```

**create_game**
```json
{
  "type": "create_game"
}
```

**join_game**
```json
{
  "type": "join_game",
  "game_id": "abc123"
}
```

**make_move**
```json
{
  "type": "make_move",
  "row": 10,
  "col": 9
}
```

**resign**
```json
{
  "type": "resign"
}
```

**spectate**
```json
{
  "type": "spectate",
  "game_id": "abc123"
}
```

**list_lobby** - Request current waiting games
```json
{
  "type": "list_lobby"
}
```

**list_active_games** - Request active games for spectating
```json
{
  "type": "list_active_games"
}
```

**pong** - Response to server ping
```json
{
  "type": "pong"
}
```

#### Server → Client

**authenticated**
```json
{
  "type": "authenticated",
  "username": "alice"
}
```

**ping** - Heartbeat (respond with pong)
```json
{
  "type": "ping"
}
```

**lobby_update** - Updated list of waiting games
```json
{
  "type": "lobby_update",
  "games": [
    {
      "game_id": "abc123",
      "creator": "bob",
      "creator_elo": 1020,
      "is_bot": true,
      "created_at": "2024-12-15T14:30:22",
      "waiting_time": 15
    }
  ]
}
```

**active_games_update** - Updated list of active/completed games
```json
{
  "type": "active_games_update",
  "games": [
    {
      "game_id": "def456",
      "player1": "alice",
      "player2": "bob",
      "player1_elo": 1050,
      "player2_elo": 1020,
      "player1_color": 1,
      "combined_elo": 2070,
      "move_count": 25,
      "spectator_count": 3,
      "status": "active",
      "current_turn": "alice"
    }
  ]
}
```

**game_created**
```json
{
  "type": "game_created",
  "game_id": "abc123",
  "color": 1
}
```

**game_started**
```json
{
  "type": "game_started",
  "game_id": "abc123",
  "player1": "alice",
  "player2": "bob",
  "your_color": 1
}
```

**game_update**
```json
{
  "type": "game_update",
  "game_id": "abc123",
  "board": [[0,0,1,...], ...],
  "move_history": [
    {"row": 10, "col": 10, "color": 1, "is_opening": true},
    {"row": 11, "col": 12, "color": 2, "is_opening": true},
    ...
  ],
  "current_turn": 1,
  "current_player": "alice",
  "game_over": false,
  "winner": null,
  "outcome": null,
  "time_left": 45.3
}
```

**error**
```json
{
  "type": "error",
  "code": "INVALID_MOVE",
  "message": "Position (10,10) is already occupied"
}
```

### Error Codes
- `AUTH_REQUIRED`: Must authenticate first
- `INVALID_TOKEN`: Token is invalid
- `ALREADY_IN_GAME`: Player already in a game
- `GAME_NOT_FOUND`: Game doesn't exist
- `NOT_IN_GAME`: Player is not in a game
- `GAME_NOT_ACTIVE`: Game is not active
- `NOT_YOUR_TURN`: It's not your turn
- `INVALID_MOVE`: Move is invalid (with explanation)

## Game Rules

- **Board**: 19x19 grid
- **Opening**: 3 random stones placed in center 5x5 area (center ±2, positions 7-11 on 0-indexed board) - Black, White, Black
- **First move**: White (player 2) makes move #4 after the random opening
- **Win condition**: 5 or more stones in a row (horizontal, vertical, diagonal)
- **Turn timer**: 60 seconds per move
- **Colors**: 1 = Black, 2 = White

## ELO System

- **Starting ELO**: 1000
- **K-factor**: Starts at 60, decreases linearly to 30 over first 30 games
- **K-factor averaging**: When two players with different K-factors play, their K-factors are averaged
- **Zero-sum**: Winner gains exactly what loser loses

## Game Files

Games are saved to `games/` directory with filename format:
```
game_YYYY-MM-DD_HHMMSS_player1_vs_player2.txt
```

Example content:
```
Game: 2024-12-15_143022_alice_vs_bob
Players: alice (Black, 1050) vs bob (White, 980)
Winner: alice (Black)
ELO Changes: alice +28, bob -28
Outcome: WIN_NORMAL

Random Opening:
(10,10):B
(11,12):W
(9,13):B

Moves:
(8,10):W
(12,11):B
...
```

## Configuration

All configuration is in `server.py`:
- `BOARD_SIZE = 19`
- `MOVE_TIMEOUT = 60` seconds
- `RECONNECT_GRACE_PERIOD = 60` seconds
- `HEARTBEAT_INTERVAL = 10` seconds
- `POST_GAME_MEMORY = 600` seconds (10 minutes)
- `INITIAL_ELO = 1000`
- `INITIAL_K_FACTOR = 60`
- `FINAL_K_FACTOR = 30`
- `K_TRANSITION_GAMES = 30`

## Server Logs

The server logs important events:
- `[CONNECTION]` - User connected
- `[DISCONNECTION]` - User disconnected
- `[REGISTRATION]` - New user registered
- `[GAME CREATED]` - New game created
- `[GAME STARTED]` - Game started with opponent
- `[GAME END]` - Game completed with ELO changes
- `[TIMEOUT]` - Player timed out
- `[RESIGNATION]` - Player resigned
- `[INVALID MOVE]` - Invalid move attempted
- `[SPECTATE]` - User spectating a game

## Database Schema

**users table:**
- `username` (PRIMARY KEY)
- `token` (UNIQUE)
- `elo` (default 1000)
- `games_played` (default 0)
- `wins` (default 0)
- `losses` (default 0)
- `is_bot` (0 or 1)

**games table:**
- `game_id` (PRIMARY KEY)
- `player1`
- `player2`
- `player1_color` (1 or 2)
- `winner`
- `outcome` (WIN_NORMAL, WIN_TIMEOUT, WIN_RESIGN, WIN_DISCONNECT, DRAW)
- `player1_elo_before`
- `player2_elo_before`
- `player1_elo_after`
- `player2_elo_after`
- `timestamp`
- `filepath`

## Troubleshooting

**"Address already in use"**
- Another process is using port 8765
- Change the port in the last line of `server.py`: `uvicorn.run(app, host="0.0.0.0", port=8766)`

**Database locked**
- Close any other processes accessing `gomoku.db`
- Delete `gomoku.db` to start fresh (loses all data)

**Bot can't connect**
- Ensure server is running
- Check bot is using correct WebSocket URL
- Verify token is valid

## License

MIT License - Free for educational use
