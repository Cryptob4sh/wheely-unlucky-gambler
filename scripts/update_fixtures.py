#!/usr/bin/env python3
"""Refresh fixtures.json for The Wheely Unlucky Footy Acca.

Reads this month's and next month's fixtures and results for the four English
leagues from Sky Sports, groups them into weekend (Fri-Mon) and midweek
(Tue-Thu) rounds, and writes fixtures.json in the format the site expects:

  {updated, source, rounds:[{id,label,sub,end,games:[[lg,home,away,day,ko]]}],
   results:{"home|away|day":[hs,as]}}

Things it keeps from the existing file:
  * every result it has ever seen (saved slips settle from these),
  * any Nations League ("NL") games and rounds, which are added by hand.

Run with no arguments. Standard library only. Exit code 0 even when Sky can't
be reached for one page; if nothing at all could be read, the file is left alone.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

FILE = os.environ.get("FIXTURES_FILE", "fixtures.json")
TODAY = dt.date.fromisoformat(os.environ["TODAY"]) if os.environ.get("TODAY") else dt.datetime.now(dt.timezone.utc).date()
KEEP_PAST_DAYS = 7      # keep a round on the site for a week after it ends
LOOK_AHEAD_DAYS = 24    # how far ahead to list rounds

LEAGUES = [("PL", "premier-league", "Premier League"), ("CH", "championship", "EFL Championship"),
           ("L1", "league-1", "EFL League One"), ("L2", "league-2", "EFL League Two")]
LEAGUE_NAMES = {"PL": "Premier League", "CH": "Championship", "L1": "League One", "L2": "League Two"}

# Sky's full club names -> the short names the site uses. Anything not listed is
# used as Sky writes it (and reported in the log so it can be added here).
NAMES = {
    "Brighton and Hove Albion": "Brighton", "Coventry City": "Coventry", "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds", "Manchester City": "Man City", "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle", "Nottingham Forest": "Nottm Forest", "Tottenham Hotspur": "Tottenham",
    "Birmingham City": "Birmingham", "Blackburn Rovers": "Blackburn", "Bolton Wanderers": "Bolton",
    "Cardiff City": "Cardiff", "Charlton Athletic": "Charlton", "Derby County": "Derby", "Lincoln City": "Lincoln",
    "Norwich City": "Norwich", "Preston North End": "Preston", "Queens Park Rangers": "QPR",
    "Sheffield United": "Sheff Utd", "Stoke City": "Stoke", "Swansea City": "Swansea",
    "West Bromwich Albion": "West Brom", "West Ham United": "West Ham", "Wolverhampton Wanderers": "Wolves",
    "Bradford City": "Bradford", "Burton Albion": "Burton", "Cambridge United": "Cambridge Utd",
    "Doncaster Rovers": "Doncaster", "Huddersfield Town": "Huddersfield", "Leicester City": "Leicester",
    "Luton Town": "Luton", "Mansfield Town": "Mansfield", "Milton Keynes Dons": "MK Dons",
    "Oxford United": "Oxford Utd", "Peterborough United": "Peterborough", "Plymouth Argyle": "Plymouth",
    "Sheffield Wednesday": "Sheff Wed", "Stockport County": "Stockport", "Wigan Athletic": "Wigan",
    "Wycombe Wanderers": "Wycombe", "Accrington Stanley": "Accrington", "Cheltenham Town": "Cheltenham",
    "Colchester United": "Colchester", "Crawley Town": "Crawley", "Crewe Alexandra": "Crewe",
    "Exeter City": "Exeter", "Fleetwood Town": "Fleetwood", "Grimsby Town": "Grimsby",
    "Newport County AFC": "Newport", "Newport County": "Newport", "Northampton Town": "Northampton",
    "Oldham Athletic": "Oldham", "Rotherham United": "Rotherham", "Salford City": "Salford",
    "Shrewsbury Town": "Shrewsbury", "Swindon Town": "Swindon", "Tranmere Rovers": "Tranmere",
}
# The 92 clubs as the site names them (2026/27).
CLUBS = set(["Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Chelsea", "Coventry", "Crystal Palace", "Everton", "Fulham", "Hull City", "Ipswich", "Leeds", "Liverpool", "Man City", "Man Utd", "Newcastle", "Nottm Forest", "Sunderland", "Tottenham", "Birmingham", "Blackburn", "Bolton", "Bristol City", "Burnley", "Cardiff", "Charlton", "Derby", "Lincoln", "Middlesbrough", "Millwall", "Norwich", "Portsmouth", "Preston", "QPR", "Sheff Utd", "Southampton", "Stoke", "Swansea", "Watford", "West Brom", "West Ham", "Wolves", "Wrexham", "AFC Wimbledon", "Barnsley", "Blackpool", "Bradford", "Bromley", "Burton", "Cambridge Utd", "Doncaster", "Huddersfield", "Leicester", "Leyton Orient", "Luton", "Mansfield", "MK Dons", "Notts County", "Oxford Utd", "Peterborough", "Plymouth", "Reading", "Sheff Wed", "Stevenage", "Stockport", "Wigan", "Wycombe", "Accrington", "Barnet", "Bristol Rovers", "Cheltenham", "Chesterfield", "Colchester", "Crawley", "Crewe", "Exeter", "Fleetwood", "Gillingham", "Grimsby", "Newport", "Northampton", "Oldham", "Port Vale", "Rochdale", "Rotherham", "Salford", "Shrewsbury", "Swindon", "Tranmere", "Walsall", "York City"])
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
unknown = set()


def log(*a):
    print(*a, file=sys.stderr)


def short(name):
    if name in NAMES:
        return NAMES[name]
    if name not in CLUBS:
        unknown.add(name)
    return name


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def parse_matches(page, year, month):
    """Every match object embedded in a Sky scores-fixtures page."""
    out = []
    for m in re.finditer(r'data-state="(\{&quot;id&quot;[^"]*)"', page):
        try:
            o = json.loads(html.unescape(m.group(1)))
        except ValueError:
            continue
        if not isinstance(o, dict) or not o.get("teams") or not o.get("start"):
            continue
        dm = re.match(r"\w+\s+(\d+)\w*\s+(\w+)", o["start"].get("date") or "")
        if not dm or dm.group(2).lower() not in MONTHS:
            continue
        mon = MONTHS[dm.group(2).lower()]
        yr = year + (1 if month == 12 and mon == 1 else 0) - (1 if month == 1 and mon == 12 else 0)
        o["_date"] = dt.date(yr, mon, int(dm.group(1)))
        out.append(o)
    return out


def ko_text(o):
    t = (o["start"].get("time12hr") or "").replace(".", ":").lower()
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", t)
    if not m:
        t24 = o["start"].get("time") or ""
        m2 = re.match(r"(\d{1,2}):(\d{2})", t24)
        if not m2:
            return "TBC"
        h, mi = int(m2.group(1)), m2.group(2)
        m = (str((h % 12) or 12), mi, "pm" if h >= 12 else "am")
        return m[0] + ("" if m[1] == "00" else ":" + m[1]) + m[2]
    return str(int(m.group(1))) + ("" if m.group(2) == "00" else ":" + m.group(2)) + m.group(3)


def day_text(d):
    return f"{DAYS[d.weekday()]} {d.day} {d.strftime('%b')}"


def block_start(d):
    """Weekend rounds run Fri-Mon, midweek rounds Tue-Thu."""
    wd = d.weekday()  # Mon=0
    if wd in (4, 5, 6):
        return d - dt.timedelta(days=wd - 4), "weekend"
    if wd == 0:
        return d - dt.timedelta(days=3), "weekend"
    return d - dt.timedelta(days=wd - 1), "midweek"


def label(a, b):
    if a == b:
        return f"{a.day} {a.strftime('%b')}"
    if a.month == b.month:
        return f"{a.day}–{b.day} {b.strftime('%b')}"
    return f"{a.day} {a.strftime('%b')}–{b.day} {b.strftime('%b')}"


def main():
    try:
        old = json.load(open(FILE, encoding="utf-8"))
    except (OSError, ValueError):
        old = {"rounds": [], "results": {}}
    results = dict(old.get("results") or {})

    months = [(TODAY.year, TODAY.month)]
    nxt = (TODAY.replace(day=28) + dt.timedelta(days=5))
    months.append((nxt.year, nxt.month))
    prev = TODAY.replace(day=1) - dt.timedelta(days=1)
    if TODAY.day <= KEEP_PAST_DAYS:
        months.insert(0, (prev.year, prev.month))

    games = {}   # key -> game dict (dedupes the same match seen on two pages)
    pages_ok = 0
    for lg, slug, comp in LEAGUES:
        for (y, mo) in months:
            url = f"https://www.skysports.com/{slug}-scores-fixtures/{y}-{mo:02d}-01"
            try:
                page = fetch(url)
            except Exception as e:  # noqa: BLE001
                log("Couldn't read", url, e)
                continue
            found = parse_matches(page, y, mo)
            log(f"{url}: {len(found)} matches")
            if found:
                pages_ok += 1
            for o in found:
                cname = ((o.get("competition") or {}).get("name") or {}).get("full") or comp
                if cname != comp:
                    continue
                h, a = short(o["teams"]["home"]["name"]["full"]), short(o["teams"]["away"]["name"]["full"])
                d = o["_date"]
                g = {"lg": lg, "h": h, "a": a, "date": d, "day": day_text(d),
                     "ko": "P" if (o.get("isPostponed") or o.get("isCancelled") or o.get("isAbandoned")) else ko_text(o)}
                if o.get("isResult") and o.get("status") in ("FT", "AET", "Pens", "FT-Pens"):
                    hs, as_ = o["teams"]["home"]["score"].get("current"), o["teams"]["away"]["score"].get("current")
                    if hs is not None and as_ is not None:
                        g["score"] = [int(hs), int(as_)]
                        results[f"{h}|{a}|{g['day']}"] = [int(hs), int(as_)]
                games[f"{h}|{a}|{d.isoformat()}"] = g

    if not pages_ok:
        log("Nothing could be read from Sky Sports, so fixtures.json was left as it was.")
        return 0

    # Build rounds from the club games.
    blocks = {}
    for g in games.values():
        start, kind = block_start(g["date"])
        blocks.setdefault(start.isoformat(), {"start": start, "kind": kind, "games": []})["games"].append(g)
    lo, hi = TODAY - dt.timedelta(days=KEEP_PAST_DAYS), TODAY + dt.timedelta(days=LOOK_AHEAD_DAYS)
    rounds = []
    for key in sorted(blocks):
        b = blocks[key]
        gs = sorted(b["games"], key=lambda g: (g["date"], "PL CH L1 L2".split().index(g["lg"]), g["ko"], g["h"]))
        first, last = gs[0]["date"], gs[-1]["date"]
        if last < lo or first > hi:
            continue
        lgs = [l for l in ("PL", "CH", "L1", "L2") if any(g["lg"] == l for g in gs)]
        sub = "All four leagues" if len(lgs) == 4 else ", ".join(LEAGUE_NAMES[l] for l in lgs)
        if b["kind"] == "midweek":
            sub = "Midweek: " + sub
        rounds.append({"id": first.isoformat(), "label": label(first, last), "sub": sub, "end": last.isoformat(),
                       "games": [[g["lg"], g["h"], g["a"], g["day"], g["ko"]] + (g["score"] if "score" in g else [])
                                 for g in gs]})

    # Keep hand-added Nations League games: merge into a round with the same id, or keep their own round.
    by_id = {r["id"]: r for r in rounds}
    for r in old.get("rounds") or []:
        nl = [g for g in (r.get("games") or []) if g and g[0] == "NL"]
        if not nl or (r.get("end") or r["id"]) < lo.isoformat():
            continue
        if r["id"] in by_id:
            by_id[r["id"]]["games"] = nl + by_id[r["id"]]["games"]
        else:
            keep = dict(r)
            keep["games"] = nl
            rounds.append(keep)
    rounds.sort(key=lambda r: r["id"])

    out = {"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "Sky Sports (updated automatically)", "rounds": rounds, "results": results}
    if unknown:
        log("Names not in the list (used as Sky writes them):", ", ".join(sorted(unknown)))
    before = json.dumps({k: old.get(k) for k in ("rounds", "results")}, sort_keys=True, ensure_ascii=False)
    after = json.dumps({k: out[k] for k in ("rounds", "results")}, sort_keys=True, ensure_ascii=False)
    if before == after:
        log("No changes.")
        return 0
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log(f"Wrote {FILE}: {len(rounds)} rounds, {sum(len(r['games']) for r in rounds)} games, {len(results)} results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
