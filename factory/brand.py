"""Load a brand folder (brands/<slug>/) and refuse a broken one with a clear error.

    python -m factory.brand <slug>        summary of the brand
    python -m factory.brand --selfcheck   run the loader's own checks
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANDS = ROOT / "brands"
REQUIRED = ("brand.json", "facts.md", "icp.md", "offers.md")
FACT = re.compile(r"^- \*\*(F\d+)\*\* \[(confirmed by Nate|needs Nate)\] (.+) — source: (\S.*)$")
NEVER = re.compile(r"^- \*\*(N\d+)\*\* (.+?) — (\S.*)$")


class BrandError(Exception):
    pass


def parse_facts(text, where="facts.md"):
    """Return (facts, never). facts: id -> {status, text, source}. never: id -> {patterns, reason}."""
    facts, never, section = {}, {}, ""
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line.startswith("- **"):
            continue
        if section == "facts":
            m = FACT.match(line)
            if not m:
                raise BrandError(
                    f"{where}:{n}: fact line needs an id, a status and a source, like "
                    f"'- **F01** [needs Nate] claim — source: file:line'. Got: {line[:90]}"
                )
            if m[1] in facts:
                raise BrandError(f"{where}:{n}: fact id {m[1]} is used twice")
            facts[m[1]] = {"status": m[2], "text": m[3].strip(), "source": m[4].strip()}
        elif section == "never claim":
            m = NEVER.match(line)
            if not m:
                raise BrandError(f"{where}:{n}: never-claim line needs '- **N01** phrase | phrase — reason'. Got: {line[:90]}")
            try:
                pats = [re.compile(p.strip(), re.I) for p in m[2].split(" | ") if p.strip()]
            except re.error as e:
                raise BrandError(f"{where}:{n}: bad phrase pattern in {m[1]}: {e}")
            never[m[1]] = {"patterns": pats, "reason": m[3].strip()}
    if not facts:
        raise BrandError(f"{where}: no fact lines found under '## Facts'")
    return facts, never


def load_brand(slug, brands_dir=None):
    d = Path(brands_dir or BRANDS) / slug
    if not d.is_dir():
        have = sorted(p.name for p in Path(brands_dir or BRANDS).glob("*") if p.is_dir())
        raise BrandError(f"No brand folder '{slug}' in {d.parent}. Brands on file: {', '.join(have) or 'none'}")
    missing = [f for f in REQUIRED if not (d / f).is_file()]
    if missing:
        raise BrandError(f"Brand '{slug}' is missing {', '.join(missing)} in {d}. A brand needs: {', '.join(REQUIRED)}")
    try:
        brand = json.loads((d / "brand.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BrandError(f"{d / 'brand.json'} is not valid JSON: {e}")
    for key in ("slug", "name", "site", "colors", "fonts", "logos", "ctas"):
        if key not in brand:
            raise BrandError(f"{d / 'brand.json'} has no '{key}'")
    facts, never = parse_facts((d / "facts.md").read_text(encoding="utf-8"), str(d / "facts.md"))
    for name, rel in brand["logos"].items():
        if not (d / rel).is_file():
            raise BrandError(f"Brand '{slug}': logo '{name}' points to {rel}, which is not in {d}")
    for cta in brand["ctas"]:
        bad = [c for c in cta.get("claims", []) if c not in facts]
        if bad:
            raise BrandError(f"Brand '{slug}': call to action {cta.get('id')} cites {bad}, not in facts.md")
    # Nate's rule: every ICP line is marked evidence or guess.
    for n, line in enumerate((d / "icp.md").read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("- ") and "[evidence" not in line and "[guess" not in line:
            raise BrandError(f"{d / 'icp.md'}:{n}: line is not marked [evidence] or [guess]: {line[:80]}")
    return {"dir": d, "brand": brand, "facts": facts, "never": never}


def selfcheck():
    import tempfile

    def fails(fn, needle):
        try:
            fn()
        except BrandError as e:
            assert needle in str(e), f"wrong error: {e}"
            return str(e)
        raise AssertionError(f"expected a BrandError containing {needle!r}")

    print("unknown brand ->", fails(lambda: load_brand("no-such-brand"), "No brand folder"))
    with tempfile.TemporaryDirectory() as t:
        b = Path(t) / "x"
        b.mkdir()
        (b / "brand.json").write_text("{}", encoding="utf-8")
        print("missing file  ->", fails(lambda: load_brand("x", t), "missing facts.md"))
    ok = "## Facts\n- **F01** [needs Nate] A claim. — source: site/index.html:1\n"
    assert parse_facts(ok)[0]["F01"]["source"] == "site/index.html:1"
    print("no status     ->", fails(lambda: parse_facts("## Facts\n- **F01** A claim. — source: x:1\n"), "status"))
    print("no source     ->", fails(lambda: parse_facts("## Facts\n- **F01** [needs Nate] A claim.\n"), "source"))
    print("duplicate id  ->", fails(lambda: parse_facts(ok + ok.split("\n", 1)[1]), "twice"))
    for p in sorted(BRANDS.glob("*")):
        if p.is_dir():
            b = load_brand(p.name)
            print(f"brand {p.name}: {len(b['facts'])} facts, {len(b['never'])} never-claim lines: ok")
    print("selfcheck passed")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        if sys.argv[1] == "--selfcheck":
            selfcheck()
        else:
            b = load_brand(sys.argv[1])
            conf = sum(f["status"] == "confirmed by Nate" for f in b["facts"].values())
            print(f"{b['brand']['name']} ({b['brand']['site']}): {len(b['facts'])} facts "
                  f"({conf} confirmed by Nate, {len(b['facts']) - conf} need Nate), "
                  f"{len(b['never'])} never-claim lines, {len(b['brand']['ctas'])} calls to action")
    except BrandError as e:
        sys.exit(f"Brand error: {e}")
