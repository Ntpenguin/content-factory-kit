"""Station 8, learn: results in, hook scoreboard out.

    python -m factory.learn <brand> <batch> [results.csv ...]
    python -m factory.learn --selfcheck

With no file named it reads every runs/<brand>/<batch>/results/*.csv that is not a sample and writes
scoreboard.md in the batch folder. A sample file (its name starts with SAMPLE, or it has a "sample"
column saying yes) is read only when named, never mixed with real files, and writes SAMPLE-scoreboard.md.

A results file has one line per piece (per platform and day if you like). Columns:
    piece        the piece id from the review page, e.g. H01-M3-A or H01-M3-A-video. An ad name that
                 starts with it works too ("H01-M3-A-video 9x16 feed").
    platform, date                      optional
    spend, impressions                  impressions is required; spend is blank or 0 for an organic post
    views_3s, thruplays                 videos only; leave blank for a still
    clicks, leads                       blank counts as 0
    fit_leads                           how many of the leads fit the customer profile; filled in by hand
Meta's export headers are accepted for the same columns (NAMES below).

It also reads decisions.json (the review page's Export) when it is saved in the batch folder.
The scoreboard ranks; it does not decide. No kill or scale threshold is on file (knowledge/platforms.md).
"""
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

from factory.brand import ROOT, BrandError, load_brand

MIN_IMPRESSIONS = 1000      # ponytail: a placeholder so 40 impressions never outrank 4,000; no threshold is on file. Set it from the first real runs.
FEW_LEADS = 5               # ponytail: also a placeholder. Under this many leads a cost per lead is mostly luck, and the line says so.
PIECE = re.compile(r"(H\d+)-(M\d+)-([A-Z])(-video)?(?![A-Za-z0-9-])")
NUMBERS = ("spend", "impressions", "views_3s", "thruplays", "clicks", "leads", "fit_leads")
# ponytail: Meta's header names are written from memory, not checked against a real export. Add the real ones here when the first export arrives.
NAMES = {"piece": ("piece", "ad name", "ad"), "platform": ("platform",), "date": ("date", "day", "reporting starts"),
         "spend": ("spend", "amount spent (usd)", "amount spent"), "impressions": ("impressions",),
         "views_3s": ("views_3s", "3-second video plays"), "thruplays": ("thruplays",),
         "clicks": ("clicks", "link clicks"), "leads": ("leads", "results"), "fit_leads": ("fit_leads",), "sample": ("sample",)}


def read(path):
    """(rows, is_sample) for one results file. Every fault names the file and the line."""
    path = Path(path)
    if not path.is_file():
        raise BrandError(f"results file {path} is not a file")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        col = {ours: next((h for h in reader.fieldnames or [] if h and h.strip().lower() in theirs), None) for ours, theirs in NAMES.items()}
        raw = list(reader)
    for need in ("piece", "impressions"):
        if not col[need]:
            raise BrandError(f"{path.name}: no \"{need}\" column (accepted names: {', '.join(NAMES[need])})")
    if not raw:
        raise BrandError(f"{path.name}: no result lines")
    rows = []
    for n, line in enumerate(raw, 2):
        get = lambda k: (line.get(col[k]) or "").strip() if col[k] else ""
        where = f"{path.name} line {n}"
        m = PIECE.match(get("piece"))
        if not m:
            raise BrandError(f"{where}: \"{get('piece')}\" does not start with a piece id such as H01-M3-A or H01-M3-A-video")
        row = {"piece": m.group(0), "platform": get("platform") or "not given", "date": get("date"), "where": where, "sample": get("sample").lower() in ("yes", "y", "true", "1")}
        for k in NUMBERS:
            text = re.sub(r"[$,\s]", "", get(k))
            try:
                row[k] = float(text) if text else None
            except ValueError:
                raise BrandError(f"{where}: {k} \"{get(k)}\" is not a number")
            if row[k] is not None and row[k] < 0:
                raise BrandError(f"{where}: {k} is below zero")
        if row["impressions"] is None:
            raise BrandError(f"{where}: impressions is blank")
        for small, big in (("views_3s", "impressions"), ("thruplays", "views_3s"), ("clicks", "impressions"), ("leads", "impressions"), ("fit_leads", "leads")):
            if (row[small] or 0) > (row[big] or 0):
                raise BrandError(f"{where}: {small} ({row[small]:g}) is more than {big} ({row[big] or 0:g})")
        rows.append(row)
    return rows, path.name.upper().startswith("SAMPLE") or any(r["sample"] for r in rows)


def total(rows):
    """One scoreboard line from result rows. A rate with nothing under it is None, never 0."""
    s = lambda k, rs=rows: sum(r[k] or 0 for r in rs)
    rate = lambda a, b: a / b if b else None
    video = [r for r in rows if r["views_3s"] is not None]          # a still has no 3-second view; it stays out of the hook rate
    judged = [r for r in rows if r["fit_leads"] is not None]
    return {"pieces": len({r["piece"] for r in rows}), "spend": s("spend"), "impressions": s("impressions"),
            "hook_rate": rate(s("views_3s", video), s("impressions", video)), "hold_rate": rate(s("thruplays", video), s("views_3s", video)),
            "ctr": rate(s("clicks"), s("impressions")), "leads": s("leads"), "fit_leads": s("fit_leads") if judged else None,
            "cpl": rate(s("spend"), s("leads")) if s("spend") else None,
            "cpfl": rate(s("spend"), s("fit_leads")) if s("spend") and judged else None}


def order(t):
    """Best first: enough impressions, then the cheapest fit lead (or lead, when fit is not filled in), then the most leads per impression."""
    cost = t["cpfl"] if t["cpfl"] is not None else t["cpl"] if t["cpl"] is not None and t["fit_leads"] is None else float("inf")
    return (t["impressions"] < MIN_IMPRESSIONS, cost, -(t["leads"] / t["impressions"] if t["impressions"] else 0), -(t["ctr"] or 0))


def note(t):
    if t["impressions"] < MIN_IMPRESSIONS:
        return f"too early (under {MIN_IMPRESSIONS:,} impressions)"
    if not t["leads"]:
        return "no leads yet"
    fit = "fit leads not filled in" if t["fit_leads"] is None else "no lead fits the profile" if not t["fit_leads"] else ""
    few = f"only {t['leads']:.0f} lead{'s' if t['leads'] > 1 else ''}: could be luck" if t["leads"] < FEW_LEADS else ""
    return "; ".join(x for x in (fit, few) if x)


money = lambda v: "-" if v is None else f"${v:,.2f}"
pct = lambda v: "-" if v is None else f"{v:.1%}"
num = lambda v: "-" if v is None else f"{v:,.0f}"
COLS = [("Pieces", "pieces", num), ("Spend", "spend", money), ("Impressions", "impressions", num), ("Hook rate", "hook_rate", pct), ("Hold rate", "hold_rate", pct),
        ("Click rate", "ctr", pct), ("Leads", "leads", num), ("Fit leads", "fit_leads", num), ("Cost per lead", "cpl", money), ("Cost per fit lead", "cpfl", money)]


def table(rows, key, head):
    """A markdown table, one line per value of key(row), best first."""
    groups = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    out = [f"| # | {head} | " + " | ".join(c[0] for c in COLS) + " | Read |", "|" + "---|" * (len(COLS) + 3)]
    for n, (k, t) in enumerate(sorted(((k, total(g)) for k, g in groups.items()), key=lambda kt: (order(kt[1]), kt[0])), 1):
        out.append(f"| {n} | {str(k).replace('|', '/')} | " + " | ".join(f(t[name]) for _, name, f in COLS) + f" | {note(t)} |")
    return out


def run(slug, batch, files=()):
    brand = load_brand(slug)
    folder = ROOT / "runs" / slug / batch
    if not (folder / "gate.json").is_file():
        raise BrandError(f"{folder / 'gate.json'} is missing: results belong to pieces that went through the gate")
    pieces = json.loads((folder / "gate.json").read_text(encoding="utf-8"))["pieces"]
    hooks = {h["id"]: h for h in json.loads((folder / "hooks.json").read_text(encoding="utf-8"))["hooks"]}
    files = [Path(f) for f in files] or sorted(p for p in (folder / "results").glob("*.csv") if not p.name.upper().startswith("SAMPLE"))
    if not files:
        raise BrandError(f"no results yet: put a results file in {folder / 'results'} (columns are listed at the top of factory/learn.py)")
    read_files = [(f, *read(f)) for f in files]
    if len({sample for _, _, sample in read_files}) > 1:
        raise BrandError("sample files and real files are never mixed: " + ", ".join(f"{f.name} ({'sample' if s else 'real'})" for f, _, s in read_files))
    sample = read_files[0][2]
    rows, seen, warnings = [], {}, []
    for _, file_rows, _ in read_files:
        for r in file_rows:
            if r["piece"] not in pieces:
                raise BrandError(f"{r['where']}: piece {r['piece']} is not in this batch's gate.json")
            same = (r["piece"], r["platform"], r["date"])
            if same in seen:
                raise BrandError(f"{r['where']}: the same piece, platform and date as {seen[same]} (a file imported twice?)")
            seen[same] = r["where"]
            hid, body, cta = r["piece"].split("-")[:3]
            hook = hooks[hid]
            r.update(hook=f"{hid} ({hook['type']}, {hook['customer']}): {hook['onscreen']}", type=hook["type"], customer=hook["customer"],
                     body=body, cta=cta, format=pieces[r["piece"]].get("lane") or "static")
            rows.append(r)
    decisions = {}
    if (folder / "decisions.json").is_file():
        d = json.loads((folder / "decisions.json").read_text(encoding="utf-8"))
        if d.get("batch") != f"{slug}:{batch}":
            raise BrandError(f"decisions.json is for {d.get('batch')!r}, not {slug}:{batch}")
        decisions = {k: v for k, v in d.get("decisions", {}).items() if v.get("decision") or (v.get("comment") or "").strip()}
    for pid in sorted({r["piece"] for r in rows}):
        if pieces[pid].get("problems"):
            warnings.append(f"{pid} has results although it failed the gate")
        if decisions.get(pid, {}).get("decision") == "reject":
            warnings.append(f"{pid} has results although it was rejected on the review page")

    tag = " (SAMPLE)" if sample else ""
    out = [f"# {'SAMPLE scoreboard' if sample else 'Scoreboard'}: {brand['brand']['name']}, {batch}", ""]
    if sample:
        out += ["**SAMPLE DATA. Every number below is made up to prove the import and the ranking. Nothing was posted or run; these are not results.**", ""]
    days = sorted({r["date"] for r in rows if r["date"]})
    out += [f"From {', '.join(f.name for f in files)}: {len(rows)} lines, {len({r['piece'] for r in rows})} pieces, {len({r['hook'] for r in rows})} hooks"
            + (f", {days[0]} to {days[-1]}" if days else "") + ".", "",
            f"Order: hooks with at least {MIN_IMPRESSIONS:,} impressions first, then the cheapest lead that fits the customer profile, then the most leads per impression. "
            "Hook rate is 3-second views over impressions and hold rate is ThruPlays over 3-second views, videos only; read them together. "
            f"Views are not sales. This ranks; it does not decide: no kill or scale threshold is on file, and under {FEW_LEADS} leads a cost per lead is mostly luck.", ""]
    out += [f"- WARNING: {w}" for w in warnings] + ([""] if warnings else [])
    out += [f"## Hooks{tag}", ""] + table(rows, lambda r: r["hook"], "Hook") + [""]
    for head, key in (("Hook type", "type"), ("Customer", "customer"), ("Body", "body"), ("Call to action", "cta"), ("Format", "format"), ("Platform", "platform"), ("Piece", "piece")):
        out += [f"## By {head.lower()}{tag}", ""] + table(rows, lambda r, key=key: r[key], head) + [""]
    if decisions:
        said = {}
        for pid, v in decisions.items():
            if (v.get("comment") or "").strip():
                said.setdefault(re.sub(r"\W+", " ", v["comment"].lower()).strip(), []).append(pid)
        out += ["## Review decisions", "", "| Piece | Decision | Comment |", "|---|---|---|"]
        out += [f"| {pid} | {v.get('decision') or '-'} | {(v.get('comment') or '').strip().replace('|', '/')} |" for pid, v in sorted(decisions.items())]
        twice = [f"- \"{c}\" ({', '.join(pids)})" for c, pids in said.items() if len(pids) > 1]
        # ponytail: only the same words count as the same comment; read the comments yourself for the same point made in other words.
        out += ["", "Comments made on more than one piece (make each a rule in the brand's facts or the gate):"] + twice if twice else []
        out += [""]
    dst = folder / ("SAMPLE-scoreboard.md" if sample else "scoreboard.md")
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"{dst} ({len(rows)} lines, {len({r['hook'] for r in rows})} hooks" + (", SAMPLE DATA" if sample else "") + (f", {len(warnings)} warnings" if warnings else "") + ")")
    return dst


def selfcheck():
    with tempfile.TemporaryDirectory() as d:
        def bad(text, name="r.csv"):
            (Path(d) / name).write_text(text, encoding="utf-8")
            try:
                return read(Path(d) / name)
            except BrandError as err:
                return str(err)
        head = "piece,platform,date,spend,impressions,views_3s,thruplays,clicks,leads,fit_leads\n"
        rows, sample = bad(head + "H01-M3-A-video 9x16 feed,meta,2026-11-20,\"$1,250.50\",4000,1200,300,80,4,1\nH01-M3-A,meta,2026-11-20,10,1000,,,5,1,\n")
        assert not sample and rows[0]["piece"] == "H01-M3-A-video" and rows[0]["spend"] == 1250.5 and rows[1]["views_3s"] is None
        t = total(rows)
        assert (t["pieces"], t["impressions"], t["leads"], t["fit_leads"]) == (2, 5000, 5, 1)
        assert t["hook_rate"] == 0.3 and t["hold_rate"] == 0.25, t                  # the still's 1,000 impressions stay out of the hook rate
        assert round(t["cpl"], 2) == 252.1 and t["cpfl"] == 1260.5
        organic = total([dict(rows[1], spend=None)])
        assert organic["cpl"] is None and organic["fit_leads"] is None and organic["hook_rate"] is None    # no spend, no cost per lead; never $0.00
        assert bad(head + "H01-M3-A,meta,,1,100,,,,,\n", "SAMPLE-x.csv")[1] and bad("piece,impressions,sample\nH01-M3-A,100,yes\n")[1]
        assert bad("Ad name,Amount spent (USD),Impressions,Link clicks,Results\nH02-M1-B,5,100,3,1\n")[0][0]["clicks"] == 3     # Meta's headers
        assert "no \"impressions\" column" in bad("piece,spend\nH01-M3-A,1\n")
        assert "no result lines" in bad(head)
        assert "line 2: \"summer ad\" does not start with a piece id" in bad(head + "summer ad,meta,,1,100,,,,,\n")
        assert "does not start with a piece id" in bad(head + "H01-M3-AB,meta,,1,100,,,,,\n")
        assert "spend \"abc\" is not a number" in bad(head + "H01-M3-A,meta,,abc,100,,,,,\n")
        assert "impressions is blank" in bad(head + "H01-M3-A,meta,,1,,,,,,\n")
        assert "below zero" in bad(head + "H01-M3-A,meta,,-1,100,,,,,\n")
        assert "views_3s (200) is more than impressions (100)" in bad(head + "H01-M3-A-video,meta,,1,100,200,,,,\n")
        assert "fit_leads (3) is more than leads (2)" in bad(head + "H01-M3-A,meta,,1,100,,,5,2,3\n")
        assert bad(head + "H01-M3-A-video_9x16,meta,,1,100,,,,,\n")[0][0]["piece"] == "H01-M3-A-video"        # an underscore after the id is fine
        try:
            read(Path(d) / "nothing.csv")
            raise AssertionError("a missing file was read")
        except BrandError as err:
            assert "is not a file" in str(err)
    line = lambda **k: dict({"piece": "H01-M3-A", "spend": 100.0, "impressions": 5000.0, "views_3s": None, "thruplays": None, "clicks": 50.0, "leads": 4.0, "fit_leads": 2.0}, **k)
    cheap, dear, early, none = total([line()]), total([line(fit_leads=1.0)]), total([line(impressions=400.0, fit_leads=4.0)]), total([line(leads=0.0, fit_leads=0.0)])
    assert sorted([none, early, dear, cheap], key=order) == [cheap, dear, none, early]     # 400 impressions never outrank 5,000
    assert note(early).startswith("too early") and note(none) == "no leads yet" and note(total([line(leads=9.0)])) == ""
    assert note(cheap) == "only 4 leads: could be luck" and note(total([line(leads=1.0, fit_leads=None)])) == "fit leads not filled in; only 1 lead: could be luck"
    print("learn selfcheck passed")


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if args == ["--selfcheck"]:
            selfcheck()
        elif len(args) >= 2:
            run(args[0], args[1], args[2:])
        else:
            sys.exit("usage: python -m factory.learn <brand> <batch> [results.csv ...]  |  --selfcheck")
    except BrandError as err:
        sys.exit(f"error: {err}")
