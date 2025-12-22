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

# Optional embedded final NET ranks (2021-2024) generated from NCAA final spreadsheets
try:
    from final_net_ranks import FINAL_NET_RANKS_BY_YEAR
except Exception:
    FINAL_NET_RANKS_BY_YEAR = None

USE_EMBEDDED_FINAL_NET_RANKS = True  # set False to revert to Excel historical columns

def scrape_net_rankings():
    """Scrape current NET rankings from NCAA website"""
    url = "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
            with open('net_rankings_cache.html', 'r') as f:
                html_content = f.read()
            print(f"Using cached HTML ({len(html_content)} characters)")
        except:
            print("ERROR: Could not read cached file either")
            print("\nDEBUG INFO:")
            print(f"  Current directory: {os.getcwd()}")
            print(f"  Files in directory: {os.listdir('.')}")
            sys.exit(1)
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    
    if not table:
        print("ERROR: Could not find rankings table on page")
        print("\nDEBUG INFO:")
        print(f"  Page title: {soup.find('title').text if soup.find('title') else 'No title'}")
        print(f"  HTML preview (first 500 chars): {html_content[:500]}")
        sys.exit(1)
    
    # Extract data
    rows = table.find('tbody').find_all('tr')
    rankings_data = []
    
    print(f"Found table with {len(rows)} rows")
    
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 2:
            rank = cols[0].text.strip()
            school = cols[1].text.strip()
            rankings_data.append({'Rank': rank, 'School': school})
    
    df = pd.DataFrame(rankings_data)
    df['Rank'] = pd.to_numeric(df['Rank'], errors='coerce')
    
    print(f"Successfully extracted {len(df)} teams")
    if len(df) > 0:
        print(f"  First team: #{df.iloc[0]['Rank']} {df.iloc[0]['School']}")
        print(f"  Last team: #{df.iloc[-1]['Rank']} {df.iloc[-1]['School']}")
    
    return df

def load_historical_data(filepath):
    """Load historical NET rankings data from Excel file"""
    try:
        df = pd.read_excel(filepath, sheet_name='Overall List')
        print(f"Loaded {len(df)} teams from historical data")
        return df
    except Exception as e:
        print(f"ERROR loading historical data: {e}")
        sys.exit(1)

def merge_and_update(historical_df, current_rankings_df):
    """Merge current rankings with historical data and recalculate averages"""
    
    # Rename columns for clarity
    current_rankings_df = current_rankings_df.rename(columns={'School': 'Team', 'Rank': '2025 NET Rank'})
    
    # Special case mappings for teams that don't match automatically
    special_mappings = {
        'Middle Tenn.': 'Mid Majordle Tenn.'  # NCAA name -> Excel name
    }
    
    # Create display name mapping based on your specifications
    # This removes (AQ) and cleans up state abbreviations
    def get_display_name(team_name):
        """Convert spreadsheet name to display name"""
        if pd.isna(team_name):
            return team_name
        import re
        # Special case for Mid Majordle Tenn -> Middle Tenn.
        if team_name == 'Mid Majordle Tenn.':
            return 'Middle Tenn.'
        # Remove (AQ) suffix
        display = re.sub(r'\(AQ\)$', '', str(team_name)).strip()
        return display
    
    # Create clean name for matching (removes (AQ), keeps state abbreviations)
    def clean_for_matching(name):
        """Remove (AQ) suffix for matching purposes"""
        if pd.isna(name):
            return name
        import re
        # Remove (AQ) suffix
        cleaned = re.sub(r'\(AQ\)$', '', str(name)).strip()
        return cleaned
    
    # Add display name column
    historical_df['Display Name'] = historical_df['Team'].apply(get_display_name)

    # --- Historical override (safe) ---
    # Replace 2021-2024 finishes using embedded final NET ranks generated from the attached files.
    # Keeps the spreadsheet versions in *_Spreadsheet columns so you can flip back instantly.
    if USE_EMBEDDED_FINAL_NET_RANKS and FINAL_NET_RANKS_BY_YEAR is not None:
        def _norm_team_name(x):
            if pd.isna(x):
                return x
            s = str(x).strip()
            s = s.replace('(AQ)', '').strip()
            return s

        for yr in (2021, 2022, 2023, 2024):
            col = f"{yr} NET Rank"
            if col in historical_df.columns:
                historical_df[f"{col} Spreadsheet"] = historical_df[col]

            ranks = FINAL_NET_RANKS_BY_YEAR.get(str(yr), FINAL_NET_RANKS_BY_YEAR.get(yr))
            if not ranks:
                continue

            historical_df[col] = historical_df['Display Name'].apply(lambda n: ranks.get(_norm_team_name(n), pd.NA))
    
    # Update the historical dataframe with new 2025 rankings
    # First, set all existing 2025 ranks to NaN
    historical_df['2025 NET Rank'] = pd.NA
    
    # Create temporary column for matching
    historical_df['_clean_name'] = historical_df['Team'].apply(clean_for_matching)
    
    matches_found = 0
    matches_details = []
    
    # Merge based on team names
    for _, row in current_rankings_df.iterrows():
        ncaa_team = row['Team']
        rank = row['2025 NET Rank']
        
        # Check special mappings first
        excel_name = special_mappings.get(ncaa_team)
        if excel_name:
            mask = historical_df['Team'] == excel_name
            if mask.any():
                historical_df.loc[mask, '2025 NET Rank'] = rank
                display_name = historical_df.loc[mask, 'Display Name'].iloc[0]
                matches_found += 1
                matches_details.append(f"  ✓ {ncaa_team} (#{rank}) → {excel_name} [Display: {display_name}] [SPECIAL MAPPING]")
                continue
        
        # Try exact match with cleaned names
        mask = historical_df['_clean_name'] == ncaa_team
        if mask.any():
            historical_df.loc[mask, '2025 NET Rank'] = rank
            original_name = historical_df.loc[mask, 'Team'].iloc[0]
            display_name = historical_df.loc[mask, 'Display Name'].iloc[0]
            matches_found += 1
            matches_details.append(f"  ✓ {ncaa_team} (#{rank}) → {original_name} [Display: {display_name}]")
            continue
            
        # Try case-insensitive match
        mask = historical_df['_clean_name'].str.lower() == ncaa_team.lower()
        if mask.any():
            historical_df.loc[mask, '2025 NET Rank'] = rank
            original_name = historical_df.loc[mask, 'Team'].iloc[0]
            display_name = historical_df.loc[mask, 'Display Name'].iloc[0]
            matches_found += 1
            matches_details.append(f"  ✓ {ncaa_team} (#{rank}) → {original_name} [case-insensitive]")
            continue
        
        # No match found
        matches_details.append(f"  ✗ {ncaa_team} (#{rank}) - NO MATCH FOUND")
    
    # Remove temporary column
    historical_df.drop('_clean_name', axis=1, inplace=True)
    
    # Assign Status based on team categories
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
        """Assign status category based on display name"""
        if display_name in power_5_teams:
            return 'Power 5'
        elif display_name in mid_major_avoid_teams:
            return 'Mid-Major Avoid'
        elif display_name in mid_major_consider_teams:
            return 'Mid-Major Consider'
        elif display_name in mid_major_play_teams:
            return 'Mid-Major Play'
        else:
            return 'Mid-Major'  # Default for any unassigned mid-majors
    
    historical_df['Status'] = historical_df['Display Name'].apply(assign_status)
    
    # Remove Saint Francis from the data
    historical_df = historical_df[historical_df['Display Name'] != 'Saint Francis']
    
    # Recalculate 5-year average
    year_cols = ['2021 NET Rank', '2022 NET Rank', '2023 NET Rank', '2024 NET Rank', '2025 NET Rank']
    # Convert columns to numeric first
    for col in year_cols:
        historical_df[col] = pd.to_numeric(historical_df[col], errors='coerce')
    historical_df['Avergae 5 Year NET'] = historical_df[year_cols].mean(axis=1, skipna=True).round(1)
    
    teams_updated = historical_df['2025 NET Rank'].notna().sum()
    print(f"Updated {teams_updated} teams with 2025 rankings ({matches_found} matches from {len(current_rankings_df)} NCAA teams)")
    
    # Show match details
    mismatches = [d for d in matches_details if "NO MATCH" in d]
    if mismatches:
        print(f"\n⚠️  WARNING: {len(mismatches)} teams from NCAA could not be matched:")
        for detail in mismatches[:20]:  # Show first 20
            print(detail)
        if len(mismatches) > 20:
            print(f"  ... and {len(mismatches) - 20} more")
    else:
        print("✓ All NCAA teams matched successfully!")
    
    # Show teams in historical data that didn't get updated
    not_updated = historical_df[historical_df['2025 NET Rank'].isna()]
    if len(not_updated) > 0:
        print(f"\n📊 {len(not_updated)} teams in your Excel file did not receive 2025 rankings")
        print("   (This is normal - these teams may not be in the current NET rankings)")
    
    # Reorder columns: Display Name, Status, then rankings (oldest to newest)
    column_order = ['Display Name', 'Status', '2021 NET Rank', '2022 NET Rank', '2023 NET Rank',
                    '2024 NET Rank', '2025 NET Rank', 'Avergae 5 Year NET']
    historical_df = historical_df[column_order]
    print(f"\n✓ Status categories assigned and columns reordered")
    
    return historical_df

def save_output(df, output_path):
    """Save updated data to CSV"""
    try:
        df.to_csv(output_path, index=False)
        print(f"Saved output to {output_path}")
    except Exception as e:
        print(f"ERROR saving output: {e}")
        sys.exit(1)

def main():
    print(f"=== NET Rankings Scraper ===")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Save current rankings to daily history BEFORE scraping new data
    print("Step 1: Archiving current rankings to daily history...")
    daily_history_path = 'net_rankings_daily.csv'
    current_data_path = 'net_rankings_data.csv'
    
    if os.path.exists(current_data_path):
        try:
            current_data = pd.read_csv(current_data_path)
            # Use TODAY's date - the current data represents today's rankings
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Prepare today's data from current rankings
            today_data = current_data[['Display Name', '2025 NET Rank']].copy()
            today_data.columns = ['Team', 'NET_Rank']
            today_data['Date'] = today
            today_data = today_data[['Date', 'Team', 'NET_Rank']]
            today_data = today_data.dropna(subset=['NET_Rank'])
            
            # Load existing daily history or create new
            if os.path.exists(daily_history_path):
                daily_history = pd.read_csv(daily_history_path)
                
                # Check if today's data already exists
                if today in daily_history['Date'].values:
                    print(f"   Daily history already contains data for {today}, skipping archive")
                else:
                    # Append today's data
                    daily_history = pd.concat([daily_history, today_data], ignore_index=True)
                    daily_history.to_csv(daily_history_path, index=False)
                    print(f"   ✓ Archived {len(today_data)} teams for {today}")
            else:
                # Create new daily history file
                today_data.to_csv(daily_history_path, index=False)
                print(f"   ✓ Created daily history with {len(today_data)} teams for {today}")
        except Exception as e:
            print(f"   ⚠ Warning: Could not archive current data: {e}")
            print(f"   Continuing with scrape...")
    else:
        print(f"   No current data file found, skipping archive (first run)")
    print()
    
    # Step 2: Scrape current rankings from NCAA.com
    print("Step 2: Scraping current NET rankings from NCAA.com...")
    current_rankings = scrape_net_rankings()
    print()
    
    # Step 3: Load historical data
    print("Step 3: Loading historical data...")
    historical_data_path = 'ACC_Who_to_Play.xlsx'
    historical_df = load_historical_data(historical_data_path)
    print()
    
    # Step 4: Merge and update
    print("Step 4: Merging data and recalculating averages...")
    updated_df = merge_and_update(historical_df, current_rankings)
    print()
    
    # Step 5: Save output
    print("Step 5: Saving updated rankings...")
    output_path = 'net_rankings_data.csv'
    save_output(updated_df, output_path)
    print()
    
    print("✓ Complete! Current rankings updated and archived to daily history.")

if __name__ == "__main__":
    main()
