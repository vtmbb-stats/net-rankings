# NET Rankings Dashboard

Live dashboard for tracking NCAA men's basketball NET rankings, built for Virginia Tech scheduling.
It shows each team's last four final NET ranks, the live current-season NET, and a rolling 5-year average,
plus a daily ranking chart for any team (click a row or use `index.html?team=Virginia%20Tech`).

## How it works

1. **GitHub Actions** (`.github/workflows/main.yml`) runs `scrape_net_rankings.py` twice a day
   (about 9 AM and 3 PM ET). It can also be started manually from the Actions tab ("Run workflow").
2. The scraper reads the NET table and the **"Through Games" date** from NCAA.com. That date tells it which
   season the page is showing, so last season's final NET is never counted as the new season.
3. It commits the data files only when the rankings actually changed.
4. **Netlify** redeploys the static site on every push.

## Seasons and the 5-year window

Seasons are labelled by the year they **end** (2026-27 = `2027`). The current season is derived from today's date
(August onward counts as the next season), so the table rolls forward on its own every August:

| Today | Columns shown | 5-year average |
|---|---|---|
| Nov 2026 | 2023–2026 Final + 2027 NET | 2023–2027 |
| Nov 2027 | 2024–2027 Final + 2028 NET | 2024–2028 |

Before the NCAA releases the first NET of a season (usually early December), the current column is blank,
the dashboard says so, and the average uses the four completed seasons.

A season's "final" is simply the last rankings the scraper saw for it, so nothing needs to be entered by hand
at the end of a season.

## Mid-major classification

Every team not listed as `Power 5` is classified from its 5-year average NET each run
(cutoffs are `AVOID_MAX` / `CONSIDER_MAX` at the top of the scraper):

| 5-year average | Status |
|---|---|
| 182 or better | Mid-Major Avoid |
| 182.1 – 208 | Mid-Major Consider |
| worse than 208 | Mid-Major Play |

These cutoffs were chosen as the closest match to the original hand-made lists (84% of mid-majors keep their label).

Because the average rolls forward, a team's label can change as new seasons come in.

## Files

| File | What it is |
|---|---|
| `scrape_net_rankings.py` | Scraper; rebuilds every data file below |
| `team_status.csv` | **Edit this** for the hand-maintained labels only: `Power 5` schools and `Exclude` (hide a team). Every other team is a mid-major, classified automatically (see above). |
| `net_ranks_by_season.json` | NET rank for every team, every season (source of truth for finals) |
| `net_rankings_data.csv` | One row per team, read by the dashboard |
| `net_rankings_daily.csv` | Date / Team / NET_Rank history for the charts (in-season, changes only) |
| `net_meta.json` | Current season, "through games" date, last check time |
| `index.html` | The dashboard (vanilla JS + Chart.js) |

## Local development

```bash
pip install -r .github/scripts/requirements.txt
python scrape_net_rankings.py                    # live scrape
python scrape_net_rankings.py --html saved.html  # parse a saved copy of the NCAA page
python -m http.server 8000                       # then open http://localhost:8000
```

## Troubleshooting

- **Action fails with "rankings table not found" or "only parsed N teams"**: NCAA.com changed its page layout,
  so the parser in `parse_rankings()` needs updating. The previous data is left untouched.
- **"no 'Through Games' date" warning**: the date label moved. The scraper falls back to comparing the page
  with last season's stored final, but `parse_through_date()` should be fixed.
- **A power-conference school shows as a mid-major**: add it to `team_status.csv` as `Power 5`.
