## 2026-02-21
*Added Round Robin button to automate bot matchmaking and fixed several bugs.*
- Added `round_robin` WebSocket handler — starts games between all available bot pairs below a game-count threshold, greedily pairing to maximize concurrent games
- Added Round Robin UI panel in Force Bot Match Mode — threshold input, orange button, status text with disable-on-click feedback
- Bots now always create new rooms instead of randomly joining existing ones — Round Robin is the sole matchmaking mechanism
- Fixed double ELO update bug — `update_game_result` now checks DB for existing game_id and returns early to prevent duplicate saves on concurrent disconnects
- Fixed `INSERT INTO` → `INSERT OR IGNORE INTO` as secondary guard against duplicate game records
- Fixed missing `broadcast_lobby_update()` after Round Robin cancels waiting games
- Fixed leaderboard win rate to exclude draws — now shows W/L/D separately, percentage is wins/(wins+losses)
- Fixed Windows console crash — replaced Unicode `→` arrow with `->` in game-end log line
- Removed unnecessary `game_cancelled` message sent to bots during force game/round robin

## 2026-02-14
*Created game statistics analyzer and improved code quality with code review fixes.*
- Added `analyze_games.py` script — generates aggregate statistics from saved game files
- Tracks win rates by color (Black vs White), outcome types, game length distribution, median/average moves
- Fixed type safety — corrected return type hints and removed unused imports in analyze_games.py
- Fixed database resource leaks — converted to context manager pattern in WebSocket handlers
- Added WebSocket connection checks — prevents errors when connection drops during message sends
- Added visual error feedback — drag-and-drop shows green/red border flash for success/failure
- Refactored game creation — extracted `create_and_start_game()` helper to eliminate duplication

## 2026-02-14
*Added force bot match feature with drag-and-drop UI for testing specific matchups.*
- Added "Force Bot Match Mode" in web UI — drag one bot onto another to force them to play
- Implemented `get_available_bots` WebSocket handler — returns bots online and not in active games
- Implemented `force_game` WebSocket handler — creates matches between two bots with validation
- Auto-cancels waiting games when bots are forced into new matches
- Auto-spectates forced matches for the user who initiated them
- Added drag-and-drop JavaScript with proper event delegation using `closest()`
- Optimized database queries — combined two separate bot lookups into single `WHERE IN` query
- Fixed control flow bug — validation failures now properly exit message handler

## 2026-02-14
*Fixed ELO display bug and added game persistence with 24-hour history.*
- Fixed ELO changes not showing for normal wins — reordered broadcast to occur after ELO calculation
- Added game persistence — server loads completed games from last 24 hours on startup
- Extended POST_GAME_MEMORY from 10 minutes to 24 hours
- Added timestamp display in web UI — "Watch Games" shows relative time (e.g., "5m ago", "2h ago")
- Added `generate_opening` flag to GameState to prevent incorrect board state when loading saved games
- Improved error handling in game file parser — specific exceptions with logged warnings
- Fixed database connection leak — switched to context manager pattern
- Sorted completed games by end time (most recent first) instead of ELO

## 2026-02-10
*Initial commit with code review fixes for security, input validation, and robustness.*
- Fixed bounds check order in `server.py` `make_move()` — was accessing board before validating indices
- Added integer type validation for `row`/`col` in WebSocket `make_move` handler
- Fixed URL injection in both bot launchers — username now properly encoded via `params=`
- Fixed `find_threats()` open-end detection in easy bot — forward/backward counts tracked separately
- Replaced bare `except:` with `except Exception:` in server (4 occurrences)
- Fixed bot reconnect loop — `reset_game_state()` called at start of `run()` in both bots
- Migrated deprecated `@app.on_event("startup")` to `lifespan` context manager
