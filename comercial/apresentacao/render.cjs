// Imprime build.html (gerado por build.py) em PDF 1920x1080, uma página por <section>.
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('file://' + path.join(__dirname, 'build.html'), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({
    path: path.join(__dirname, '..', 'Keystone-Apresentacao-Comercial.pdf'),
    width: '1920px',
    height: '1080px',
    printBackground: true,
    preferCSSPageSize: true,
  });
  await browser.close();
})();
