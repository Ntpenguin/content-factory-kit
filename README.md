# Content factory kit

The tools behind Built with Baron's ad and short-video line: static ads, AI-voice videos and edits of filmed talking-head footage (word-lit captions, silence cuts, a moving graphic per point), driven by Claude Code.

Download: green **Code** button → **Download ZIP**, or `git clone`.

## What's inside
- `.claude/skills/`: Claude Code skills that load on their own when you open this folder:
  - `remotion`: building and rendering Remotion videos (trimmed copy of `remotion-dev/skills`)
  - `watch`: watch a video URL or file as frames plus transcript (MIT, Bradley Bonanno)
  - `ig-reel`, `ig-caption`, `ig-carousel`: reel scripts with scored hooks, captions, carousels (MIT, Jake Schincariol)
- `factory/`: the Python line (hooks, copy checks, statics, video, footage edits, dashboard)
- `remotion/`: the video templates (Punch, Board, Line, Talk, Static)
- `knowledge/`: editing rules, hooks, formats, platform and compliance notes
- `checks/`: self-tests
- `HOWTO.md`: every command

## Setup
1. Python 3: `pip install -r requirements.txt`; `ffmpeg` on PATH.
2. `npm ci` inside `remotion/`.
3. Add your own brand under `brands/<brand>/` (`facts.md`: every claim your copy may use) and batches under `runs/<brand>/`. Not included here: brand data, footage, renders, sounds.

Remotion's free license covers individuals and companies of up to 3 people; bigger teams need a Remotion company license.
