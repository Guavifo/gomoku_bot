import asyncio
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Set, Tuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import random

# Configuration
BOARD_SIZE = 19
MOVE_TIMEOUT = 60  # seconds
RECONNECT_GRACE_PERIOD = 60  # seconds
HEARTBEAT_INTERVAL = 10  # seconds
POST_GAME_MEMORY = 86400  # 24 hours in seconds
INITIAL_ELO = 1000
INITIAL_K_FACTOR = 60
FINAL_K_FACTOR = 30
K_TRANSITION_GAMES = 30

@asynccontextmanager
async def lifespan(app):
    # Load recent completed games from database
    load_recent_completed_games()

    # Start background tasks
    asyncio.create_task(heartbeat_task())
    asyncio.create_task(timeout_check_task())
    asyncio.create_task(cleanup_completed_games_task())
    print("[SERVER] Gomoku server started")
    print(f"[SERVER] Server running at: http://0.0.0.0:8000")
    print(f"[SERVER] Local access: http://localhost:8000")
    print(f"[SERVER] WebSocket endpoint: ws://0.0.0.0:8000/ws")
    print(f"[SERVER] Board size: {BOARD_SIZE}x{BOARD_SIZE}")
    print(f"[SERVER] Move timeout: {MOVE_TIMEOUT}s")
    print(f"[SERVER] Heartbeat interval: {HEARTBEAT_INTERVAL}s")
    yield

app = FastAPI(lifespan=lifespan)

# Database initialization
def init_db():
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        elo INTEGER DEFAULT 1000,
        games_played INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        is_bot INTEGER DEFAULT 0
    )''')
    
    # Games table
    c.execute('''CREATE TABLE IF NOT EXISTS games (
        game_id TEXT PRIMARY KEY,
        player1 TEXT NOT NULL,
        player2 TEXT NOT NULL,
        player1_color INTEGER NOT NULL,
        winner TEXT,
        outcome TEXT,
        player1_elo_before INTEGER,
        player2_elo_before INTEGER,
        player1_elo_after INTEGER,
        player2_elo_after INTEGER,
        timestamp TEXT NOT NULL,
        filepath TEXT
    )''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Game state management
class GameState:
    def __init__(self, game_id: str, player1: str, player2: str, player1_color: int, generate_opening: bool = True):
        self.game_id = game_id
        self.player1 = player1
        self.player2 = player2
        self.player1_color = player1_color  # 1 = Black, 2 = White
        self.player2_color = 3 - player1_color
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.move_history = []
        self.current_turn = 2  # White goes first after Black-White-Black opening
        self.game_over = False
        self.winner = None
        self.outcome = None
        self.start_time = time.time()
        self.last_move_time = time.time()
        self.spectators: Set[WebSocket] = set()
        self.player_connections: Dict[str, WebSocket] = {}
        self.end_time = None
        self.elo_changes = {}  # Store ELO changes: {username: change_amount}

        # Generate random opening (3 stones in center 5x5) for new games
        if generate_opening:
            self.generate_random_opening()
    
    def generate_random_opening(self):
        """Generate 3 random stones in the center 5x5 area (rows/cols 7-11)"""
        positions = set()
        center = BOARD_SIZE // 2  # 9 for a 19x19 board
        center_range = range(center - 2, center + 3)  # 7-11 inclusive (5x5 area)
        
        # Generate 3 unique random positions
        while len(positions) < 3:
            row = random.choice(center_range)
            col = random.choice(center_range)
            positions.add((row, col))
        
        positions = list(positions)
        
        # Place stones: Black, White, Black
        colors = [1, 2, 1]
        for (row, col), color in zip(positions, colors):
            self.board[row][col] = color
            self.move_history.append({
                "row": row,
                "col": col,
                "color": color,
                "is_opening": True
            })
    
    def make_move(self, row: int, col: int, color: int) -> bool:
        """Attempt to make a move. Returns True if successful."""
        if self.game_over:
            return False
        if row < 0 or row >= BOARD_SIZE or col < 0 or col >= BOARD_SIZE:
            return False
        if self.board[row][col] != 0:
            return False
        if color != self.current_turn:
            return False
        
        self.board[row][col] = color
        self.move_history.append({
            "row": row,
            "col": col,
            "color": color,
            "is_opening": False
        })
        self.last_move_time = time.time()
        
        # Check for win
        if self.check_win(row, col, color):
            self.game_over = True
            self.winner = self.player1 if color == self.player1_color else self.player2
            self.outcome = "WIN_NORMAL"
            self.end_time = time.time()
            return True
        
        # Check for draw (board full)
        if all(self.board[r][c] != 0 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)):
            self.game_over = True
            self.winner = None
            self.outcome = "DRAW"
            self.end_time = time.time()
            return True
        
        # Switch turns
        self.current_turn = 3 - self.current_turn
        return True
    
    def check_win(self, row: int, col: int, color: int) -> bool:
        """Check if placing a stone at (row, col) creates 5+ in a row"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
            count = 1  # Count the stone just placed
            
            # Check positive direction
            r, c = row + dr, col + dc
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == color:
                count += 1
                r += dr
                c += dc
            
            # Check negative direction
            r, c = row - dr, col - dc
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == color:
                count += 1
                r -= dr
                c -= dc
            
            if count >= 5:
                return True
        
        return False
    
    def get_current_player(self) -> str:
        """Get the username of the player whose turn it is"""
        if self.current_turn == self.player1_color:
            return self.player1
        return self.player2
    
    def forfeit(self, player: str, reason: str):
        """Forfeit the game for a player"""
        if self.game_over:
            return
        
        self.game_over = True
        self.winner = self.player2 if player == self.player1 else self.player1
        
        if reason == "timeout":
            self.outcome = "WIN_TIMEOUT"
        elif reason == "disconnect":
            self.outcome = "WIN_DISCONNECT"
        elif reason == "resignation":
            self.outcome = "WIN_RESIGN"
        else:
            self.outcome = "WIN_DISCONNECT"
        
        self.end_time = time.time()

# Connection management
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # username -> websocket
        self.user_info: Dict[str, dict] = {}  # username -> {token, is_bot, last_ping}
        self.waiting_games: Dict[str, GameState] = {}  # game_id -> GameState
        self.active_games: Dict[str, GameState] = {}  # game_id -> GameState
        self.completed_games: List[Tuple[GameState, float]] = []  # (GameState, completion_time)
        self.user_to_game: Dict[str, str] = {}  # username -> game_id
    
    async def connect(self, websocket: WebSocket, username: str):
        self.active_connections[username] = websocket
        self.user_info[username] = {
            "last_ping": time.time()
        }
        print(f"[CONNECTION] {username} connected")
    
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
        if username in self.user_info:
            del self.user_info[username]
        print(f"[DISCONNECTION] {username} disconnected")
    
    async def send_personal_message(self, message: dict, username: str):
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_json(message)
            except Exception:
                pass
    
    async def broadcast_lobby_update(self):
        """Send updated lobby list to all connected clients"""
        lobby_list = []
        for game_id, game in self.waiting_games.items():
            creator = game.player1
            creator_elo = get_user_elo(creator)
            is_bot = get_user_is_bot(creator)
            
            lobby_list.append({
                "game_id": game_id,
                "creator": creator,
                "creator_elo": creator_elo,
                "is_bot": is_bot,
                "created_at": datetime.fromtimestamp(game.start_time).isoformat(),
                "waiting_time": int(time.time() - game.start_time)
            })
        
        message = {
            "type": "lobby_update",
            "games": lobby_list
        }
        
        # Send to all connected users
        for username in list(self.active_connections.keys()):
            await self.send_personal_message(message, username)
    
    async def broadcast_active_games_update(self):
        """Send updated active games list to all connected clients"""
        games_list = []
        
        # Include active games
        for game_id, game in self.active_games.items():
            player1_elo = get_user_elo(game.player1)
            player2_elo = get_user_elo(game.player2)
            
            games_list.append({
                "game_id": game_id,
                "player1": game.player1,
                "player2": game.player2,
                "player1_elo": player1_elo,
                "player2_elo": player2_elo,
                "player1_color": game.player1_color,
                "combined_elo": player1_elo + player2_elo,
                "move_count": len([m for m in game.move_history if not m.get("is_opening", False)]),
                "spectator_count": len(game.spectators),
                "status": "active",
                "current_turn": game.get_current_player()
            })
        
        # Include recently completed games (within 24 hours)
        current_time = time.time()
        for game, completion_time in self.completed_games:
            if current_time - completion_time <= POST_GAME_MEMORY:
                player1_elo = get_user_elo(game.player1)
                player2_elo = get_user_elo(game.player2)

                games_list.append({
                    "game_id": game.game_id,
                    "player1": game.player1,
                    "player2": game.player2,
                    "player1_elo": player1_elo,
                    "player2_elo": player2_elo,
                    "player1_color": game.player1_color,
                    "combined_elo": player1_elo + player2_elo,
                    "move_count": len([m for m in game.move_history if not m.get("is_opening", False)]),
                    "spectator_count": len(game.spectators),
                    "status": "completed",
                    "winner": game.winner,
                    "outcome": game.outcome,
                    "end_time": completion_time
                })

        # Sort by status first (active before completed), then by end_time for completed (most recent first)
        games_list.sort(key=lambda g: (0 if g["status"] == "active" else 1, -g.get("end_time", 0)))
        
        message = {
            "type": "active_games_update",
            "games": games_list
        }
        
        # Send to all connected users
        for username in list(self.active_connections.keys()):
            await self.send_personal_message(message, username)
    
    async def broadcast_game_update(self, game: GameState):
        """Send game state update to players and spectators"""
        message = {
            "type": "game_update",
            "game_id": game.game_id,
            "board": game.board,
            "move_history": game.move_history,
            "current_turn": game.current_turn,
            "current_player": game.get_current_player() if not game.game_over else None,
            "game_over": game.game_over,
            "winner": game.winner,
            "outcome": game.outcome,
            "time_left": max(0, MOVE_TIMEOUT - (time.time() - game.last_move_time)) if not game.game_over else 0,
            "elo_changes": game.elo_changes if game.game_over else {}
        }
        
        # Send to both players using their stored connections
        for player_name, player_ws in game.player_connections.items():
            try:
                await player_ws.send_json(message)
            except Exception:
                pass
        
        # Send to all spectators
        for spectator in list(game.spectators):
            try:
                await spectator.send_json(message)
            except Exception:
                game.spectators.discard(spectator)

manager = ConnectionManager()

# Database helper functions
def get_user_by_token(token: str) -> Optional[str]:
    """Get username by token"""
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE token = ?", (token,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_elo(username: str) -> int:
    """Get user's current ELO"""
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    c.execute("SELECT elo FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else INITIAL_ELO

def get_user_games_played(username: str) -> int:
    """Get number of games played by user"""
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    c.execute("SELECT games_played FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user_is_bot(username: str) -> bool:
    """Check if user is a bot"""
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    c.execute("SELECT is_bot FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return bool(result[0]) if result else False

def calculate_elo_change(winner_elo: int, loser_elo: int, winner_games: int, loser_games: int) -> Tuple[int, int]:
    """Calculate ELO changes for both players"""
    # Calculate K-factor for each player
    winner_k = max(FINAL_K_FACTOR, INITIAL_K_FACTOR - winner_games)
    loser_k = max(FINAL_K_FACTOR, INITIAL_K_FACTOR - loser_games)
    
    # Average K-factor
    k = (winner_k + loser_k) / 2
    
    # Expected scores
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 - expected_winner
    
    # Calculate changes
    winner_change = round(k * (1 - expected_winner))
    loser_change = round(k * (0 - expected_loser))
    
    return winner_change, loser_change

def update_game_result(game: GameState):
    """Update database with game result and ELO changes"""
    if game.winner is None:
        # Draw - no ELO change
        conn = sqlite3.connect('gomoku.db')
        c = conn.cursor()
        
        player1_elo = get_user_elo(game.player1)
        player2_elo = get_user_elo(game.player2)
        
        # Store zero ELO changes for draw
        game.elo_changes[game.player1] = 0
        game.elo_changes[game.player2] = 0
        
        # Update games played
        c.execute("UPDATE users SET games_played = games_played + 1 WHERE username IN (?, ?)",
                  (game.player1, game.player2))
        
        # Save game record
        timestamp = datetime.fromtimestamp(game.start_time).isoformat()
        filename = save_game_to_file(game, player1_elo, player2_elo, player1_elo, player2_elo)
        
        c.execute('''INSERT INTO games 
                     (game_id, player1, player2, player1_color, winner, outcome, 
                      player1_elo_before, player2_elo_before, player1_elo_after, player2_elo_after,
                      timestamp, filepath)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (game.game_id, game.player1, game.player2, game.player1_color, None, game.outcome,
                   player1_elo, player2_elo, player1_elo, player2_elo, timestamp, filename))
        
        conn.commit()
        conn.close()
        return
    
    # Determine winner and loser
    winner = game.winner
    loser = game.player2 if winner == game.player1 else game.player1
    
    # Get current stats
    winner_elo = get_user_elo(winner)
    loser_elo = get_user_elo(loser)
    winner_games = get_user_games_played(winner)
    loser_games = get_user_games_played(loser)
    
    # Calculate ELO changes
    winner_change, loser_change = calculate_elo_change(winner_elo, loser_elo, winner_games, loser_games)
    
    new_winner_elo = winner_elo + winner_change
    new_loser_elo = loser_elo + loser_change
    
    # Store ELO changes in game object for client display
    game.elo_changes[winner] = winner_change
    game.elo_changes[loser] = loser_change
    
    # Update database
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    
    # Update winner
    c.execute('''UPDATE users 
                 SET elo = ?, games_played = games_played + 1, wins = wins + 1
                 WHERE username = ?''',
              (new_winner_elo, winner))
    
    # Update loser
    c.execute('''UPDATE users 
                 SET elo = ?, games_played = games_played + 1, losses = losses + 1
                 WHERE username = ?''',
              (new_loser_elo, loser))
    
    # Save game record
    timestamp = datetime.fromtimestamp(game.start_time).isoformat()
    
    player1_elo_before = winner_elo if winner == game.player1 else loser_elo
    player2_elo_before = loser_elo if winner == game.player1 else winner_elo
    player1_elo_after = new_winner_elo if winner == game.player1 else new_loser_elo
    player2_elo_after = new_loser_elo if winner == game.player1 else new_winner_elo
    
    filename = save_game_to_file(game, player1_elo_before, player2_elo_before, 
                                  player1_elo_after, player2_elo_after)
    
    c.execute('''INSERT INTO games 
                 (game_id, player1, player2, player1_color, winner, outcome, 
                  player1_elo_before, player2_elo_before, player1_elo_after, player2_elo_after,
                  timestamp, filepath)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (game.game_id, game.player1, game.player2, game.player1_color, winner, game.outcome,
               player1_elo_before, player2_elo_before, player1_elo_after, player2_elo_after,
               timestamp, filename))
    
    conn.commit()
    conn.close()
    
    print(f"[GAME END] {winner} defeats {loser}. ELO: {winner} {winner_elo}→{new_winner_elo} (+{winner_change}), {loser} {loser_elo}→{new_loser_elo} ({loser_change})")

def save_game_to_file(game: GameState, p1_elo_before: int, p2_elo_before: int,
                       p1_elo_after: int, p2_elo_after: int) -> str:
    """Save game to text file"""
    timestamp_str = datetime.fromtimestamp(game.start_time).strftime("%Y-%m-%d_%H%M%S")
    filename = f"games/game_{timestamp_str}_{game.player1}_vs_{game.player2}.txt"
    
    # Create games directory if it doesn't exist
    import os
    os.makedirs("games", exist_ok=True)
    
    with open(filename, 'w') as f:
        # Header
        f.write(f"Game: {timestamp_str}_{game.player1}_vs_{game.player2}\n")
        
        # Players info
        p1_color_str = "Black" if game.player1_color == 1 else "White"
        p2_color_str = "Black" if game.player2_color == 1 else "White"
        f.write(f"Players: {game.player1} ({p1_color_str}, {p1_elo_before}) vs {game.player2} ({p2_color_str}, {p2_elo_before})\n")
        
        # Winner and outcome
        if game.winner:
            winner_color = p1_color_str if game.winner == game.player1 else p2_color_str
            f.write(f"Winner: {game.winner} ({winner_color})\n")
        else:
            f.write(f"Winner: Draw\n")
        
        # ELO changes
        p1_change = p1_elo_after - p1_elo_before
        p2_change = p2_elo_after - p2_elo_before
        p1_change_str = f"+{p1_change}" if p1_change >= 0 else str(p1_change)
        p2_change_str = f"+{p2_change}" if p2_change >= 0 else str(p2_change)
        f.write(f"ELO Changes: {game.player1} {p1_change_str}, {game.player2} {p2_change_str}\n")
        f.write(f"Outcome: {game.outcome}\n\n")
        
        # Random opening
        f.write("Random Opening:\n")
        for move in game.move_history:
            if move.get("is_opening", False):
                color_str = "B" if move["color"] == 1 else "W"
                f.write(f"({move['row']},{move['col']}):{color_str}\n")
        
        # Moves
        f.write("\nMoves:\n")
        for move in game.move_history:
            if not move.get("is_opening", False):
                color_str = "B" if move["color"] == 1 else "W"
                f.write(f"({move['row']},{move['col']}):{color_str}\n")
    
    return filename

def load_recent_completed_games() -> None:
    """Load completed games from the last 24 hours from database into memory"""
    # Calculate cutoff time (24 hours ago)
    cutoff_time = datetime.now().timestamp() - POST_GAME_MEMORY
    cutoff_datetime = datetime.fromtimestamp(cutoff_time).isoformat()

    # Query games completed in the last 24 hours
    with sqlite3.connect('gomoku.db') as conn:
        c = conn.cursor()
        c.execute('''SELECT game_id, player1, player2, player1_color, winner, outcome,
                            timestamp, filepath
                     FROM games
                     WHERE timestamp > ?
                     ORDER BY timestamp DESC''', (cutoff_datetime,))
        results = c.fetchall()

    loaded_count = 0
    for row in results:
        game_id, player1, player2, player1_color, winner, outcome, timestamp_str, filepath = row

        # Parse the game file to get move history
        move_history = []
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    in_opening = False
                    in_moves = False

                    for line in f:
                        line = line.strip()
                        if line == "Random Opening:":
                            in_opening = True
                            in_moves = False
                            continue
                        elif line == "Moves:":
                            in_opening = False
                            in_moves = True
                            continue

                        # Parse move line: (row,col):Color
                        if (in_opening or in_moves) and line.startswith('('):
                            try:
                                # Extract (row,col):Color
                                coord_part, color_part = line.split(':')
                                coord_part = coord_part.strip('()')
                                row, col = map(int, coord_part.split(','))
                                color = 1 if color_part == 'B' else 2

                                move_history.append({
                                    "row": row,
                                    "col": col,
                                    "color": color,
                                    "is_opening": in_opening
                                })
                            except (ValueError, IndexError) as e:
                                print(f"[LOAD] Warning: Failed to parse move line '{line}': {e}")
                                continue
            except (OSError, IOError) as e:
                print(f"[LOAD] Warning: Could not load game file {filepath}: {e}")
                continue

        # Create GameState without generating random opening
        game = GameState(game_id, player1, player2, player1_color, generate_opening=False)
        game.move_history = move_history
        game.game_over = True
        game.winner = winner
        game.outcome = outcome

        # Reconstruct the board from move history
        for move in move_history:
            game.board[move['row']][move['col']] = move['color']

        # Parse timestamp to get completion time
        completion_time = datetime.fromisoformat(timestamp_str).timestamp()

        # Add to completed games
        manager.completed_games.append((game, completion_time))
        loaded_count += 1

    print(f"[STARTUP] Loaded {loaded_count} completed games from the last 24 hours")

# Background tasks
async def heartbeat_task():
    """Send periodic pings to all connected clients"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        
        for username in list(manager.active_connections.keys()):
            try:
                await manager.send_personal_message({"type": "ping"}, username)
            except Exception:
                pass

async def timeout_check_task():
    """Check for move timeouts"""
    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        
        current_time = time.time()
        
        for game_id, game in list(manager.active_games.items()):
            if game.game_over:
                continue
            
            # Check if current player has exceeded move timeout
            time_since_last_move = current_time - game.last_move_time
            if time_since_last_move > MOVE_TIMEOUT:
                current_player = game.get_current_player()
                print(f"[TIMEOUT] {current_player} timed out in game {game_id}")
                game.forfeit(current_player, "timeout")
                
                # Update database
                update_game_result(game)
                
                # Broadcast final state
                await manager.broadcast_game_update(game)
                
                # Move to completed games
                manager.completed_games.append((game, time.time()))
                del manager.active_games[game_id]
                
                # Remove from user_to_game mapping
                if game.player1 in manager.user_to_game:
                    del manager.user_to_game[game.player1]
                if game.player2 in manager.user_to_game:
                    del manager.user_to_game[game.player2]
                
                # Update active games list
                await manager.broadcast_active_games_update()

async def cleanup_completed_games_task():
    """Remove completed games from memory after POST_GAME_MEMORY seconds"""
    while True:
        await asyncio.sleep(60)  # Check every minute
        
        current_time = time.time()
        manager.completed_games = [
            (game, completion_time)
            for game, completion_time in manager.completed_games
            if current_time - completion_time <= POST_GAME_MEMORY
        ]

# HTTP endpoints
@app.post("/register")
async def register(username: str, is_bot: bool = False):
    """Register a new user"""
    # Validate username
    if len(username) < 3 or len(username) > 20:
        return {"error": "Username must be 3-20 characters"}
    
    if not username.replace("_", "").isalnum():
        return {"error": "Username must be alphanumeric with underscores"}
    
    # Check if username already exists
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return {"error": "Username already exists"}
    
    # Generate token
    token = str(uuid.uuid4())
    
    # Insert user
    c.execute('''INSERT INTO users (username, token, elo, games_played, wins, losses, is_bot)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (username, token, INITIAL_ELO, 0, 0, 0, 1 if is_bot else 0))
    conn.commit()
    conn.close()
    
    print(f"[REGISTRATION] New user: {username} (bot={is_bot})")
    return {"username": username, "token": token}

@app.get("/leaderboard")
async def get_leaderboard():
    """Get leaderboard sorted by ELO"""
    conn = sqlite3.connect('gomoku.db')
    c = conn.cursor()
    c.execute('''SELECT username, elo, games_played, wins, losses, is_bot
                 FROM users
                 ORDER BY elo DESC''')
    results = c.fetchall()
    conn.close()
    
    leaderboard = []
    for row in results:
        username, elo, games_played, wins, losses, is_bot = row
        win_rate = (wins / games_played * 100) if games_played > 0 else 0
        leaderboard.append({
            "username": username,
            "elo": elo,
            "games_played": games_played,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "is_bot": bool(is_bot)
        })
    
    return {"leaderboard": leaderboard}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    username = None
    
    try:
        # Wait for authentication (don't accept yet)
        await websocket.accept()
        auth_message = await websocket.receive_json()
        
        if auth_message.get("type") != "authenticate":
            await websocket.send_json({"type": "error", "code": "AUTH_REQUIRED", "message": "Must authenticate first"})
            await websocket.close()
            return
        
        token = auth_message.get("token")
        if not token:
            await websocket.send_json({"type": "error", "code": "INVALID_TOKEN", "message": "Token required"})
            await websocket.close()
            return
        
        # Verify token
        username = get_user_by_token(token)
        if not username:
            await websocket.send_json({"type": "error", "code": "INVALID_TOKEN", "message": "Invalid token"})
            await websocket.close()
            return
        
        # Connect user
        await manager.connect(websocket, username)
        await websocket.send_json({"type": "authenticated", "username": username})
        
        # Send initial lobby and active games
        await manager.broadcast_lobby_update()
        await manager.broadcast_active_games_update()
        
        # Message loop
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            
            if message_type == "pong":
                # Update last ping time
                if username in manager.user_info:
                    manager.user_info[username]["last_ping"] = time.time()
            
            elif message_type == "create_game":
                # Check if user already in a game
                if username in manager.user_to_game:
                    await websocket.send_json({
                        "type": "error",
                        "code": "ALREADY_IN_GAME",
                        "message": "You already have a game waiting. Cancel it first or wait for opponent."
                    })
                    continue
                
                # Create new game
                game_id = str(uuid.uuid4())[:8]
                
                # Player 1 is creator, randomly assign color
                player1_color = random.choice([1, 2])
                
                game = GameState(game_id, username, None, player1_color)
                manager.waiting_games[game_id] = game
                manager.user_to_game[username] = game_id
                game.player_connections[username] = websocket
                
                await websocket.send_json({
                    "type": "game_created",
                    "game_id": game_id,
                    "color": player1_color
                })
                
                # Broadcast lobby update
                await manager.broadcast_lobby_update()
                
                print(f"[GAME CREATED] {username} created game {game_id}")
            
            elif message_type == "join_game":
                game_id = message.get("game_id")
                
                # Check if user already in a game
                if username in manager.user_to_game:
                    await websocket.send_json({
                        "type": "error",
                        "code": "ALREADY_IN_GAME",
                        "message": "You are already in a game"
                    })
                    continue
                
                # Check if game exists
                if game_id not in manager.waiting_games:
                    await websocket.send_json({
                        "type": "error",
                        "code": "GAME_NOT_FOUND",
                        "message": "Game not found or already started"
                    })
                    continue
                
                game = manager.waiting_games[game_id]
                
                # Join game
                game.player2 = username
                game.player_connections[username] = websocket
                manager.user_to_game[username] = game_id
                
                # Reset the move timer - game is now starting
                game.last_move_time = time.time()
                
                # Move to active games
                del manager.waiting_games[game_id]
                manager.active_games[game_id] = game
                
                # Notify both players
                await manager.send_personal_message({
                    "type": "game_started",
                    "game_id": game_id,
                    "player1": game.player1,
                    "player2": game.player2,
                    "your_color": game.player1_color
                }, game.player1)
                
                await manager.send_personal_message({
                    "type": "game_started",
                    "game_id": game_id,
                    "player1": game.player1,
                    "player2": game.player2,
                    "your_color": game.player2_color
                }, game.player2)
                
                # Send initial game state
                await manager.broadcast_game_update(game)
                
                # Update lobby and active games
                await manager.broadcast_lobby_update()
                await manager.broadcast_active_games_update()
                
                print(f"[GAME STARTED] {game.player1} vs {game.player2} (game {game_id})")
            
            elif message_type == "make_move":
                row = message.get("row")
                col = message.get("col")

                # Validate row and col are integers
                if not isinstance(row, int) or not isinstance(col, int):
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_MOVE",
                        "message": "Row and col must be integers"
                    })
                    continue

                # Find user's game
                if username not in manager.user_to_game:
                    await websocket.send_json({
                        "type": "error",
                        "code": "NOT_IN_GAME",
                        "message": "You are not in a game"
                    })
                    continue
                
                game_id = manager.user_to_game[username]
                
                if game_id not in manager.active_games:
                    await websocket.send_json({
                        "type": "error",
                        "code": "GAME_NOT_ACTIVE",
                        "message": "Game is not active"
                    })
                    continue
                
                game = manager.active_games[game_id]
                
                # Validate it's player's turn
                if game.get_current_player() != username:
                    await websocket.send_json({
                        "type": "error",
                        "code": "NOT_YOUR_TURN",
                        "message": "It is not your turn"
                    })
                    continue
                
                # Determine player's color
                player_color = game.player1_color if username == game.player1 else game.player2_color
                
                # Attempt move
                if game.make_move(row, col, player_color):
                    # Check if game is over
                    if game.game_over:
                        # Update database (calculates ELO changes)
                        update_game_result(game)

                        # Broadcast final state with ELO changes
                        await manager.broadcast_game_update(game)

                        # Move to completed games
                        manager.completed_games.append((game, time.time()))
                        del manager.active_games[game_id]

                        # Remove from user_to_game mapping
                        if game.player1 in manager.user_to_game:
                            del manager.user_to_game[game.player1]
                        if game.player2 in manager.user_to_game:
                            del manager.user_to_game[game.player2]

                        # Update active games list
                        await manager.broadcast_active_games_update()
                    else:
                        # Game continues - broadcast move update
                        await manager.broadcast_game_update(game)
                else:
                    # Invalid move
                    if row < 0 or row >= BOARD_SIZE or col < 0 or col >= BOARD_SIZE:
                        error_msg = f"Position ({row},{col}) is out of bounds"
                    elif game.board[row][col] != 0:
                        error_msg = f"Position ({row},{col}) is already occupied"
                    else:
                        error_msg = "Invalid move"
                    
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_MOVE",
                        "message": error_msg
                    })
                    print(f"[INVALID MOVE] {username}: {error_msg}")
            
            elif message_type == "resign":
                # Find user's game
                if username not in manager.user_to_game:
                    await websocket.send_json({
                        "type": "error",
                        "code": "NOT_IN_GAME",
                        "message": "You are not in a game"
                    })
                    continue
                
                game_id = manager.user_to_game[username]
                
                if game_id in manager.waiting_games:
                    # Cancel waiting game
                    game = manager.waiting_games[game_id]
                    del manager.waiting_games[game_id]
                    del manager.user_to_game[username]
                    await websocket.send_json({"type": "game_cancelled"})
                    await manager.broadcast_lobby_update()
                    print(f"[GAME CANCELLED] {username} cancelled game {game_id}")
                    
                elif game_id in manager.active_games:
                    # Resign from active game
                    game = manager.active_games[game_id]
                    game.forfeit(username, "resignation")
                    
                    # Update database
                    update_game_result(game)
                    
                    # Broadcast final state
                    await manager.broadcast_game_update(game)
                    
                    # Move to completed games
                    manager.completed_games.append((game, time.time()))
                    del manager.active_games[game_id]
                    
                    # Remove from user_to_game mapping
                    if game.player1 in manager.user_to_game:
                        del manager.user_to_game[game.player1]
                    if game.player2 in manager.user_to_game:
                        del manager.user_to_game[game.player2]
                    
                    # Update active games list
                    await manager.broadcast_active_games_update()
                    
                    print(f"[RESIGNATION] {username} resigned from game {game_id}")
            
            elif message_type == "spectate":
                game_id = message.get("game_id")
                
                # Check if game exists in active or completed
                game = None
                if game_id in manager.active_games:
                    game = manager.active_games[game_id]
                else:
                    # Check completed games
                    for completed_game, _ in manager.completed_games:
                        if completed_game.game_id == game_id:
                            game = completed_game
                            break
                
                if not game:
                    await websocket.send_json({
                        "type": "error",
                        "code": "GAME_NOT_FOUND",
                        "message": "Game not found"
                    })
                    continue
                
                # Add to spectators
                game.spectators.add(websocket)
                
                # Send current game state
                message = {
                    "type": "spectate_game",
                    "game_id": game.game_id,
                    "player1": game.player1,
                    "player2": game.player2,
                    "player1_color": game.player1_color,
                    "board": game.board,
                    "move_history": game.move_history,
                    "current_turn": game.current_turn,
                    "current_player": game.get_current_player() if not game.game_over else None,
                    "game_over": game.game_over,
                    "winner": game.winner,
                    "outcome": game.outcome
                }
                await websocket.send_json(message)
                
                print(f"[SPECTATE] {username} is spectating game {game_id}")
            
            elif message_type == "list_lobby":
                await manager.broadcast_lobby_update()
            
            elif message_type == "list_active_games":
                await manager.broadcast_active_games_update()
    
    except WebSocketDisconnect:
        print(f"[DISCONNECT] {username} disconnected")
    except Exception as e:
        print(f"[ERROR] WebSocket error for {username}: {e}")
    finally:
        if username:
            # Handle disconnection
            manager.disconnect(username)
            
            # Check if user was in a game
            if username in manager.user_to_game:
                game_id = manager.user_to_game[username]
                
                if game_id in manager.waiting_games:
                    # Remove waiting game
                    del manager.waiting_games[game_id]
                    del manager.user_to_game[username]
                    await manager.broadcast_lobby_update()
                
                elif game_id in manager.active_games:
                    # Forfeit active game after grace period
                    # For now, immediate forfeit on disconnect
                    game = manager.active_games[game_id]
                    game.forfeit(username, "disconnect")
                    
                    # Update database
                    update_game_result(game)
                    
                    # Broadcast final state
                    await manager.broadcast_game_update(game)
                    
                    # Move to completed games
                    manager.completed_games.append((game, time.time()))
                    del manager.active_games[game_id]
                    
                    # Remove from user_to_game mapping
                    if game.player1 in manager.user_to_game:
                        del manager.user_to_game[game.player1]
                    if game.player2 in manager.user_to_game:
                        del manager.user_to_game[game.player2]
                    
                    # Update active games list
                    await manager.broadcast_active_games_update()

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
