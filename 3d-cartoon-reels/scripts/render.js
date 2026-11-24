// Usage:
//   node render.js video <out.mp4> [audio.wav] [startSec] [endSec]
//   node render.js stills <outDir> t1 t2 t3 ...
//   node render.js thumb <out.png>      (calls window.renderThumb())
const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const W = 1080, H = 1920, FPS = 30;
const CHROME = process.env.CHROME_PATH || [
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
].find(p => fs.existsSync(p));

const http = require('http');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg' };
function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      const p = path.join(__dirname, decodeURIComponent(req.url.split('?')[0]));
      fs.readFile(p, (err, data) => {
        if (err) { rsp.writeHead(404); return rsp.end(); }
        rsp.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' }); rsp.end(data);
      });
    }).listen(0, '127.0.0.1', () => res(srv));
  });
}

async function open() {
  const srv = await serve();
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
      '--ignore-gpu-blocklist', '--allow-file-access-from-files', `--window-size=${W},${H}`],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  page.on('console', m => { if (m.type() === 'error') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  await page.goto(`http://127.0.0.1:${srv.address().port}/comp.html`, { waitUntil: 'load' });
  browser.on('disconnected', () => srv.close());
  await page.waitForFunction('window.ready !== undefined', { timeout: 60000 });
  await page.evaluate('window.ready');
  return { browser, page };
}

async function shot(page, t) {
  await page.evaluate(t => window.renderFrame(t), t);
  return page.screenshot({ type: 'jpeg', quality: 92, optimizeForSpeed: true });
}

(async () => {
  const [mode, out, ...rest] = process.argv.slice(2);
  const { browser, page } = await open();
  const dur = await page.evaluate('window.DURATION || 2');
  if (mode === 'stills') {
    fs.mkdirSync(out, { recursive: true });
    for (const ts of rest) {
      const buf = await shot(page, parseFloat(ts));
      fs.writeFileSync(path.join(out, `s_${parseFloat(ts).toFixed(2).padStart(6, '0')}.jpg`), buf);
    }
    console.log('stills ->', out);
  } else if (mode === 'thumb') {
    await page.evaluate('window.renderThumb()');
    fs.writeFileSync(out, await page.screenshot({ type: 'png' }));
  } else {
    const audio = rest[0] && rest[0] !== '-' ? rest[0] : null;
    const t0 = rest[1] ? parseFloat(rest[1]) : 0;
    const t1 = rest[2] ? parseFloat(rest[2]) : dur;
    const n0 = Math.round(t0 * FPS), n1 = Math.round(t1 * FPS);
    const args = ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-'];
    if (audio) args.push('-ss', String(t0), '-t', String(t1 - t0), '-i', audio);
    args.push('-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(FPS));
    if (audio) args.push('-c:a', 'aac', '-b:a', '192k', '-shortest');
    args.push(out);
    const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'ignore', 'inherit'] });
    const start = Date.now();
    for (let n = n0; n < n1; n++) {
      const buf = await shot(page, n / FPS);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if ((n - n0) % 60 === 0) console.log(`frame ${n}/${n1}  ${((Date.now() - start) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('video ->', out, `${((Date.now() - start) / 1000).toFixed(0)}s`);
  }
  await browser.close();
  process.exit(0);
})();
