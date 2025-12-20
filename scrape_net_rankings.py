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
    
    # Scrape current rankings
    print("Step 1: Scraping current NET rankings...")
    current_rankings = scrape_net_rankings()
    print()
    
    # Load historical data
    print("Step 2: Loading historical data...")
    historical_data_path = 'ACC_Who_to_Play.xlsx'
    historical_df = load_historical_data(historical_data_path)
    print()
    
    # Merge and update
    print("Step 3: Merging data and recalculating averages...")
    updated_df = merge_and_update(historical_df, current_rankings)
    print()
    
    # Save output
    print("Step 4: Saving output...")
    output_path = 'net_rankings_data.csv'
    save_output(updated_df, output_path)
    print()
    
    print("✓ Complete!")

if __name__ == "__main__":
    main()
