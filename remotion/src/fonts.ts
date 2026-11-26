// Fonts a brand.json may name. Adding a font is one import and one entry here.
import {loadFont as inter} from '@remotion/google-fonts/Inter';
import {loadFont as jetBrainsMono} from '@remotion/google-fonts/JetBrainsMono';
import {loadFont as fraunces} from '@remotion/google-fonts/Fraunces';

const LOADERS: Record<string, typeof inter> = {
  Inter: inter,
  'JetBrains Mono': jetBrainsMono as typeof inter,
  Fraunces: fraunces as typeof inter,
};

export const font = (name: string): string => {
  const load = LOADERS[name];
  if (!load) {
    throw new Error(`Font "${name}" is not in remotion/src/fonts.ts. Add an import and an entry there.`);
  }
  return load('normal', {weights: ['400', '500', '700', '800'], subsets: ['latin']}).fontFamily;
};
