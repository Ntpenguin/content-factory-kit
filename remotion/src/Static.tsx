// One static ad template set, driven by a brand.json and a piece spec.
// Layouts: plain (headline and support), phone (notification tiles), list (one card of rows), cols (two cards).
// No copy lives in this file: every word comes from the spec the gate has already checked.
import React from 'react';
import {AbsoluteFill, Img} from 'remotion';
import {font} from './fonts';

type Row = [kind: string, text: string];
type Card = {title?: string; rows: Row[]};
export type StaticProps = {
  w: number;
  h: number;
  safe: {top: number; bottom: number; side: number};
  brand: {
    colors: Record<string, string>;
    fonts: {display: string; body: string; mono: string};
    lockup: string;
    footer: string;
  };
  piece: {
    layout: string;
    chip: string;
    headline: string;
    cards: Card[];
    support: string;
    label: string;
    cta: string;
    url: string;
  };
};

export const Icon: React.FC<{kind: string; size: number; c: Record<string, string>}> = ({kind, size, c}) => {
  const color = kind === 'ok' ? c.good ?? c.accent : kind === 'miss' ? c.bad ?? c.text3 : kind === 'ring' ? c.accent : c.text3;
  const stroke = {stroke: color, strokeWidth: 2.4, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const};
  return (
    <div
      style={{
        width: size, height: size, borderRadius: size, flexShrink: 0,
        background: `${color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <svg width={size * 0.56} height={size * 0.56} viewBox="0 0 24 24">
        {kind === 'ok' ? <path d="M4 12.5l5 5L20 6.5" {...stroke} /> : null}
        {kind === 'miss' ? <path d="M6 6l12 12M18 6L6 18" {...stroke} /> : null}
        {kind === 'ring' ? (
          <path
            d="M6.6 3h3l1.5 4.2-2 1.4a12 12 0 0 0 6.3 6.3l1.4-2 4.2 1.5v3A2.6 2.6 0 0 1 18.4 20 15.4 15.4 0 0 1 4 5.6 2.6 2.6 0 0 1 6.6 3z"
            {...stroke}
          />
        ) : null}
        {kind === 'info' ? <path d="M5 12h14M13 6l6 6-6 6" {...stroke} /> : null}
      </svg>
    </div>
  );
};

export const Static: React.FC<StaticProps> = ({w, h, safe, brand, piece}) => {
  const c = brand.colors;
  const display = font(brand.fonts.display);
  const body = font(brand.fonts.body);
  const mono = font(brand.fonts.mono);
  const boxW = w - safe.side * 2;
  const boxH = h - safe.top - safe.bottom;
  const u = Math.min(boxW, boxH * 0.8) / 100;
  const hairline = `1px solid ${c.text}1f`;

  const n = piece.headline.length;
  const headSize = (n <= 20 ? 13 : n <= 30 ? 11 : 9.4) * u * (piece.layout === 'plain' ? 1.2 : 1);
  const sentences = piece.headline.split(/(?<=[.?!])\s+/);

  const rowText = (size: number): React.CSSProperties => ({
    fontFamily: body, fontWeight: 500, fontSize: size, lineHeight: 1.25, color: c.text,
  });

  const cards = piece.cards.map((card, i) => {
    const small = piece.layout === 'cols';
    const size = (small ? 3.0 : 3.5) * u;
    const second = small && i === 1;
    return (
      <div
        key={i}
        style={{
          flex: 1, display: 'flex', flexDirection: 'column', gap: piece.layout === 'phone' ? 1.3 * u : 0,
          ...(piece.layout === 'phone'
            ? {}
            : {background: c.card, border: second ? `2px solid ${c.accent}` : hairline, borderRadius: 2.4 * u, padding: `${0.6 * u}px ${2.2 * u}px`}),
        }}
      >
        {card.title ? (
          <div
            style={{
              fontFamily: mono, fontWeight: 700, fontSize: 2.3 * u, letterSpacing: 0.12 * u,
              color: second ? c.accent : c.text3, padding: `${1.6 * u}px 0 ${0.6 * u}px`,
            }}
          >
            {card.title}
          </div>
        ) : null}
        {card.rows.map(([kind, text], j) => (
          <div
            key={j}
            style={{
              display: 'flex', alignItems: 'center', gap: 1.8 * u,
              ...(piece.layout === 'phone'
                ? {background: c.card, border: hairline, borderRadius: 2.4 * u, padding: `${1.7 * u}px ${2 * u}px`}
                : {padding: `${1.5 * u}px 0`, borderTop: j > 0 ? hairline : 'none'}),
            }}
          >
            <Icon kind={kind} size={(small ? 4.4 : 5.2) * u} c={c} />
            <div style={rowText(size)}>{text}</div>
          </div>
        ))}
      </div>
    );
  });

  return (
    <AbsoluteFill style={{background: c.bg}}>
      {/* Kept faint on purpose: the gate fails any pixel far from the background outside the safe box. */}
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 80% 12%, ${c.accent}12, transparent 55%)`}} />
      <div
        style={{
          position: 'absolute', left: safe.side, top: safe.top, width: boxW, height: boxH,
          display: 'flex', flexDirection: 'column',
        }}
      >
        <div>
          {piece.chip ? (
            <div
              style={{
                display: 'inline-block', fontFamily: mono, fontWeight: 700, fontSize: 2.5 * u, letterSpacing: 0.2 * u,
                color: c.accent, border: `2px solid ${c.accent}66`, borderRadius: 99, padding: `${0.8 * u}px ${2 * u}px`,
                marginBottom: 2.4 * u, textTransform: 'uppercase',
              }}
            >
              {piece.chip}
            </div>
          ) : null}
          <div
            style={{
              fontFamily: display, fontWeight: 800, fontSize: headSize, lineHeight: 1.04, letterSpacing: -0.035 * headSize,
              color: c.text, textWrap: 'balance',
            }}
          >
            {sentences.map((s, i) => (
              <span key={i} style={{color: sentences.length > 1 && i === sentences.length - 1 ? c.accent : c.text}}>
                {s}{' '}
              </span>
            ))}
          </div>
        </div>

        <div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 2.2 * u, padding: `${2.4 * u}px 0`}}>
          {piece.label ? (
            <div style={{display: 'flex', alignItems: 'center', gap: 1 * u, fontFamily: mono, fontWeight: 500, fontSize: 2.3 * u, color: c.text2}}>
              <div style={{width: 1.1 * u, height: 1.1 * u, borderRadius: 99, background: c.accent}} />
              {piece.label}
            </div>
          ) : null}
          {cards.length ? <div style={{display: 'flex', gap: 2 * u, alignItems: 'stretch'}}>{cards}</div> : null}
          {piece.support ? (
            <div style={{fontFamily: body, fontWeight: 500, fontSize: (piece.layout === 'plain' ? 4.4 : 3.3) * u, lineHeight: 1.3, color: c.text2, textWrap: 'balance'}}>
              {piece.support}
            </div>
          ) : null}
        </div>

        <div>
          <div
            style={{
              display: 'inline-block', background: c.accent, color: c.accentInk ?? c.bg, fontFamily: body, fontWeight: 800,
              fontSize: 3.4 * u, lineHeight: 1.2, borderRadius: 2 * u, padding: `${1.7 * u}px ${2.6 * u}px`, textWrap: 'balance',
            }}
          >
            {piece.cta}
          </div>
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 2 * u}}>
            <div style={{fontFamily: mono, fontWeight: 500, fontSize: 2.7 * u, color: c.text2}}>{piece.url}</div>
            {brand.lockup ? <Img src={brand.lockup} style={{height: 5 * u}} /> : null}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
