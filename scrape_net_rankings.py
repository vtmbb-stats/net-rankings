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

def scrape_net_rankings():
    """Scrape current NET rankings from NCAA website"""
    url = "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html_content = response.text
        
    except Exception as e:
        print(f"WARNING: Network request failed ({e})")
        print("Attempting to read from cached HTML file...")
        try:
            with open('net_rankings_cache.html', 'r') as f:
                html_content = f.read()
        except:
            print("ERROR: Could not read cached file either")
            sys.exit(1)
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    
    if not table:
        print("ERROR: Could not find rankings table on page")
        sys.exit(1)
    
    # Extract data
    rows = table.find('tbody').find_all('tr')
    rankings_data = []
    
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 2:
            rank = cols[0].text.strip()
            school = cols[1].text.strip()
            rankings_data.append({'Rank': rank, 'School': school})
    
    df = pd.DataFrame(rankings_data)
    df['Rank'] = pd.to_numeric(df['Rank'], errors='coerce')
    
    print(f"Successfully scraped {len(df)} teams")
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
    
    # Update the historical dataframe with new 2025 rankings
    # First, set all existing 2025 ranks to NaN
    historical_df['2025 NET Rank'] = pd.NA
    
    # Merge based on team names
    for _, row in current_rankings_df.iterrows():
        team = row['Team']
        rank = row['2025 NET Rank']
        
        # Try to find exact match
        mask = historical_df['Team'] == team
        if mask.any():
            historical_df.loc[mask, '2025 NET Rank'] = rank
        else:
            # Try case-insensitive match
            mask = historical_df['Team'].str.lower() == team.lower()
            if mask.any():
                historical_df.loc[mask, '2025 NET Rank'] = rank
    
    # Recalculate 5-year average
    year_cols = ['2021 NET Rank', '2022 NET Rank', '2023 NET Rank', '2024 NET Rank', '2025 NET Rank']
    # Convert columns to numeric first
    for col in year_cols:
        historical_df[col] = pd.to_numeric(historical_df[col], errors='coerce')
    historical_df['Avergae 5 Year NET'] = historical_df[year_cols].mean(axis=1, skipna=True).round(1)
    
    teams_updated = historical_df['2025 NET Rank'].notna().sum()
    print(f"Updated {teams_updated} teams with 2025 rankings")
    
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
