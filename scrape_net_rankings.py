#!/usr/bin/env python3
"""
NET Rankings Scraper
Scrapes NCAA NET rankings and merges with historical data
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import sys
import os

try:
    from final_net_ranks import FINAL_NET_RANKS_BY_YEAR
except Exception:
    FINAL_NET_RANKS_BY_YEAR = None

USE_EMBEDDED_FINAL_NET_RANKS = True

def scrape_net_rankings():
    url = "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    html_content = None

    try:
        print("Attempting to fetch from NCAA.com...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html_content = response.text
        print(f"Successfully fetched page ({len(html_content)} characters)")
    except Exception as e:
        print(f"WARNING: Network request failed ({e})")
        print("Attempting to read from cached HTML file...")
        try:
            with open("net_rankings_cache.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            print(f"Using cached HTML ({len(html_content)} characters)")
        except Exception:
            print("ERROR: Could not read cached file either")
            print("\nDEBUG INFO:")
            print(f"  Current directory: {os.getcwd()}")
            print(f"  Files in directory: {os.listdir('.')}")
            sys.exit(1)

    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table")

    if not table:
        print("ERROR: Could not find rankings table on page")
        print("\nDEBUG INFO:")
        print(f"  Page title: {soup.find('title').text if soup.find('title') else 'No title'}")
        print(f"  HTML preview (first 500 chars): {html_content[:500]}")
        sys.exit(1)

    tbody = table.find("tbody")
    if not tbody:
        print("ERROR: Table found but missing tbody")
        sys.exit(1)

    rows = tbody.find_all("tr")
    rankings_data = []

    print(f"Found table with {len(rows)} rows")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            rank = cols[0].get_text(strip=True)
            school = cols[1].get_text(strip=True)
            rankings_data.append({"Rank": rank, "School": school})

    df = pd.DataFrame(rankings_data)
    df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce")

    df = df.dropna(subset=["Rank", "School"])
    df["Rank"] = df["Rank"].astype(int)

    print(f"Successfully extracted {len(df)} teams")
    if len(df) > 0:
        print(f"  First team: #{df.iloc[0]['Rank']} {df.iloc[0]['School']}")
        print(f"  Last team: #{df.iloc[-1]['Rank']} {df.iloc[-1]['School']}")

    return df

def load_historical_data(filepath):
    try:
        df = pd.read_excel(filepath, sheet_name="Overall List")
        print(f"Loaded {len(df)} teams from historical data")
        return df
    except Exception as e:
        print(f"ERROR loading historical data: {e}")
        sys.exit(1)

def merge_and_update(historical_df, current_rankings_df):
    current_rankings_df = current_rankings_df.rename(columns={"School": "Team", "Rank": "2025 NET Rank"})

    special_mappings = {
        "Middle Tenn.": "Mid Majordle Tenn."
    }

    def get_display_name(team_name):
        if pd.isna(team_name):
            return team_name
        import re
        if team_name == "Mid Majordle Tenn.":
            return "Middle Tenn."
        display = re.sub(r"\(AQ\)$", "", str(team_name)).strip()
        return display

    def clean_for_matching(name):
        if pd.isna(name):
            return name
        import re
        cleaned = re.sub(r"\(AQ\)$", "", str(name)).strip()
        return cleaned

    historical_df["Display Name"] = historical_df["Team"].apply(get_display_name)

    if USE_EMBEDDED_FINAL_NET_RANKS and FINAL_NET_RANKS_BY_YEAR is not None:
        def _norm_team_name(x):
            if pd.isna(x):
                return x
            s = str(x).strip()
            s = s.replace("(AQ)", "").strip()
            return s

        for yr in (2021, 2022, 2023, 2024):
            col = f"{yr} NET Rank"
            if col in historical_df.columns:
                historical_df[f"{col} Spreadsheet"] = historical_df[col]

            ranks = FINAL_NET_RANKS_BY_YEAR.get(str(yr), FINAL_NET_RANKS_BY_YEAR.get(yr))
            if not ranks:
                continue

            historical_df[col] = historical_df["Display Name"].apply(lambda n: ranks.get(_norm_team_name(n), pd.NA))

    historical_df["2025 NET Rank"] = pd.NA
    historical_df["_clean_name"] = historical_df["Team"].apply(clean_for_matching)

    matches_found = 0
    matches_details = []

    for _, row in current_rankings_df.iterrows():
        ncaa_team = row["Team"]
        rank = row["2025 NET Rank"]

        excel_name = special_mappings.get(ncaa_team)
        if excel_name:
            mask = historical_df["Team"] == excel_name
            if mask.any():
                historical_df.loc[mask, "2025 NET Rank"] = rank
                display_name = historical_df.loc[mask, "Display Name"].iloc[0]
                matches_found += 1
                matches_details.append(f"  ✓ {ncaa_team} (#{rank}) → {excel_name} [Display: {display_name}] [SPECIAL MAPPING]")
                continue

        mask = historical_df["_clean_name"] == ncaa_team
        if mask.any():
            historical_df.loc[mask, "2025 NET Rank"] = rank
            original_name = historical_df.loc[mask, "Team"].iloc[0]
            display_name = historical_df.loc[mask, "Display Name"].iloc[0]
            matches_found += 1
            matches_details.append(f"  ✓ {ncaa_team} (#{rank}) → {original_name} [Display: {display_name}]")
            continue

        mask = historical_df["_clean_name"].str.lower() == str(ncaa_team).lower()
        if mask.any():
            historical_df.loc[mask, "2025 NET Rank"] = rank
            original_name = historical_df.loc[mask, "Team"].iloc[0]
            matches_found += 1
            matches_details.append(f"  ✓ {ncaa_team} (#{rank}) → {original_name} [case-insensitive]")
            continue

        matches_details.append(f"  ✗ {ncaa_team} (#{rank}) - NO MATCH FOUND")

    historical_df.drop("_clean_name", axis=1, inplace=True)

    power_5_teams = [
        'Alabama', 'Arizona', 'Arizona St.', 'Arkansas', 'Auburn', 'BYU', 'Baylor',
        'Boston College', 'Butler', 'California', 'Cincinnati', 'Clemson', 'Colorado',
        'Creighton', 'DePaul', 'Duke', 'Florida', 'Florida St.', 'Georgetown', 'Georgia',
        'Georgia Tech', 'Houston', 'Illinois', 'Indiana', 'Iowa', 'Iowa St.', 'Kansas',
        'Kansas St.', 'Kentucky', 'LSU', 'Louisville', 'Marquette', 'Maryland', 'Miami (FL)',
        'Michigan', 'Michigan St.', 'Minnesota', 'Mississippi St.', 'Missouri', 'NC State',
        'Nebraska', 'North Carolina', 'Northwestern', 'Notre Dame', 'Ohio St.', 'Oklahoma',
        'Oklahoma St.', 'Ole Miss', 'Oregon', 'Penn St.', 'Pittsburgh', 'Providence',
        'Purdue', 'Rutgers', 'SMU', 'Seton Hall', 'South Carolina', 'Southern California',
        "St. John's (NY)", 'Stanford', 'Syracuse', 'TCU', 'Tennessee', 'Texas', 'Texas A&M',
        'Texas Tech', 'UCF', 'UCLA', 'UConn', 'Utah', 'Vanderbilt', 'Villanova', 'Virginia',
        'Virginia Tech', 'Wake Forest', 'Washington', 'West Virginia', 'Wisconsin', 'Xavier'
    ]

    mid_major_avoid_teams = [
        'Gonzaga', "Saint Mary's (CA)", 'San Diego St.', 'Boise St.', 'Utah St.', 'Memphis',
        'VCU', 'Colorado St.', 'Drake', 'North Texas', 'Dayton', 'San Francisco', 'Nevada',
        'Washington St.', 'UAB', 'Grand Canyon', 'Liberty', 'Yale', 'Santa Clara', 'UC Irvine',
        'Fla. Atlantic', 'Bradley', 'St. Bonaventure', 'Loyola Chicago', 'Saint Louis', 'Furman',
        'Davidson', 'Belmont', 'Akron', 'UNLV', 'George Mason', 'Princeton', 'Wichita St.',
        'Louisiana Tech', 'New Mexico', 'Toledo', 'Kent St.', 'South Dakota St.', 'Colgate',
        'Vermont', 'Chattanooga', 'Richmond', 'UNC Greensboro', 'UC Santa Barbara', 'Ohio',
        'Tulane', 'James Madison', 'Col. of Charleston', 'Cornell', 'Western Ky.', 'Indiana St.',
        'Utah Valley', 'Hofstra', 'Missouri St.', 'UNI', 'Sam Houston', 'Wyoming', 'Murray St.',
        'Temple', 'Wofford', 'Samford', 'Duquesne', "Saint Joseph's", 'LMU (CA)', 'UNCW',
        'Southern Ill.', 'UC Riverside', 'Towson', 'Drexel', 'Seattle U', 'South Alabama', 'Troy',
        'New Mexico St.', 'South Fla.', 'Cleveland St.', 'Morehead St.', 'ETSU', 'Longwood',
        'Lipscomb', 'Middle Tenn.', 'Montana', 'North Dakota St.', 'Louisiana', 'Arkansas St.',
        'Youngstown St.', 'UC San Diego', 'High Point', 'Oregon St.'
    ]

    mid_major_consider_teams = [
        'Iona', 'Winthrop', 'App State', 'Massachusetts', 'Bryant', 'Wright St.', 'Marshall',
        'Montana St.', 'UTEP', 'SFA', 'Abilene Christian', 'Rhode Island', 'Jacksonville St.',
        'Texas St.', 'Eastern Wash.', 'Hawaii', 'Norfolk St.', 'Charlotte', 'East Carolina',
        'Fresno St.', 'Weber St.', 'UNC Asheville', 'Oral Roberts', 'UMass Lowell', 'St. Thomas (MN)',
        'Northern Colo.', 'Oakland', 'George Washington', 'Illinois St.', 'Purdue Fort Wayne',
        'Kennesaw St.', 'Long Beach St.', 'Miami (OH)', 'McNeese', 'Milwaukee', 'San Jose St.',
        'UIC', 'Western Caro.', 'North Ala.', 'CSUN', 'Dartmouth', 'Air Force', 'VMI', 'Robert Morris'
    ]

    mid_major_play_teams = [
        'Northern Ky.', 'Brown', 'Delaware', 'Eastern Ky.', 'UC Davis', 'Southern Utah',
        'California Baptist', 'Mercer', 'Quinnipiac', 'Gardner-Webb', 'Navy', 'Fordham',
        'Pepperdine', 'Rice', 'Harvard', 'Nicholls', 'La Salle', 'Georgia St.', 'Old Dominion',
        'Buffalo', 'Tarleton St.', 'Penn', 'FGCU', 'UT Arlington', "Saint Peter's", 'A&M-Corpus Christi',
        'Radford', 'Tulsa', 'Cal St. Fullerton', 'Queens (NC)', 'Ball St.', 'Monmouth',
        "Mount St. Mary's", 'Jacksonville', 'Northeastern', 'Marist', 'Campbell', 'UMBC', 'Siena',
        'Boston U.', 'Merrimack', 'Bowling Green', 'South Dakota', 'CSU Bakersfield', 'Valparaiso',
        'Fairfield', 'Portland St.', 'Southern Miss.', 'Kansas City', 'Wagner', 'UTSA', 'Niagara',
        'Portland', 'Coastal Carolina', 'Ga. Southern', 'Southern U.', 'Texas Southern', 'Elon',
        'Rider', 'Pacific', 'San Diego', 'Little Rock', 'Army West Point', 'Detroit Mercy', 'Stetson',
        'Stony Brook', 'American', 'Bellarmine', 'Southeast Mo. St.', 'Idaho St.', 'SIUE',
        'North Florida', 'New Hampshire', 'Bucknell', 'FIU', 'Utah Tech', 'Canisius', 'UAlbany',
        'Howard', 'Southeastern La.', 'Austin Peay', 'Evansville', 'Maine', 'Western Ill.',
        'Lafayette', 'UT Martin', 'Loyola Maryland', 'Grambling', 'N.C. Central', 'The Citadel',
        'Jackson St.', 'Lehigh', 'Lamar University', 'Central Conn. St.', 'Northwestern St.',
        'Tennessee St.', 'Manhattan', 'Omaha', 'North Dakota', 'Central Mich.', 'UTRGV', 'Morgan St.',
        'Northern Ariz.', 'LIU', 'Sacred Heart', 'Sacramento St.', 'Presbyterian', 'Prairie View',
        'Cal Poly', 'Alcorn', 'William & Mary', 'Binghamton', 'Denver', 'Columbia', 'USC Upstate',
        'South Carolina St.', 'FDU', 'ULM', 'Western Mich.', 'Hampton', 'Southern Ind.', 'Eastern Mich.',
        'NIU', 'Green Bay', 'Holy Cross', 'UMES', 'N.C. A&T', 'Idaho', 'New Orleans', 'Bethune-Cookman',
        'Alabama St.', 'Charleston So.', 'Coppin St.', 'NJIT', 'East Texas A&M', 'Florida A&M', 'UIW',
        'Le Moyne', 'Eastern Ill.', 'Stonehill', 'Chicago St.', 'Alabama A&M', 'Central Ark.',
        'Delaware St.', 'IU Indy', 'Houston Christian', 'Lindenwood', 'Ark.-Pine Bluff', 'Mississippi Val.'
    ]

    def assign_status(display_name):
        if display_name in power_5_teams:
            return "Power 5"
        if display_name in mid_major_avoid_teams:
            return "Mid-Major Avoid"
        if display_name in mid_major_consider_teams:
            return "Mid-Major Consider"
        if display_name in mid_major_play_teams:
            return "Mid-Major Play"
        return "Mid-Major"

    historical_df["Status"] = historical_df["Display Name"].apply(assign_status)

    historical_df = historical_df[historical_df["Display Name"] != "Saint Francis"]

    year_cols = ["2021 NET Rank", "2022 NET Rank", "2023 NET Rank", "2024 NET Rank", "2025 NET Rank"]
    for col in year_cols:
        historical_df[col] = pd.to_numeric(historical_df[col], errors="coerce")
    historical_df["Average 5 Year NET"] = historical_df[year_cols].mean(axis=1, skipna=True).round(1)

    teams_updated = historical_df["2025 NET Rank"].notna().sum()
    print(f"Updated {teams_updated} teams with 2025 rankings ({matches_found} matches from {len(current_rankings_df)} NCAA teams)")

    mismatches = [d for d in matches_details if "NO MATCH" in d]
    if mismatches:
        print(f"\n⚠️  WARNING: {len(mismatches)} teams from NCAA could not be matched:")
        for detail in mismatches[:20]:
            print(detail)
        if len(mismatches) > 20:
            print(f"  ... and {len(mismatches) - 20} more")
    else:
        print("✓ All NCAA teams matched successfully!")

    not_updated = historical_df[historical_df["2025 NET Rank"].isna()]
    if len(not_updated) > 0:
        print(f"\n📊 {len(not_updated)} teams in your Excel file did not receive 2025 rankings")
        print("   (This is normal - these teams may not be in the current NET rankings)")

    column_order = [
        "Display Name", "Status",
        "2021 NET Rank", "2022 NET Rank", "2023 NET Rank", "2024 NET Rank", "2025 NET Rank",
        "Average 5 Year NET"
    ]
    historical_df = historical_df[column_order]
    print("\n✓ Status categories assigned and columns reordered")

    return historical_df

def update_daily_history(updated_df, daily_history_path="net_rankings_daily.csv"):
    """
    Append today's rankings to the daily history file for time-series tracking
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Load existing daily history if it exists
    if os.path.exists(daily_history_path):
        try:
            daily_df = pd.read_csv(daily_history_path)
            print(f"Loaded existing daily history: {len(daily_df)} records")
            
            # Remove any existing entries for today (in case we're re-running)
            daily_df = daily_df[daily_df['date'] != today]
            print(f"Removed any existing entries for {today}")
        except Exception as e:
            print(f"Warning: Could not load existing daily history ({e}), creating new file")
            daily_df = pd.DataFrame(columns=['date', 'team', 'rank'])
    else:
        print("No existing daily history found, creating new file")
        daily_df = pd.DataFrame(columns=['date', 'team', 'rank'])
    
    # Create today's entries from the updated rankings
    new_entries = []
    for _, row in updated_df.iterrows():
        team_name = row['Display Name']
        current_rank = row['2025 NET Rank']
        
        # Only add if team has a valid current ranking
        if pd.notna(current_rank):
            new_entries.append({
                'date': today,
                'team': team_name,
                'rank': int(current_rank)
            })
    
    # Append new entries
    if new_entries:
        new_df = pd.DataFrame(new_entries)
        daily_df = pd.concat([daily_df, new_df], ignore_index=True)
        print(f"Added {len(new_entries)} rankings for {today}")
    else:
        print("Warning: No new rankings to add for today")
    
    # Sort by date and team
    daily_df = daily_df.sort_values(['date', 'team'])
    
    # Save updated daily history
    daily_df.to_csv(daily_history_path, index=False)
    print(f"✓ Daily history updated: {len(daily_df)} total records in {daily_history_path}")
    
    # Show some stats
    unique_dates = daily_df['date'].nunique()
    print(f"  Tracking {unique_dates} unique dates")
    
    return daily_df

def save_output(df, output_path):
    try:
        df.to_csv(output_path, index=False)
        print(f"Saved output to {output_path}")
    except Exception as e:
        print(f"ERROR saving output: {e}")
        sys.exit(1)

def main():
    print("=== NET Rankings Scraper ===")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("Step 1: Scraping current NET rankings from NCAA.com...")
    current_rankings = scrape_net_rankings()
    print()

    print("Step 2: Loading historical data...")
    historical_data_path = "ACC_Who_to_Play.xlsx"
    historical_df = load_historical_data(historical_data_path)
    print()

    print("Step 3: Merging data and recalculating averages...")
    updated_df = merge_and_update(historical_df, current_rankings)
    print()

    print("Step 4: Saving updated rankings...")
    save_output(updated_df, "net_rankings_data.csv")
    print()

    print("Step 5: Updating daily history for time-series tracking...")
    update_daily_history(updated_df, "net_rankings_daily.csv")
    print()

    print("✓ Complete! Current rankings and daily history updated.")

if __name__ == "__main__":
    main()
