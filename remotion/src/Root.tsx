import React from 'react';
import {Composition} from 'remotion';
import {Board, BoardProps} from './Board';
import {Line, LineProps} from './Line';
import {Punch, PunchProps} from './Punch';
import {Static, StaticProps} from './Static';
import {Talk, TalkProps} from './Talk';

// Every value comes from the job file factory/statics.py or factory/video.py writes; these defaults only keep the studio from crashing.
const demo: StaticProps = {
  w: 1080,
  h: 1080,
  safe: {top: 54, bottom: 54, side: 54},
  brand: {
    colors: {bg: '#101010', card: '#1c1c1c', text: '#ffffff', text2: '#bbbbbb', text3: '#888888', accent: '#58e0d8', accentInk: '#04201f', good: '#4cc38a', bad: '#f2777a'},
    fonts: {display: 'Inter', body: 'Inter', mono: 'JetBrains Mono'},
    lockup: '',
    footer: 'example.com',
  },
  piece: {layout: 'plain', chip: '', headline: 'Placeholder. Not an ad.', cards: [], support: '', label: '', cta: 'Placeholder', url: 'example.com'},
};

const demoVideo: PunchProps = {
  w: 1080, h: 1920, fps: 30, dur: 2, bare: false, safe: {top: 270, bottom: 384, side: 65}, brand: demo.brand,
  piece: {
    chip: '', headline: 'Placeholder. Not an ad.', label: '', cta: 'Placeholder', url: 'example.com',
    scenes: [{from: 0, dur: 2, kind: 'hook', clip: ''}], rows: [], caps: [], audio: [],
  },
};

const demoBoard: BoardProps = {
  ...demoVideo,
  piece: {...demoVideo.piece, series: 'Placeholder', tint: 0, scenes: [{from: 0, dur: 2, kind: 'hook', clip: ''}]},
};

const demoLine: LineProps = {
  w: 1080, h: 1920, fps: 30, dur: 8, bare: false, safe: demoVideo.safe, brand: demo.brand,
  piece: {
    chip: '', headline: 'Placeholder. Not an ad.', accent: 'Not an ad.', phone: {ringing: 'Ringing', missed: 'Missed', rolled: 'Rolled'}, who: 'Placeholder', label: '',
    cards: [{text: 'One', at: 5}, {text: 'Two', at: 5.4}, {text: 'Three', at: 5.8}], cta: 'Placeholder', url: 'example.com',
    marks: {slam: 0.17, accent: 1, ring: 1.5, missed: 2.5, leave: 3, wave: [3.5, 4.5], hero: 7, end: 7.6},
    camera: [[0, 0], [0.5, 0], [1.4, 1], [3.1, 1], [3.6, 2], [4.4, 2], [5.2, 3], [6.4, 3], [7, 4]],
    wave: [], caps: [], audio: [],
  },
};

const demoTalk: TalkProps = {w: 1080, h: 1920, fps: 30, dur: 2, talk: '', clip: '', lockup: '', shots: [{from: 0, layout: 'full'}], caps: [], plate: {from: 0, to: 0}, marks: {}};

export const Root: React.FC = () => (
  <>
    <Composition
      id="Static"
      component={Static}
      durationInFrames={1}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={demo}
      calculateMetadata={({props}) => ({width: props.w, height: props.h})}
    />
    <Composition
      id="Punch"
      component={Punch}
      durationInFrames={60}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={demoVideo}
      calculateMetadata={({props}) => ({width: props.w, height: props.h, fps: props.fps, durationInFrames: Math.max(1, Math.round(props.dur * props.fps))})}
    />
    <Composition
      id="Board"
      component={Board}
      durationInFrames={60}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={demoBoard}
      calculateMetadata={({props}) => ({width: props.w, height: props.h, fps: props.fps, durationInFrames: Math.max(1, Math.round(props.dur * props.fps))})}
    />
    <Composition
      id="Line"
      component={Line}
      durationInFrames={240}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={demoLine}
      calculateMetadata={({props}) => ({width: props.w, height: props.h, fps: props.fps, durationInFrames: Math.max(1, Math.round(props.dur * props.fps))})}
    />
    <Composition
      id="Talk"
      component={Talk}
      durationInFrames={60}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={demoTalk}
      calculateMetadata={({props}) => ({width: props.w, height: props.h, fps: props.fps, durationInFrames: Math.max(1, Math.round(props.dur * props.fps))})}
    />
  </>
);
