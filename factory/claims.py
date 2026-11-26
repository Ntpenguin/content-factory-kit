"""Copy checks every station shares: fact ids, never-claim lines, numbers, AI tells.

check_copy(text, cited, brand) returns a list of problems; empty means the copy passes.
`brand` is what factory.brand.load_brand returns.
"""
import re

WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}
# ponytail: "one" is left out because it is mostly a pronoun ("the one answering", "no one").
# A "one in seven" style claim is still caught by its other number.
CLOCK = re.compile(r"\b\d{1,2}(:\d\d)?\s?(a\.?m\.?|p\.?m\.?)(?![a-z])", re.I)  # "2 AM" sets a scene, it is not a claim
NUM = re.compile(r"\d+(?:[.,]\d+)*|\b(?:" + "|".join(WORDS) + r")\b", re.I)
# Amounts and comparisons said in words ("most", "half", "every", "a week", "more jobs than"). A line may use one only if a
# cited fact uses the same word. ponytail: a word list, so phrasing it lacks ("the bulk of") still passes; the fresh
# reader (factory.read) is the check for meaning.
QUANT = r"half|most|majority|every|everyone|everybody|all|twice|double|triple|always|percent|a (?:minute|hour|day|week|month|year)"
COMPARE = r"more|fewer|less|better|cheaper|faster|lower|higher"
QUANT_IN_COPY = re.compile(rf"\b(?:{QUANT})\b|\b(?:{COMPARE})\b(?=[^.?!]{{0,40}}\bthan\b)", re.I)   # a comparison needs its "than"
QUANT_IN_FACT = re.compile(rf"\b(?:{QUANT}|{COMPARE})\b", re.I)
SAME = {"everyone": "every", "everybody": "every"}

# Wording that reads as machine-written or as hype (brand voice: plain words, no hype).
AI_TELLS = [
    (re.compile(r"[—–]"), "a long dash"),
    (re.compile(r"\b(?:not|isn['’]?t|aren['’]?t|wasn['’]?t)\b[^.?!;]{0,50}[.,;:]\s+(?:it['’]?s|it is|that['’]?s|this is|they['’]?re)\b", re.I),
     "the \"it's not X, it's Y\" pattern"),
    (re.compile(r"\b(?:game.?chang\w*|revolution\w*|unlock\w*|seamless\w*|cutting.edge|leverag\w+|elevate\w*|"
                r"supercharg\w*|effortless\w*|transform\w*|delve\w*|say goodbye|in today['’]s|skyrocket\w*|"
                r"next.level|state.of.the.art)\b", re.I), "a hype word"),
]


def numbers(text):
    """Numbers in copy as a set of strings, clock times removed, number words turned into digits."""
    out = set()
    for m in NUM.finditer(CLOCK.sub(" ", text)):
        t = m[0].lower()
        out.add(str(WORDS[t]) if t in WORDS else t.replace(",", ""))
    return out


def quants(text, pattern=QUANT_IN_COPY):
    """Amount and comparison words in a line, lower case ("everyone" counts as "every")."""
    return {SAME.get(w, w) for w in (m[0].lower() for m in pattern.finditer(text))}


def check_copy(text, cited, brand):
    facts, never = brand["facts"], brand["never"]
    problems = [f"cites {c}, which is not in facts.md" for c in cited if c not in facts]
    allowed, said = set(), set()
    for c in cited:
        if c in facts:
            allowed |= numbers(facts[c]["text"])
            said |= quants(facts[c]["text"], QUANT_IN_FACT)
    for n in sorted(numbers(text) - allowed):
        problems.append(f"the number {n} is not in any cited fact")
    for w in sorted(quants(text) - said):
        problems.append(f"\"{w}\" claims an amount or a comparison that no cited fact makes")
    for nid, rule in never.items():
        for p in rule["patterns"]:
            m = p.search(text)
            if m:
                problems.append(f"never-claim {nid}: \"{m[0]}\" ({rule['reason']})")
                break
    for pattern, name in AI_TELLS:
        m = pattern.search(text)
        if m:
            problems.append(f"wording: {name} (\"{m[0][:40]}\")")
    return problems


def selfcheck():
    never = {"N01": {"patterns": [re.compile("never miss a call", re.I)], "reason": "results promise"}}
    brand = {"facts": {"F10": {"text": "The survey is free and takes about 60 seconds: six taps."},
                       "F12": {"text": "Nate reads every answer."}}, "never": never}
    ok = lambda t, c=(): check_copy(t, list(c), brand)
    assert ok("Free. Sixty seconds. 6 taps.", ["F10"]) == []
    assert ok("It's 2 AM. A pipe just burst. Who picks up?") == []           # a clock time is not a claim
    assert "not in facts.md" in ok("Free survey.", ["F99"])[0]               # a claim with no fact fails
    assert "number 90" in ok("Free. 90 seconds.", ["F10"])[0]                # a number the fact does not hold
    assert "number 60" in ok("Takes 60 seconds.")[0]                         # a number with no fact cited
    assert "never-claim N01" in ok("Never miss a call again.")[0]
    assert "\"half\" claims" in ok("Most plumbers lose half their calls.")[0]  # amounts in words need a fact too
    assert "\"most\" claims" in ok("Most plumbers lose half their calls.")[1]
    assert "\"every\" claims" in ok("Everyone in Austin is switching.")[0]
    assert "\"more\" claims" in ok("It books more jobs than a front-desk hire.", ["F10"])[0]
    assert "\"a week\" claims" in ok("Set up in a week.", ["F10"])[0]
    assert ok("Get more calls answered. Learn more.") == []                     # "more" without "than" is not a comparison
    assert ok("Every answer is read.", ["F12"]) == []                      # the cited fact says "every"
    assert "it's not X" in ok("This isn't voicemail. It's a booked job.")[0]
    assert "long dash" in ok("Your phone — answered.")[0]
    assert "hype word" in ok("Unlock your phone line.")[0]
    print("claims selfcheck passed")


if __name__ == "__main__":
    selfcheck()
