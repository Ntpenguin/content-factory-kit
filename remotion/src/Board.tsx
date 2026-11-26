// The "board" lesson video (the look of the reel Nate sent on 2026-11-19): no person and no pictures. A dark board, the
// series name and "PART 02 / 03" with a progress bar on top, one glowing numbered card for each body beat, and the camera
// travelling down the board from the hook to each card to the end card. Captions in capitals carry every spoken line.
// The timeline is the punch video's (factory/video.py); a board scene also names its card ("part") and how the card draws
// its rows ("widget"). No widget adds a word of its own: every word on screen is in the spec and went through the gate.
import React from 'react';
import {AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import {PunchProps} from './Punch';
import {Icon} from './Static';
import {font} from './fonts';

// A card's accent colour. The example gives every part its own; `tint` picks where a video starts, so two videos open on
// different colours. The first is the brand's own accent look (teal), the rest are picked to read on a near-black card.
const PALETTE = ['#58e0d8', '#6aa9ff', '#b497ff', '#f2b84b', '#4cc38a', '#ff8ac0'];

// Every timing value of the board video. Seconds unless marked. The travel spring is over-damped on purpose: it never overshoots.
const MOTION = {
  travel: {damping: 20, stiffness: 110, mass: 0.8}, // the camera moving to the next card
  pop: {damping: 14, stiffness: 170, mass: 0.6}, // rows, chips and end-card parts landing
  wordFade: 0.14, // each sentence of the hook fades in as the voice reaches it
  overview: {first: 0.3, stagger: 0.16}, // the list of cards under the hook
  glow: {period: 2.2, low: 0.26, high: 0.5}, // a card's glow breathes, so a held frame is never dead still
  tick: 0.45, // a checklist box is ticked this long after its row lands
  dot: 1.1, // trips a second of the dot that runs down a flow arrow
  end: {stagger: 0.12, damping: 13, buttonFrom: 0.86, pulse: 0.012, pulseSpeed: 4},
  caption: {damping: 16, from: 0.9},
};

type Scene = PunchProps['piece']['scenes'][number] & {part?: string; widget?: string; reveals?: number[]; rate?: number};
type Row = PunchProps['piece']['rows'][number];
export type BoardProps = Omit<PunchProps, 'piece'> & {piece: Omit<PunchProps['piece'], 'scenes'> & {series: string; tint: number; stat?: string; source?: string; scenes: Scene[]}};

const a = (hex: string, alpha: number) => hex + Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, '0');
const two = (n: number) => String(n).padStart(2, '0');
const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};

export const Board: React.FC<BoardProps> = ({w, h, fps, dur, bare, safe, brand, piece}) => {
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
  const hairline = `1px solid ${a(c.text, 0.12)}`;
  const pop = (at: number, damping = MOTION.pop.damping) => spring({frame: frame - f(at), fps, config: {damping, stiffness: MOTION.pop.stiffness, mass: MOTION.pop.mass}});
  // A thing landing: it fades and rises into its laid-out place, never past its laid-out size.
  const land = (at: number) => {
    const p = pop(at);
    return {opacity: Math.min(1, p * 1.5), transform: `translateY(${(1 - Math.min(1, p)) * 4 * u}px) scale(${Math.min(1, 0.94 + 0.06 * p)})`};
  };

  const scenes = piece.scenes;
  const found = scenes.findIndex((s) => t >= s.from && t < s.from + s.dur);
  const si = found < 0 ? scenes.length - 1 : found;
  const scene = scenes[si];
  const parts = scenes.map((s, i) => ({...s, i})).filter((s) => s.kind === 'body');
  const tintOf = (k: number) => PALETTE[(piece.tint + k) % PALETTE.length];
  const pi = parts.findIndex((p) => p.i === si); // which card the voice is on; -1 on the hook and the end card
  const accent = pi >= 0 ? tintOf(pi) : scene.kind === 'end' ? c.accent : tintOf(0);
  // The camera: every scene has a place down the board, one screen apart; `pos` is where the camera is, in scenes.
  const pos = si === 0 ? 0 : si - 1 + spring({frame: frame - f(scene.from), fps, config: MOTION.travel});
  const headH = 12 * u;
  const capH = 25 * u;
  const viewH = boxH - headH - capH;
  const text = {fontFamily: body, fontWeight: 700, fontSize: 6.4 * u, lineHeight: 1.2, color: c.text, textWrap: 'balance' as const};
  const line = (width: string) => <div style={{width, height: 1.5 * u, borderRadius: 99, background: a(c.text, 0.1)}} />;
  const chip = (k: number, size = 3.6) => (
    <div style={{fontFamily: mono, fontWeight: 800, fontSize: size * u, lineHeight: 1, color: c.bg, background: tintOf(k), borderRadius: 0.4 * size * u, padding: `${0.24 * size * u}px ${0.42 * size * u}px`, flexShrink: 0}}>{two(k + 1)}</div>
  );

  // How a card draws its rows. Each takes the rows and the card's colour; shapes and icons only, no words but the rows'.
  const widgets: Record<string, (rows: Row[], col: string) => React.ReactNode> = {
    list: (rows) => (
      <div style={{display: 'flex', flexDirection: 'column', gap: 2.2 * u}}>
        {rows.map((r, j) => (
          <div key={j} style={{display: 'flex', alignItems: 'center', gap: 2.4 * u, background: c.bg2 ?? c.bg, border: hairline, borderRadius: 2.8 * u, padding: `${2.6 * u}px ${2.8 * u}px`, ...land(r.at)}}>
            <Icon kind={r.kind} size={9 * u} c={c} />
            <div style={text}>{r.text}</div>
          </div>
        ))}
      </div>
    ),
    phone: (rows) => (
      <div style={{alignSelf: 'center', width: 68 * u, flex: 1, border: `${0.5 * u}px solid ${a(c.text, 0.3)}`, borderRadius: 7 * u, padding: 3 * u, boxSizing: 'border-box', background: c.bg, display: 'flex', flexDirection: 'column', gap: 2 * u}}>
        <div style={{alignSelf: 'center', width: 16 * u, height: 1.6 * u, borderRadius: 99, background: a(c.text, 0.3), marginBottom: 1.5 * u}} />
        {rows.map((r, j) => (
          <div key={j} style={{display: 'flex', alignItems: 'center', gap: 2 * u, background: c.card, border: hairline, borderRadius: 2.8 * u, padding: 2.2 * u, ...land(r.at)}}>
            <Icon kind={r.kind} size={8 * u} c={c} />
            <div style={{...text, fontSize: 5.6 * u}}>{r.text}</div>
          </div>
        ))}
        <div style={{flex: 1}} />
        <div style={{alignSelf: 'center', width: 20 * u, height: 0.9 * u, borderRadius: 99, background: a(c.text, 0.3)}} />
      </div>
    ),
    steps: (rows, col) => (
      <div style={{display: 'flex', flexDirection: 'column'}}>
        {rows.map((r, j) => (
          <div key={j} style={{display: 'flex', gap: 3.2 * u}}>
            <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
              <div style={{width: 11 * u, height: 11 * u, borderRadius: 99, background: col, color: c.bg, fontFamily: display, fontWeight: 800, fontSize: 6 * u, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, ...land(r.at)}}>{j + 1}</div>
              {j < rows.length - 1 ? <div style={{width: 0.5 * u, flex: 1, minHeight: 6 * u, background: a(col, 0.5), transformOrigin: 'top', transform: `scaleY(${Math.min(1, pop(rows[j + 1].at))})`}} /> : null}
            </div>
            <div style={{...text, fontSize: 6.8 * u, paddingTop: 1.4 * u, paddingBottom: j < rows.length - 1 ? 7 * u : 0, ...land(r.at)}}>{r.text}</div>
          </div>
        ))}
      </div>
    ),
    thread: (rows, col) => (
      <div style={{display: 'flex', flexDirection: 'column', gap: 2.6 * u}}>
        {rows.map((r, j) => {
          const mine = r.kind !== 'ring'; // a ring row is the other side of the conversation
          return (
            <div
              key={j}
              style={{
                ...text, alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '84%', background: mine ? col : c.bg2 ?? c.bg, color: mine ? c.bg : c.text,
                border: mine ? 'none' : hairline, borderRadius: 3.6 * u, [mine ? 'borderBottomRightRadius' : 'borderBottomLeftRadius']: 0.8 * u,
                padding: `${2.4 * u}px ${3.2 * u}px`, ...land(r.at),
              }}
            >
              {r.text}
            </div>
          );
        })}
      </div>
    ),
    flow: (rows, col) => (
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        {rows.map((r, j) => (
          <React.Fragment key={j}>
            {j > 0 ? (
              <div style={{position: 'relative', width: 0.5 * u, height: 8 * u, background: a(col, 0.45), opacity: Math.min(1, pop(r.at) * 1.5)}}>
                <div style={{position: 'absolute', left: -0.95 * u, top: `${((t * MOTION.dot) % 1) * 100}%`, marginTop: -1.2 * u, width: 2.4 * u, height: 2.4 * u, borderRadius: 99, background: col}} />
              </div>
            ) : null}
            <div style={{alignSelf: 'stretch', display: 'flex', alignItems: 'center', gap: 2.4 * u, border: `${0.3 * u}px solid ${a(col, 0.7)}`, background: a(col, 0.08), borderRadius: 3 * u, padding: `${2.6 * u}px ${2.8 * u}px`, ...land(r.at)}}>
              <Icon kind={r.kind} size={8.5 * u} c={c} />
              <div style={text}>{r.text}</div>
            </div>
          </React.Fragment>
        ))}
      </div>
    ),
    check: (rows, col) => (
      <div style={{display: 'flex', flexDirection: 'column'}}>
        {rows.map((r, j) => {
          const done = interpolate(t - r.at - MOTION.tick, [0, 0.25], [0, 1], clamp);
          return (
            <div key={j} style={{display: 'flex', alignItems: 'center', gap: 3 * u, padding: `${3 * u}px 0`, borderBottom: j < rows.length - 1 ? hairline : 'none', ...land(r.at)}}>
              <div style={{width: 9 * u, height: 9 * u, borderRadius: 2.2 * u, border: `${0.45 * u}px solid ${col}`, background: a(col, 0.1 + 0.9 * done), boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
                <svg width={5.6 * u} height={5.6 * u} viewBox="0 0 24 24">
                  <path d="M4 12.5l5 5L20 6.5" stroke={c.bg} strokeWidth={3.4} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={24} strokeDashoffset={24 * (1 - done)} />
                </svg>
              </div>
              <div style={{...text, fontSize: 6.8 * u}}>{r.text}</div>
            </div>
          );
        })}
      </div>
    ),
    site: (rows, col) => (
      <div style={{border: `${0.3 * u}px solid ${a(c.text, 0.22)}`, borderRadius: 3.4 * u, overflow: 'hidden', background: c.bg}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 1.2 * u, padding: `${1.9 * u}px ${2.4 * u}px`, background: c.bg2 ?? c.card, borderBottom: hairline}}>
          {[c.bad, c.warn, c.good].map((dot, i) => (
            <div key={i} style={{width: 1.9 * u, height: 1.9 * u, borderRadius: 99, background: a(dot ?? c.text3, 0.75)}} />
          ))}
          <div style={{flex: 1, height: 3.4 * u, borderRadius: 99, background: a(c.text, 0.08), marginLeft: 1.6 * u}} />
        </div>
        <div style={{padding: 3.2 * u, display: 'flex', flexDirection: 'column', gap: 2.8 * u}}>
          {line('52%')}
          {rows.map((r, j) =>
            r.kind === 'ok' ? (
              <div key={j} style={{...text, alignSelf: 'flex-start', fontWeight: 800, fontSize: 5.4 * u, color: c.bg, background: col, borderRadius: 2.4 * u, padding: `${2.3 * u}px ${3.4 * u}px`, ...land(r.at)}}>{r.text}</div>
            ) : (
              <div key={j} style={{display: 'flex', flexDirection: 'column', gap: 2 * u, border: `${0.3 * u}px solid ${a(col, 0.6)}`, background: a(col, 0.07), borderRadius: 2.6 * u, padding: 2.8 * u, ...land(r.at)}}>
                <div style={text}>{r.text}</div>
                {line('70%')}
              </div>
            ),
          )}
          {line('36%')}
        </div>
      </div>
    ),
  };

  // The hook: the headline as big as its length allows, each sentence fading in as it is said, over the list of cards to come.
  const n = piece.headline.length;
  const headSize = (n <= 22 ? 14 : n <= 32 ? 12 : 10.5) * u;
  const sentences = piece.headline.split(/(?<=[.?!])\s+/);
  const accentFrom = sentences.length > 1 ? n - sentences[sentences.length - 1].length : Infinity; // the last sentence is in the accent colour
  let headAt = 0;
  const heads = (piece.head ?? [{text: piece.headline, at: 0}]).map((part) => {
    const start = headAt;
    headAt += part.text.length + 1;
    return {...part, start};
  });
  const bar = Math.min(1, spring({frame: frame - 4, fps, config: {damping: 18, stiffness: 120, mass: 0.7}}));
  const hook = (
    <div style={{margin: `0 ${3 * u}px`, display: 'flex', flexDirection: 'column'}}>
      <div style={{fontFamily: display, fontWeight: 800, fontSize: headSize, lineHeight: 1.05, letterSpacing: -0.035 * headSize, textWrap: 'balance', textShadow: `0 0 ${3 * u}px ${a(tintOf(0), 0.45)}`}}>
        {heads.map((part, i) => (
          <span key={i} style={{color: part.start >= accentFrom ? tintOf(0) : c.text, opacity: part.at <= 0 ? 1 : interpolate(t - part.at, [0, MOTION.wordFade], [0, 1], clamp)}}>{part.text} </span>
        ))}
      </div>
      <div style={{width: 26 * u * bar, height: 1 * u, borderRadius: 99, background: tintOf(0), marginTop: 3 * u}} />
      <div style={{display: 'flex', flexDirection: 'column', gap: 1.9 * u, marginTop: 6 * u}}>
        {parts.map((p, k) => (
          <div key={k} style={{display: 'flex', alignItems: 'center', gap: 2.4 * u, background: c.card, border: `${0.25 * u}px solid ${a(tintOf(k), 0.55)}`, borderRadius: 2.6 * u, padding: `${2.1 * u}px ${2.6 * u}px`, boxShadow: `0 0 ${2 * u}px ${a(tintOf(k), 0.2)}`, ...land(scenes[0].reveals?.[k] ?? MOTION.overview.first + k * MOTION.overview.stagger)}}>
            {chip(k)}
            <div style={{fontFamily: mono, fontWeight: 700, fontSize: 3.8 * u, letterSpacing: 0.25 * u, color: tintOf(k), textTransform: 'uppercase'}}>{p.part}</div>
          </div>
        ))}
      </div>
    </div>
  );

  // The opening (Nate, 2026-11-19: "a crazy stat ... something realistic then cut the graphic type videos"): a realistic clip
  // or still fills the frame, the sourced figure counts up huge over it, the headline under it; then a hard cut to the board.
  const img = scenes[0].image ?? '';
  const open = img && si === 0 ? scenes[0] : null;
  const num = /^(\d+(?:\.\d+)?)(.*)$/.exec(piece.stat ?? '');
  const counted = num ? (parseFloat(num[1]) * Math.min(1, interpolate(t, [0.15, 1.1], [0, 1], clamp))).toFixed(num[1].split('.')[1]?.length ?? 0) + num[2] : piece.stat;
  const statSize = Math.min(34, 130 / Math.max(3, (piece.stat ?? '').length)) * u;
  const opening = (
    <div style={{margin: `0 ${3 * u}px`, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 2.5 * u}}>
      <div style={{fontFamily: display, fontWeight: 800, fontSize: statSize, lineHeight: 1, letterSpacing: -0.04 * statSize, color: tintOf(0), textShadow: `0 0 ${4 * u}px ${a(tintOf(0), 0.7)}, 0 ${0.6 * u}px ${2 * u}px rgba(0,0,0,0.8)`, transform: `scale(${1.25 - 0.25 * Math.min(1, pop(0.1))})`}}>{counted}</div>
      <div style={{fontFamily: display, fontWeight: 800, fontSize: 8.6 * u, lineHeight: 1.08, color: c.text, textWrap: 'balance', textShadow: `0 ${0.5 * u}px ${2.5 * u}px rgba(0,0,0,0.9)`, ...land(0.5)}}>{piece.headline}</div>
      <div style={{fontFamily: mono, fontWeight: 700, fontSize: 3 * u, letterSpacing: 0.2 * u, color: c.text, opacity: 0.85 * Math.min(1, pop(0.9) * 1.5), textTransform: 'uppercase', background: 'rgba(0,0,0,0.45)', borderRadius: 1.5 * u, padding: `${1 * u}px ${2 * u}px`}}>Source: {piece.source}</div>
    </div>
  );

  const card = (s: Scene & {i: number}, k: number) => {
    const col = tintOf(k);
    const glow = MOTION.glow.low + (MOTION.glow.high - MOTION.glow.low) * (0.5 + 0.5 * Math.sin((t / MOTION.glow.period) * 2 * Math.PI));
    return (
      <div style={{margin: `0 ${3 * u}px`, height: viewH - 8 * u, boxSizing: 'border-box', background: `linear-gradient(${a(col, 0.12)}, ${c.card} 40%)`, border: `${0.35 * u}px solid ${a(col, 0.8)}`, borderRadius: 4.5 * u, boxShadow: `0 0 ${3 * u}px ${a(col, glow)}`, padding: 4 * u, display: 'flex', flexDirection: 'column', gap: 3.5 * u}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 2.2 * u}}>
          {chip(k, 4.4)}
          <div style={{fontFamily: mono, fontWeight: 700, fontSize: 4.3 * u, letterSpacing: 0.3 * u, color: col, textTransform: 'uppercase'}}>{s.part}</div>
        </div>
        <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
          {(widgets[s.widget ?? 'list'] ?? widgets.list)(piece.rows.filter((r) => r.scene === s.i), col)}
        </div>
      </div>
    );
  };

  // The end card: the board's cards as a row of small chips (the board seen from far), then the logo, the button, the address.
  const end = (s: Scene) => {
    const at = (i: number) => pop(s.from + MOTION.end.stagger * i, MOTION.end.damping);
    return (
      <div style={{margin: `0 ${3 * u}px`, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3.8 * u, textAlign: 'center'}}>
        <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 1.6 * u, opacity: Math.min(1, at(0) * 1.5)}}>
          {parts.map((p, k) => (
            <div key={k} style={{fontFamily: mono, fontWeight: 700, fontSize: 2.9 * u, letterSpacing: 0.2 * u, color: tintOf(k), border: `${0.25 * u}px solid ${a(tintOf(k), 0.6)}`, borderRadius: 1.8 * u, padding: `${1.2 * u}px ${1.8 * u}px`, textTransform: 'uppercase'}}>
              {two(k + 1)} {p.part}
            </div>
          ))}
        </div>
        {brand.lockup ? <Img src={brand.lockup} style={{height: 9.5 * u, opacity: Math.min(1, at(1) * 1.5)}} /> : null}
        <div
          style={{
            background: c.accent, color: c.accentInk ?? c.bg, fontFamily: body, fontWeight: 800, fontSize: 7.6 * u, lineHeight: 1.15, borderRadius: 3 * u, padding: `${3.2 * u}px ${4 * u}px`, textWrap: 'balance',
            opacity: Math.min(1, at(2) * 1.5), transform: `scale(${Math.min(1, MOTION.end.buttonFrom + (1 - MOTION.end.buttonFrom) * at(2)) * (1 - MOTION.end.pulse + MOTION.end.pulse * Math.sin((t - s.from) * MOTION.end.pulseSpeed))})`,
          }}
        >
          {piece.cta.replace(/-/g, '‑')}
        </div>
        <div style={{fontFamily: mono, fontWeight: 500, fontSize: 4.8 * u, color: c.text2, opacity: s.cut ? pop(s.cut, MOTION.end.damping) : at(3)}}>{piece.url}</div>
      </div>
    );
  };

  // Captions: capitals, the word being said in the card's colour, lit at its heard time (cap.ats); without heard words, by its share of the caption's
  // letters (off by a few frames at most).
  const cap = piece.caps.find((k) => t >= k.from && t < k.from + k.dur);
  const capWords = cap ? cap.text.split(' ') : [];
  const letters = capWords.join('').length || 1;
  let seen = 0;
  const said = !cap ? -1 : cap.ats ? cap.ats.filter((a) => a <= t - cap.from).length - 1 : capWords.findIndex((wd) => (seen += wd.length) / letters > (t - cap.from) / cap.dur); // heard times when the voice was listened to
  const capP = cap ? spring({frame: frame - f(cap.from), fps, config: {damping: MOTION.caption.damping, stiffness: MOTION.pop.stiffness, mass: MOTION.pop.mass}}) : 0;

  return (
    <AbsoluteFill style={{background: c.bg}}>
      {/* The board: a faint dot grid and a glow in the card's colour. Both stay far under what the gate counts as content outside the safe box. */}
      <AbsoluteFill style={{backgroundImage: `radial-gradient(${a(c.text, 0.07)} 1.5px, transparent 1.6px)`, backgroundSize: `${4.4 * u}px ${4.4 * u}px`}} />
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 30%, ${a(accent, 0.08)}, transparent 60%)`}} />
      {/* bare: the safe-zone check sees the frame without the footage, as in Punch */}
      {open && !bare ? (
        <AbsoluteFill style={{overflow: 'hidden'}}>
          <AbsoluteFill style={{transform: `scale(${1 + 0.08 * Math.min(1, t / open.dur)})`}}>
            {img.endsWith('.mp4') ? (
              <OffthreadVideo src={staticFile(img)} muted playbackRate={open.rate ?? 1} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            ) : (
              <Img src={staticFile(img)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            )}
          </AbsoluteFill>
          <AbsoluteFill style={{background: 'linear-gradient(rgba(0,0,0,0.2), rgba(0,0,0,0.5) 36%, rgba(0,0,0,0.15) 58%, rgba(0,0,0,0.4))'}} />
        </AbsoluteFill>
      ) : null}
      {piece.music ? (
        <Audio
          src={staticFile(piece.music.src)}
          loop
          volume={(fr) => {
            const m = piece.music!, last = f(dur), up = Math.max(13, Math.min(f(m.up), last - 30));
            return interpolate(fr, [0, 12, up, up + 8, last - 20, last], [0, m.vol, m.vol, m.top, m.top, 0], clamp);
          }}
        />
      ) : null}
      {piece.audio.map((s, i) => (
        <Sequence key={`a${i}`} from={f(s.from)} durationInFrames={Math.max(1, f(s.dur))}>
          <Audio src={staticFile(s.src)} trimBefore={f(s.start)} volume={s.vol} />
        </Sequence>
      ))}

      <div style={{position: 'absolute', left: safe.side, top: safe.top, width: boxW, height: boxH, display: 'flex', flexDirection: 'column'}}>
        <div style={{height: headH, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 1.8 * u, opacity: open ? 0 : 1}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontFamily: mono, fontWeight: 700, fontSize: 3.3 * u, letterSpacing: 0.35 * u, textTransform: 'uppercase'}}>
            <span style={{color: c.text2}}>{piece.series}</span>
            <span style={{color: accent}}>{pi >= 0 ? `Part ${two(pi + 1)} / ${two(parts.length)}` : ''}</span>
          </div>
          <div style={{display: 'flex', gap: 1.2 * u}}>
            {parts.map((p, k) => (
              <div key={k} style={{flex: 1, height: 1.1 * u, borderRadius: 99, background: a(c.text, 0.12), overflow: 'hidden'}}>
                <div style={{width: `${interpolate(t, [p.from, p.from + p.dur], [0, 100], clamp)}%`, height: '100%', borderRadius: 99, background: tintOf(k)}} />
              </div>
            ))}
          </div>
        </div>
        {/* The camera's window. It clips, so a card on its way in or out never leaves the safe box. */}
        <div style={{position: 'relative', height: viewH, overflow: 'hidden'}}>
          {scenes.map((s, i) =>
            Math.abs(i - pos) < 1 ? (
              <div key={i} style={{position: 'absolute', left: 0, top: (i - pos) * viewH, width: boxW, height: viewH, opacity: 1 - 0.7 * Math.abs(i - pos), display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
                {i === 0 ? (scenes[0].image ? (open ? opening : null) : hook) : s.kind === 'end' ? end(s) : card({...s, i}, parts.findIndex((p) => p.i === i))}
              </div>
            ) : null,
          )}
        </div>
        <div style={{height: capH, boxSizing: 'border-box', padding: `0 ${1.2 * u}px`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          {cap ? (
            <div style={{fontFamily: display, fontWeight: 800, fontSize: 7.4 * u, lineHeight: 1.12, color: c.text, textAlign: 'center', textTransform: 'uppercase', textWrap: 'balance', textShadow: open ? `0 ${0.5 * u}px ${2 * u}px rgba(0,0,0,0.9)` : undefined, transform: `scale(${Math.min(1, MOTION.caption.from + (1 - MOTION.caption.from) * capP)})`}}>
              {capWords.map((wd, i) => (
                <React.Fragment key={i}>
                  <span style={i === said ? {color: accent} : undefined}>{wd}</span>
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
