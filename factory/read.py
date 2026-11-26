"""The read pass: a fresh reader checks that each line says only what its facts say (what no rule can judge).

    python -m factory.read <brand> <batch>                 writes read-pending.json: every line nobody has read yet
    python -m factory.read <brand> <batch> <verdicts.json> saves a reader's verdicts in read.json
    python -m factory.read --selfcheck

A verdicts file is a list of {"key", "ok": true or false, "why": one sentence, "by": who read it}. The reader is someone
who did not write the copy: a fresh subagent given read-pending.json and RUBRIC, or Nate. A verdict is kept under a hash of
the line and the text of the facts it cites, so editing either one makes the line unread again (like the look note).
"""
import hashlib
import json
import sys
from datetime import datetime

from factory.brand import ROOT, BrandError, load_brand

SKIP = {"url", "label", "speaker"}      # fixed strings from brand.json and speaker tags: nothing to judge
RUBRIC = """For each line decide ok true or false and give one plain sentence why.
- A line that cites facts: ok only if the cited fact text backs every claim in the line: amounts, times, results,
  promises, comparisons, who it is for. A line that says more than its fact, or something else, is not ok.
- A line that cites no fact (a scene line): ok only if it claims nothing as true about the product, its results,
  customers, competitors or the world (no statistics, no "most plumbers", no "other movers make you wait").
  Setting a scene ("It's 2 AM. A pipe just burst.") or asking a question is ok.
- Judge only the words given. Do not assume anything about the business that the facts do not say."""


def key(text, ids, facts):
    blob = json.dumps([text, [[i, facts[i]["text"] if i in facts else None] for i in sorted(ids)]], ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def lines(folder, facts):
    """{key: {piece, where, text, facts}} for every line in gate.json a reader should judge, one entry per distinct line."""
    if not (folder / "gate.json").is_file():
        raise BrandError(f"{folder / 'gate.json'} is missing: run a production lane first")
    out = {}
    for pid, p in json.loads((folder / "gate.json").read_text(encoding="utf-8"))["pieces"].items():
        for where, text, ids in p["lines"]:
            if where not in SKIP:
                out.setdefault(key(text, ids, facts), {"piece": pid, "where": where, "text": text,
                                                       "facts": {i: facts[i]["text"] if i in facts else "(not in facts.md)" for i in ids}})
    return out


def saved(folder):
    path = folder / "read.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def verdict(folder, text, ids, facts, cache=None):
    """The saved verdict for this exact line and fact wording, or None."""
    return (saved(folder) if cache is None else cache).get(key(text, ids, facts))


def pending(folder, facts):
    done = saved(folder)
    todo = [{"key": k, **v} for k, v in lines(folder, facts).items() if k not in done]
    (folder / "read-pending.json").write_text(json.dumps({"rubric": RUBRIC, "lines": todo}, indent=1, ensure_ascii=False), encoding="utf-8")
    return todo


def save(folder, facts, verdicts):
    known, done = lines(folder, facts), saved(folder)
    for v in verdicts:
        if v.get("key") not in known:
            raise BrandError(f"verdict for unknown line {v.get('key')!r}: run `python -m factory.read` again and read the new read-pending.json")
        if not isinstance(v.get("ok"), bool) or not str(v.get("why", "")).strip() or not str(v.get("by", "")).strip():
            raise BrandError(f"verdict {v['key']}: needs \"ok\" true or false, a \"why\" and a \"by\"")
        done[v["key"]] = {"ok": v["ok"], "why": v["why"].strip(), "by": v["by"].strip(), "text": known[v["key"]]["text"],
                          "at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    (folder / "read.json").write_text(json.dumps(done, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(verdicts)


def selfcheck():
    import tempfile
    from pathlib import Path
    facts = {"F10": {"text": "The survey takes about 60 seconds."}}
    with tempfile.TemporaryDirectory() as d:
        folder = Path(d)
        gate = {"pieces": {"H01-M3-A": {"lines": [["headline", "Sixty seconds.", ["F10"]], ["say", "Most plumbers miss calls.", []],
                                                  ["url", "x.com", []], ["say", "Most plumbers miss calls.", []]]}}}
        (folder / "gate.json").write_text(json.dumps(gate), encoding="utf-8")
        todo = pending(folder, facts)
        assert [t["text"] for t in todo] == ["Sixty seconds.", "Most plumbers miss calls."]     # url skipped, repeat read once
        bad = todo[1]["key"]
        assert save(folder, facts, [{"key": bad, "ok": False, "why": "a claim about plumbers with no fact", "by": "test"}]) == 1
        assert verdict(folder, "Most plumbers miss calls.", [], facts)["ok"] is False
        assert [t["text"] for t in pending(folder, facts)] == ["Sixty seconds."]
        facts["F10"]["text"] = "The survey takes about 90 seconds."                             # the fact changed: unread again
        assert verdict(folder, "Sixty seconds.", ["F10"], facts) is None
        for wrong, needle in (([{"key": "nope", "ok": True, "why": "x", "by": "x"}], "unknown line"),
                              ([{"key": bad, "ok": "yes", "why": "x", "by": "x"}], "true or false"),
                              ([{"key": bad, "ok": True, "why": "", "by": "x"}], "a \"why\"")):
            try:
                save(folder, facts, wrong)
                raise AssertionError(needle)
            except BrandError as err:
                assert needle in str(err), err
    print("read selfcheck passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
    elif len(sys.argv) in (3, 4):
        try:
            folder = ROOT / "runs" / sys.argv[1] / sys.argv[2]
            facts = load_brand(sys.argv[1])["facts"]
            if len(sys.argv) == 4:
                print(f"saved {save(folder, facts, json.loads(open(sys.argv[3], encoding='utf-8').read()))} verdicts in {folder / 'read.json'}")
            todo = pending(folder, facts)
            print(f"{len(todo)} lines nobody has read: {folder / 'read-pending.json'}")
        except BrandError as err:
            sys.exit(f"error: {err}")
    else:
        sys.exit(__doc__)
