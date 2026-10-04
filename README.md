# The Wheely Unlucky Gambler

Live site: https://wheely-unlucky-gambler.netlify.app

- `index.html` – the whole app (wheels/balls, betting slip, results, predictions).
- `fixtures.json` – upcoming fixtures and final scores for the Premier League, Championship, League One and League Two. Updated automatically by Claude scheduled tasks; the site reads it straight from this repository, so it doesn't need re-publishing on Netlify when fixtures or scores change.
- `firestore.rules` – the Firebase security rules (everyone can look; only the admin can change slips and results; followers can only cast their own prediction).
- Icons, `manifest.webmanifest` and `sw.js` let the site install to a phone home screen.

## fixtures.json format

```json
{
  "updated": "2026-10-09T08:00:00Z",
  "rounds": [
    { "id": "2026-10-09", "label": "9–12 Oct", "sub": "All four leagues", "end": "2026-10-12",
      "games": [["PL", "Arsenal", "Leeds", "Sat 10 Oct", "12:30pm", 2, 0]] }
  ],
  "results": { "Burton|Huddersfield|Sat 3 Oct": [2, 1] }
}
```

Each game is `[league, home, away, day, kick-off, homeGoals, awayGoals]`; kick-off `"P"` means postponed; goals are left off until full time. `results` keeps final scores from earlier rounds so old slips still settle. Team names must match the app's 92 short names exactly.
