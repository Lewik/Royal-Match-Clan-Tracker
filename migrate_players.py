import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clan.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    game_start_date TEXT
)""")

try:
    c.execute("ALTER TABLE members ADD COLUMN player_id INTEGER REFERENCES players(id)")
except Exception:
    pass
c.execute("UPDATE members SET player_id = NULL")
c.execute("DELETE FROM players")

snap_ids = [r[0] for r in c.execute("SELECT id FROM snapshots ORDER BY date").fetchall()]

known = c.execute(
    "SELECT DISTINCT name, game_start_date FROM members WHERE game_start_date IS NOT NULL"
).fetchall()
for row in known:
    c.execute("INSERT INTO players(name, game_start_date) VALUES(?, ?)",
              (row['name'], row['game_start_date']))

c.execute("""
    UPDATE members SET player_id = (
        SELECT p.id FROM players p
        WHERE p.name = members.name AND p.game_start_date = members.game_start_date
    ) WHERE game_start_date IS NOT NULL
""")

null_player_cache = {}


def get_or_create_null_player(name):
    if name not in null_player_cache:
        null_player_cache[name] = []
    c.execute("INSERT INTO players(name, game_start_date) VALUES(?, NULL)", (name,))
    pid = c.lastrowid
    null_player_cache[name].append(pid)
    return pid


for snap_idx in range(len(snap_ids) - 1, -1, -1):
    snap_id = snap_ids[snap_idx]
    next_snap_id = snap_ids[snap_idx + 1] if snap_idx + 1 < len(snap_ids) else None

    unassigned = c.execute(
        "SELECT id, name, level FROM members WHERE snapshot_id=? AND player_id IS NULL",
        (snap_id,)
    ).fetchall()

    by_name = {}
    for m in unassigned:
        by_name.setdefault(m['name'], []).append(dict(m))

    for name, members in by_name.items():
        if next_snap_id:
            next_assigned = c.execute(
                "SELECT player_id, level FROM members WHERE snapshot_id=? AND name=? AND player_id IS NOT NULL",
                (next_snap_id, name)
            ).fetchall()
            next_assigned = [dict(r) for r in next_assigned]
        else:
            next_assigned = []

        available = list(next_assigned)
        for m in sorted(members, key=lambda x: x['level'], reverse=True):
            matched = None
            best_dist = float('inf')
            for ap in available:
                if m['level'] <= ap['level'] * 1.2:
                    dist = abs(m['level'] - ap['level'])
                    if dist < best_dist:
                        best_dist = dist
                        matched = ap
            if matched:
                c.execute("UPDATE members SET player_id=? WHERE id=?",
                          (matched['player_id'], m['id']))
                available.remove(matched)
            else:
                reuse = c.execute(
                    "SELECT DISTINCT player_id FROM members WHERE name=? AND player_id IS NOT NULL AND snapshot_id < ?",
                    (name, snap_id)
                ).fetchall()
                assigned_pids = {r['player_id'] for r in c.execute(
                    "SELECT DISTINCT player_id FROM members WHERE snapshot_id=? AND name=? AND player_id IS NOT NULL",
                    (snap_id, name)
                ).fetchall()}
                reuse = [r for r in reuse if r['player_id'] not in assigned_pids]

                if len(reuse) == 1:
                    c.execute("UPDATE members SET player_id=? WHERE id=?",
                              (reuse[0]['player_id'], m['id']))
                else:
                    pid = get_or_create_null_player(name)
                    c.execute("UPDATE members SET player_id=? WHERE id=?", (pid, m['id']))

conn.commit()

unassigned = c.execute("SELECT COUNT(*) FROM members WHERE player_id IS NULL").fetchone()[0]
total_players = c.execute("SELECT COUNT(*) FROM players").fetchone()[0]
current = c.execute("SELECT COUNT(DISTINCT player_id) FROM members WHERE snapshot_id=?",
                    (snap_ids[-1],)).fetchone()[0]
print(f"Players: {total_players}, Current: {current}, Unassigned: {unassigned}")

dupes = c.execute("SELECT p.name FROM players p GROUP BY p.name HAVING COUNT(*) > 1").fetchall()
for d in dupes:
    rows = c.execute("""
        SELECT p.id, p.name, p.game_start_date, COUNT(m.id) as snaps,
               MIN(m.level) as min_lvl, MAX(m.level) as max_lvl
        FROM players p LEFT JOIN members m ON m.player_id = p.id
        WHERE p.name=?
        GROUP BY p.id
    """, (d['name'],)).fetchall()
    print(f"\n  {d['name']}:")
    for r in rows:
        print(f"    #{r['id']} gsd={r['game_start_date']} snaps={r['snaps']} lvl={r['min_lvl']}-{r['max_lvl']}")

conn.close()
