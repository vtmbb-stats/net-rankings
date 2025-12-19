# NET Rankings Dashboard

Automated NCAA Men's Basketball NET Rankings tracker with historical data (2021-2025).

## Features

- **Daily Updates**: Automatically scrapes NCAA NET rankings every day at 8 AM EST
- **Historical Tracking**: Shows rankings from 2021-2025 with 5-year averages
- **Interactive Filtering**: Filter by Power Conference vs Mid-Major
- **Search**: Find teams quickly by name
- **Sorting**: Click any column header to sort
- **Color Coding**: Visual indicators for ranking tiers (Elite, Great, Good, Okay, Poor)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd net-rankings-dashboard
```

### 2. Add Your Historical Data

Replace `ACC_Who_to_Play.xlsx` with your own historical rankings file, or use the provided template.

### 3. Set up GitHub Repository

1. Create a new repository on GitHub
2. Push your code:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

### 4. Set up Netlify

#### Option A: Connect via Netlify Dashboard (Recommended)
1. Go to [netlify.com](https://netlify.com) and sign in
2. Click "Add new site" → "Import an existing project"
3. Choose GitHub and select your repository
4. Deploy settings:
   - Build command: (leave empty)
   - Publish directory: `.` (root)
5. Click "Deploy site"
6. Note your Site ID (found in Site settings → General → Site details → API ID)

#### Option B: Use Netlify CLI
```bash
npm install -g netlify-cli
netlify login
netlify init
```

### 5. Configure GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

1. **NETLIFY_AUTH_TOKEN**
   - Get from: https://app.netlify.com/user/applications#personal-access-tokens
   - Click "New access token"
   - Give it a name and copy the token

2. **NETLIFY_SITE_ID**
   - Get from: Netlify Dashboard → Site settings → Site information → API ID

### 6. Test the Workflow

The workflow will run automatically daily at 8 AM EST. To test it manually:

1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select "Update NET Rankings" workflow
4. Click "Run workflow" → "Run workflow"

## Local Development

### Run the scraper locally:

```bash
python3 scrape_net_rankings.py
```

### View the site locally:

```bash
# Simple HTTP server
python3 -m http.server 8000

# Or use Node.js
npx serve .
```

Then open http://localhost:8000 in your browser.

## File Structure

```
.
├── scrape_net_rankings.py      # Python scraper script
├── ACC_Who_to_Play.xlsx        # Historical data (your file)
├── net_rankings_data.csv       # Generated data file
├── index.html                  # Main dashboard page
├── .github/
│   └── workflows/
│       └── update-rankings.yml # GitHub Actions workflow
└── README.md
```

## How It Works

1. **GitHub Actions** runs the scraper daily
2. **Python script** fetches current NET rankings from NCAA.com
3. **Data merge** combines with your historical Excel data
4. **CSV generation** creates updated data file
5. **Auto-commit** pushes changes to GitHub
6. **Netlify deployment** automatically updates the live site

## Troubleshooting

### Python version issues on Netlify?
The project uses Python 3.11 (specified in `runtime.txt`). If you see build errors about pandas compilation:
- Make sure `runtime.txt` exists in your repository root
- Verify it contains exactly: `python-3.11`
- Don't use Python 3.14 - pandas doesn't have prebuilt wheels for it yet

### Scraper not updating?
- Check GitHub Actions logs for errors
- Verify NCAA.com hasn't changed their page structure
- Make sure secrets are configured correctly

### Netlify deploy fails?
- Verify NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID are correct
- Check Netlify build logs
- Ensure the repository is connected to Netlify

### Data not showing on site?
- Check that `net_rankings_data.csv` exists
- Open browser console (F12) for JavaScript errors
- Verify CSV format matches expected structure

## Customization

### Change update schedule:
Edit `.github/workflows/update-rankings.yml`:
```yaml
schedule:
  - cron: '0 13 * * *'  # Change time here (UTC)
```

### Add more color tiers:
Edit the `getRankColorClass()` function in `index.html`

### Modify team classification:
Update the historical data Excel file's "Mid Major" column

## License

MIT License - Feel free to use and modify!

## Credits

- NCAA data from NCAA.com
- Built with vanilla JavaScript (no frameworks needed!)
- Automated with GitHub Actions and Netlify
