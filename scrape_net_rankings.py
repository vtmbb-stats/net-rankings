#!/usr/bin/env python3
"""
NET Rankings Scraper

Pulls the current NCAA men's basketball NET rankings from NCAA.com and builds
the files the dashboard reads:

  net_ranks_by_season.json  NET rank per team for every season (the source of truth).
                            The current season's entry is overwritten on every run,
                            so once the season ends it simply holds the final NET.
  net_rankings_data.csv     One row per team: status, last 4 final ranks, current
                            rank and the rolling 5-year average.
  net_rankings_daily.csv    Time series for the team charts (a snapshot is only
                            appended in-season, when the rankings actually change).
  net_meta.json             Season / "through games" info shown on the dashboard.

Seasons are labelled by the year they END (2026-27 season = 2027), matching
the dashboard. The season shown on NCAA.com is read from its "Through Games"
date, so last season's final NET is never mistaken for the new season.

Usage:
  python scrape_net_rankings.py                   # live scrape
  python scrape_net_rankings.py --html page.html  # use a saved copy of the page
"""

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

NET_URL = "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings"
EASTERN = ZoneInfo("America/New_York")
WINDOW = 5  # seasons in the rolling average (current season + 4 finals)

# Mid-majors are classified from their rolling 5-year average NET each run.
AVOID_MAX = 150     # avg <= 150        -> Mid-Major Avoid
CONSIDER_MAX = 200  # avg 150.1 - 200   -> Mid-Major Consider; above 200 -> Mid-Major Play

ROOT = Path(__file__).resolve().parent
RANKS_PATH = ROOT / "net_ranks_by_season.json"
STATUS_PATH = ROOT / "team_status.csv"
DATA_PATH = ROOT / "net_rankings_data.csv"
DAILY_PATH = ROOT / "net_rankings_daily.csv"
META_PATH = ROOT / "net_meta.json"

# NCAA.com name -> name used in our files, for any team NCAA renames.
NAME_FIXES: dict[str, str] = {}


def season_for(d: date) -> int:
    """Season label (end year) for a date. Aug 2026 - Jul 2027 -> 2027."""
    return d.year + 1 if d.month >= 8 else d.year


def season_name(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def fetch_html(html_path: str | None) -> str:
    if html_path:
        print(f"Reading saved page from {html_path}")
        return Path(html_path).read_text(encoding="utf-8")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(NET_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    print(f"Fetched NCAA.com ({len(resp.text):,} chars)")
    return resp.text


def parse_through_date(soup: BeautifulSoup) -> date | None:
    """Parse the 'Through Games Apr. 06 2026' label above the table."""
    el = soup.find(class_="rankings-last-updated")
    text = el.get_text(" ", strip=True) if el else soup.get_text(" ")
    m = re.search(r"Through Games\s+([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", text)
    if not m:
        return None
    month, day, year = m.groups()
    try:
        return datetime.strptime(f"{month[:3]} {day} {year}", "%b %d %Y").date()
    except ValueError:
        return None


def parse_rankings(html: str) -> tuple[pd.DataFrame, date | None]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None or table.find("tbody") is None:
        title = soup.title.get_text(strip=True) if soup.title else "no title"
        sys.exit(f"ERROR: rankings table not found on page ({title})")

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    idx = {h: i for i, h in enumerate(headers)}
    for required in ("Rank", "School"):
        if required not in idx:
            sys.exit(f"ERROR: table is missing a '{required}' column; headers were {headers}")

    def cell(cols, name):
        i = idx.get(name)
        return cols[i].get_text(strip=True) if i is not None and i < len(cols) else ""

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cols = tr.find_all("td")
        rank = cell(cols, "Rank")
        if not rank.isdigit():
            continue
        school = cell(cols, "School")
        rows.append({
            "Team": NAME_FIXES.get(school, school),
            "Rank": int(rank),
            "Record": cell(cols, "Record"),
            "Conference": cell(cols, "Conf"),
            "Quad 1": cell(cols, "Quad 1"),
        })

    df = pd.DataFrame(rows)
    if len(df) < 300:
        sys.exit(f"ERROR: only parsed {len(df)} teams; page layout may have changed")
    if df["Team"].duplicated().any():
        sys.exit(f"ERROR: duplicate teams on page: {df.loc[df['Team'].duplicated(), 'Team'].tolist()}")

    through = parse_through_date(soup)
    print(f"Parsed {len(df)} teams (#1 {df.iloc[0]['Team']}), through games {through or 'UNKNOWN'}")
    return df, through


def load_status() -> dict[str, str]:
    with open(STATUS_PATH, newline="", encoding="utf-8") as f:
        return {r["Team"].strip(): r["Status"].strip() for r in csv.DictReader(f)}


def mid_major_status(avg: float) -> str:
    if pd.isna(avg):
        return "Mid-Major"
    if avg <= AVOID_MAX:
        return "Mid-Major Avoid"
    if avg <= CONSIDER_MAX:
        return "Mid-Major Consider"
    return "Mid-Major Play"


def determine_page_season(through: date | None, ranks: dict, current_season: int, scraped: dict) -> int:
    if through is not None:
        return season_for(through)
    # Fallback: if the page is identical to last season's stored final, it is still last season.
    if ranks.get(str(current_season - 1)) == scraped:
        print("WARNING: no 'Through Games' date; page matches last season's final")
        return current_season - 1
    print("WARNING: no 'Through Games' date; assuming the page shows the current season")
    return current_season


def build_dashboard(ranks: dict, status: dict, current_season: int, page_df: pd.DataFrame,
                    current_live: bool) -> pd.DataFrame:
    seasons = list(range(current_season - WINDOW + 1, current_season + 1))
    cols = [f"NET {s}" for s in seasons]

    # Team universe: the teams on the NCAA page right now (the current D-I field),
    # minus anything marked Exclude in team_status.csv.
    teams = sorted(t for t in page_df["Team"] if status.get(t) != "Exclude")

    info = page_df.set_index("Team")
    out = []
    for t in teams:
        row = {
            "Team": t,
            "Status": status.get(t, ""),  # Power 5 from team_status.csv; mid-majors filled below
            "Conference": info.at[t, "Conference"],
            "Record": info.at[t, "Record"] if current_live else "",
            "Quad 1": info.at[t, "Quad 1"] if current_live else "",
        }
        for s, c in zip(seasons, cols):
            row[c] = ranks.get(str(s), {}).get(t)
        out.append(row)

    df = pd.DataFrame(out)
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df["Average 5 Year NET"] = df[cols].astype("float").mean(axis=1, skipna=True).round(1)
    mid = df["Status"] != "Power 5"
    df.loc[mid, "Status"] = df.loc[mid, "Average 5 Year NET"].apply(mid_major_status)
    return df


def update_daily(page_df: pd.DataFrame, today: str) -> None:
    snapshot = page_df[["Team", "Rank"]].rename(columns={"Rank": "NET_Rank"})
    if DAILY_PATH.exists():
        daily = pd.read_csv(DAILY_PATH)
        daily = daily[daily["Date"] != today]  # a re-run on the same day replaces that day
    else:
        daily = pd.DataFrame(columns=["Date", "Team", "NET_Rank"])

    if len(daily):
        last_date = daily["Date"].max()
        last = daily[daily["Date"] == last_date]
        if dict(zip(last["Team"], last["NET_Rank"])) == dict(zip(snapshot["Team"], snapshot["NET_Rank"])):
            print(f"Daily history: rankings unchanged since {last_date}, nothing appended")
            daily.to_csv(DAILY_PATH, index=False)
            return

    snapshot.insert(0, "Date", today)
    daily = pd.concat([daily, snapshot], ignore_index=True).sort_values(["Date", "Team"])
    daily.to_csv(DAILY_PATH, index=False)
    print(f"Daily history: appended {len(snapshot)} rows for {today} ({daily['Date'].nunique()} snapshots)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="parse a saved copy of the NCAA page instead of fetching it")
    args = ap.parse_args()

    now = datetime.now(EASTERN)
    today = now.date().isoformat()
    current_season = season_for(now.date())
    print(f"=== NET Rankings Scraper  {now:%Y-%m-%d %H:%M %Z}  (current season {season_name(current_season)}) ===")

    page_df, through = parse_rankings(fetch_html(args.html))
    scraped = dict(zip(page_df["Team"], page_df["Rank"].astype(int)))

    ranks = json.loads(RANKS_PATH.read_text(encoding="utf-8")) if RANKS_PATH.exists() else {}
    page_season = determine_page_season(through, ranks, current_season, scraped)
    if page_season > current_season:
        sys.exit(f"ERROR: page season {page_season} is ahead of the calendar season {current_season}")

    current_live = page_season == current_season
    ranks[str(page_season)] = dict(sorted(scraped.items()))
    RANKS_PATH.write_text(json.dumps(dict(sorted(ranks.items())), indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    if current_live:
        print(f"{season_name(current_season)} NET is live: stored {len(scraped)} ranks")
    else:
        print(f"{season_name(current_season)} NET not released yet; page still shows the "
              f"{season_name(page_season)} final (refreshed that season's stored ranks)")

    status = load_status()
    df = build_dashboard(ranks, status, current_season, page_df, current_live)
    df.to_csv(DATA_PATH, index=False)
    print(f"Wrote {DATA_PATH.name}: {len(df)} teams")
    print("  " + ", ".join(f"{k}: {v}" for k, v in df["Status"].value_counts().items()))

    if current_live:
        update_daily(page_df, today)
    else:
        print("Daily history: off-season, nothing appended")

    META_PATH.write_text(json.dumps({
        "current_season": current_season,
        "seasons": list(range(current_season - WINDOW + 1, current_season + 1)),
        "current_live": current_live,
        "page_season": page_season,
        "through_games": through.isoformat() if through else None,
        "scraped_at": now.isoformat(timespec="minutes"),
    }, indent=1) + "\n", encoding="utf-8")
    print("Done.")


if __name__ == "__main__":
    main()
