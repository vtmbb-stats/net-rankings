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

1. Go to [netlify.com](https://netlify.com) and sign in
2. Click "Add new site" → "Import an existing project"
3. Choose GitHub and select your repository
4. **Build settings:**
   - Build command: **(leave empty)**
   - Publish directory: `.`
5. Click "Deploy site"
6. Done! Deploys in ~30 seconds

**Important:** Don't add a build command. Netlify should only deploy the static files. Python scraping happens in GitHub Actions.

**You don't need Netlify API tokens** - Netlify automatically redeploys when it sees changes pushed to your GitHub repo.

### 5. Test the Workflow

The workflow will run automatically daily at 8 AM EST. To test it manually:

1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select "Update NET Rankings" workflow
4. Click "Run workflow" → "Run workflow"
5. Wait ~30 seconds for completion
6. Netlify will auto-redeploy (~30 seconds more)
7. Check your live site!

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

**Simple & Fast Architecture:**

1. **GitHub Actions** runs the Python scraper daily at 8 AM EST
   - Fetches current NET rankings from NCAA.com
   - Merges with historical data
   - Updates `net_rankings_data.csv`
   - Commits and pushes to GitHub

2. **Netlify** detects the push and redeploys automatically
   - Only deploys static files (HTML, CSS, CSV)
   - No Python installation needed
   - **Deploys in 10-30 seconds** ⚡

This separation keeps deployments fast and reliable. Python runs where it should (GitHub Actions), and Netlify does what it does best (instant static file hosting).

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
