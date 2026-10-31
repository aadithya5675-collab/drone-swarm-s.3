import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
import fs from 'node:fs';
import path from 'node:path';

// The app is built straight into sim/dashboard/ (served by `python3 -m http.server 8080 --directory dashboard`),
// next to the data it reads: replays/, terrain.json, valley.json. Old hashed bundles are removed first.
const DASH = path.resolve(__dirname, '..');

function cleanAssets(): Plugin {
  return { name: 'clean-assets', apply: 'build', buildStart() { fs.rmSync(path.join(DASH, 'assets'), { recursive: true, force: true }); } };
}
// dev server: serve the dashboard's data files from the parent folder
function dashData(): Plugin {
  return {
    name: 'dash-data', apply: 'serve',
    configureServer(s) {
      s.middlewares.use((req, res, next) => {
        const u = decodeURIComponent((req.url || '').split('?')[0]);
        if (/^\/(replays\/|terrain\.json|valley\.json|valley\.jpg)/.test(u)) {
          const f = path.join(DASH, u);
          if (fs.existsSync(f)) { res.setHeader('Content-Length', fs.statSync(f).size); fs.createReadStream(f).pipe(res); return; }
        }
        next();
      });
    }
  };
}

export default defineConfig({
  base: './',
  plugins: [react(), tailwind(), cleanAssets(), dashData()],
  build: {
    outDir: DASH, emptyOutDir: false, assetsDir: 'assets', chunkSizeWarningLimit: 1600,
    rollupOptions: { input: { story: path.resolve(__dirname, 'story.html'), index: path.resolve(__dirname, 'index.html') } }
  }
});
