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
        Choose the best move based on current board state.
        
        This is the main strategy function that students should improve!
        
        Current strategy:
        1. Try to complete my own 4-in-a-row with open end
        2. Try to block opponent's 4-in-a-row with open end
        3. Try to complete my own 3-in-a-row with open end
        4. Try to block opponent's 3-in-a-row with open end
        5. Play in center if available
        6. Play a random valid move
        """
        opponent_color = 3 - my_color
        
        # 1. Check if I can complete a 4-in-a-row (winning move)
        my_4_threats = find_threats(board, my_color, 4)
        if my_4_threats:
            return random.choice(my_4_threats)
        
        # 2. Check if I need to block opponent's 4-in-a-row
        opp_4_threats = find_threats(board, opponent_color, 4)
        if opp_4_threats:
            return random.choice(opp_4_threats)
        
        # 3. Check if I can complete a 3-in-a-row
        my_3_threats = find_threats(board, my_color, 3)
        if my_3_threats:
            return random.choice(my_3_threats)
        
        # 4. Check if I need to block opponent's 3-in-a-row
        opp_3_threats = find_threats(board, opponent_color, 3)
        if opp_3_threats:
            return random.choice(opp_3_threats)
        
        # 5. Try to play in center
        center = BOARD_SIZE // 2
        if board[center][center] == EMPTY:
            return (center, center)
        
        # Spiral outward from center
        for distance in range(1, BOARD_SIZE):
            for dr in range(-distance, distance + 1):
                for dc in range(-distance, distance + 1):
                    if abs(dr) == distance or abs(dc) == distance:
                        row = center + dr
                        col = center + dc
                        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
                            if board[row][col] == EMPTY:
                                return (row, col)
        
        # 6. Fallback to random valid move
        valid_moves = []
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if board[row][col] == EMPTY:
                    valid_moves.append((row, col))
        
        if valid_moves:
            return random.choice(valid_moves)
        
        return None
    
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


def find_threats(board, color, length):
    """
    Find all positions where placing a stone would create or complete
    a line of 'length' stones with at least one open end.
    
    Returns a list of (row, col) tuples representing valid threat positions.
    """
    threats = []
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]  # horizontal, vertical, diagonals
    
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY:
                continue
            
            # Try placing a stone here
            for dr, dc in directions:
                # Count consecutive stones in both directions separately
                forward_count = 0
                r, c = row + dr, col + dc
                while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == color:
                    forward_count += 1
                    r += dr
                    c += dc

                backward_count = 0
                r, c = row - dr, col - dc
                while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == color:
                    backward_count += 1
                    r -= dr
                    c -= dc

                # If we have exactly 'length' stones in a row by placing here
                if forward_count + backward_count == length:
                    # Check if at least one end is open
                    # Positive end: one past the last forward stone
                    r_pos = row + dr * (forward_count + 1)
                    c_pos = col + dc * (forward_count + 1)
                    pos_open = (0 <= r_pos < BOARD_SIZE and 0 <= c_pos < BOARD_SIZE and
                                board[r_pos][c_pos] == EMPTY)

                    # Negative end: one past the last backward stone
                    r_neg = row - dr * (backward_count + 1)
                    c_neg = col - dc * (backward_count + 1)
                    neg_open = (0 <= r_neg < BOARD_SIZE and 0 <= c_neg < BOARD_SIZE and
                                board[r_neg][c_neg] == EMPTY)

                    # If at least one end is open, this is a threat
                    if pos_open or neg_open:
                        threats.append((row, col))
                        break  # Don't double-count this position
    
    return threats


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
