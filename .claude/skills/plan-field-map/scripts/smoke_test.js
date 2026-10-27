// Headless smoke test of a built app folder (index.html + data/).
// Usage: node smoke_test.js APP_DIR OUT_DIR
// Needs Playwright (preinstalled in Claude cloud sessions) and Leaflet from npm:
//   (cd OUT_DIR && npm pack leaflet@1.9.4 && tar xzf leaflet-1.9.4.tgz)
// Leaflet is served locally and map tiles are blocked, because sandboxes often
// cannot reach unpkg/OSM; the drawing overlay still renders, which is what we check.
const { chromium } = require("playwright");
const path = require("path"), fs = require("fs"), http = require("http");
const [app, out] = process.argv.slice(2).map(p => path.resolve(p));
const LD = path.join(out, "package/dist/");
const types = { ".html": "text/html", ".js": "text/javascript", ".webp": "image/webp", ".css": "text/css" };
const srv = http.createServer((q, r) => {
  const f = path.join(app, decodeURIComponent(q.url.split("?")[0]).replace(/\/$/, "/index.html"));
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); return r.end(); } r.writeHead(200, { "content-type": types[path.extname(f)] || "application/octet-stream" }); r.end(d); });
}).listen(0, async () => {
  const port = srv.address().port, errors = [];
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 390, height: 780 }, acceptDownloads: true });
  const p = await ctx.newPage();
  p.on("pageerror", e => errors.push(e.message));
  await p.addInitScript(() => {
    window.__cbs = []; navigator.geolocation.watchPosition = ok => { __cbs.push(ok); return 1; }; navigator.geolocation.clearWatch = () => {};
    window.__feed = (lat, lon, heading, speed) => __cbs.forEach(f => f({ coords: { latitude: lat, longitude: lon, accuracy: 5, heading, speed } }));
  });
  await p.route("https://unpkg.com/**", r => r.fulfill({ path: LD + r.request().url().split("/dist/")[1] }));
  await p.route(/tile\.openstreetmap|arcgisonline|googleapis/, r => r.abort());
  await p.goto(`http://localhost:${port}/`); await p.waitForTimeout(2000);
  await p.screenshot({ path: path.join(out, "1-overview.png") });
  const first = await p.evaluate(() => PLAN.poles[0]);
  await p.goto(`http://localhost:${port}/#${first.id}`); await p.waitForTimeout(1200);
  const open = await p.$eval("#sheet", e => e.classList.contains("open"));
  const checks = await p.$$("#sChecks input[data-k]");
  if (checks.length) await checks[0].click();
  await p.fill("#sNote", "test");
  await p.screenshot({ path: path.join(out, "2-pole-card.png") });
  await p.click("#sMark");
  const allTicked = await p.$$eval("#sChecks input[data-k]", e => e.every(i => i.checked));
  await p.click("#sheetClose");
  await p.click("#hdgBtn"); await p.waitForTimeout(300);
  await p.evaluate(([la, lo]) => __feed(la, lo, 90, 8), [first.lat, first.lon]); await p.waitForTimeout(1000);
  const rot = await p.$eval("#map", e => e.style.transform); // expect rotate(-90deg) for heading 90
  await p.screenshot({ path: path.join(out, "3-driving.png") });
  await p.click("#hdgBtn"); await p.click("#menuBtn"); await p.waitForTimeout(200);
  await p.screenshot({ path: path.join(out, "4-menu.png") });
  const [dl] = await Promise.all([p.waitForEvent("download"), p.click("#exportCsv")]);
  const csv = fs.readFileSync(await dl.path(), "utf8").split("\n");
  console.log(JSON.stringify({ poles: await p.evaluate(() => PLAN.poles.length), cardOpened: open, markInstalledTicksAll: allTicked,
    drivingRotation: rot, csvHeader: csv[0].replace(/^﻿/, ""), csvFirstRow: csv.find(l => l.startsWith(first.id)), pageErrors: errors }, null, 1));
  await b.close(); srv.close();
});
