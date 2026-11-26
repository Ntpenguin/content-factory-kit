"""Station 4: check a batch's hooks, then write the hook sheet and the test matrix.

    python -m factory.hooks <brand> <batch>     check runs/<brand>/<batch>/hooks.json; write hook-sheet.md, matrix.csv
    python -m factory.hooks --selfcheck

A batch folder holds hooks.json (bodies and hooks) and evidence.md (E ids). Nothing is written
unless every hook passes.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from factory.brand import ROOT, BrandError, load_brand
from factory.claims import check_copy
from factory.vendor.instagram_agent import hookscore

# Awareness level each hook type is written for (knowledge/hooks.md section 1, source S1).
AWARENESS = {"curiosity": "Unaware", "pain": "Problem-aware", "promise": "Solution-aware",
             "proof": "Product-aware", "offer": "Most aware"}
EVIDENCE = re.compile(r"^- \*\*(E\d+)\*\* \[(measured|claim|guess|stat)\] (.+) — source: (\S.*)$")
MAX_ONSCREEN = 7    # "under 8 words in the first second" (Nate's plan)
MAX_SPOKEN = 20     # about seven seconds at a talking pace; the hook is the first line, not the script
WAVE = (3, 6)       # distinct concepts in a first test on a small budget (knowledge/platforms.md, S11)


def word_count(text):
    return sum(1 for w in text.split() if re.search(r"\w", w))


def load_evidence(path):
    if not path.is_file():
        raise BrandError(f"{path} is missing. A batch needs evidence.md before hooks can be checked")
    known = set(re.findall(r"^\| (S\d+) \|", (ROOT / "knowledge" / "sources.md").read_text(encoding="utf-8"), re.M))
    out, section = {}, ""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip().lower()
        if section != "evidence" or not line.startswith("- **"):
            continue
        m = EVIDENCE.match(line)
        if not m:
            raise BrandError(f"{path}:{n}: evidence line needs an id, a grade and a source. Got: {line[:90]}")
        bad = [s for s in re.findall(r"\bS\d+\b", m[4]) if s not in known]
        if bad:
            raise BrandError(f"{path}:{n}: {m[1]} cites {bad}, not in knowledge/sources.md")
        out[m[1]] = {"grade": m[2], "text": m[3], "source": m[4]}
    return out


def with_stats(brand, evidence):
    """A copy of the brand whose facts also hold each [stat] evidence line under its E id: a figure a named third party
    published, quoted from a page this session read. Copy that cites the E id may use that line's numbers and words;
    claims about the brand itself still come only from facts.md (Nate, 2026-11-19: "an insane [business fact] to hook the viewer")."""
    stats = {e: {"text": v["text"], "status": "stat, source: " + v["source"]} for e, v in evidence.items() if v["grade"] == "stat"}
    return {**brand, "facts": {**brand["facts"], **stats}}


def check_hooks(data, brand, evidence):
    """Return {hook id: [problems]} for the hooks that fail, plus batch-level problems under '-'."""
    bad = {}
    add = lambda k, msg: bad.setdefault(k, []).append(msg)
    bodies, ctas = data.get("bodies", {}), {c["id"] for c in brand["brand"]["ctas"]}
    callouts = set(brand["brand"].get("audience_callouts", [])) | {"all"}
    for bid, body in bodies.items():
        for f in body.get("facts", []):
            if f not in brand["facts"]:
                add("-", f"body {bid} cites {f}, which is not in facts.md")
    seen_id, seen_line = set(), {}
    for i, h in enumerate(data.get("hooks", []), 1):
        hid = h.get("id") or f"(hook {i}, no id)"
        missing = [k for k in ("id", "type", "customer", "spoken", "onscreen", "evidence", "facts", "bodies") if k not in h]
        if missing:
            add(hid, f"missing {', '.join(missing)}")
            continue
        if hid in seen_id:
            add(hid, "id is used twice")
        seen_id.add(hid)
        if h["type"] not in AWARENESS:
            add(hid, f"type '{h['type']}' is not one of {', '.join(AWARENESS)}")
        if h["customer"] not in callouts:
            add(hid, f"customer '{h['customer']}' is not one of {', '.join(sorted(callouts))}")
        if not h["evidence"]:
            add(hid, "no evidence listed")
        for e in h["evidence"]:
            if e not in evidence:
                add(hid, f"evidence {e} is not in evidence.md")
        if not h["bodies"]:
            add(hid, "no body listed")
        for b in h["bodies"]:
            if b not in bodies:
                add(hid, f"body {b} is not defined in this batch")
        n = word_count(h["onscreen"])
        if n > MAX_ONSCREEN:
            add(hid, f"on-screen text is {n} words; the limit is {MAX_ONSCREEN}")
        n = word_count(h["spoken"])
        if not 1 <= n <= MAX_SPOKEN:
            add(hid, f"spoken line is {n} words; the limit is {MAX_SPOKEN}")
        for part in ("spoken", "onscreen"):
            for p in check_copy(h[part], h["facts"], brand):
                add(hid, f"{part}: {p}")
        if ("stat" in h) != ("source" in h):
            add(hid, "a hook with a big figure needs both \"stat\" (the figure) and \"source\" (who published it)")
        for part in ("stat", "source"):
            if part in h:
                stats = [f for f in h["facts"] if evidence.get(f, {}).get("grade") == "stat"]
                if not stats:
                    add(hid, f"{part}: a big figure must cite a [stat] line of evidence.md in \"facts\"")
                for p in check_copy(h[part], stats, brand):
                    add(hid, f"{part}: {p}")
        key = re.sub(r"\W+", " ", h["spoken"].lower()).strip()
        if key in seen_line:
            add(hid, f"same spoken line as {seen_line[key]}")
        seen_line[key] = hid
        if "test" in h:
            b, _, c = h["test"].partition("-")
            if b not in h["bodies"] or c not in ctas:
                add(hid, f"first test '{h['test']}' must be one of its bodies and a call to action ({', '.join(sorted(ctas))})")
    wave = sum("test" in h for h in data.get("hooks", []))
    if not WAVE[0] <= wave <= WAVE[1]:
        add("-", f"{wave} hooks are marked for the first test; it should be {WAVE[0]} to {WAVE[1]}")
    return bad


def lint(text):
    """Advisory notes from the Instagram Agent Skill's scorer: (overall verdict, notes to show).

    Only its length and weak-opener checks are shown per hook. Its "stakes" and "specificity"
    checks match a creator's word list ("2 AM, a pipe just burst" scores as nothing at stake),
    so the overall score is counted once in the sheet's header and ranks nothing.
    """
    results, _, verdict, flags = hookscore.run(text)
    notes = [f"{word_count(text)} words"]
    m = re.search(r'weak opener "[^"]+"', results["FRONTLOAD"][1])
    if m:
        notes.append(m[0])
    return verdict, notes + flags


def write_sheet(folder, data, brand, evidence):
    b, hooks = brand["brand"], data["hooks"]
    callouts = b.get("audience_callouts", [])
    who = lambda h: ", ".join(callouts) if h["customer"] == "all" else h["customer"]
    confirmed = sum(f["status"] == "confirmed by Nate" for f in brand["facts"].values())
    rows = [(h, *lint(h["spoken"])) for h in hooks]
    verdicts = Counter(v for _, v, _ in rows)
    L = [f"# Hook sheet: {b['name']}, {data['batch']}", "",
         f"**{len(hooks)} hooks, all passing the automatic checks** (run by `python -m factory.hooks {b['slug']} {data['batch']}`). "
         "This file is written by that command; edit `hooks.json`, not this.", "",
         "## Read this first",
         "- **No hook here has been tested.** The evidence is other people's videos, rival ads and guesses about the buyer (`evidence.md` grades each one). No ad has run for this brand.",
         f"- **Drafts until Nate confirms `facts.md`:** {confirmed} of {len(brand['facts'])} facts are confirmed.",
         "- **What the checks cover:** every cited fact exists, no never-claim wording, every number is in a cited fact (clock times such as \"2 AM\" set a scene and are let through), "
         f"on-screen text is {MAX_ONSCREEN} words or fewer, no long dashes, hype words or \"it's not X, it's Y\", every evidence id exists.",
         "- **What they do not cover:** whether a line with no fact cited makes a claim anyway. Those were read by Claude, not by a rule.",
         f"- **The hook grader from the reel** (Instagram Agent Skill) calls {verdicts['STRONG']} of these strong, {verdicts['OK']} ok and {verdicts['WEAK']} weak. "
         "Do not read much into that: it matches words from a creator's list, so \"2 AM, a pipe just burst\" scores as nothing at stake, and its author's own test shows it does not pick winners. "
         "Each hook below shows only its two useful notes: the spoken word count (the grader wants 12 or fewer; the on-screen line is what has to land in the first second) and any weak opening word.", ""]
    L += ["## First test (the hooks to try first)",
          f"{WAVE[0]} to {WAVE[1]} distinct ideas fit one small ad set. Jarvis's pick, for Nate to change:", ""]
    for h in hooks:
        if "test" in h:
            L.append(f"- **{h['id']}-{h['test']}** ({h['type']}, {who(h)}): \"{h['spoken']}\"")
    L.append("")
    for t, level in AWARENESS.items():
        group = [r for r in rows if r[0]["type"] == t]
        L += [f"## {t.capitalize()} hooks: for viewers who are {level.lower()} ({len(group)})", ""]
        for h, _, notes in group:
            L += [f"**{h['id']}** · {who(h)} · " + " · ".join(notes),
                  f"- Say: \"{h['spoken']}\"",
                  f"- On screen: {h['onscreen']}",
                  "- Evidence: " + "; ".join(f"{e} [{evidence[e]['grade']}]" for e in h["evidence"]),
                  "- Facts: " + (", ".join(h["facts"]) if h["facts"] else "none cited (a scene or a question; the body carries the claims)"),
                  "- Bodies: " + ", ".join(f"{m} {data['bodies'][m]['name']}" for m in h["bodies"])
                  + (f" · first test: {h['id']}-{h['test']}" if "test" in h else "")]
            if h.get("note"):
                L.append(f"- Note: {h['note']}")
            L.append("")
    counts = Counter(who(h) if h["customer"] != "all" else "All of them" for h in hooks)
    combos = sum(len(h["bodies"]) for h in hooks) * len(b["ctas"])
    L += ["## Counts",
          "- By customer: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()),
          "- By type: " + ", ".join(f"{t} {sum(h['type'] == t for h in hooks)}" for t in AWARENESS),
          f"- Matrix: {combos} combinations of hook, body and call to action in `matrix.csv` (file names like `H15-M1-A`).",
          "", "## Bodies"]
    L += [f"- **{m}** {v['name']}: {v['what']} ({', '.join(v['facts'])})" for m, v in data["bodies"].items()]
    L += ["", "## Calls to action"]
    L += [f"- **{c['id']}** {c['text']} ({', '.join(c.get('claims', []))})" for c in b["ctas"]]
    (folder / "hook-sheet.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with open(folder / "matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "hook", "body", "cta", "first_test", "type", "customer", "spoken", "onscreen", "cta_text"])
        for h in hooks:
            for m in h["bodies"]:
                for c in b["ctas"]:
                    combo = f"{m}-{c['id']}"
                    w.writerow([f"{h['id']}-{combo}", h["id"], m, c["id"], "yes" if h.get("test") == combo else "",
                                h["type"], who(h), h["spoken"], h["onscreen"], c["text"]])
    return combos


def run(slug, batch):
    brand = load_brand(slug)
    folder = ROOT / "runs" / slug / batch
    if not (folder / "hooks.json").is_file():
        raise BrandError(f"{folder / 'hooks.json'} is missing")
    data = json.loads((folder / "hooks.json").read_text(encoding="utf-8"))
    evidence = load_evidence(folder / "evidence.md")
    bad = check_hooks(data, with_stats(brand, evidence), evidence)
    if bad:
        for hid, problems in bad.items():
            for p in problems:
                print(f"FAIL {hid}: {p}")
        sys.exit(f"{len(bad)} of {len(data.get('hooks', []))} hooks failed (or the batch did). Nothing written.")
    combos = write_sheet(folder, data, brand, evidence)
    print(f"{len(data['hooks'])} hooks pass. Wrote {folder / 'hook-sheet.md'} and matrix.csv ({combos} combinations).")


def selfcheck():
    brand = load_brand("builtwithbaron")
    m = EVIDENCE.match("- **E12** [stat] CallRail: \"82% say they'll call a competitor\". — source: callrail.com/blog")
    assert m and m[2] == "stat", "a [stat] line of evidence.md must parse"
    ev = {"E01": {"grade": "guess"}}
    base = {"id": "H01", "type": "pain", "customer": "Plumbers", "spoken": "Plumbers: hands full, phone ringing.",
            "onscreen": "Hands full. Phone ringing.", "evidence": ["E01"], "facts": [], "bodies": ["M1"], "test": "M1-A"}
    batch = lambda *hooks: {"bodies": {"M1": {"name": "Demo", "facts": ["F25"]}}, "hooks": list(hooks)}
    more = [dict(base, id=f"H0{i}", spoken=f"Plumbers: phone ringing, job {'abcdefg'[i]}.") for i in (2, 3)]

    def fails(needle, **change):
        bad = check_hooks(batch(dict(base, **change), *more), brand, ev)
        msgs = " | ".join(bad.get(change.get("id", "H01"), []) + bad.get("-", []))
        assert needle in msgs, f"expected {needle!r}, got: {msgs or 'a pass'}"
        print(f"  fails as it should: {msgs[:110]}")

    assert check_hooks(batch(base, *more), brand, ev) == {}, check_hooks(batch(base, *more), brand, ev)
    fails("not in facts.md", facts=["F99"])                                     # a claim with no fact behind it
    fails("never-claim N01", spoken="Plumbers: never miss a call again.")
    fails("never-claim N03", onscreen="Only $99 per month")
    fails("number 24", spoken="Plumbers: we answer 24 hours a day.")
    fails("on-screen text is 9 words", onscreen="This on screen line has too many words here")
    fails("evidence E77", evidence=["E77"])
    fails("no evidence", evidence=[])
    fails("customer 'Dentists'", customer="Dentists")
    fails("body M9", bodies=["M9"], test="M9-A")
    fails("first test", test="M1-Z")
    fails("it's not X", spoken="This isn't voicemail. It's a booked job.")
    assert "same spoken line" in str(check_hooks(batch(base, dict(base, id="H02"), more[1]), brand, ev))
    assert "first test" in str(check_hooks(batch(base), brand, ev))               # one hook is not a test wave
    # A sourced figure: copy citing a [stat] line may use its numbers; nothing else may.
    ev2 = {"E01": {"grade": "guess"}, "E02": {"grade": "stat", "text": "82% say they'll call a competitor (survey of 1,000)", "source": "x"},
           "E03": {"grade": "claim", "text": "82% of something", "source": "y"}}
    sb = with_stats(brand, ev2)
    stat = dict(base, spoken="82% say they'll call a competitor.", facts=["E02"], stat="82%", source="Survey of 1,000")
    assert check_hooks(batch(stat, *more), sb, ev2) == {}, check_hooks(batch(stat, *more), sb, ev2)
    assert "E03, which is not in facts.md" in str(check_hooks(batch(dict(stat, facts=["E03"]), *more), sb, ev2))   # only [stat] lines merge
    assert "number 83" in str(check_hooks(batch(dict(stat, stat="83%"), *more), sb, ev2))      # a figure the source does not give
    assert "number 2000" in str(check_hooks(batch(dict(stat, source="Survey of 2,000"), *more), sb, ev2))
    assert "needs both" in str(check_hooks(batch(dict(base, stat="82%", facts=["E02"]), *more), sb, ev2))
    assert "number 82" in str(check_hooks(batch(stat, *more), brand, ev2))     # without the merge the figure is refused
    assert sum(f["status"] == "confirmed by Nate" for f in sb["facts"].values()) == sum(f["status"] == "confirmed by Nate" for f in brand["facts"].values())
    try:
        load_evidence(ROOT / "runs" / "no-such" / "evidence.md")
        raise AssertionError("a missing evidence.md should be an error")
    except BrandError as e:
        print(f"  clear error: {e}")
    print("hooks selfcheck passed")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if sys.argv[1:] == ["--selfcheck"]:
            selfcheck()
        elif len(sys.argv) == 3:
            run(sys.argv[1], sys.argv[2])
        else:
            sys.exit(__doc__)
    except BrandError as e:
        sys.exit(f"Error: {e}")
