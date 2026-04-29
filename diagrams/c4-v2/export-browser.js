// Headless PNG/SVG export через Structurizr scripting API.
// Запускается в docker-контейнере ghcr.io/puppeteer/puppeteer с host network либо host.docker.internal.
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const VIEWS = [
  'Context',
  'Containers',
  'Overview',
  'PolicyFlow',
  'AccessEvaluation',
  'Verification',
  'IntegrationRollup',
  'RuleHandlerDispatch',
];
const PORT = process.env.STRUCTURIZR_PORT || '7070';
const BASE_URL = process.env.STRUCTURIZR_URL || `http://host.docker.internal:${PORT}`;
const OUT_DIR = process.env.OUT_DIR || '/out';

(async () => {
  // Структурайзер Lite валидирует Host == localhost. Host-заголовок Chrome менять не даёт.
  // Обход: резолвим localhost изнутри контейнера в host.docker.internal, тогда Host остаётся "localhost:8080".
  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--force-color-profile=srgb',
    ],
  });
  const page = await browser.newPage();
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  await page.setViewport({ width: 2400, height: 1600, deviceScaleFactor: 2 });
  page.on('console', (m) => process.stdout.write('[browser] ' + m.text() + '\n'));
  // Сбросить сохранённую тему до первой загрузки страницы
  await page.evaluateOnNewDocument(() => {
    try { localStorage.removeItem('structurizr.colorScheme'); } catch (_) {}
    try { localStorage.setItem('structurizr.colorScheme', 'light'); } catch (_) {}
  });

  const firstKey = VIEWS[0];
  const url = `http://localhost:${PORT}/workspace/1/diagrams#${firstKey}`;
  console.log('goto', url);
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
  await page.waitForFunction('window.structurizr && window.structurizr.scripting && typeof window.structurizr.scripting.changeView === "function"', { timeout: 45000 });

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.mkdirSync(path.join(OUT_DIR, 'svg'), { recursive: true });
  fs.mkdirSync(path.join(OUT_DIR, 'png'), { recursive: true });

  // Диагностика: список доступных view (key и id)
  const available = await page.evaluate(() => {
    if (!window.structurizr.scripting.getViews) return 'getViews not available';
    return window.structurizr.scripting.getViews().map((v) => ({ key: v.key, name: v.name }));
  });
  console.log('available views:', JSON.stringify(available));

  for (const key of VIEWS) {
    process.stdout.write(`== ${key} ==\n`);
    try {
      // Каждый view открываем через полноценный goto — чище, чем changeView (исключает гонку при смене хэша).
      await page.goto(`http://localhost:${PORT}/workspace/1/diagrams#${key}`, { waitUntil: 'networkidle2', timeout: 45000 });
      await page.waitForFunction('window.structurizr && window.structurizr.scripting && typeof window.structurizr.scripting.exportCurrentDiagramToPNG === "function"', { timeout: 30000 });
      await new Promise((r) => setTimeout(r, 3000));

      // PNG
      try {
        const pngDataUrl = await page.evaluate(() => new Promise((resolve) => {
          const t = setTimeout(() => resolve(null), 15000);
          window.structurizr.scripting.exportCurrentDiagramToPNG({ crop: 50, includeMetadata: false }, (url) => { clearTimeout(t); resolve(url); });
        }));
        if (typeof pngDataUrl === 'string' && pngDataUrl.startsWith('data:image/png;base64,')) {
          const b64 = pngDataUrl.slice('data:image/png;base64,'.length);
          fs.writeFileSync(path.join(OUT_DIR, 'png', `structurizr-${key}.png`), Buffer.from(b64, 'base64'));
          console.log('  wrote png:', key, 'size=', b64.length);
        } else {
          console.error('  bad pngDataUrl for', key, String(pngDataUrl).slice(0, 120));
        }
      } catch (e) { console.error('  png export error for', key, e.message); }

      // SVG
      try {
        const svgText = await page.evaluate(() => new Promise((resolve) => {
          if (typeof window.structurizr.scripting.exportCurrentDiagramToSVG !== 'function') { resolve(null); return; }
          const t = setTimeout(() => resolve(null), 15000);
          window.structurizr.scripting.exportCurrentDiagramToSVG({ crop: 50, includeMetadata: false }, (svg) => { clearTimeout(t); resolve(svg); });
        }));
        if (svgText && typeof svgText === 'string' && svgText.trim().startsWith('<')) {
          fs.writeFileSync(path.join(OUT_DIR, 'svg', `structurizr-${key}.svg`), svgText, 'utf-8');
          console.log('  wrote svg:', key, 'size=', svgText.length);
        } else {
          console.log('  svg API unavailable or empty for', key);
        }
      } catch (e) { console.error('  svg export error for', key, e.message); }
    } catch (e) {
      console.error('  view error for', key, e.message);
    }
  }

  await browser.close();
  console.log('done');
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
