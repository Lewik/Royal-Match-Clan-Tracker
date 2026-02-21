import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clan.db')
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

snapshots = c.execute("SELECT id, date FROM snapshots ORDER BY date").fetchall()
snap_dates = [s['date'] for s in snapshots]
snap_ids = [s['id'] for s in snapshots]

PROTECTED_MEMBERS = {'Lewik', 'Irina', 'Daminor', 'yaroslav'}

all_members = c.execute(
    "SELECT snapshot_id, position, name, help, level, source_file FROM members ORDER BY snapshot_id, position"
).fetchall()
conn.close()

player_history = {}
for m in all_members:
    name = m['name']
    snap_id = m['snapshot_id']
    if name not in player_history:
        player_history[name] = {}
    if name in player_history and snap_id in player_history[name]:
        key = f"{name}#{m['level']}"
        if key not in player_history:
            player_history[key] = {}
        player_history[key][snap_id] = {'level': m['level'], 'help': m['help'], 'position': m['position'], 'source_file': m['source_file']}
    else:
        player_history[name][snap_id] = {'level': m['level'], 'help': m['help'], 'position': m['position'], 'source_file': m['source_file']}


def resolve_duplicates(player_history, snap_ids):
    resolved = {}
    for name, history in player_history.items():
        if '#' in name:
            continue
        resolved[name] = history

    for name, history in player_history.items():
        if '#' not in name:
            continue
        base_name = name.split('#')[0]
        if base_name not in resolved:
            resolved[base_name] = history
        else:
            existing = resolved[base_name]
            merged_key = name
            resolved[merged_key] = history

    return resolved


player_history = resolve_duplicates(player_history, snap_ids)

players = []
for name, history in player_history.items():
    latest_snap = max(history.keys())
    latest = history[latest_snap]

    first_snap = min(history.keys())
    first = history[first_snap]

    total_delta = latest['level'] - first['level']
    latest_help = latest['help']

    has_latest = snap_ids[-1] in history
    has_prev = len(snap_ids) >= 2 and snap_ids[-2] in history

    if has_latest and has_prev:
        recent_delta = history[snap_ids[-1]]['level'] - history[snap_ids[-2]]['level']
    else:
        recent_delta = None

    inactive = has_latest and recent_delta is not None and recent_delta == 0 and latest_help == 0

    display_name = name.split('#')[0] if '#' in name else name

    players.append({
        'name': name,
        'display_name': display_name,
        'history': history,
        'latest_level': latest['level'],
        'latest_help': latest_help,
        'latest_position': latest['position'] if has_latest else 999,
        'total_delta': total_delta,
        'recent_delta': recent_delta,
        'inactive': inactive,
        'is_new': not has_prev and has_latest,
    })

players.sort(key=lambda p: p['latest_position'])

inactive_count = sum(1 for p in players if p['inactive'])
total = sum(1 for p in players if snap_ids[-1] in p['history'])
generated = datetime.now().strftime("%Y-%m-%d %H:%M")

# --- Table rows ---
rows_html = []
for p in players:
    if snap_ids[-1] not in p['history']:
        continue

    is_protected = p['display_name'] in PROTECTED_MEMBERS
    row_class = "inactive" if p['inactive'] else ("new-member" if p['is_new'] else "active")
    if is_protected:
        row_class += " protected"

    shield = ' <span class="shield">&#128274;</span>' if is_protected else ''
    cells = f'<td>{p["latest_position"]}</td><td>{p["display_name"]}{shield}</td>'
    for sid in snap_ids:
        if sid in p['history']:
            h = p['history'][sid]
            src = h.get('source_file', '')
            link = lambda v: f'<a href="{src}">{v}</a>' if src else str(v)
            cells += f'<td>{link(h["level"])}</td><td>{link(h["help"])}</td>'
        else:
            cells += '<td class="na">—</td><td class="na">—</td>'

    if p['recent_delta'] is not None:
        d = p['recent_delta']
        delta_str = f"+{d}" if d > 0 else str(d)
    elif p['is_new']:
        delta_str = "нов."
    else:
        delta_str = "—"
    cells += f'<td class="delta">{delta_str}</td>'

    rows_html.append(f'<tr class="{row_class}">{cells}</tr>')

# --- Chart data ---
chart_datasets = []
palette = [
    '#4dc9f6','#f67019','#f53794','#537bc4','#acc236',
    '#166a8f','#00a950','#58595b','#8549ba','#e6194b',
    '#3cb44b','#ffe119','#4363d8','#f58231','#911eb4',
    '#42d4f4','#f032e6','#bfef45','#fabed4','#469990',
]

for i, p in enumerate(players):
    if len(p['history']) < 2:
        continue
    data_points = []
    for sid, date in zip(snap_ids, snap_dates):
        if sid in p['history']:
            data_points.append({'x': date, 'y': p['history'][sid]['level']})
        else:
            data_points.append(None)

    color = '#f66' if p['inactive'] else palette[i % len(palette)]
    chart_datasets.append({
        'label': p['display_name'],
        'data': data_points,
        'borderColor': color,
        'backgroundColor': color,
        'borderWidth': p['inactive'] and 1 or 2,
        'pointRadius': 4,
        'tension': 0.3,
        'spanGaps': True,
    })

date_headers = ''.join(f'<th colspan="2">{d}</th>' for d in snap_dates)

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Three Stripes — Clan Tracker</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #eee;
    padding: 20px;
    max-width: 900px;
    margin: 0 auto;
  }}
  h1 {{
    text-align: center;
    margin-bottom: 5px;
    font-size: 1.5em;
  }}
  .meta {{
    text-align: center;
    color: #888;
    font-size: 0.85em;
    margin-bottom: 20px;
  }}
  .stats {{
    display: flex;
    justify-content: center;
    gap: 30px;
    margin-bottom: 20px;
    font-size: 0.9em;
  }}
  .stats span {{
    padding: 6px 14px;
    border-radius: 8px;
    background: #16213e;
  }}
  .chart-container {{
    margin: 30px 0;
    background: #16213e;
    border-radius: 12px;
    padding: 20px;
    height: 500px;
  }}
  .chart-container h2 {{
    font-size: 1.1em;
    margin-bottom: 15px;
    color: #aaa;
  }}
  .table-wrap {{
    overflow-x: auto;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    white-space: nowrap;
  }}
  th {{
    background: #16213e;
    padding: 10px 8px;
    text-align: left;
    font-size: 0.85em;
    color: #aaa;
    position: sticky;
    top: 0;
  }}
  td {{
    padding: 8px;
    border-bottom: 1px solid #222;
    font-size: 0.9em;
  }}
  td.na {{
    color: #555;
  }}
  tr.inactive {{
    background: #2a1a1a;
  }}
  tr.inactive td {{
    color: #f66;
  }}
  tr.active td.delta {{
    color: #6f6;
  }}
  tr.new-member td {{
    color: #6cf;
  }}
  tr.inactive td.delta {{
    font-weight: bold;
  }}
  td a {{
    color: inherit;
    text-decoration: none;
    border-bottom: 1px dotted #555;
  }}
  td a:hover {{
    border-bottom-color: #aaa;
  }}
  .shield {{
    font-size: 0.75em;
  }}
  @media (max-width: 600px) {{
    body {{ padding: 10px; }}
    td, th {{ padding: 6px 4px; font-size: 0.8em; }}
    .chart-container {{ height: 400px; padding: 10px; }}
  }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
<h1>Three Stripes</h1>
<div class="meta">
  {snap_dates[0]} &rarr; {snap_dates[-1]} &middot; {len(snap_dates)} снапшотов &middot; Обновлено {generated}
</div>
<div class="stats">
  <span>Участников: {total}</span>
  <span style="color:#f66">Неактивных: {inactive_count}</span>
</div>

<div class="chart-container">
  <h2>Прогресс по уровням</h2>
  <canvas id="levelChart"></canvas>
</div>

<div class="table-wrap">
<table>
<thead>
  <tr>
    <th rowspan="2">#</th>
    <th rowspan="2">Имя</th>
    {date_headers}
    <th rowspan="2">&Delta;</th>
  </tr>
  <tr>
    {''.join('<th>Ур.</th><th>Пом.</th>' for _ in snap_dates)}
  </tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>

<script>
const datasets = {json.dumps(chart_datasets, ensure_ascii=False, default=str)};
new Chart(document.getElementById('levelChart'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(snap_dates)},
    datasets: datasets,
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{
      mode: 'nearest',
      intersect: false,
    }},
    plugins: {{
      legend: {{
        display: true,
        position: 'bottom',
        labels: {{
          color: '#aaa',
          font: {{ size: 10 }},
          boxWidth: 12,
          padding: 8,
        }},
        onClick: function(e, legendItem, legend) {{
          const index = legendItem.datasetIndex;
          const ci = legend.chart;
          const meta = ci.getDatasetMeta(index);
          meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null;
          ci.update();
        }},
      }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            return ctx.dataset.label + ': уровень ' + ctx.parsed.y;
          }}
        }}
      }}
    }},
    scales: {{
      x: {{
        ticks: {{ color: '#888' }},
        grid: {{ color: '#333' }},
      }},
      y: {{
        ticks: {{ color: '#888' }},
        grid: {{ color: '#333' }},
        title: {{
          display: true,
          text: 'Уровень',
          color: '#666',
        }}
      }}
    }}
  }}
}});
</script>
</body>
</html>
"""

with open(HTML_PATH, 'w') as f:
    f.write(html)

print(f"Generated {HTML_PATH}")
print(f"Snapshots: {len(snap_dates)}, Members: {total}, Inactive: {inactive_count}")
