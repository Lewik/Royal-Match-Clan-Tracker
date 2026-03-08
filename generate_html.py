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

PROTECTED_MEMBERS = {'Lewik', 'Irina', 'Daminor', 'yaroslav', 'ARTEM', 'NASTENKA31', '1959'}
MAX_LEVEL = 13100

all_members = c.execute(
    "SELECT snapshot_id, position, name, help, level, source_file, league_crowns, league_max_crowns, league_wins, game_start_date, profile_wins, profile_help_given, profile_help_received, profile_territories, profile_collections, profile_sets FROM members ORDER BY snapshot_id, position"
).fetchall()

last_profile_date = c.execute(
    "SELECT s.date FROM snapshots s JOIN members m ON m.snapshot_id = s.id WHERE m.profile_wins IS NOT NULL ORDER BY s.date DESC LIMIT 1"
).fetchone()
last_profile_date = last_profile_date[0] if last_profile_date else None
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
        player_history[key][snap_id] = {'level': m['level'], 'help': m['help'], 'position': m['position'], 'source_file': m['source_file'], 'league_crowns': m['league_crowns'], 'league_max_crowns': m['league_max_crowns'], 'league_wins': m['league_wins'], 'game_start_date': m['game_start_date'], 'profile_wins': m['profile_wins'], 'profile_help_given': m['profile_help_given'], 'profile_help_received': m['profile_help_received'], 'profile_territories': m['profile_territories'], 'profile_collections': m['profile_collections'], 'profile_sets': m['profile_sets']}
    else:
        player_history[name][snap_id] = {'level': m['level'], 'help': m['help'], 'position': m['position'], 'source_file': m['source_file'], 'league_crowns': m['league_crowns'], 'league_max_crowns': m['league_max_crowns'], 'league_wins': m['league_wins'], 'game_start_date': m['game_start_date'], 'profile_wins': m['profile_wins'], 'profile_help_given': m['profile_help_given'], 'profile_help_received': m['profile_help_received'], 'profile_territories': m['profile_territories'], 'profile_collections': m['profile_collections'], 'profile_sets': m['profile_sets']}


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

has_league_data = any(
    p['history'].get(snap_ids[-1], {}).get('league_crowns') is not None
    for p in players if snap_ids[-1] in p['history']
)

table_snap_ids = snap_ids[-3:]
table_snap_dates = snap_dates[-3:]

# --- Birthdays (game start anniversaries by month) ---
from datetime import date
today = date.today()
MONTH_NAMES = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь',
}
by_month = {}
for p in players:
    if snap_ids[-1] not in p['history']:
        continue
    gsd = p['history'][snap_ids[-1]].get('game_start_date')
    if not gsd:
        continue
    parts = gsd.split('/')
    if len(parts) != 2:
        continue
    start_month, start_year = int(parts[0]), int(parts[1])
    years = today.year - start_year
    if start_month > today.month:
        years -= 1
    if years <= 0:
        continue
    by_month.setdefault(start_month, []).append({
        'name': p['display_name'],
        'years': years,
    })

current_month_players = by_month.get(today.month, [])
if current_month_players:
    birthday_month = today.month
else:
    for offset in range(1, 13):
        m = (today.month - 1 + offset) % 12 + 1
        if m in by_month:
            birthday_month = m
            break
    else:
        birthday_month = None

birthday_html = ''
if birthday_month is not None:
    bday_players = by_month[birthday_month]
    is_current = birthday_month == today.month
    month_label = MONTH_NAMES[birthday_month]
    if is_current:
        birthday_html += f'<li style="color:#f5c842;margin-bottom:6px">В этом месяце ({month_label}):</li>\n'
    else:
        birthday_html += f'<li style="color:#f5c842;margin-bottom:6px">Ближайшие — {month_label}:</li>\n'
    for b in sorted(bday_players, key=lambda x: -x['years']):
        suffix = {1: 'год', 2: 'года', 3: 'года', 4: 'года'}.get(b['years'] % 10, 'лет')
        if 11 <= b['years'] % 100 <= 14:
            suffix = 'лет'
        birthday_html += f'<li><strong>{b["name"]}</strong> — {b["years"]} {suffix} в игре</li>\n'

# --- Fun facts ---
current_players = [p for p in players if snap_ids[-1] in p['history']]
latest_data = {p['display_name']: p['history'][snap_ids[-1]] for p in current_players}
facts = []

def parse_gsd(gsd):
    if not gsd:
        return (9999, 99)
    parts = gsd.split('/')
    return (int(parts[1]), int(parts[0]))

def fmt(n):
    return f'{n:,}'.replace(',', '\u2009')

top_help = max(latest_data.items(), key=lambda x: x[1].get('profile_help_given') or 0)
if top_help[1].get('profile_help_given'):
    facts.append(f'<strong>{top_help[0]}</strong> — монстр помощи: {fmt(top_help[1]["profile_help_given"])} отправлено, {fmt(top_help[1]["profile_help_received"])} получено')

most_independent = max(
    ((n, d) for n, d in latest_data.items() if (d.get('profile_help_given') or 0) > 0 and (d.get('profile_help_received') or 0) > 0),
    key=lambda x: (x[1]['profile_help_given'] / x[1]['profile_help_received']),
    default=None
)
if most_independent:
    ratio = most_independent[1]['profile_help_given'] / most_independent[1]['profile_help_received']
    facts.append(f'<strong>{most_independent[0]}</strong> — самостоятельный: отдаёт в {ratio:.0f}× больше помощи, чем получает')

lone_wolves = [n for n, d in latest_data.items() if (d.get('profile_help_given') or 0) == 0 and (d.get('profile_help_received') or 0) == 0]
if lone_wolves:
    facts.append(f'<strong>{", ".join(lone_wolves)}</strong> — волк-одиночка: 0 помощи в обе стороны')

fastest = None
for n, d in latest_data.items():
    gsd = d.get('game_start_date')
    if not gsd:
        continue
    parts = gsd.split('/')
    start = date(int(parts[1]), int(parts[0]), 1)
    months = (today.year - start.year) * 12 + today.month - start.month
    if months <= 0:
        continue
    lvl_per_month = (d.get('level') or 0) / months
    if fastest is None or lvl_per_month > fastest[1]:
        fastest = (n, lvl_per_month, d.get('level'), months)
if fastest:
    facts.append(f'<strong>{fastest[0]}</strong> — самый быстрый: {fmt(fastest[2])} уровней за {fastest[3]} мес. ({fastest[1]:.0f}/мес.)')

slowest = None
for n, d in latest_data.items():
    gsd = d.get('game_start_date')
    if not gsd:
        continue
    parts = gsd.split('/')
    start = date(int(parts[1]), int(parts[0]), 1)
    months = (today.year - start.year) * 12 + today.month - start.month
    if months < 6:
        continue
    lvl_per_month = (d.get('level') or 0) / months
    if slowest is None or lvl_per_month < slowest[1]:
        slowest = (n, lvl_per_month, d.get('level'), months)
if slowest:
    facts.append(f'<strong>{slowest[0]}</strong> — самый неторопливый: {fmt(slowest[2])} уровней за {slowest[3]} мес. ({slowest[1]:.0f}/мес.)')

oldest = min(latest_data.items(), key=lambda x: parse_gsd(x[1].get('game_start_date')))
if oldest[1].get('game_start_date'):
    parts = oldest[1]['game_start_date'].split('/')
    start = date(int(parts[1]), int(parts[0]), 1)
    months = (today.year - start.year) * 12 + today.month - start.month
    years = months // 12
    rem = months % 12
    age = f'{years} г. {rem} мес.' if rem else f'{years} г.'
    facts.append(f'<strong>{oldest[0]}</strong> — самый давний игрок ({age}, с {oldest[1]["game_start_date"]})')

facts_html = '\n'.join(f'<li>{f}</li>' for f in facts)

# --- Table rows ---
rows_html = []
max_level_separator_added = False
league_cols = 3 if has_league_data else 0
total_cols = 3 + len(table_snap_ids) * 2 + league_cols + 1
for p in players:
    if snap_ids[-1] not in p['history']:
        continue

    if not max_level_separator_added and p['latest_level'] < MAX_LEVEL:
        rows_html.append(f'<tr class="max-level-separator"><td colspan="{total_cols}"></td></tr>')
        max_level_separator_added = True

    is_protected = p['display_name'] in PROTECTED_MEMBERS
    row_class = "inactive" if p['inactive'] else ("new-member" if p['is_new'] else "active")
    if is_protected:
        row_class += " protected"

    shield = ' <span class="shield" title="Защищённый игрок — не будет исключён на общих условиях">&#128274;</span>' if is_protected else ''
    game_start = None
    for sid in reversed(snap_ids):
        if sid in p['history'] and p['history'][sid].get('game_start_date'):
            game_start = p['history'][sid]['game_start_date']
            break
    cells = f'<td>{p["latest_position"]}</td><td>{p["display_name"]}{shield}</td><td class="na">{game_start or "—"}</td>'
    for sid in table_snap_ids:
        if sid in p['history']:
            h = p['history'][sid]
            sources = [s for s in (h.get('source_file') or '').split(',') if s]
            def make_links(v, srcs=sources):
                if not srcs:
                    return str(v)
                srcs_js = ','.join(srcs)
                return f'<a href="#" onclick="showImgs(\'{srcs_js}\');return false">{v}</a>'
            cells += f'<td>{make_links(h["level"])}</td><td>{make_links(h["help"])}</td>'
        else:
            cells += '<td class="na">—</td><td class="na">—</td>'

    if has_league_data:
        latest = p['history'].get(snap_ids[-1], {})
        lc = latest.get('league_crowns')
        if lc is not None:
            l_sources = [s for s in (latest.get('source_file') or '').split(',') if s]
            l_srcs_js = ','.join(l_sources)
            def l_link(v):
                return f'<a href="#" onclick="showImgs(\'{l_srcs_js}\');return false">{v}</a>' if l_sources else str(v)
            cells += f'<td>{l_link(lc)}</td><td>{l_link(latest.get("league_max_crowns", "—"))}</td><td>{l_link(latest.get("league_wins", "—"))}</td>'
        else:
            cells += '<td class="na">—</td><td class="na">—</td><td class="na">—</td>'

    if p['recent_delta'] is not None:
        d = p['recent_delta']
        delta_str = f"+{d}" if d > 0 else str(d)
    elif p['is_new']:
        delta_str = "новый"
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
    if len(p['history']) < 2 or snap_ids[-1] not in p['history']:
        continue
    data_points = []
    for sid, date in zip(snap_ids, snap_dates):
        if sid in p['history']:
            data_points.append({'x': date, 'y': p['history'][sid]['level']})

    color = '#f66' if p['inactive'] else palette[i % len(palette)]
    chart_datasets.append({
        'label': p['display_name'],
        'data': data_points,
        'borderColor': color,
        'backgroundColor': color,
        'borderWidth': p['inactive'] and 1 or 2,
        'pointRadius': 4,
        'tension': 0.3,
    })

date_headers = ''.join(f'<th colspan="2">{d}</th>' for d in table_snap_dates)
league_headers_top = '<th colspan="3">Лига</th>' if has_league_data else ''
league_headers_bottom = '<th>Короны</th><th>Макс</th><th>Победы</th>' if has_league_data else ''

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Three Stripes — Clan Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Luckiest+Guy&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1b2444;
    color: #e8e0d0;
    padding: 20px;
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{
    text-align: center;
    margin-bottom: 5px;
    font-family: 'Luckiest Guy', cursive;
    font-size: 2.2em;
    color: #f5c842;
    text-shadow: 2px 2px 0 #1a2040, 0 0 10px rgba(245, 200, 66, 0.3);
    letter-spacing: 2px;
  }}
  .meta {{
    text-align: center;
    color: #8090b0;
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
    padding: 8px 18px;
    border-radius: 12px;
    background: #243054;
    border: 2px solid #8a7030;
    font-weight: bold;
  }}
  .top-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
  }}
  .chart-container {{
    background: #243054;
    border: 2px solid #8a7030;
    border-radius: 16px;
    padding: 20px;
    height: 400px;
    position: relative;
  }}
  .chart-container h2 {{
    font-size: 1.1em;
    margin-bottom: 15px;
    color: #f5c842;
  }}
  .table-wrap {{
    overflow-x: auto;
    background: #243054;
    border: 2px solid #8a7030;
    border-radius: 16px;
    padding: 4px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    white-space: nowrap;
  }}
  th {{
    background: #243054;
    padding: 10px 8px;
    text-align: left;
    font-size: 0.85em;
    color: #f5c842;
    position: sticky;
    top: 0;
    border-bottom: 2px solid #3a4a70;
  }}
  td {{
    padding: 8px;
    border-bottom: 1px solid #2d3d60;
    font-size: 0.9em;
  }}
  td.na {{
    color: #4a5a80;
  }}
  tr:hover {{
    background: #2a3a5e;
  }}
  tr.inactive {{
    background: #2e2030;
  }}
  tr.inactive:hover {{
    background: #3a2840;
  }}
  tr.inactive td {{
    color: #e07070;
  }}
  tr.active td.delta {{
    color: #7edb7e;
  }}
  tr.new-member td {{
    color: #70bfff;
  }}
  tr.inactive td.delta {{
    font-weight: bold;
  }}
  td a {{
    color: inherit;
    text-decoration: none;
    border-bottom: 1px dotted #4a5a80;
  }}
  td a:hover {{
    border-bottom-color: #f5c842;
  }}
  tr.max-level-separator td {{
    padding: 0;
    border-bottom: 3px solid #f5c842;
  }}
  .shield {{
    font-size: 0.75em;
  }}
  .rules {{
    background: #243054;
    border: 2px solid #8a7030;
    border-radius: 16px;
    padding: 20px;
    font-size: 0.9em;
    color: #b0c0d8;
  }}
  .rules h2 {{
    font-size: 1.1em;
    margin: 15px 0 10px;
    color: #f5c842;
  }}
  .rules h2:first-child {{
    margin-top: 0;
  }}
  .rules ul {{
    margin: 8px 0 8px 20px;
  }}
  .modal-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    z-index: 1000;
    justify-content: center;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    overflow: auto;
    padding: 20px;
  }}
  .modal-overlay.active {{
    display: flex;
  }}
  .modal-overlay img {{
    max-height: 90vh;
    border: 3px solid #8a7030;
    border-radius: 12px;
    flex-shrink: 0;
  }}
  @media (max-width: 768px) {{
    .top-grid {{
      grid-template-columns: 1fr;
    }}
  }}
  @media (max-width: 600px) {{
    body {{ padding: 10px; }}
    td, th {{ padding: 6px 4px; font-size: 0.8em; }}
    .chart-container {{ padding: 10px; }}
  }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
<h1>Three Stripes</h1>

<div class="top-grid">
  <div class="chart-container">
    <h2>Прогресс по уровням</h2>
    <canvas id="levelChart"></canvas>
  </div>
  <div class="rules">
    <h2>Последнее обновление</h2>
    <p>Список: <span id="lastUpdate" data-date="{snap_dates[-1]}">{snap_dates[-1]}</span></p>
    <p>Профили: <span id="lastProfileUpdate" data-date="{last_profile_date or ''}">{last_profile_date or '—'}</span></p>
    <h2>О клане</h2>
    <p>Three Stripes — русскоязычный клан для тех, кто играет в удовольствие. Никакого хардкора, просто заходим и кайфуем.</p>
    <h2>Активность</h2>
    <p>Чтобы в клане были живые люди, мы периодически (примерно каждую субботу) освобождаем места. Сейчас неактивным считается игрок, у которого за последний период:</p>
    <ul>
      <li>Не изменился уровень</li>
      <li>Нет ни одной помощи</li>
    </ul>
    <p>Это не жёсткое правило — ситуации бывают разные, и подход может меняться.</p>
    <p>Игроки с &#128274; не затрагиваются при ротации.</p>
  </div>
</div>

<div class="top-grid">
  <div class="rules">
    <h2>&#127874; Королевские дни рождения</h2>
    <ul>
      {birthday_html}
    </ul>
  </div>
  <div class="rules">
    <h2>&#127942; Интересные факты</h2>
    <ul>
      {facts_html}
    </ul>
  </div>
</div>

<div class="table-wrap">
<table>
<thead>
  <tr>
    <th rowspan="2">#</th>
    <th rowspan="2">Имя</th>
    <th rowspan="2">В игре с</th>
    {date_headers}
    {league_headers_top}
    <th rowspan="2">Результат<br><small>{table_snap_dates[-2]} &rarr; {table_snap_dates[-1]}</small></th>
  </tr>
  <tr>
    {''.join('<th>Уровень</th><th>Помощь</th>' for _ in table_snap_dates)}
    {league_headers_bottom}
  </tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>

<div class="modal-overlay" id="imgOverlay"></div>
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
          color: '#8090b0',
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
        ticks: {{ color: '#8090b0' }},
        grid: {{ color: '#2d3d60' }},
      }},
      y: {{
        ticks: {{ color: '#8090b0' }},
        grid: {{ color: '#2d3d60' }},
        title: {{
          display: true,
          text: 'Уровень',
          color: '#8090b0',
        }}
      }}
    }}
  }}
}});

function formatAgo(el) {{
  if (!el || !el.dataset.date) return;
  const d = new Date(el.dataset.date);
  const diff = Math.floor((new Date() - d) / 86400000);
  const days = diff === 0 ? 'сегодня' : diff === 1 ? '1 день назад' : diff < 5 ? diff + ' дня назад' : diff + ' дней назад';
  el.textContent = el.dataset.date + ' (' + days + ')';
}}
formatAgo(document.getElementById('lastUpdate'));
formatAgo(document.getElementById('lastProfileUpdate'));

const overlay = document.getElementById('imgOverlay');
function showImgs(srcList) {{
  overlay.innerHTML = srcList.split(',').map(s => {{
    const date = s.split('/')[1] || '';
    return '<div style="text-align:center"><div style="color:#f5c842;margin-bottom:6px;font-size:0.85em">' + date + '</div><img src="' + s + '"></div>';
  }}).join('');
  overlay.classList.add('active');
}}
function closeOverlay() {{
  overlay.classList.remove('active');
  overlay.innerHTML = '';
}}
overlay.addEventListener('click', closeOverlay);
document.addEventListener('keydown', (e) => {{ if (e.key === 'Escape') closeOverlay(); }});
</script>
<footer class="meta" style="text-align:center;color:#4a5a80;font-size:0.8em;margin-top:20px;padding:10px">
  {snap_dates[0]} &rarr; {snap_dates[-1]} &middot; {len(snap_dates)} снапшотов
</footer>
</body>
</html>
"""

with open(HTML_PATH, 'w') as f:
    f.write(html)

print(f"Generated {HTML_PATH}")
print(f"Snapshots: {len(snap_dates)}, Members: {total}, Inactive: {inactive_count}")
