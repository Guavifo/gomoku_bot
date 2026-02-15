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
