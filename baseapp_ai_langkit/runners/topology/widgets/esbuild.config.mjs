import { build } from 'esbuild';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const staticDir = resolve(__dirname, '..', '..', 'static');

const jsOut = resolve(staticDir, 'runner_topology_widget.js');

mkdirSync(staticDir, { recursive: true });

await build({
  entryPoints: [resolve(__dirname, 'src', 'mount.tsx')],
  bundle: true,
  format: 'iife',
  globalName: 'RunnerTopologyWidget',
  outfile: jsOut,
  platform: 'browser',
  target: ['es2020'],
  jsx: 'automatic',
  loader: { '.css': 'css' },
  minify: true,
  sourcemap: false,
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
});

console.log(`Built ${jsOut}`);
console.log(
  `Built ${jsOut.replace(/\.js$/, '.css')} (sibling emitted by esbuild)`,
);
