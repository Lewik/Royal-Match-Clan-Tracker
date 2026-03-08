# Royal Match Clan Tracker

## Project
Track clan member activity via screenshots, detect inactive players.

## Pipeline
```
Screenshots → OCR → SQLite → Python → index.html → GitHub Pages
```

## OCR Rules

### Game data invariants
- **Level never decreases** between snapshots. If OCR shows a decrease — it's a misread, re-examine the screenshot
- Help counter resets weekly (official: "Helps are counted weekly and reset at the end of every week"). Shows how many lives a player sent to teammates this week. Cannot compare across snapshots unless they're within the same week

### Known OCR pitfalls
- **Animated/decorative fonts**: some player names use stylized fonts where digits/letters are hard to distinguish (e.g. `2` looking like `z`). Always flag uncertain readings to the user
- **Partially visible rows**: screenshots cut off top/bottom entries. Don't guess — ask the user to clarify
- **Duplicate names**: multiple players can have the same name (e.g. "123", "Alex"). Match between snapshots by name + approximate level, not name alone
- **Cyrillic/Latin ambiguity**: game allows mixed scripts in names, `a`/`а`, `c`/`с`, `e`/`е` can be either

## SQLite Schema
- `snapshots(id, date)`
- `members(id, snapshot_id, position, name, help, level, source_file, league_crowns, league_max_crowns, league_wins, game_start_date, profile_wins, profile_help_given, profile_help_received, profile_territories, profile_collections, profile_sets)`
  - `source_file`: comma-separated paths (clan list screenshot + profile screenshot if taken)
  - `league_*`: NULL for most players, filled from profile screenshots for league-tracked players
  - `game_start_date`: MM/YYYY when the player started playing Royal Match (NOT clan join date). Filled from profile screenshots
  - `profile_*`: general stats from player profile (wins, help given/received, territories, collections, sets). Not displayed in HTML but stored for analysis

## Inactivity Definition
A member is inactive only when BOTH conditions are true:
- Level delta = 0 (no level progression)
- Help = 0 in the latest snapshot (no help given at all)

If a member has 0 level delta but non-zero help — they are NOT inactive.

## Snapshot Workflow

When user drops new screenshot files into the project root:

1. **Move** screenshots to `screenshots/YYYY-MM-DD/` (ask user for the date if unclear)
2. **OCR** via `.claude/agents/ocr.md` sub-agent to save main context (~50K tokens per snapshot from images):
   - Query DB for current member list (name + level) to pass as context
   - Launch OCR agent with: screenshot paths + member list
   - Agent reads images, returns structured table, flags uncertainties
   - **Do NOT read screenshot images in the main conversation** — delegate to the agent. Exception: if agent results are unclear or user reports errors, reading specific screenshots directly is allowed
3. **Insert** into SQLite: create new `snapshots` row, then `members` rows with `source_file` pointing to the screenshot
4. **Request profile screenshots** for:
   - League-tracked players (see League Tracking section) — update `league_*` columns
   - All new players — to fill `game_start_date`
   - **Once a month**: all players — to update `profile_*` stats (wins, help given/received, territories, collections, sets)
   - Append profile screenshot path to `source_file`
   - After monthly profile update: analyze data and propose **fun facts** for the site (records, milestones, unusual stats). Different observations each time — be creative. User picks which ones to display
5. **Generate** HTML: `python3 generate_html.py`
6. **Verify** the page works locally (open in browser, check chart renders)
7. **Commit + push** when user confirms everything looks good

Screenshots are typically taken ~weekly on Sundays. The number of screenshots per snapshot varies (usually 7-9, covering the full member list with overlap).

## Max Level

Royal Match adds new levels every 2 weeks (~50 levels per update). There is no fixed cap — the game grows continuously. We track `MAX_LEVEL` in `generate_html.py` as a manually set constant.

**How to estimate:** take the top player's level as reference. If multiple top players share the exact same level — they've likely hit the current content cap. Update `MAX_LEVEL` to that value. Players at or above `MAX_LEVEL` are visually separated in the table with a golden divider.

**Reference points:**
- Nov 2025: ~12400 levels
- Mar 2026: ~13100 levels

## League Tracking (Royal League)

Players who complete all available levels enter the Royal League — a recurring tournament with crowns and rankings. Their level stops growing, so our standard inactivity metric (level delta + help) doesn't work for them.

**What we track from profile screenshots:** total crowns, max crowns per league, league wins (all cumulative).

**Who needs a profile screenshot:**
- Player's level >= `MAX_LEVEL` in current snapshot, OR
- Player has any `league_crowns` data in any previous snapshot (once tracked — always tracked, even if they fall below MAX_LEVEL when new levels are released)
- **All new players** (first appearance in a snapshot) — to fill `game_start_date`

**Workflow:** After processing clan list screenshots, actively ask the user for profile screenshots of:
1. All league-tracked players (for league stats)
2. All new players (for game start date)
Each profile = one extra screenshot (tap player → screenshot → back).

## File Structure
```
screenshots/          # committed to git, viewable on GitHub Pages
  YYYY-MM-DD/         # one folder per snapshot date
clan.db               # .gitignored
seed_data.py          # one-time initial data seed
```
