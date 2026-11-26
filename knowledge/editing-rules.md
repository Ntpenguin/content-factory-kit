# Editing rules

Seven rules from the editing video Nate sent [S4], then the retention findings on file. Lines marked **(checked)** are enforced by the factory's validator or gate; the rest need a person.

## The seven rules [S4]

1. **Give direction before editing.** A ten-minute brief per batch: one or two reference videos and what is good in each, the feel (how fast, how heavy), and a starting visual. His claim: it saves about two hours of revisions. → `runs/<brand>/<batch>/brief.md`.
2. **Sift by measurement, not by feel.**
   - Remove dead space first. He treats two to three frames of silence as dead space, measured against the room's own noise floor (the quietest 10% of 10 ms windows), not a fixed level.
   - Words ending in S, T, D, K or P get cut early or late: pad the cut and check it.
   - Five retake types: repeats, reopens, replacements, rephrases, exceptions. Keep the last clean take.
3. **Good input, good output.** Feed the editor specifics: hook templates, the customer profile, reference videos. This is why the factory has `brands/` and `knowledge/`.
4. **Less is more.** **(checked)** At most 3 transitions in a video. No transition between every scene. Every element needs a reason. "Retention maxing" (everything moving, heavy sound effects) is what makes an edit look like AI.
5. **Cut scenes on purpose.** Think in layouts and decide when to change them. A video should not sit on one layout the whole way.
6. **Make it once, use it ten times.** Build one or two core graphics per video and reuse them.
7. **Catch it before the reviewer does.** **(checked)** A quality pass before delivery: spelling of on-screen text, clipped words, export settings, caption sync. Log every review comment; a comment made twice becomes a permanent rule.

## Retention findings on file [S8, S9]

- Start mid-action; the first frame is the payoff or the problem, never a logo. **(checked: no logo-only first scene)**
- Text on screen in the first second, under 8 words. **(checked)**
- One idea and one action per shot; cut every 1 to 3 seconds.
- 8 to 15 s for organic loops, up to 25 s for an explainer. **(checked: length limit per lane)**
- It works muted: captions carry every spoken line. **(checked: every voice line has a caption)**
- Design one sound moment (a ring, a click); most Reels are watched with sound on [Meta 2024, via S9], and captions still cover mute viewers.
- A product shot early raised 6-second view-through 17%; a logo up front cut it 14% [Vidmob and TikTok, 1,678 ads, via S9].
- End on the product in action; organic pieces loop back to the first frame.

## Factory defaults that come from these rules

- Captions: two to five words on screen at a time, one highlighted word at most. The highlighted word is the one being said, lit at its heard time 2 frames early, in every lane (Nate, 2026-11-22, "Yes" to word-by-word captions on the AI ads too; `ats` from `captions()` in `factory/video.py`). Each lane keeps its own look: the pill in punch and line videos, the card colour on the board, the coloured word on talking-head edits.
- Sound effects only on named motions (a card landing, a stamp, a swipe), never on every cut.
- An intensity setting per piece: quiet (captions plus an occasional cutaway) or busy.
- Safe-zone check on every size (see `platforms.md`). **(checked)**

## Motion rules [S16]

- **One block for every timing number.** The punch video's durations, springs and staggers all sit in `MOTION` at the top of `remotion/src/Punch.tsx`. A note about feel ("too slow", "too bouncy") changes a number there, never a value in the markup.
- **Turn a vague note into numbers first.** Name the element, its value now and the new value. Give at most 3 readings of the note and say which to try first. Together with rule 7, a note given twice becomes a line here.
- **Tear a reference down before copying it.** Look at its frames in time order and write what moves, in what order, roughly how fast and why it works, with guesses labelled. Keep it to 8 points at most, then 3 ideas to borrow. This goes in the batch's `brief.md` (rule 1).
- **Motion-safety pass.** Flag flashing, large fast movement and long loops, each with a calmer option. Say what needs a real phone to judge. Not checked by the gate: a person looks.

## One-line style [S17]

From a prompt sheet for a spec ad ("From A to Z"), not from measured results. The sheet's own claims are marked (sheet); what the factory does is marked (factory). Lane: `python -m factory.line`, `remotion/src/Line.tsx`.

- **The logo's own idea is the story.** Pick the one shape in the brand's logo that can mean something (the sheet's arrow; Built with Baron's stem of the B) and let it carry the whole pitch. A style without that idea is just a glowing line. (sheet; needs a person per brand)
- **One line, one function.** Every stop hands the same line of light to the next, so the piece reads as one shot with no cuts. The line is drawn by one shared routine. (sheet; factory: `route` and `headAt` in `Line.tsx`)
- **The line does every job and ends as the logo.** It is the ring, the voice, the rail of the cards and at last a part of the mark. The brand's real logo is only moved, scaled or faded, never redrawn in another colour. (sheet)
- **Dark stage, one accent.** Near-black background, the accent colour for the line and at most one word per line of text; phone, cards and type big and well lit. (sheet)
- **One slam on the first beat.** Frame 0 is already moving and the hit lands at 0.17 s; readable in a fraction of a second, not a burst of effects. (sheet; factory: `SLAM` in `factory/line.py`)
- **A breath, then the hit.** Music drops out for about half a second before the logo lands, and nothing else sounds near the hit. (sheet: 60 ms; factory: `BREATH`, and the order check in `line.py`)
- **Voice first, then lock the timeline to it.** Every move is placed on a spoken word. (sheet; factory: the timeline is built from the voice files' cue words)
- **Objects look real.** Rounded edges, a shadow, real text on the phone screen; flat boxes and grey placeholder bars read as fake. (sheet)
- **Look at it frame by frame and on a phone** before anyone sees it: hand-overs, pops, clipped text in 9:16. (sheet; factory: contact sheets by the session, the phone is Nate's)
- **Where the factory differs on purpose.** The sheet puts a sound on every visible move (about 90 cues in 21 s). The factory's default above is sounds on named motions only, so the first line piece has 7. The sheet renders at 60 fps with motion blur; the gate requires 30 fps, and a trail whose length follows speed stands in for blur. Both wait on Nate's answer.

## Talking-head edits [S20]

For footage Nate films of himself. From the Herk Edit Kit's playbook: one creator's measurements of his own reels, a starting point and not law. The first edit of video 1 (`H11-nate-v1.mp4`, 2026-11-20) broke the lines marked (v1); Nate: "I wasn't a fan of your edit".

- **Nate's notes on v1 (2026-11-22):** "There was no graphics didn't cut out pauses didn't feel like a viral video." So: a moving graphic for every point he names (the Every shot moves rule below); every pause between phrases cut by measured silence, not by transcript times; and a pace that never sits still (short shots, a punch-in on each turn, captions that swap with the voice, a music bed and effects). v2 (`H11-nate-v2.mp4`) is the first edit built to these.
- **Nate's note on v2 (2026-11-22):** "subtitles should highlight word as I say it." So captions light the word being said (the chunk's colour, teal when the chunk is white, slightly larger), timed from each word's start in the cut, 2 frames early.
- **House settings: the default for every future edit of Nate's footage (Nate, 2026-11-22: "Make sure these are the settings for all feature edits", taken as "future").** v3 of video 1 (`H11-nate-v3.mp4`) is the reference. Start each new edit from copies of `runs/builtwithbaron/2026-11-19-fact-first/edit-nate-v2/cut.py` and `build.py` and the Remotion composition `Talk` (`remotion/src/Talk.tsx`); change only the takes, the shot plan, the graphics and the colour-word lists. Changing a setting below needs Nate's note.
  - Cut: one ffmpeg pass on exact frames; phrases split at transcript gaps over 0.12 s; each edge moved to measured silence (10 dB above the room's noise floor), 0.04 s lead-in, 0.07 s tail, plus 0.1 s after a comma; 4 ms audio fades at each join.
  - Shots: about 19 per 35 s, average under 2 s, none over 2.8 s; split (graphic top 880 px, teal seam, face below), punch-in (x1.42), full (x1.28) and full-screen graphic; a 1.05-to-1 settle on every cut; a moving graphic for every point named; first frame already showing the hook graphic.
  - Captions: 1 to 3 words, uppercase Inter 800 at 68 px in a dark box (88% black, thin light edge, 18 px corners); at the seam in split, lower third otherwise; about a third of chunks coloured by meaning (red loss, teal keyword, green action); the word being said lit in the chunk's colour (teal on white chunks) at x1.06, 2 frames ahead of the voice, 0.22 em between words.
  - Sound: lo-fi bed 15 dB under the voice, sidechain-ducked; a soft pop when a graphic lands, a whoosh only on the FIX cards; limiter, then two-pass loudnorm to -14 LUFS, true peak about -1.8 dB; AAC 192k.
  - Delivery: 1080x1920, 30 fps; a phone copy at 1.3 Mb/s for Drive.
- **Every note becomes a rule here.** Nate says what he dislikes in plain words; the fix goes into the edit and into this section, so he never gives a note twice.
- **Cut between phrases, never inside one.** Keep the last clean take of each line. Remove dead air between phrases (under about 0.2 s left); keep the natural beat after a comma or "First," (0.2 to 0.4 s). Never speed the voice up.
- **Cut in one pass by exact frames.** Encoding each piece separately and joining them drifts the lips by about a frame at half the joins. (v1 did this)
- **Shots are short.** About 1.1 to 1.4 s on average, none over about 2.8 s; the first cut lands within a second. Each item in a spoken list gets its own shot. (v1: one clip held 5.5 s, then 33 s of the same shot)
- **Three layouts, hard cuts between them.** Split (footage on top, speaker below), full footage, and a punch-in on the speaker for the pivot and the call to action. The speaker is on screen about half the time and never gone more than about 3.5 s. (v1: speaker full frame for 85%)
- **Every shot moves, and shows the thing being named.** In order of preference: real footage, a real screen recording zoomed to the part named, an animated screen mock (labelled as an example), AI video. No still pictures; no generic "person at a computer". Use each scene once. Never invent a number or a result to decorate a line (the Claims rule).
- **Captions: one look for the whole video.** 1 to 3 words, split at phrase ends, hard swap, in the same dark box with a thin light edge so they read on any background. Never white on a light background; never over the mouth or chin. Colour on about a third of the chunks, the whole chunk. (v1: bare white captions on a bright hallway, plus labels in a second style)
- **Sound.** A music bed about 11 dB under the voice, ducked under speech. Sound effects only on visible actions (a tap when something lands, a click for small screen items), soft and varied; no whoosh on every cut. Never fade the last word. -14 LUFS, true peak at or under -1.5 dB, measured on the delivered file. (v1: no music, no effects; peak -1.0 dB)
- **Start on speech, end on the last word.** Speech within 0.1 s; no intro or outro card.
- **Checks before Nate sees it.** Frame strips across every cut (10 frames each side); the first 2.5 s frame by frame for anything over the mouth; the brightness behind every caption; the final file transcribed and each cut's words compared with the raw footage (a transcript alone is not proof: a clipped word is still guessed right); loudness and peak on the delivered file.
- **Where the factory differs on purpose.** The kit builds with HyperFrames and transcribes with ElevenLabs; the factory keeps Remotion and local Whisper, which do the same jobs with nothing new to install or pay for. The Claims rule and the source-on-screen rule still cover every caption and graphic.

## Needs a person

- Choosing references and the overall feel; which moments to stress; whether a retake's tone is better; the final creative review after the automatic pass [S4].
