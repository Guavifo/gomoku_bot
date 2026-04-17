# Gomoku Bot Template

A starter bot for the Gomoku hackathon! This bot connects to the game server, finds games, and plays with a basic strategy. Your challenge is to improve the strategy and make it win more games!

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

### 3. Run the Launcher

```bash
python launcher.py
```

The interactive launcher will guide you through:
- **Creating a new bot account** (automatically registers with the server)
- **Running your bot** (uses credentials from config.json)
- **Deleting credentials** (clears config.json)
- **Viewing your configuration**

### Running Multiple Bots

To have bots fight each other:

1. **Open multiple terminal windows**
2. **In each terminal:**
   - Navigate to the bot folder
   - Activate the virtual environment
   - Run `python launcher.py`
   - Create a different account (different username)
   - Select option 2 to run the bot

Or duplicate the entire bot folder and run a separate bot from each copy!

### Alternative: Manual Setup

If you prefer to set up manually:

1. **Get Your Token:**
   ```bash
   curl -X POST 'http://localhost:8765/register?username=YOUR_BOT_NAME&is_bot=true'
   ```

2. **Edit config.json:**
   ```json
   {
       "server_url": "ws://localhost:8765/ws",
       "username": "YOUR_BOT_NAME",
       "token": "your-token-here"
   }
   ```

3. **Run the bot:**
   ```bash
   python bot.py
   ```

Your bot will automatically:
- Connect to the server
- Find games to join (or create new ones)
- Play against other bots and humans
- Keep playing continuously

## How It Works

The bot has a simple strategy implemented in the `choose_move()` function:

1. **Complete my own 4-in-a-row** (winning move)
2. **Block opponent's 4-in-a-row** (prevent their win)
3. **Complete my own 3-in-a-row**
4. **Block opponent's 3-in-a-row**
5. **Play in center** if available
6. **Spiral outward** from center
7. **Random valid move** as fallback

## Your Mission

**Improve the `choose_move()` function to make your bot win more games!**

The current strategy is very basic. Here are some ways you could improve it:

- Look further ahead (what happens after my move?)
- Evaluate board positions (which moves lead to better positions?)
- Recognize patterns (double threats, forcing sequences)
- Consider both offense and defense together
- Prioritize moves near existing stones
- Learn from winning/losing patterns

## Board Representation

The board is a 19x19 grid represented as a 2D list:

```python
board[row][col]  # Access position at (row, col)

# Values:
EMPTY = 0  # No stone
BLACK = 1  # Black stone  
WHITE = 2  # White stone
```

Coordinates are 0-indexed (0-18 for each dimension).

## Helper Functions

### `find_threats(board, color, length)`

Finds all positions where placing a stone would create a line of `length` stones with at least one open end.

**Parameters:**
- `board`: Current board state (2D list)
- `color`: Stone color to check (BLACK or WHITE)
- `length`: Number of consecutive stones to look for (e.g., 4 for 4-in-a-row)

**Returns:**
- List of `(row, col)` tuples representing threat positions

**Example:**
```python
# Find all positions that would complete a 4-in-a-row for my color
my_threats = find_threats(board, my_color, 4)
if my_threats:
    # Pick one of the winning moves
    return random.choice(my_threats)
```

## Understanding the Strategy

### What's a "threat"?

A threat is a position where:
1. Placing a stone creates a line of N consecutive stones
2. At least one end of the line is open (can be extended)

Example: If there are 3 black stones in a row like `_ B B B _`, placing a stone at either end creates a 4-in-a-row threat.

### Why check threats in order?

The bot checks threats in priority order:
- Winning moves first (complete my 4-in-a-row)
- Defensive moves second (block opponent's 4-in-a-row)
- Then offensive 3-in-a-rows
- Then defensive 3-in-a-rows

This ensures the bot doesn't miss winning opportunities or lose to obvious threats.

## Tips for Improvement

### Start Simple
- Adjust the priorities (maybe block before attacking?)
- Add more threat lengths (check for 2-in-a-row?)
- Weight center moves differently

### Go Deeper
- Implement minimax or alpha-beta search
- Create a board evaluation function
- Look 2-3 moves ahead
- Detect double-threat situations (attacking two ways at once)

### Get Creative
- Learn patterns from winning games
- Detect "forcing" moves that require a response
- Build an opening book
- Implement Monte Carlo Tree Search

## Testing Your Bot

1. Run your bot: `python bot.py`
2. Watch it play through the web interface: http://localhost:8765
3. Check the leaderboard to see your ranking
4. Review game files in `games/` folder to see what happened

## Common Issues

### "Connection refused"
- Make sure the server is running: `python server.py` in the server directory

### "Invalid token"
- Re-register your bot to get a new token
- Make sure you copied the full token string

### "Bot not moving"
- Check for error messages in the console
- The bot might be waiting its turn
- Verify the board state is being received

### "Bot keeps losing"
- That's expected! The starter strategy is very basic
- Time to improve the `choose_move()` function!

## Bot Behavior

The bot automatically:
- **Reconnects** if disconnected
- **Finds new games** after each game ends
- **Randomly chooses** to create or join games (keeps lobby balanced)
- **Responds to pings** to stay connected
- **Handles errors** gracefully

You don't need to modify this behavior - focus on improving the strategy!

## Game Rules Reminder

- **Board**: 19x19 grid
- **Opening**: 3 random stones placed automatically (Black, White, Black)
- **Objective**: Get 5+ in a row (horizontal, vertical, or diagonal)
- **Turn timer**: 60 seconds per move
- **Colors**: Black (1) goes first after opening, White (2) goes second

## Good Luck!

May the best bot win! Remember:
- Start with small improvements
- Test frequently
- Learn from your losses
- Have fun! 🎮

For questions about the server API, see the server repository's README.
