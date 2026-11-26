// The kinetic "punch" video, driven by a brand.json and a timeline factory/video.py builds from the piece spec.
// Scenes: hook (the on-screen hook, optionally over a presenter clip), body (rows landing in one card), end (the CTA).
// A faceless video gives each hook and body scene a still picture that fills the frame and drifts slowly.
// Captions carry every spoken line. No copy and no scene timing lives in this file; how things move is in MOTION below.
import React from 'react';
import {AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import {Icon} from './Static';
import {font} from './fonts';

// Every timing and easing value in the punch video, in one place (knowledge/editing-rules.md, "Motion rules"): a note about
// feel changes a number here, never a value in the markup below. Seconds unless marked; sizes are in layout units (u).
// A spring's damping sets its bounce (lower bounces more). Nothing may grow past its laid-out size: the safe box is checked.
const MOTION = {
  sceneFade: 0.2, // a later scene fades in
  sceneRise: {damping: 16, distance: 6}, // and rises into place as its whoosh lands
  wordFade: 0.14, // each piece of the headline fades in as the voice reaches it
  hookPush: 0.05, // a big hook grows 5% over its scene
  underline: {delayFrames: 4, spring: {damping: 18, stiffness: 120, mass: 0.7}}, // the accent bar under a big hook
  pop: {damping: 14, stiffness: 170, mass: 0.6}, // rows, captions and end-card parts landing
  card: {hold: 3.2, fadeOut: 0.15, rise: 5, from: 0.94}, // a pop-up card over footage: seconds shown, fade, rise, start scale
  end: {stagger: 0.12, damping: 13, buttonFrom: 0.86, pulse: 0.012, pulseSpeed: 4}, // logo, button, address a beat apart; the button's slow pulse
  caption: {damping: 16, from: 0.9},
  stillDrift: 0.08, // a still picture drifts 8% over its scene
  glow: {size: 6, period: 2.5}, // the background glow's drift, so a held frame is never dead still
  speakerBars: 3, // frames per step of the speaking-indicator bars
};

export type PunchProps = {
  w: number;
  h: number;
  fps: number;
  dur: number; // seconds
  bare: boolean; // true hides footage, so the safe-zone check sees only text and graphics
  safe: {top: number; bottom: number; side: number};
  brand: {colors: Record<string, string>; fonts: {display: string; body: string; mono: string}; lockup: string; footer: string};
  piece: {
    chip: string;
    headline: string;
    label: string;
    cta: string;
    url: string;
    scenes: {from: number; dur: number; kind: string; clip: string; image?: string; cut?: number; zooms?: number[]; punch?: number}[]; // clip: a video that fills the frame (stepping `punch` closer, then back, at each of `zooms`); image: a still that does, cutting to a closer crop at `cut`
    head?: {text: string; at: number}[]; // the headline in pieces, each coming up at its second (the first at 0)
    wave?: number[]; // a recorded call's loudness, one value a frame (0 to 1): the call screen's sound bars
    rows: {scene: number; at: number; kind: string; text: string}[];
    caps: {from: number; dur: number; text: string; who: string; ats?: number[]}[]; // ats: when each word is heard, from the caption's start
    audio: {from: number; src: string; start: number; dur: number; vol: number}[];
    music?: {src: string; vol: number; top: number; up: number}; // the bed: `vol` under the voice, `top` from `up` seconds on
  };
};

export const Punch: React.FC<PunchProps> = ({w, h, fps, dur, bare, safe, brand, piece}) => {
  const frame = useCurrentFrame();
  const t = frame / fps;
  const f = (s: number) => Math.round(s * fps);
  const c = brand.colors;
  const display = font(brand.fonts.display);
  const body = font(brand.fonts.body);
  const mono = font(brand.fonts.mono);
  const boxW = w - safe.side * 2;
  const boxH = h - safe.top - safe.bottom;
  const u = Math.min(boxW, boxH * 0.8) / 100;
  const hairline = `1px solid ${c.text}1f`;
  const pop = (at: number, damping = MOTION.pop.damping) => spring({frame: frame - f(at), fps, config: {damping, stiffness: MOTION.pop.stiffness, mass: MOTION.pop.mass}});

  const found = piece.scenes.findIndex((s) => t >= s.from && t < s.from + s.dur);
  const si = found < 0 ? piece.scenes.length - 1 : found;
  const scene = piece.scenes[si];
  const cap = piece.caps.find((k) => t >= k.from && t < k.from + k.dur);
  const filled = Boolean(scene.clip || scene.image); // something fills the frame behind the text
  const footage = filled && !bare;
  // The first scene is there on frame 0 (the hook is the first frame); later scenes fade in over a fifth of a second.
  const enter = si === 0 ? 1 : interpolate(t - scene.from, [0, MOTION.sceneFade], [0, 1], {extrapolateRight: 'clamp'});
  const shadow = footage ? '0 4px 24px rgba(0,0,0,0.85)' : 'none';

  // Nothing here may scale past its laid-out size (a pop that overshoots, a pulse): a full-width card would leave the safe box.
  // Laid out to fill the safe box: the hook is as big as its length allows, the body is centred above the captions,
  // every row is its own card (all of a scene's rows hold their place from the start, so nothing jumps as they land).
  const big = scene.kind === 'hook' && !filled;
  const n = piece.headline.length;
  const headSize = (big ? (n <= 20 ? 17 : n <= 30 ? 15 : 13) : filled ? (scene.image && scene.kind === 'hook' ? 10.5 : 6.2) : 9) * u; // over a still picture the hook can be bigger than over a person's face
  const sentences = piece.headline.split(/(?<=[.?!])\s+/);
  const accentFrom = sentences.length > 1 ? piece.headline.length - sentences[sentences.length - 1].length : Infinity; // the last sentence is in the accent colour
  let headAt = 0;
  const parts = (piece.head ?? [{text: piece.headline, at: 0}]).map((part) => {
    const start = headAt;
    headAt += part.text.length + 1;
    return {...part, start};
  });
  const push = big ? 1 + MOTION.hookPush * Math.min(1, (t - scene.from) / scene.dur) : 1;
  const slide = si === 0 ? 0 : (1 - pop(scene.from, MOTION.sceneRise.damping)) * MOTION.sceneRise.distance * u; // a later scene rises into place as its whoosh lands
  const bar = spring({frame: frame - MOTION.underline.delayFrames, fps, config: MOTION.underline.spring});

  const head = (
    <div style={{transform: `scale(${push})`, transformOrigin: 'left center', width: big ? boxW / 1.05 : undefined /* the push ends at the box edge, never past it */}}>
      {piece.chip ? (
        <div
          style={{
            display: 'inline-block', fontFamily: mono, fontWeight: 700, fontSize: 3.4 * u, letterSpacing: 0.2 * u, color: c.accent,
            border: `2px solid ${c.accent}66`, borderRadius: 99, padding: `${0.9 * u}px ${2.2 * u}px`, marginBottom: 2.4 * u,
            textTransform: 'uppercase', background: footage ? `${c.bg}cc` : 'transparent',
          }}
        >
          {piece.chip}
        </div>
      ) : null}
      <div style={{fontFamily: display, fontWeight: 800, fontSize: headSize, lineHeight: 1.05, letterSpacing: -0.035 * headSize, textWrap: 'balance', textShadow: shadow, paddingLeft: 0.04 * headSize /* a j or a V hangs left of its box */}}>
        {/* Each piece fades in when the voice gets to it; it holds its place from frame 0, so the lines never re-flow. */}
        {parts.map((part, i) => (
          <span key={i} style={{color: part.start >= accentFrom ? c.accent : c.text, opacity: part.at <= 0 ? 1 : interpolate(t - part.at, [0, MOTION.wordFade], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>{part.text} </span>
        ))}
      </div>
      {big ? <div style={{width: 26 * u * bar, height: 1 * u, borderRadius: 99, background: c.accent, marginTop: 3 * u, marginLeft: 0.5 * u}} /> : null}
    </div>
  );

  const sceneRows = piece.rows.filter((r) => r.scene === si);
  const now = sceneRows.reduce((last, r, j) => (r.at <= t ? j : last), -1); // the row the voice is on wears an accent ring
  // Over a filmed clip the rows are pop-up cards: one at a time, above the captions, gone after MOTION.card.hold seconds or when the next lands.
  const over = Boolean(scene.clip) && scene.kind === 'hook';
  const gone = now < 0 ? 0 : Math.min(sceneRows[now].at + MOTION.card.hold, sceneRows[now + 1]?.at ?? Infinity);
  const shown = over ? sceneRows.filter((_, j) => j === now && t < gone) : sceneRows;
  const rowSize = (over ? 6.4 : sceneRows.length <= 2 ? 7.2 : sceneRows.length === 3 ? 6.4 : 5.8) * u;
  const cards = shown.length ? (
    <div style={{display: 'flex', flexDirection: 'column', gap: 1.6 * u, alignItems: over ? 'center' : 'stretch'}}>
      {shown.map((r, j) => {
        const p = pop(r.at) * (over ? interpolate(t, [gone - MOTION.card.fadeOut, gone], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1);
        return (
          <div
            key={j}
            style={{
              display: 'flex', alignItems: 'center', gap: 2.2 * u, background: c.card, border: hairline, borderRadius: 2.6 * u,
              padding: `${2.4 * u}px ${2.8 * u}px`, opacity: Math.min(1, p * 1.5), transform: `translateY(${(1 - p) * MOTION.card.rise * u}px) scale(${Math.min(1, MOTION.card.from + (1 - MOTION.card.from) * p)})`,
              boxShadow: over ? (footage ? '0 6px 30px rgba(0,0,0,0.55)' : 'none') : j === now && sceneRows.length > 1 ? `inset 0 0 0 ${0.4 * u}px ${c.accent}` : 'none',
            }}
          >
            <Icon kind={r.kind} size={rowSize * 1.45} c={c} />
            <div style={{fontFamily: body, fontWeight: 700, fontSize: rowSize, lineHeight: 1.2, color: c.text, textWrap: 'balance'}}>{r.text}</div>
          </div>
        );
      })}
    </div>
  ) : null;

  const label = piece.label ? (
    <div style={{display: 'flex', alignItems: 'center', gap: 1.2 * u, fontFamily: mono, fontWeight: 500, fontSize: 3.6 * u, color: c.text2}}>
      <div style={{width: 1.5 * u, height: 1.5 * u, borderRadius: 99, background: c.accent}} />
      {piece.label}
    </div>
  ) : null;

  // The call screen, for a piece that plays a recorded call: who is speaking, and bars that move with the recording's own sound
  // (the newest frame on the right, two frames a bar). The first voice heard has the accent colour, the other the text colour.
  const wave = piece.wave;
  const who = [...piece.caps].reverse().find((k) => k.from <= t && k.who)?.who ?? '';
  const first = piece.caps.find((k) => k.who)?.who;
  const call = wave ? (
    <div style={{background: c.card, border: hairline, borderRadius: 3 * u, padding: `${2.4 * u}px ${3 * u}px`, display: 'flex', flexDirection: 'column', gap: 2 * u}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 2.4 * u}}>
        <div style={{width: 9 * u, height: 9 * u, borderRadius: 99, background: `${c.accent}26`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
          <Icon kind="ring" size={6 * u} c={c} />
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 0.6 * u}}>
          <div style={{fontFamily: body, fontWeight: 800, fontSize: 5.6 * u, lineHeight: 1.1, color: c.text, minHeight: 6.2 * u}}>{who}</div>
          {label}
        </div>
      </div>
      <div style={{display: 'flex', alignItems: 'center', gap: 0.9 * u, height: 9.5 * u}}>
        {Array.from({length: 30}, (_, i) => (
          <div key={i} style={{flex: 1, height: `${8 + 92 * (wave[frame - (29 - i) * 2] ?? 0)}%`, borderRadius: 99, background: who === first ? c.accent : c.text}} />
        ))}
      </div>
    </div>
  ) : null;

  // The end card: the logo and the button land a beat apart, the address halfway through (scene.cut); the button keeps a slow pulse.
  const land = (i: number) => pop(scene.from + MOTION.end.stagger * i, MOTION.end.damping);
  const end = (
    <div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 3.6 * u, textAlign: 'center'}}>
      {brand.lockup ? <Img src={brand.lockup} style={{height: 9.5 * u, opacity: Math.min(1, land(0) * 1.5)}} /> : null}
      <div
        style={{
          background: c.accent, color: c.accentInk ?? c.bg, fontFamily: body, fontWeight: 800, fontSize: 8 * u, lineHeight: 1.15,
          borderRadius: 3 * u, padding: `${3.2 * u}px ${4 * u}px`, textWrap: 'balance',
          opacity: Math.min(1, land(1) * 1.5), transform: `scale(${Math.min(1, MOTION.end.buttonFrom + (1 - MOTION.end.buttonFrom) * land(1)) * (1 - MOTION.end.pulse + MOTION.end.pulse * Math.sin((t - scene.from) * MOTION.end.pulseSpeed))})`,
        }}
      >
        {piece.cta.replace(/-/g, '‑') /* a hyphenated word (60-second) stays on one line */}
      </div>
      <div style={{fontFamily: mono, fontWeight: 500, fontSize: 4.8 * u, color: c.text2, opacity: scene.cut ? pop(scene.cut, MOTION.end.damping) : land(2)}}>{piece.url}</div>
    </div>
  );

  // Captions: the word being said sits on an accent pill, lit at its heard time (cap.ats); without heard words, by its share of the caption's
  // letters (off by a few frames at most).
  const capP = cap ? pop(cap.from, MOTION.caption.damping) : 0;
  const capWords = cap ? cap.text.split(' ') : [];
  const letters = capWords.join('').length || 1;
  let seen = 0;
  const said = !cap ? -1 : cap.ats ? cap.ats.filter((a) => a <= t - cap.from).length - 1 : capWords.findIndex((wd) => (seen += wd.length) / letters > (t - cap.from) / cap.dur); // heard times when the voice was listened to
  const bars = [0, 1, 2, 3].map((i) => 0.6 + 0.9 * Math.abs(Math.sin(frame / MOTION.speakerBars + i * 1.7)));
  const glow = 80 + MOTION.glow.size * Math.sin(t / MOTION.glow.period); // the faint glow drifts, so a held frame is never dead still

  return (
    <AbsoluteFill style={{background: c.bg}}>
      {/* Kept faint on purpose: the gate fails any pixel far from the background outside the safe box. */}
      <AbsoluteFill style={{background: `radial-gradient(ellipse at ${glow}% 12%, ${c.accent}12, transparent 55%)`}} />
      {piece.scenes.map((s, i) =>
        s.clip && !bare ? (
          <Sequence key={`v${i}`} from={f(s.from)} durationInFrames={Math.max(1, f(s.dur))}>
            {/* Filmed footage steps closer on one cut and back on the next, around the face (upper middle): a jump in the cut reads as a camera change. */}
            <OffthreadVideo src={staticFile(s.clip)} style={{width: '100%', height: '100%', objectFit: 'cover', transformOrigin: '50% 38%', transform: `scale(${(s.zooms ?? []).filter((z) => z <= t).length % 2 ? s.punch ?? 1 : 1})`}} />
            <AbsoluteFill style={{background: `linear-gradient(${c.bg}99, transparent 30%, transparent 55%, ${c.bg}e6)`}} />
          </Sequence>
        ) : s.image && !bare ? (
          // A still that drifts: in on one scene, out on the next, 8% over the scene. It is the background, so it may scale.
          // Held past a few seconds it cuts once to a closer crop, off-centre (s.cut), so no picture sits still for long.
          // ponytail: the crop is 14% because the pictures are 752 px wide and already stretched; go closer with sharper pictures.
          <Sequence key={`i${i}`} from={f(s.from)} durationInFrames={Math.max(1, f(s.dur))}>
            <Img
              src={staticFile(s.image)}
              style={{
                width: '100%', height: '100%', objectFit: 'cover', transformOrigin: s.cut && t >= s.cut ? (i % 2 ? '32% 42%' : '68% 46%') : 'center',
                transform: `scale(${(s.cut && t >= s.cut ? 1.14 : 1) + MOTION.stillDrift * (i % 2 ? 1 - (t - s.from) / s.dur : (t - s.from) / s.dur)})`,
              }}
            />
            {/* Under the hook's headline the shade runs further down: a daylight picture is bright where the headline sits. */}
            <AbsoluteFill style={{background: `linear-gradient(${c.bg}${s.kind === 'hook' ? 'b3' : '99'}, ${s.kind === 'hook' ? `${c.bg}99 34%, transparent 52%` : 'transparent 28%'}, transparent 64%, ${c.bg}d9)`}} />
          </Sequence>
        ) : null,
      )}
      {piece.music ? (
        // Fades in over 12 frames, comes up once the last line is said, fades out over the last 20 (Bobble Breakdown's curve).
        <Audio
          src={staticFile(piece.music.src)}
          loop
          volume={(fr) => {
            const m = piece.music!, end = f(dur), up = Math.max(13, Math.min(f(m.up), end - 30));
            return interpolate(fr, [0, 12, up, up + 8, end - 20, end], [0, m.vol, m.vol, m.top, m.top, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          }}
        />
      ) : null}
      {piece.audio.map((a, i) => (
        <Sequence key={`a${i}`} from={f(a.from)} durationInFrames={Math.max(1, f(a.dur))}>
          <Audio src={staticFile(a.src)} trimBefore={f(a.start)} volume={a.vol} />
        </Sequence>
      ))}

      <div style={{position: 'absolute', left: safe.side, top: safe.top, width: boxW, height: boxH, display: 'flex', flexDirection: 'column', opacity: enter}}>
        {scene.kind === 'end' ? (
          end
        ) : (
          <div
            style={{
              flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: filled ? 'flex-start' : 'center', gap: 2.8 * u,
              paddingTop: filled ? boxH * 0.08 : 0, transform: `translateY(${slide}px)`,
            }}
          >
            {scene.kind === 'body' && scene.image ? null : head /* over a body picture the row is the only text above the captions */}
            {scene.kind === 'body' ? call ?? label : null}
            {over ? <div style={{flex: 1}} /> : null}
            {scene.kind === 'body' || over ? cards : null}
          </div>
        )}
        {/* Captions: a fixed band at the bottom of the safe box, so they never move the layout above. The padding keeps descenders
            and the word pill inside the box. */}
        <div style={{height: 22 * u, boxSizing: 'border-box', padding: `0 ${1.2 * u}px ${1.7 * u}px`, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', gap: 1.2 * u}}>
          {cap && cap.who ? (
            <div style={{display: 'flex', alignItems: 'center', gap: 1.2 * u, fontFamily: mono, fontWeight: 700, fontSize: 3.6 * u, color: c.accent, textShadow: shadow}}>
              {wave ? null : (
                <div style={{display: 'flex', alignItems: 'center', gap: 0.4 * u, height: 3.6 * u}}>
                  {bars.map((b, i) => (
                    <div key={i} style={{width: 0.6 * u, height: b * 2.1 * u, borderRadius: 99, background: c.accent}} />
                  ))}
                </div>
              )}
              {cap.who}
            </div>
          ) : null}
          {cap ? (
            <div
              style={{
                fontFamily: body, fontWeight: 800, fontSize: 6.4 * u, lineHeight: 1.22, color: c.text, textAlign: 'center', textWrap: 'balance',
                transform: `scale(${Math.min(1, MOTION.caption.from + (1 - MOTION.caption.from) * capP)})`, textShadow: shadow,
              }}
            >
              {capWords.map((wd, i) => (
                <React.Fragment key={i}>
                  <span style={i === said ? {background: c.accent, color: c.accentInk ?? c.bg, borderRadius: 1 * u, boxShadow: `0 0 0 ${0.7 * u}px ${c.accent}`, textShadow: 'none'} : undefined}>{wd}</span>
                  {i < capWords.length - 1 ? ' ' : ''}
                </React.Fragment>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
