// The "one line" video (knowledge/editing-rules.md, "One-line style" [S17]): one continuous shot, no cuts. A single line of
// light in the brand's accent colour does every job: it slams in as the bar beside the hook, runs round the ringing phone,
// becomes the assistant's voice, lights three cards and ends as the stem of the logo. The camera follows it down a tall
// "world" of five stops. factory/line.py builds the timing from the voice files; no copy lives in this file.
import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import {Icon} from './Static';
import {font} from './fonts';
import type {PunchProps} from './Punch';

// Every timing and easing value, in one place ("Motion rules" [S16]). Seconds unless marked; sizes in layout units (u).
const MOTION = {
  flyIn: 0.25, // on frame 0 the head is this share of the screen height above the bar: on screen and already moving
  shake: {size: 1.3, decay: 9, speed: 70}, // the frame's kick on the slam and on the logo hit
  reach: 0.45, // the line leaves this long before a sound it has to land on
  sweep: 0.45, // the line crossing the assistant's card
  after: 0.35, // from the last card to the end of the stack
  trail: {perSpeed: 0.1, min: 2.5, max: 80}, // the hot streak behind the head: seconds of travel it covers, and its limits
  ink: 0.5, // opacity of the line where it has cooled into a drawn part (the bar, the phone's edge, the card rail)
  camera: {push: 0.04, drift: 0.6, driftSpeed: 0.5}, // slow push-in and drift while it holds on a stop
  blur: 1.6, // defocus of a stop one whole stop away from the camera
  phone: {rise: 0.7, from: 40, tilt: 25, shake: 1.3, shakeSpeed: 38},
  wave: {height: 7, cycles: 9, speed: 14},
  pop: {damping: 14, stiffness: 170, mass: 0.6},
  unlit: 0.28, // a card before the line reaches it
  logo: {stagger: 0.08, from: 4}, // the two bowls of the B after the stem lands
  end: {fade: 0.2, stagger: 0.12, damping: 13, buttonFrom: 0.86},
  caption: {damping: 16, from: 0.9},
  glow: {size: 6, period: 2.5},
};

export type LineProps = Pick<PunchProps, 'w' | 'h' | 'fps' | 'dur' | 'bare' | 'safe' | 'brand'> & {
  piece: {
    chip: string;
    headline: string;
    accent: string; // the end of the headline shown in the accent colour
    phone: {ringing: string; missed: string; rolled: string};
    who: string; // the name on the assistant's card
    label: string;
    cards: {text: string; at: number}[]; // three cards, each lit when the line reaches it
    cta: string;
    url: string;
    marks: {slam: number; accent: number; ring: number; missed: number; leave: number; wave: [number, number]; hero: number; end: number}; // slam: the line hits the bottom of the hook bar; accent: the headline's last words are said and take the accent colour
    camera: [number, number][]; // [second, stop 0 to 4]: where the camera is; it eases between two entries and holds between equal ones
    wave: number[]; // the recorded call's loudness, one value a frame
    caps: PunchProps['piece']['caps'];
    audio: PunchProps['piece']['audio'];
    music?: {src: string; vol: number; top: number; up: number; breath: [number, number]}; // silent in `breath`, just before the logo hit
  };
};

type Way = {x: number; y: number; r?: number; name?: string};
type Pt = {x: number; y: number; d: number};
type Key = [number, number, ((x: number) => number)?];

// The whole line as points a few pixels apart, with the distance along it at every named waypoint
// (`name` after its corner, `nameIn` before it). Corners are rounded with radius r.
const route = (ways: Way[], step: number) => {
  const pts: Pt[] = [{x: ways[0].x, y: ways[0].y, d: 0}];
  const mark: Record<string, number> = {};
  const last = () => pts[pts.length - 1];
  const push = (x: number, y: number) => {
    const a = last(), len = Math.hypot(x - a.x, y - a.y), n = Math.ceil(len / step);
    for (let i = 1; i <= n; i++) pts.push({x: a.x + ((x - a.x) * i) / n, y: a.y + ((y - a.y) * i) / n, d: a.d + (len * i) / n});
  };
  ways.forEach((b, i) => {
    if (!i) return;
    const a = ways[i - 1], c = ways[i + 1];
    const la = Math.hypot(a.x - b.x, a.y - b.y), lc = c ? Math.hypot(c.x - b.x, c.y - b.y) : 0;
    const r = Math.min(b.r ?? 0, la / 2, lc / 2);
    if (!r) {
      push(b.x, b.y);
      if (b.name) mark[b.name] = mark[`${b.name}In`] = last().d;
      return;
    }
    const p1 = {x: b.x + ((a.x - b.x) / la) * r, y: b.y + ((a.y - b.y) / la) * r};
    const p2 = {x: b.x + ((c.x - b.x) / lc) * r, y: b.y + ((c.y - b.y) / lc) * r};
    push(p1.x, p1.y);
    if (b.name) mark[`${b.name}In`] = last().d;
    for (let k = 1; k <= 8; k++) {
      const s = k / 8;
      push((1 - s) ** 2 * p1.x + 2 * (1 - s) * s * b.x + s * s * p2.x, (1 - s) ** 2 * p1.y + 2 * (1 - s) * s * b.y + s * s * p2.y);
    }
    if (b.name) mark[b.name] = last().d;
  });
  return {pts, mark};
};

// A value that moves through [time, value, easing] keys; it holds before the first and after the last.
const along = (keys: Key[], t: number) => {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, v1, ease = Easing.inOut(Easing.cubic)] = keys[i];
    const [t0, v0] = keys[i - 1];
    if (t <= t1) return t1 <= t0 ? v1 : v0 + (v1 - v0) * ease((t - t0) / (t1 - t0));
  }
  return keys[keys.length - 1][1];
};

export const Line: React.FC<LineProps> = ({w, h, fps, dur, bare, safe, brand, piece}) => {
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
  const m = piece.marks;
  const pop = (at: number, damping = MOTION.pop.damping) => spring({frame: frame - f(at), fps, config: {damping, stiffness: MOTION.pop.stiffness, mass: MOTION.pop.mass}});

  // The world: five stops one under the other, x measured from the middle. A stop's centre sits in the middle of the
  // safe box above the caption band; a stop is never taller than that space, so the next one is off screen while it holds.
  const band = 22 * u; // captions
  const cx = w / 2, cy = safe.top + (boxH - band) / 2;
  const P = boxH * 1.3; // distance between stops
  const wide = boxW - 4 * u; // content is narrower than the safe box by the camera's drift
  const xL = -wide / 2 + 1 * u; // the line's rail down the left
  const hh = 30 * u; // half the hook bar
  const pw = 50 * u, ph = 98 * u, pr = 7.5 * u, gap = 1.4 * u; // the phone, and how far outside its edge the line runs
  const cardH = 44 * u, waveY = 2 * P + 9 * u, waveX = wide / 2 - 6 * u; // the assistant's card and the line's row in it
  const rowH = 20 * u, rowGap = 3 * u, stackH = 3 * rowH + 2 * rowGap;
  const M = 56 * u, markY = 4 * P - 4 * u, stemX = -0.18 * M; // the logo mark; its stem is 18% left of centre and 60% tall

  const {pts, mark} = React.useMemo(() => {
    const top = P - ph / 2 - gap, bottom = P + ph / 2 + gap, side = pw / 2 + gap, R = pr + gap;
    return route(
      [
        {x: xL, y: -hh - 0.9 * h},
        {x: xL, y: -hh, name: 'barTop'},
        {x: xL, y: hh, name: 'barEnd'},
        {x: xL, y: top - 8 * u, r: 6 * u},
        {x: 0, y: top - 8 * u, r: 6 * u},
        {x: 0, y: top, r: 3 * u, name: 'loop'}, // once and a half round the phone, leaving from the bottom
        {x: side, y: top, r: R}, {x: side, y: bottom, r: R}, {x: -side, y: bottom, r: R}, {x: -side, y: top, r: R},
        {x: 0, y: top},
        {x: side, y: top, r: R}, {x: side, y: bottom, r: R},
        {x: 0, y: bottom, r: 3 * u, name: 'loopEnd'},
        {x: 0, y: 2 * P - cardH / 2 - 8 * u, r: 6 * u},
        {x: -waveX, y: 2 * P - cardH / 2 - 8 * u, r: 6 * u},
        {x: -waveX, y: waveY, r: 4 * u, name: 'wave'},
        {x: waveX, y: waveY, r: 4 * u, name: 'waveEnd'},
        {x: waveX, y: 3 * P - stackH / 2 - 8 * u, r: 6 * u},
        {x: xL, y: 3 * P - stackH / 2 - 8 * u, r: 6 * u},
        {x: xL, y: 3 * P - stackH / 2, name: 'rail'},
        ...[0, 1, 2].map((j) => ({x: xL, y: 3 * P - stackH / 2 + j * (rowH + rowGap) + rowH / 2, name: `card${j}`})),
        {x: xL, y: 3 * P + stackH / 2, name: 'railEnd'},
        {x: xL, y: markY - 0.3 * M - 9 * u, r: 6 * u},
        {x: stemX, y: markY - 0.3 * M - 9 * u, r: 6 * u},
        {x: stemX, y: markY - 0.3 * M, name: 'stem'},
        {x: stemX, y: markY + 0.3 * M, name: 'stemEnd'},
      ],
      0.6 * u,
    );
  }, [w, h, u, P]);

  // Where the head of the line is, as a distance along it. Everything the line does goes through this one function.
  const linear = (x: number) => x;
  const headAt = (s: number) =>
    along(
      [
        [0, mark.barTop - MOTION.flyIn * h],
        [m.slam, mark.barEnd, Easing.in(Easing.quad)],
        [m.ring - MOTION.reach, mark.barEnd],
        [m.ring, mark.loop],
        [m.missed, mark.loopEnd, linear],
        [m.leave, mark.loopEnd],
        [m.wave[0], mark.wave],
        [m.wave[0] + MOTION.sweep, mark.waveEndIn, Easing.out(Easing.cubic)],
        [m.wave[1], mark.waveEndIn],
        [piece.cards[0].at, mark.card0],
        [piece.cards[1].at, mark.card1],
        [piece.cards[2].at, mark.card2],
        [piece.cards[2].at + MOTION.after, mark.railEnd],
        [m.hero - MOTION.reach, mark.railEnd],
        [m.hero, mark.stemEnd, Easing.in(Easing.quad)],
      ],
      s,
    );
  const head = headAt(t);
  const speed = Math.abs(head - headAt(t - 1 / fps)) * fps;

  // The camera: factory/line.py says when it leaves for a stop and when it lands; while it holds it pushes in and drifts.
  const cam = MOTION.camera;
  const at = along(piece.camera, t); // which stop the camera is on, 0 to 4, fractions while it moves
  const settled = 1 - Math.min(1, Math.abs(at - Math.round(at)) * 4);
  const zoom = 1 - cam.push * (1 - settled) - 0.012 * (1 + Math.sin(t * cam.driftSpeed)) / 2; // never past 1: nothing leaves the safe box
  const kick = (from: number) => (t < from ? 0 : MOTION.shake.size * u * Math.exp(-(t - from) * MOTION.shake.decay) * Math.sin((t - from) * MOTION.shake.speed));
  const camX = cam.drift * u * Math.sin(t * cam.driftSpeed * 1.4);
  const camY = at * P + cam.drift * u * Math.sin(t * cam.driftSpeed + 1) + kick(m.slam) + kick(m.hero);

  // The line on screen. In the assistant's card it moves with the recording's own loudness.
  const env = ((piece.wave[frame - 1] ?? 0) + (piece.wave[frame] ?? 0) + (piece.wave[frame + 1] ?? 0)) / 3;
  const waveLen = mark.waveEndIn - mark.wave;
  const shape = (p: Pt) => {
    const s = (p.d - mark.wave) / waveLen;
    const lift = s > 0 && s < 1 && p.d <= head ? MOTION.wave.height * u * env * Math.sin(s * MOTION.wave.cycles * 2 * Math.PI - t * MOTION.wave.speed) * Math.sin(Math.PI * s) : 0;
    return `${(cx + (p.x - camX) * zoom).toFixed(1)},${(cy + (p.y - lift - camY) * zoom).toFixed(1)}`;
  };
  const point = (d: number): Pt => {
    let lo = 0, hi = pts.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (pts[mid].d < d) lo = mid;
      else hi = mid;
    }
    const a = pts[lo], b = pts[hi], s = b.d > a.d ? Math.min(1, Math.max(0, (d - a.d) / (b.d - a.d))) : 0;
    return {x: a.x + (b.x - a.x) * s, y: a.y + (b.y - a.y) * s, d};
  };
  const stretch = (d0: number, d1: number) => [point(d0), ...pts.filter((p) => p.d > d0 && p.d < d1), point(d1)].map(shape).join(' ');
  const landed = t >= m.hero; // the line has become the logo's stem
  const inks: [number, number, number][] = [
    [mark.barTop, mark.barEnd, 1.3], [mark.loop, mark.loopEnd, 0.8], [mark.wave, mark.waveEndIn, 0.9], [mark.rail, mark.railEnd, 1.1],
    ...(landed ? [] : ([[mark.stem, mark.stemEnd, 1.3]] as [number, number, number][])),
  ];
  const trail = Math.min(MOTION.trail.max * u, Math.max(MOTION.trail.min * u, speed * MOTION.trail.perSpeed));
  const tip = shape(point(head)).split(',').map(Number);
  const lineStyle = {fill: 'none', stroke: c.accent, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const};
  const line = bare ? null : (
    <svg width={w} height={h} style={{position: 'absolute', left: 0, top: 0}}>
      <defs>
        <filter id="soft" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={1.6 * u} />
        </filter>
      </defs>
      {inks.map(([a, b, width], i) => (head > a ? <polyline key={i} points={stretch(a, Math.min(b, head))} {...lineStyle} strokeWidth={width * u * zoom} opacity={MOTION.ink} /> : null))}
      {landed ? null : (
        <>
          <g filter="url(#soft)">
            <polyline points={stretch(head - trail, head)} {...lineStyle} strokeWidth={3.2 * u} opacity={0.55} />
            <circle cx={tip[0]} cy={tip[1]} r={2.6 * u} fill={c.accent} opacity={0.8} />
          </g>
          <polyline points={stretch(head - trail, head)} {...lineStyle} strokeWidth={0.9 * u} opacity={0.45} />
          <polyline points={stretch(head - trail * 0.5, head)} {...lineStyle} strokeWidth={1.1 * u} opacity={0.8} />
          <polyline points={stretch(head - trail * 0.2, head)} {...lineStyle} stroke={c.accent2 ?? c.accent} strokeWidth={1.3 * u} />
          <circle cx={tip[0]} cy={tip[1]} r={(0.95 + 0.15 * Math.sin(t * 6)) * u} fill="#fff" />
        </>
      )}
    </svg>
  );

  // A stop: a box in the world, centred on its place, out of focus while the camera is elsewhere.
  const stop = (i: number, height: number, children: React.ReactNode, style: React.CSSProperties = {}) => {
    const far = Math.min(1, Math.abs(at - i));
    return (
      <div
        style={{
          position: 'absolute', left: -wide / 2, top: i * P - height / 2, width: wide, height, display: 'flex', flexDirection: 'column', justifyContent: 'center',
          filter: far > 0.02 ? `blur(${(far * MOTION.blur * u).toFixed(1)}px)` : undefined, opacity: 1 - 0.5 * far, ...style,
        }}
      >
        {children}
      </div>
    );
  };

  const cut = piece.headline.length - piece.accent.length;
  const slammed = pop(m.slam, 12);
  const hook = stop(
    0,
    hh * 2,
    <div style={{paddingLeft: 6 * u, transform: `scale(${0.95 + 0.05 * Math.min(1, slammed)})`, transformOrigin: 'left center'}}>
      {piece.chip ? (
        <div style={{display: 'inline-block', fontFamily: mono, fontWeight: 700, fontSize: 3.4 * u, letterSpacing: 0.2 * u, color: c.accent, border: `2px solid ${c.accent}66`, borderRadius: 99, padding: `${0.9 * u}px ${2.2 * u}px`, marginBottom: 2.6 * u, textTransform: 'uppercase'}}>
          {piece.chip}
        </div>
      ) : null}
      <div style={{fontFamily: display, fontWeight: 800, fontSize: 14 * u, lineHeight: 1.04, letterSpacing: -0.5 * u, color: c.text}}>
        {piece.headline.slice(0, cut)}
        <span style={{color: t >= m.accent ? c.accent : c.text, textShadow: `0 0 ${3 * u * Math.max(0, 1 - (t - m.accent) * 2)}px ${t >= m.accent ? c.accent : 'transparent'}`}}>{piece.accent}</span>
      </div>
    </div>,
  );

  // The phone rises as the camera arrives, shakes while it rings, then says what happened to the call.
  const up = pop(m.ring - MOTION.phone.rise, 16);
  const ringing = t >= m.ring && t < m.missed;
  const state = t < m.missed ? piece.phone.ringing : t < m.leave ? piece.phone.missed : piece.phone.rolled;
  const stateAt = t < m.missed ? m.ring - MOTION.phone.rise : t < m.leave ? m.missed : m.leave;
  const phone = stop(
    1,
    ph,
    <div style={{alignSelf: 'center', width: pw, height: ph, perspective: 220 * u}}>
      <div
        style={{
          width: '100%', height: '100%', boxSizing: 'border-box', borderRadius: pr, background: '#000', border: `${0.5 * u}px solid ${c.text}33`, padding: 1.4 * u,
          opacity: Math.min(1, up * 1.5), transform: `translateY(${(1 - up) * MOTION.phone.from * u}px) rotateX(${(1 - up) * MOTION.phone.tilt}deg) rotate(${ringing ? MOTION.phone.shake * Math.sin(t * MOTION.phone.shakeSpeed) : 0}deg)`,
          boxShadow: `0 ${3 * u}px ${9 * u}px rgba(0,0,0,0.6)`,
        }}
      >
        <div style={{width: '100%', height: '100%', borderRadius: pr - 1.4 * u, background: c.card, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3 * u, position: 'relative'}}>
          <div style={{position: 'absolute', top: 2.2 * u, width: 13 * u, height: 3.2 * u, borderRadius: 99, background: '#000'}} />
          <div style={{transform: `scale(${ringing ? 1 + 0.06 * Math.sin(t * 12) : 1})`}}>
            <Icon kind={t < m.missed ? 'ring' : t < m.leave ? 'miss' : 'info'} size={17 * u} c={c} />
          </div>
          <div style={{fontFamily: body, fontWeight: 800, fontSize: 5.4 * u, lineHeight: 1.15, color: t >= m.leave ? c.accent : c.text, textAlign: 'center', padding: `0 ${3 * u}px`, textWrap: 'balance', opacity: Math.min(1, pop(stateAt) * 1.5)}}>
            {state}
          </div>
        </div>
      </div>
    </div>,
  );

  const answered = pop(m.wave[0] - MOTION.reach, 16);
  const assistant = stop(
    2,
    cardH,
    <div style={{height: '100%', boxSizing: 'border-box', background: c.card, border: hairline, borderRadius: 3 * u, padding: `${3 * u}px ${3.4 * u}px`, opacity: Math.min(1, answered * 1.5), transform: `scale(${0.95 + 0.05 * Math.min(1, answered)})`}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 2.6 * u}}>
        <div style={{width: 10 * u, height: 10 * u, borderRadius: 99, background: `${c.accent}26`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
          <Icon kind="ring" size={6.6 * u} c={c} />
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 0.8 * u}}>
          <div style={{fontFamily: body, fontWeight: 800, fontSize: 6 * u, lineHeight: 1.1, color: c.text}}>{piece.who}</div>
          <div style={{display: 'flex', alignItems: 'center', gap: 1.2 * u, fontFamily: mono, fontWeight: 500, fontSize: 3.6 * u, color: c.text2}}>
            <div style={{width: 1.5 * u, height: 1.5 * u, borderRadius: 99, background: c.accent}} />
            {piece.label}
          </div>
        </div>
      </div>
    </div>,
  );

  const stack = stop(
    3,
    stackH,
    <div style={{display: 'flex', flexDirection: 'column', gap: rowGap, paddingLeft: 5 * u}}>
      {piece.cards.map((card, j) => {
        const p = pop(card.at);
        const lit = Math.min(1, p * 1.5);
        return (
          <div key={j} style={{height: rowH, boxSizing: 'border-box', display: 'flex', alignItems: 'center', gap: 2.6 * u, background: c.card, border: hairline, borderRadius: 2.6 * u, padding: `0 ${3 * u}px`, opacity: MOTION.unlit + (1 - MOTION.unlit) * lit, transform: `scale(${0.96 + 0.04 * Math.min(1, p)})`, transformOrigin: 'left center', boxShadow: `inset 0 0 0 ${0.4 * u * lit}px ${c.accent}`}}>
            <Icon kind="ok" size={9.6 * u} c={c} />
            <div style={{fontFamily: body, fontWeight: 700, fontSize: 6.6 * u, lineHeight: 1.2, color: c.text}}>{card.text}</div>
          </div>
        );
      })}
    </div>,
  );

  // The logo: the line is its stem. On the hit the stem swells to full width and the two bowls of the B slide in.
  // The shapes are the brand's own mark (assets/mark-on-dark.svg), moved and faded only. Then the end card takes its place.
  const hit = pop(m.hero, 12);
  const bowl = (i: number) => pop(m.hero + MOTION.logo.stagger * (i + 1), 15);
  const out = interpolate(t, [m.end, m.end + MOTION.end.fade], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const land = (i: number) => pop(m.end + MOTION.end.stagger * i, MOTION.end.damping);
  const hero = (
    <>
      {landed ? (
        <svg viewBox="0 0 100 100" style={{position: 'absolute', left: -M / 2, top: markY - M / 2, width: M, height: M, opacity: out, overflow: 'visible'}}>
          <rect x={32 - 8 * Math.min(1, 0.15 + 0.85 * hit)} y={20} width={16 * Math.min(1, 0.15 + 0.85 * hit)} height={60} rx={3} fill={c.accent} />
          <path d="M46 20h12a13.5 13.5 0 0 1 0 27H46z" fill="#fff" opacity={Math.min(1, bowl(0) * 1.5)} transform={`translate(${-(1 - Math.min(1, bowl(0))) * MOTION.logo.from} 0)`} />
          <path d="M46 53h17a13.5 13.5 0 0 1 0 27H46z" fill="#fff" opacity={Math.min(1, bowl(1) * 1.5)} transform={`translate(${-(1 - Math.min(1, bowl(1))) * MOTION.logo.from} 0)`} />
        </svg>
      ) : null}
      {t >= m.end
        ? stop(
            4,
            boxH - band,
            <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3.6 * u, textAlign: 'center'}}>
              {brand.lockup ? <Img src={brand.lockup} style={{height: 12 * u, opacity: Math.min(1, land(0) * 1.5)}} /> : null}
              <div style={{background: c.accent, color: c.accentInk ?? c.bg, fontFamily: body, fontWeight: 800, fontSize: 8 * u, lineHeight: 1.15, borderRadius: 3 * u, padding: `${3.2 * u}px ${4 * u}px`, textWrap: 'balance', opacity: Math.min(1, land(1) * 1.5), transform: `scale(${Math.min(1, MOTION.end.buttonFrom + (1 - MOTION.end.buttonFrom) * land(1))})`}}>
                {piece.cta.replace(/-/g, '‑')}
              </div>
              <div style={{fontFamily: mono, fontWeight: 500, fontSize: 4.8 * u, color: c.text2, opacity: Math.min(1, land(3))}}>{piece.url}</div>
            </div>,
          )
        : null}
    </>
  );

  // Captions, as in the punch video: a fixed band at the bottom of the safe box, the word being said on an accent pill.
  const cap = piece.caps.find((k) => t >= k.from && t < k.from + k.dur);
  const capP = cap ? pop(cap.from, MOTION.caption.damping) : 0;
  const capWords = cap ? cap.text.split(' ') : [];
  const letters = capWords.join('').length || 1;
  let seen = 0;
  const said = !cap ? -1 : cap.ats ? cap.ats.filter((a) => a <= t - cap.from).length - 1 : capWords.findIndex((wd) => (seen += wd.length) / letters > (t - cap.from) / cap.dur); // heard times when the voice was listened to
  const glow = 80 + MOTION.glow.size * Math.sin(t / MOTION.glow.period);

  return (
    <AbsoluteFill style={{background: c.bg}}>
      <AbsoluteFill style={{background: `radial-gradient(ellipse at ${glow}% 12%, ${c.accent}12, transparent 55%)`}} />
      {piece.music ? (
        <Audio
          src={staticFile(piece.music.src)}
          loop
          volume={(fr) => {
            const mu = piece.music!, end = f(dur), up2 = Math.max(13, Math.min(f(mu.up), end - 30)), b0 = f(mu.breath[0]), b1 = f(mu.breath[1]);
            const bed = interpolate(fr, [0, 12, up2, up2 + 8, end - 20, end], [0, mu.vol, mu.vol, mu.top, mu.top, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return bed * interpolate(fr, [b0, b0 + 5, b1 - 1, b1 + 3], [1, 0, 0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          }}
        />
      ) : null}
      {piece.audio.map((a, i) => (
        <Sequence key={`a${i}`} from={f(a.from)} durationInFrames={Math.max(1, f(a.dur))}>
          <Audio src={staticFile(a.src)} trimBefore={f(a.start)} volume={a.vol} />
        </Sequence>
      ))}

      <div style={{position: 'absolute', left: 0, top: 0, transformOrigin: '0 0', transform: `translate(${cx}px, ${cy}px) scale(${zoom}) translate(${-camX}px, ${-camY}px)`}}>
        {hook}
        {phone}
        {assistant}
        {stack}
        {hero}
      </div>
      {line}
      {/* The floor: whatever the camera is travelling past fades out under the captions, so they are never read over a moving object. */}
      <div style={{position: 'absolute', left: 0, top: safe.top + boxH - band - 8 * u, width: w, height: h - (safe.top + boxH - band - 8 * u), background: `linear-gradient(${c.bg}00, ${c.bg}f2 ${14 * u}px, ${c.bg})`}} />

      <div style={{position: 'absolute', left: safe.side, top: safe.top + boxH - band, width: boxW, height: band, boxSizing: 'border-box', padding: `0 ${1.2 * u}px ${1.7 * u}px`, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', gap: 1.2 * u}}>
        {cap && cap.who ? <div style={{fontFamily: mono, fontWeight: 700, fontSize: 3.6 * u, color: c.accent}}>{cap.who}</div> : null}
        {cap ? (
          <div style={{fontFamily: body, fontWeight: 800, fontSize: 6.4 * u, lineHeight: 1.22, color: c.text, textAlign: 'center', textWrap: 'balance', transform: `scale(${Math.min(1, MOTION.caption.from + (1 - MOTION.caption.from) * capP)})`, textShadow: `0 0 ${2 * u}px ${c.bg}`}}>
            {capWords.map((wd, i) => (
              <React.Fragment key={i}>
                <span style={i === said ? {background: c.accent, color: c.accentInk ?? c.bg, borderRadius: 1 * u, boxShadow: `0 0 0 ${0.7 * u}px ${c.accent}`, textShadow: 'none'} : undefined}>{wd}</span>
                {i < capWords.length - 1 ? ' ' : ''}
              </React.Fragment>
            ))}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
