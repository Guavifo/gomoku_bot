## 2026-03-28
*Fixed completed game spectating — board, move history, and ELO data now load correctly when clicking a finished game.*
- Fixed `GameState.finalize()` — no longer clears `board` or `move_history`; only resets connections/spectators so games remain viewable after completion
- Fixed `load_recent_completed_games` — now assigns `move_history` to game object, reconstructs board by replaying moves, and loads ELO before/after from DB
- Added `player1/2_elo_before/after` fields to `GameState` — populated in `update_game_result` for live games and from DB for loaded games
- Fixed `UnboundLocalError` in `update_game_result` — ELO field assignments were placed before the local variables were defined, silently crashing game resolution and preventing ELO updates
- `spectate_game` WebSocket message now includes `elo_changes`, `player1_elo_before/after`, `player2_elo_before/after`

## 2026-02-25
*Fixed bot disconnects, self-matches, and server slowdown; added auto round robin loop.*
- Added "Start Auto" button for round robin — loops automatically until all pairs meet the threshold, retrying while bots are busy
- Fixed auto loop stopping early — server now sends `bots_busy` flag so client can distinguish "all done" from "all bots currently playing"
- Fixed WebSocket 1009 errors — raised `max_size` to 10 MB on both server (`uvicorn`) and all bot clients (`websockets.connect`)
- Fixed bots playing themselves — added self-match guard in `create_and_start_game` and in the join-game path
- Improved server memory usage — `move_count` is now cached on `GameState` instead of recomputed on every broadcast
- Added `GameState.finalize()` — clears `board`, `move_history`, `spectators`, and `player_connections` when a game ends
- Capped `completed_games` in memory to last 100 games or 24 hours, whichever is less
- Startup load no longer reconstructs board from file — only computes `move_count` for the lobby display

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
