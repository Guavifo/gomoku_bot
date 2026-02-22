import asyncio
import websockets
import json
import random
import sys
import os

# Load configuration from config.json
def load_config():
    """Load configuration from config.json"""
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    return {
        "server_url": "ws://localhost:8000/ws",
        "username": "",
        "token": ""
    }

# Load config
config = load_config()
SERVER_URL = config.get("server_url", "ws://localhost:8000/ws")
TOKEN = config.get("token", "")
USERNAME = config.get("username", "")

# Board representation
BOARD_SIZE = 19
EMPTY = 0
BLACK = 1
WHITE = 2

class GomokuBot:
    def __init__(self, token, username):
        self.token = token
        self.username = username
        self.ws = None
        self.game_id = None
        self.my_color = None
        self.board = None
        self.game_over = False
        
    async def connect(self):
        """Connect to the game server"""
        print(f"[BOT] Connecting to {SERVER_URL}...")
        self.ws = await websockets.connect(SERVER_URL)
        
        # Authenticate
        await self.send_message({
            "type": "authenticate",
            "token": self.token
        })
        
        print(f"[BOT] Connected as {self.username}")
    
    async def send_message(self, message):
        """Send a message to the server"""
        await self.ws.send(json.dumps(message))
    
    async def handle_message(self, message):
        """Handle incoming messages from server"""
        msg_type = message.get("type")
        
        if msg_type == "authenticated":
            print(f"[BOT] Authenticated successfully")
            # Randomly decide to create or join a game
            await self.find_game()
        
        elif msg_type == "ping":
            # Respond to heartbeat
            await self.send_message({"type": "pong"})
        
        elif msg_type == "lobby_update":
            # Received lobby games list
            games = message.get("games", [])
            if games:
                # Join the oldest waiting game
                oldest_game = games[0]
                print(f"[BOT] Joining game {oldest_game['game_id']} created by {oldest_game['creator']}")
                await self.send_message({
                    "type": "join_game",
                    "game_id": oldest_game["game_id"]
                })
            else:
                # No games available, create one
                print(f"[BOT] No games available, creating new game")
                await self.send_message({"type": "create_game"})
        
        elif msg_type == "game_created":
            self.game_id = message.get("game_id")
            self.my_color = message.get("color")
            color_name = "Black" if self.my_color == BLACK else "White"
            print(f"[BOT] Created game {self.game_id}, playing as {color_name}")
            print(f"[BOT] Waiting for opponent...")
        
        elif msg_type == "game_started":
            self.game_id = message.get("game_id")
            self.my_color = message.get("your_color")
            player1 = message.get("player1")
            player2 = message.get("player2")
            opponent = player2 if player1 == self.username else player1
            color_name = "Black" if self.my_color == BLACK else "White"
            print(f"[BOT] Game started! Playing as {color_name} against {opponent}")
        
        elif msg_type == "game_update":
            self.board = message.get("board")
            current_turn = message.get("current_turn")
            game_over = message.get("game_over")
            winner = message.get("winner")
            
            if game_over:
                self.game_over = True
                if winner == self.username:
                    print(f"[BOT] Victory! I won the game!")
                elif winner:
                    print(f"[BOT] Defeat. {winner} won the game.")
                else:
                    print(f"[BOT] Game ended in a draw.")
                
                # Wait a bit then find another game
                await asyncio.sleep(2)
                self.reset_game_state()
                await self.find_game()
            
            elif current_turn == self.my_color:
                # It's my turn
                move = self.choose_move(self.board, self.my_color, self.game_id)
                if move:
                    row, col = move
                    print(f"[BOT] Making move: ({row},{col})")
                    await self.send_message({
                        "type": "make_move",
                        "row": row,
                        "col": col
                    })
        
        elif msg_type == "error":
            code = message.get("code")
            error_message = message.get("message")
            print(f"[ERROR] {code}: {error_message}")

            if code == "ALREADY_IN_GAME":
                # Already in a game, wait for updates
                pass
            elif code == "GAME_NOT_FOUND":
                # Game not found, try to find another
                await self.find_game()

    async def find_game(self):
        """Create a new game and wait for an opponent"""
        print(f"[BOT] Creating new game")
        await self.send_message({"type": "create_game"})
    
    def reset_game_state(self):
        """Reset game state for next game"""
        self.game_id = None
        self.my_color = None
        self.board = None
        self.game_over = False
    
    def choose_move(self, board, my_color, game_id):
        """
        Choose the best move based on current board state using position ranking system.
        
        This strategy uses a comprehensive scoring system that evaluates each empty position
        by looking at patterns in all 8 directions (horizontal, vertical, and diagonals).
        
        The ranking system prioritizes:
        1. Immediate wins (4-in-a-row that can become 5)
        2. Blocking opponent's immediate wins
        3. Creating forcing moves (3-in-a-row with both ends open)
        4. Blocking opponent's forcing moves
        5. Building 2-in-a-row and 3-in-a-row patterns
        6. General positional play
        """
        # Create rankings matrix
        rankings = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        
        # Rank all empty cells
        opponent_color = 3 - my_color
        rank_cells(board, rankings, my_color, opponent_color)
        
        # Add small random values to break ties
        add_random_rankings(board, rankings)
        
        # Pick the highest ranked position
        return pick_highest(board, rankings)
    
    async def run(self):
        """Main bot loop"""
        self.reset_game_state()
        await self.connect()
        
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Failed to parse message: {e}")
                except Exception as e:
                    print(f"[ERROR] Error handling message: {e}")
        except websockets.exceptions.ConnectionClosed:
            print(f"[BOT] Connection closed")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
        finally:
            if self.ws:
                await self.ws.close()


def add_random_rankings(board, rankings):
    """Add small random values to rankings to break ties"""
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                rankings[row][col] += round(random.random(), 4)


def rank_cells(board, rankings, my_color, opponent_color):
    """
    Rank all empty cells by examining patterns in all 8 directions.
    For each empty cell, look at nearby stones in each direction and score
    the position based on offensive and defensive patterns.
    """
    # 8 directions: right, down-right, down, down-left, left, up-left, up, up-right
    wheel = [[0,1], [1,1], [1,0], [1,-1], [0,-1], [-1,-1], [-1,0], [-1,1]]
    
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            # Only rank empty cells
            if board[row][col] == EMPTY:
                # Check patterns in all 8 directions
                for v, h in wheel:
                    # Create a view of nearby cells in this direction
                    # Pattern: [4 back][3 back][2 back][1 back][CURRENT][1 ahead][2 ahead][3 ahead][4 ahead]
                    nearby = [3, 3, 3, 3, 0, 3, 3, 3, 3]  # Default to walls (3)
                    
                    # Look backward (indices 0-3)
                    for i in range(1, 5):
                        r, c = row - v * i, col - h * i
                        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                            nearby[4 - i] = board[r][c]
                    
                    # Look forward (indices 5-8)
                    for i in range(1, 5):
                        r, c = row + v * i, col + h * i
                        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                            nearby[4 + i] = board[r][c]
                    
                    # Score this pattern
                    rankings[row][col] += score_row(nearby, my_color, opponent_color)


def score_row(r, my_color, opponent_color):
    """
    Score a 9-cell pattern where index 4 is the empty cell being evaluated.
    
    Pattern indices: [0][1][2][3][4][5][6][7][8]
    where [4] is the current empty position
    
    Values:
    - 0 = empty
    - my_color = my stone (1 or 2)
    - opponent_color = opponent's stone (2 or 1)
    - 3 = wall/edge
    """
    
    # === IMMEDIATE WINNING MOVES (10000+ points) ===
    # Four of my stones in a row - I can win immediately
    if r[0] == my_color and r[1] == my_color and r[2] == my_color and r[3] == my_color:
        return 10000
    elif r[1] == my_color and r[2] == my_color and r[3] == my_color and r[5] == my_color:
        return 10000
    elif r[2] == my_color and r[3] == my_color and r[5] == my_color and r[6] == my_color:
        return 5000
    
    # === BLOCK OPPONENT'S IMMEDIATE WIN (8000+ points) ===
    # Four opponent stones in a row - must block
    elif r[0] == opponent_color and r[1] == opponent_color and r[2] == opponent_color and r[3] == opponent_color:
        return 8000
    elif r[1] == opponent_color and r[2] == opponent_color and r[3] == opponent_color and r[5] == opponent_color:
        return 8000
    elif r[2] == opponent_color and r[3] == opponent_color and r[5] == opponent_color and r[6] == opponent_color:
        return 4000
    
    # === FORCING MOVES - Create double threats (1000 points) ===
    # Three of my stones with both ends open - creates forcing move
    elif r[0] == 0 and r[1] == my_color and r[2] == my_color and r[3] == my_color and r[5] == 0:
        return 1000
    elif r[1] == 0 and r[2] == my_color and r[3] == my_color and r[5] == my_color and r[6] == 0:
        return 1000
    
    # === BLOCK OPPONENT'S FORCING MOVES (800 points) ===
    elif r[0] == 0 and r[1] == opponent_color and r[2] == opponent_color and r[3] == opponent_color and r[5] == 0:
        return 800
    elif r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color and r[5] == opponent_color and r[6] == 0:
        return 800
    
    # === BUILD STRONG ATTACKS - Three in a row patterns (100 points) ===
    # Three of my stones with one end open
    elif r[0] == 0 and r[1] == my_color and r[2] == my_color and r[3] == my_color:
        return 100
    elif r[0] == my_color and r[1] == 0 and r[2] == my_color and r[3] == my_color:
        return 100
    elif r[0] == my_color and r[1] == my_color and r[2] == 0 and r[3] == my_color:
        return 100
    elif r[0] == my_color and r[1] == my_color and r[2] == my_color and r[3] == 0:
        return 100
    elif r[1] == 0 and r[2] == my_color and r[3] == my_color and r[5] == my_color:
        return 100
    elif r[1] == my_color and r[2] == 0 and r[3] == my_color and r[5] == my_color:
        return 100
    elif r[1] == my_color and r[2] == my_color and r[3] == 0 and r[5] == my_color:
        return 100
    elif r[1] == my_color and r[2] == my_color and r[3] == my_color and r[5] == 0:
        return 100
    elif r[2] == 0 and r[3] == my_color and r[5] == my_color and r[6] == my_color:
        return 50
    elif r[2] == my_color and r[3] == 0 and r[5] == my_color and r[6] == my_color:
        return 50
    elif r[2] == my_color and r[3] == my_color and r[5] == 0 and r[6] == my_color:
        return 50
    elif r[2] == my_color and r[3] == my_color and r[5] == my_color and r[6] == 0:
        return 50
    
    # Three of my stones with gaps but open ends
    elif r[0] == 0 and r[1] == 0 and r[2] == my_color and r[3] == my_color and r[5] == 0:
        return 100
    elif r[0] == 0 and r[1] == my_color and r[2] == 0 and r[3] == my_color and r[5] == 0:
        return 100
    elif r[0] == 0 and r[1] == my_color and r[2] == my_color and r[3] == 0 and r[5] == 0:
        return 100
    elif r[1] == 0 and r[2] == 0 and r[3] == my_color and r[5] == my_color and r[6] == 0:
        return 100
    elif r[1] == 0 and r[2] == my_color and r[3] == 0 and r[5] == my_color and r[6] == 0:
        return 100
    elif r[1] == 0 and r[2] == my_color and r[3] == my_color and r[5] == 0 and r[6] == 0:
        return 100
    
    # === BLOCK OPPONENT'S ATTACKS - Three in a row patterns (80 points) ===
    elif r[0] == 0 and r[1] == opponent_color and r[2] == opponent_color and r[3] == opponent_color:
        return 80
    elif r[0] == opponent_color and r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color:
        return 80
    elif r[0] == opponent_color and r[1] == opponent_color and r[2] == 0 and r[3] == opponent_color:
        return 80
    elif r[0] == opponent_color and r[1] == opponent_color and r[2] == opponent_color and r[3] == 0:
        return 80
    elif r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color and r[5] == opponent_color:
        return 80
    elif r[1] == opponent_color and r[2] == 0 and r[3] == opponent_color and r[5] == opponent_color:
        return 80
    elif r[1] == opponent_color and r[2] == opponent_color and r[3] == 0 and r[5] == opponent_color:
        return 80
    elif r[1] == opponent_color and r[2] == opponent_color and r[3] == opponent_color and r[5] == 0:
        return 80
    elif r[2] == 0 and r[3] == opponent_color and r[5] == opponent_color and r[6] == opponent_color:
        return 40
    elif r[2] == opponent_color and r[3] == 0 and r[5] == opponent_color and r[6] == opponent_color:
        return 40
    elif r[2] == opponent_color and r[3] == opponent_color and r[5] == 0 and r[6] == opponent_color:
        return 40
    elif r[2] == opponent_color and r[3] == opponent_color and r[5] == opponent_color and r[6] == 0:
        return 40
    
    # Three opponent stones with gaps
    elif r[0] == 0 and r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color and r[5] == 0:
        return 80
    elif r[0] == 0 and r[1] == opponent_color and r[2] == 0 and r[3] == opponent_color and r[5] == 0:
        return 80
    elif r[0] == 0 and r[1] == opponent_color and r[2] == opponent_color and r[3] == 0 and r[5] == 0:
        return 80
    elif r[1] == 0 and r[2] == 0 and r[3] == opponent_color and r[5] == opponent_color and r[6] == 0:
        return 80
    elif r[1] == 0 and r[2] == opponent_color and r[3] == 0 and r[5] == opponent_color and r[6] == 0:
        return 80
    elif r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color and r[5] == 0 and r[6] == 0:
        return 80
    
    # === BUILD TWO IN A ROW - My stones (10 points) ===
    # Two of my stones with open space around
    elif r[0] == my_color and r[1] == my_color and r[2] == 0 and r[3] == 0:
        return 10
    elif r[0] == my_color and r[1] == 0 and r[2] == my_color and r[3] == 0:
        return 10
    elif r[0] == my_color and r[1] == 0 and r[2] == 0 and r[3] == my_color:
        return 10
    elif r[0] == 0 and r[1] == my_color and r[2] == my_color and r[3] == 0:
        return 10
    elif r[0] == 0 and r[1] == my_color and r[2] == 0 and r[3] == my_color:
        return 10
    elif r[0] == 0 and r[1] == 0 and r[2] == my_color and r[3] == my_color:
        return 10
    
    # Shifted window
    elif r[1] == my_color and r[2] == my_color and r[3] == 0 and r[5] == 0:
        return 10
    elif r[1] == my_color and r[2] == 0 and r[3] == my_color and r[5] == 0:
        return 10
    elif r[1] == my_color and r[2] == 0 and r[3] == 0 and r[5] == my_color:
        return 10
    elif r[1] == 0 and r[2] == my_color and r[3] == my_color and r[5] == 0:
        return 10
    elif r[1] == 0 and r[2] == my_color and r[3] == 0 and r[5] == my_color:
        return 10
    elif r[1] == 0 and r[2] == 0 and r[3] == my_color and r[5] == my_color:
        return 10
    
    # Shifted window again
    elif r[2] == my_color and r[3] == my_color and r[5] == 0 and r[6] == 0:
        return 10
    elif r[2] == my_color and r[3] == 0 and r[5] == my_color and r[6] == 0:
        return 10
    elif r[2] == my_color and r[3] == 0 and r[5] == 0 and r[6] == my_color:
        return 5
    elif r[2] == 0 and r[3] == my_color and r[5] == my_color and r[6] == 0:
        return 5
    elif r[2] == 0 and r[3] == my_color and r[5] == 0 and r[6] == my_color:
        return 10
    elif r[2] == 0 and r[3] == 0 and r[5] == my_color and r[6] == my_color:
        return 10
    
    # === BLOCK TWO IN A ROW - Opponent stones (10 points) ===
    elif r[0] == opponent_color and r[1] == opponent_color and r[2] == 0 and r[3] == 0:
        return 10
    elif r[0] == opponent_color and r[1] == 0 and r[2] == opponent_color and r[3] == 0:
        return 10
    elif r[0] == opponent_color and r[1] == 0 and r[2] == 0 and r[3] == opponent_color:
        return 10
    elif r[0] == 0 and r[1] == opponent_color and r[2] == opponent_color and r[3] == 0:
        return 10
    elif r[0] == 0 and r[1] == opponent_color and r[2] == 0 and r[3] == opponent_color:
        return 10
    elif r[0] == 0 and r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color:
        return 10
    
    # Shifted window
    elif r[1] == opponent_color and r[2] == opponent_color and r[3] == 0 and r[5] == 0:
        return 10
    elif r[1] == opponent_color and r[2] == 0 and r[3] == opponent_color and r[5] == 0:
        return 10
    elif r[1] == opponent_color and r[2] == 0 and r[3] == 0 and r[5] == opponent_color:
        return 10
    elif r[1] == 0 and r[2] == opponent_color and r[3] == opponent_color and r[5] == 0:
        return 10
    elif r[1] == 0 and r[2] == opponent_color and r[3] == 0 and r[5] == opponent_color:
        return 10
    elif r[1] == 0 and r[2] == 0 and r[3] == opponent_color and r[5] == opponent_color:
        return 10
    
    # Shifted window again
    elif r[2] == opponent_color and r[3] == opponent_color and r[5] == 0 and r[6] == 0:
        return 10
    elif r[2] == opponent_color and r[3] == 0 and r[5] == opponent_color and r[6] == 0:
        return 10
    elif r[2] == opponent_color and r[3] == 0 and r[5] == 0 and r[6] == opponent_color:
        return 5
    elif r[2] == 0 and r[3] == opponent_color and r[5] == opponent_color and r[6] == 0:
        return 5
    elif r[2] == 0 and r[3] == opponent_color and r[5] == 0 and r[6] == opponent_color:
        return 10
    elif r[2] == 0 and r[3] == 0 and r[5] == opponent_color and r[6] == opponent_color:
        return 10
    
    # === SINGLE STONE EXTENSIONS (1 point) ===
    # One of my stones with space to build
    elif r[0] == my_color and r[1] == 0 and r[2] == 0 and r[3] == 0:
        return 1
    elif r[0] == 0 and r[1] == my_color and r[2] == 0 and r[3] == 0:
        return 1
    elif r[0] == 0 and r[1] == 0 and r[2] == my_color and r[3] == 0:
        return 1
    elif r[0] == 0 and r[1] == 0 and r[2] == 0 and r[3] == my_color:
        return 1
    elif r[1] == my_color and r[2] == 0 and r[3] == 0 and r[5] == 0:
        return 1
    elif r[1] == 0 and r[2] == my_color and r[3] == 0 and r[5] == 0:
        return 1
    elif r[1] == 0 and r[2] == 0 and r[3] == my_color and r[5] == 0:
        return 1
    elif r[1] == 0 and r[2] == 0 and r[3] == 0 and r[5] == my_color:
        return 1
    elif r[2] == my_color and r[3] == 0 and r[5] == 0 and r[6] == 0:
        return 1
    elif r[2] == 0 and r[3] == my_color and r[5] == 0 and r[6] == 0:
        return 1
    
    # One opponent stone
    elif r[0] == opponent_color and r[1] == 0 and r[2] == 0 and r[3] == 0:
        return 1
    elif r[0] == 0 and r[1] == opponent_color and r[2] == 0 and r[3] == 0:
        return 1
    elif r[0] == 0 and r[1] == 0 and r[2] == opponent_color and r[3] == 0:
        return 1
    elif r[0] == 0 and r[1] == 0 and r[2] == 0 and r[3] == opponent_color:
        return 1
    elif r[1] == opponent_color and r[2] == 0 and r[3] == 0 and r[5] == 0:
        return 1
    elif r[1] == 0 and r[2] == opponent_color and r[3] == 0 and r[5] == 0:
        return 1
    elif r[1] == 0 and r[2] == 0 and r[3] == opponent_color and r[5] == 0:
        return 1
    elif r[1] == 0 and r[2] == 0 and r[3] == 0 and r[5] == opponent_color:
        return 1
    elif r[2] == opponent_color and r[3] == 0 and r[5] == 0 and r[6] == 0:
        return 1
    elif r[2] == 0 and r[3] == opponent_color and r[5] == 0 and r[6] == 0:
        return 1
    
    else:
        return 0


def pick_highest(board, rankings):
    """
    Select the move with the highest ranking score.
    Returns (row, col) tuple or None if no valid moves.
    """
    highest = 0
    best_row = 0
    best_col = 0
    
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if rankings[row][col] > highest:
                best_row = row
                best_col = col
                highest = rankings[row][col]
    
    # Verify the selected position is actually empty
    if board[best_row][best_col] == EMPTY:
        return (best_row, best_col)
    else:
        # Fallback: find any valid move
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if board[row][col] == EMPTY:
                    return (row, col)
        return None


async def main():
    # Check if token and username are provided
    if not TOKEN or not USERNAME:
        print("ERROR: Please set your TOKEN and USERNAME in the script")
        print("Get your token by running:")
        print("  curl -X POST 'http://localhost:8000/register?username=YOUR_USERNAME&is_bot=true'")
        sys.exit(1)
    
    bot = GomokuBot(TOKEN, USERNAME)
    
    while True:
        try:
            await bot.run()
        except Exception as e:
            print(f"[ERROR] Bot crashed: {e}")
        
        # Wait before reconnecting
        print("[BOT] Reconnecting in 5 seconds...")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
