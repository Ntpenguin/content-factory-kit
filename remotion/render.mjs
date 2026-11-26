// node render.mjs <jobs.json> [public folder]
// jobs: [{"id": "Static", "out": "C:/.../1x1.png", "props": {...}}]. Bundles once, renders every job.
// An .mp4 output is rendered as a video; a .png as a still (of frame job.frame, default 0).
// The public folder holds the audio and clips a video's props name; it is copied into the bundle.
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const publicDir = process.argv[3] ? path.resolve(process.argv[3]) : undefined;
const serveUrl = await bundle({entryPoint: path.join(here, 'src', 'index.ts'), ...(publicDir ? {publicDir} : {})});
let failed = 0;
for (const job of jobs) {
  try {
    const composition = await selectComposition({serveUrl, id: job.id, inputProps: job.props});
    fs.mkdirSync(path.dirname(job.out), {recursive: true});
    if (job.out.endsWith('.mp4')) {
      await renderMedia({composition, serveUrl, outputLocation: job.out, inputProps: job.props, codec: 'h264', overwrite: true});
    } else {
      await renderStill({composition, serveUrl, output: job.out, inputProps: job.props, frame: job.frame ?? 0, imageFormat: 'png', overwrite: true});
    }
    console.log('rendered', job.out);
  } catch (err) {
    failed++;
    console.error('FAILED', job.out, String(err && err.message ? err.message : err).split('\n')[0]);
  }
}
process.exit(failed ? 1 : 0);
