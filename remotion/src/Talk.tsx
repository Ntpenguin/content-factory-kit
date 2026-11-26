// A talking-head edit: Nate's cut footage with a graphic on every beat (knowledge/editing-rules.md, "Talking-head edits").
// Layouts: split (graphic on top, face below, captions on the seam), full (face, slow push), punch (face close), graphic (full screen).
// The timeline (shots, captions, marks) comes from tmp/shoot1/v2/build.py; no copy is decided here except the mock-ups' labels.
import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import {font} from './fonts';

const C = {bg: '#08090a', bg2: '#131417', card: '#1a1c20', text: '#f7f8f8', text2: '#b4b8c0', text3: '#8a8f98', accent: '#58e0d8', ink: '#04201f', good: '#4cc38a', bad: '#f2777a'};
const SEAM = 880; // the split line
const ZOOM: Record<string, number> = {missed: 1.25, loop: 1.25, forward: 1, reply: 1.15, brand: 1.2, cta: 1.3}; // mock-ups are laid out small, then scaled to fill the panel
const CAP_COL: Record<string, string> = {w: C.text, r: C.bad, t: C.accent, g: C.good};

export type TalkProps = {
  w: number; h: number; fps: number; dur: number;
  talk: string; clip: string; lockup: string;
  shots: {from: number; layout: 'split' | 'full' | 'punch' | 'graphic'; g?: string}[];
  caps: {from: number; to: number; text: string; col: string; words?: {w: string; at: number}[]}[]; // words: the one being said is lit
  plate: {from: number; to: number};
  marks: Record<string, number>;
};

export const Talk: React.FC<TalkProps> = ({fps, talk, clip, lockup, shots, caps, plate, marks}) => {
  const frame = useCurrentFrame();
  const t = frame / fps;
  const inter = font('Inter');
  const mono = font('JetBrains Mono');
  let si = 0;
  shots.forEach((s, i) => { if (t >= s.from) si = i; });
  const shot = shots[si];
  const lt = t - shot.from; // time into this shot
  const end = si + 1 < shots.length ? shots[si + 1].from : shot.from + 4;
  const sp = (at: number, damping = 14) => spring({frame: Math.round((lt - at) * fps), fps, config: {damping, stiffness: 170, mass: 0.6}});
  const enter = sp(0);
  const L = shot.layout;

  // The face: one video, framed per layout. Face centre sits about x 540, y 1130 of the source frame.
  const push = interpolate(t - shot.from, [0, end - shot.from], [0, 1], {extrapolateRight: 'clamp'});
  const kick = interpolate(lt, [0, 0.18], [1.05, 1], {extrapolateRight: 'clamp'}); // every cut lands with a small settle
  const face = L === 'split'
    ? {top: SEAM, height: 1920 - SEAM, y: -650, s: (1.12 + 0.04 * push) * kick}
    : L === 'punch' ? {top: 0, height: 1920, y: -40, s: (1.42 + 0.05 * push) * kick}
    : {top: 0, height: 1920, y: -120, s: (1.28 + 0.06 * push) * kick};

  const cap = caps.find((c) => t >= c.from && t < c.to);
  const capY = L === 'split' ? SEAM : L === 'graphic' ? 1500 : 1440;

  const box = (extra: React.CSSProperties = {}): React.CSSProperties => ({background: C.card, border: `2px solid ${C.text}1f`, borderRadius: 28, ...extra});
  const label = (text: string) => <div style={{fontFamily: mono, fontSize: 26, color: C.text3, letterSpacing: 2, textTransform: 'uppercase'}}>{text}</div>;
  const source = (text: string) => <div style={{fontFamily: inter, fontSize: 28, fontWeight: 500, color: C.text2, marginTop: 18}}>{text}</div>;
  const count = (to: number, d = 0.7) => Math.round(interpolate(lt, [0.05, d], [0, to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: (x) => 1 - Math.pow(1 - x, 3)}));
  const rise = (at: number) => { const p = sp(at); return {opacity: Math.min(1, p * 1.5), transform: `translateY(${(1 - p) * 40}px) scale(${0.92 + 0.08 * p})`}; };
  const example = <div style={{position: 'absolute', right: 40, top: 40, fontFamily: mono, fontSize: 24, color: C.text3, border: `1px solid ${C.text3}`, borderRadius: 8, padding: '4px 12px'}}>EXAMPLE</div>;

  const phone = (children: React.ReactNode, scale = 1) => (
    <div style={{width: 340 * scale, height: 640 * scale, borderRadius: 54 * scale, background: '#000', border: `6px solid #2a2d33`, position: 'relative', overflow: 'hidden', boxShadow: '0 30px 80px rgba(0,0,0,0.6)'}}>
      <div style={{position: 'absolute', top: 14 * scale, left: '50%', width: 100 * scale, height: 28 * scale, marginLeft: -50 * scale, borderRadius: 20, background: '#111'}} />
      <div style={{position: 'absolute', inset: 0, paddingTop: 70 * scale, display: 'flex', flexDirection: 'column', alignItems: 'center', fontFamily: inter, color: C.text}}>{children}</div>
    </div>
  );
  const ring = (at = 0) => 1 + 0.04 * Math.sin((lt - at) * 28) * (lt > at ? 1 : 0);

  const graphic = (g: string): React.ReactNode => {
    switch (g) {
      case 'stat82': // the hook: AI truck clip under a count-up of CallRail's figure, on frame 0
        return (
          <AbsoluteFill>
            <OffthreadVideo src={staticFile(clip)} muted style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${1.05 + 0.06 * lt / 5})`}} />
            <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(8,9,10,0.35), rgba(8,9,10,0.85))'}} />
            <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', padding: 60, textAlign: 'center'}}>
              <div style={{fontFamily: inter, fontWeight: 800, fontSize: 260, lineHeight: 1, color: C.bad, letterSpacing: -8, transform: `scale(${interpolate(lt, [0, 0.25], [1.08, 1], {extrapolateRight: 'clamp'})})`}}>82%</div>
              <div style={{fontFamily: inter, fontWeight: 800, fontSize: 54, color: C.text, marginTop: 10, lineHeight: 1.15}}>say they'll call a competitor<br />if you don't answer</div>
              {source('Source: CallRail, survey of 1,000 U.S. consumers')}
            </AbsoluteFill>
          </AbsoluteFill>
        );
      case 'missed': { // missed calls stacking up
        const n = Math.min(4, Math.floor(lt / 0.32) + 1);
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
            <div style={{display: 'flex', flexDirection: 'column', gap: 18, width: 760}}>
              {Array.from({length: n}).map((_, i) => (
                <div key={i} style={{...box({padding: '22px 30px', display: 'flex', alignItems: 'center', gap: 24}), ...rise(i * 0.32)}}>
                  <div style={{width: 64, height: 64, borderRadius: 32, background: `${C.bad}26`, color: C.bad, fontSize: 38, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: inter, fontWeight: 800}}>✕</div>
                  <div style={{fontFamily: inter, flex: 1}}>
                    <div style={{fontSize: 40, fontWeight: 800, color: C.text}}>Missed call</div>
                    <div style={{fontSize: 28, color: C.text3}}>(512) ••• ••{(17 + i * 23) % 100}</div>
                  </div>
                  <div style={{fontFamily: mono, fontSize: 26, color: C.text3}}>{['now', '2m', '9m', '14m'][i]}</div>
                </div>
              ))}
            </div>
          </AbsoluteFill>
        );
      }
      case 'loop': // two fixes, the second hidden until later
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 34}}>
            <div style={{fontFamily: inter, fontWeight: 800, fontSize: 92, color: C.text, ...rise(0)}}>2 FIXES</div>
            <div style={{display: 'flex', gap: 30}}>
              <div style={{...box({width: 380, height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}), ...rise(0.15)}}>
                {label('Fix 1')}
                <div style={{fontFamily: inter, fontWeight: 800, fontSize: 46, color: C.accent, marginTop: 12}}>Forward</div>
              </div>
              <div style={{...box({width: 380, height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', borderColor: C.accent}), ...rise(0.3)}}>
                {label('Fix 2')}
                <div style={{fontFamily: inter, fontWeight: 800, fontSize: 46, color: C.text, marginTop: 12, filter: 'blur(14px)'}}>Settings</div>
                <div style={{fontFamily: inter, fontSize: 30, color: C.text2, marginTop: 14}}>already on your phone</div>
              </div>
            </div>
          </AbsoluteFill>
        );
      case 'brand':
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
            <div style={{...box({padding: '60px 70px'}), ...rise(0)}}><Img src={staticFile(lockup)} style={{width: 640}} /></div>
          </AbsoluteFill>
        );
      case 'vm42': { // 42 of 100 callers leave a voicemail
        const lit = count(42, 0.9);
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 50}}>
              <div style={{display: 'grid', gridTemplateColumns: 'repeat(10, 34px)', gap: 10}}>
                {Array.from({length: 100}).map((_, i) => (
                  <div key={i} style={{width: 34, height: 34, borderRadius: 17, background: i < lit ? C.accent : '#2a2d33'}} />
                ))}
              </div>
              <div style={{textAlign: 'left'}}>
                <div style={{fontFamily: inter, fontWeight: 800, fontSize: 170, color: C.accent, lineHeight: 1}}>{lit}%</div>
                <div style={{fontFamily: inter, fontWeight: 800, fontSize: 46, color: C.text}}>leave a<br />voicemail</div>
              </div>
            </div>
            {source('Source: CallRail, survey of 1,000 U.S. consumers')}
          </AbsoluteFill>
        );
      }
      case 'fix1':
      case 'fix2':
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', background: `radial-gradient(circle at 50% 40%, ${C.accent}22, ${C.bg} 60%)`}}>
            <div style={{fontFamily: mono, fontSize: 40, color: C.accent, letterSpacing: 8, ...rise(0)}}>{g === 'fix1' ? 'FIX 1' : 'FIX 2'}</div>
            <div style={{fontFamily: inter, fontWeight: 800, fontSize: 112, color: C.text, textAlign: 'center', lineHeight: 1.02, marginTop: 20, padding: '0 60px', ...rise(0.1)}}>
              {g === 'fix1' ? <>Forward the<br />calls you miss</> : <>Answer<br />with a text</>}
            </div>
          </AbsoluteFill>
        );
      case 'forward': { // phone A rings, the call hops to phone B
        const hop = interpolate(lt, [0.6, 1.1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 40}}>
              <div style={{transform: `scale(${hop < 1 ? ring() : 1})`, opacity: 1 - 0.5 * hop}}>{phone(<><div style={{fontSize: 34, color: C.text2}}>Your phone</div><div style={{fontSize: 46, fontWeight: 800, marginTop: 20}}>{hop < 1 ? 'Ringing…' : 'No answer'}</div></>, 0.85)}</div>
              <div style={{width: 160, height: 8, background: '#2a2d33', borderRadius: 4, position: 'relative'}}>
                <div style={{width: `${hop * 100}%`, height: 8, background: C.accent, borderRadius: 4}} />
                <div style={{position: 'absolute', right: -14, top: -16, fontSize: 40, color: C.accent, opacity: hop}}>▶</div>
              </div>
              <div style={{transform: `scale(${hop >= 1 ? ring(1.1) : 1})`, opacity: 0.5 + 0.5 * hop}}>{phone(<><div style={{fontSize: 34, color: C.text2}}>Second number</div><div style={{fontSize: 46, fontWeight: 800, marginTop: 20, color: hop >= 1 ? C.good : C.text3}}>{hop >= 1 ? 'Ringing…' : '—'}</div></>, 0.85)}</div>
            </div>
          </AbsoluteFill>
        );
      }
      case 'reply': { // incoming call with the text-reply option, Android's name highlighted on its word
        const android = marks.android !== undefined && t >= marks.android;
        const row = (name: string, on: boolean, at: number) => (
          <div style={{...box({padding: '20px 26px', width: 520, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderColor: on ? C.accent : `${C.text}1f`}), ...rise(at)}}>
            <div style={{fontFamily: inter, fontWeight: 800, fontSize: 36, color: on ? C.accent : C.text}}>{name}</div>
            <div style={{fontFamily: mono, fontSize: 24, color: C.text3}}>{on ? '✓' : ''}</div>
          </div>
        );
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 34}}>
              <div style={{transform: `scale(${ring()})`}}>{phone(<><div style={{fontSize: 30, color: C.text2}}>Incoming call</div><div style={{fontSize: 44, fontWeight: 800, marginTop: 14}}>(512) •••</div><div style={{marginTop: 260, fontSize: 28, color: C.accent, border: `2px solid ${C.accent}`, borderRadius: 30, padding: '10px 22px'}}>💬 Message</div></>, 0.85)}</div>
              <div style={{display: 'flex', flexDirection: 'column', gap: 18}}>
                <div style={{fontFamily: mono, fontSize: 26, color: C.text3}}>IPHONE</div>
                {row('Respond with Text', !android, 0.1)}
                <div style={{fontFamily: mono, fontSize: 26, color: C.text3, marginTop: 12}}>ANDROID</div>
                {row('Quick responses', android, 0.25)}
              </div>
            </div>
          </AbsoluteFill>
        );
      }
      case 'assistant': { // the phone rings, then the assistant picks up
        const answered = marks.answers !== undefined && t >= marks.answers;
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
            <div style={{transform: `scale(${1.15 * (answered ? 1 : ring())})`}}>
              {phone(answered ? (
                <>
                  <div style={{fontSize: 30, color: C.good}}>Assistant answered</div>
                  <div style={{fontSize: 44, fontWeight: 800, marginTop: 14}}>00:0{Math.min(9, Math.floor(t - marks.answers))}</div>
                  <div style={{display: 'flex', gap: 8, alignItems: 'center', height: 160, marginTop: 60}}>
                    {Array.from({length: 11}).map((_, i) => <div key={i} style={{width: 12, borderRadius: 6, background: C.accent, height: 30 + 90 * Math.abs(Math.sin(frame * 0.35 + i * 0.9))}} />)}
                  </div>
                </>
              ) : (
                <><div style={{fontSize: 30, color: C.text2}}>Incoming call</div><div style={{fontSize: 44, fontWeight: 800, marginTop: 14}}>Ringing…</div></>
              ))}
            </div>
          </AbsoluteFill>
        );
      }
      case 'cta':
        return (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 34}}>
            <div style={rise(0)}><Img src={staticFile(lockup)} style={{width: 620}} /></div>
            <div style={{fontFamily: inter, fontWeight: 800, fontSize: 52, color: C.ink, background: C.accent, borderRadius: 999, padding: '22px 52px', ...rise(0.15)}}>builtwithbaron.com</div>
          </AbsoluteFill>
        );
      default:
        return null;
    }
  };

  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: 'absolute', left: 0, right: 0, top: face.top, height: face.height, overflow: 'hidden', opacity: L === 'graphic' ? 0 : 1}}>
        <OffthreadVideo src={staticFile(talk)} muted style={{position: 'absolute', left: 0, top: face.y, width: 1080, height: 1920, transformOrigin: '540px 1130px', transform: `scale(${face.s})`}} />
      </div>
      {L === 'split' && shot.g ? (
        <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: SEAM, overflow: 'hidden', background: `radial-gradient(circle at 50% 45%, ${C.accent}1c, ${C.bg} 65%)`, opacity: si === 0 ? 1 : Math.min(1, enter * 1.6)}}>
          <AbsoluteFill style={{transform: `scale(${ZOOM[shot.g] ?? 1})`}}>{graphic(shot.g)}</AbsoluteFill>
          {['forward', 'reply', 'assistant'].includes(shot.g) ? example : null}
        </div>
      ) : null}
      {L === 'graphic' && shot.g ? <AbsoluteFill style={{background: C.bg}}>{graphic(shot.g)}</AbsoluteFill> : null}
      {L === 'split' ? <div style={{position: 'absolute', left: 0, right: 0, top: SEAM - 2, height: 4, background: C.accent}} /> : null}
      {t >= plate.from && t < plate.to ? (
        <div style={{position: 'absolute', left: 60, top: 1180, ...box({padding: '20px 30px'}), ...(() => { const p = spring({frame: frame - Math.round(plate.from * fps), fps, config: {damping: 14}}); return {opacity: p, transform: `translateX(${(1 - p) * -60}px)`}; })()}}>
          <div style={{fontFamily: inter, fontWeight: 800, fontSize: 48, color: C.text}}>Nate Baron</div>
          <div style={{fontFamily: inter, fontWeight: 500, fontSize: 32, color: C.accent}}>Built with Baron · Austin</div>
        </div>
      ) : null}
      {cap ? (
        <div style={{position: 'absolute', left: 0, right: 0, top: capY, display: 'flex', justifyContent: 'center', transform: 'translateY(-50%)'}}>
          <div style={{fontFamily: inter, fontWeight: 800, fontSize: 68, lineHeight: 1.05, textTransform: 'uppercase', color: C.text, background: 'rgba(8,9,10,0.88)', border: `2px solid ${C.text}33`, borderRadius: 18, padding: '14px 30px', maxWidth: 900, textAlign: 'center'}}>
            {(cap.words ?? [{w: cap.text, at: cap.from}]).map((wd, i, ws) => {
              // the word being said: lit in the chunk's colour (teal when the chunk has none) and a touch bigger; the rest stay white
              const on = t >= wd.at && (i + 1 >= ws.length || t < ws[i + 1].at);
              return <span key={i} style={{display: 'inline-block', margin: '0 0.22em', color: on ? (cap.col === 'w' ? C.accent : CAP_COL[cap.col]) : C.text, transform: `scale(${on ? 1.06 : 1})`}}>{wd.w}</span>;
            })}
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
