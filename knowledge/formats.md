# Formats: what the pieces look like

## 1. Formats of the most-viewed product Shorts [S8, dataset]

144 product Shorts, median 35.6 million views, median length 16 seconds. Organic views of consumer products, picked because they were viral.

| Format | Videos | Share | Median views |
|---|---|---|---|
| Satisfying demo | 35 | 24% | 51.1M |
| Problem, then solution | 25 | 17% | 41.4M |
| Comedy skit | 16 | 11% | 34.2M |
| Unboxing | 12 | 8% | 28.2M |
| Old way vs new way | 10 | 7% | 37.9M |
| Skeptic test | 10 | 7% | 56.5M |
| Hack or tutorial | 8 | 6% | 26.4M |
| POV skit | 7 | 5% | 30.1M |
| Things-you-need list | 6 | 4% | 26.5M |
| Gift idea | 4 | 3% | 39.1M |
| Before and after | 3 | 2% | 29.3M |

Also from the same set:
- **Length:** 45% run 15 s or less, 37% run 16 to 30 s, 17% run longer.
- **Sound:** 44% music only, 36% music plus some speech, 8% voiceover, 5% talking head.
- **Who is on screen:** 44% hands only, 39% a face, 15% a character.

**How far this carries:** a phone service has no "satisfying motion". The formats that transfer to a service are problem-then-solution, old way vs new way, the skeptic test (call the line and hear it) and the POV skit. Paid ads that must explain an offer use more words than viral Shorts do [S9].

## 2. Bodies ("meats") for a service ad [S1, S12]

The Goated Ads walk-through lists body types; the Built with Baron script bank already uses five:

| Id | Body | What it shows |
|---|---|---|
| M1 | Demo | The call being answered (labelled "Demo call · AI voice") |
| M2 | Proof | Real work: what was built for Fast Fix Work, named as a moving company |
| M3 | Educational | How it works: phone rings first, rolls over, off any time |
| M4 | Story | One evening in the owner's day (a scene, no invented customer) |
| M5 | Faceless | The survey on screen: six taps, top three |

Walk-through body order [S1]: audience callout, key insight, benefits, proof, the problem, "what if".
Villain and hero order [S3]: hook, villain, hero, demo or proof, call to action.

## 3. The lanes this factory makes

| Lane | Sizes | Made with | Use |
|---|---|---|---|
| Statics | 1080x1080, 1080x1350, 1080x1920 | Remotion stills from one template set | Feed and story ads, cheapest hook tests |
| Kinetic "punch" video | 1080x1920, 1080x1350 | Remotion (text, cards, sound effects, optional voice) | 8 to 20 s hook tests; works muted |
| AI presenter | 1080x1920 | Higgsfield clip under the same captions | Narrator in the third person only; never a customer |
| Real footage | 1080x1920 | Nate's phone clip, trimmed and captioned | Remakes of winning hooks; the research on file says real people beat polish [S9] |
| Faceless explainer | 1080x1920, 1080x1350 | Remotion: an AI voice over full-frame AI still pictures with no people (Higgsfield `gpt_image_2_6`, about 0.5 credit a picture), one picture per line, captions, music, end card. Built 2026-11-16 as a test; the old muapi skill is not used | 10 to 25 s explainers; organic reach. Untested on an audience |

## 4. Static ad layouts (from the Fast Fix Work kit) [S13]

- One idea per frame: a headline of a few words, one support line, the logo and site.
- Layout types worth a template each: big headline; phone screen (missed call, text thread, call log); checklist; before vs after as two columns of process (never results); quote-style line from the brand (never a customer).
- Text stays inside the safe zone of the tallest placement (see `platforms.md`).

## 5. Variation rules

- Change one thing per variant: the hook, or the body, or the call to action [S6's "one variable at a time", S1's matrix].
- Review variants side by side at the same size, each next to its source [S5].
- For AI clips: make the still first, then animate it; fix one named fault by edit instead of regenerating; plan two or three tries for anything with moving parts and price them in the quote [S5].
