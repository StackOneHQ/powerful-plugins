#!/usr/bin/env node
// Design-floor audit for a decision page: every visible text node's computed size and its contrast
// against what is actually behind it, plus chart-mark contrast, in light and dark at each width.
//
//   node audit-design-floor.mjs <page.html | URL> [--click "<css selector>"]... [--widths 1440,320]
//
// Each --click is run in order after the first audit (open a panel, switch a tab) and the page is
// audited again. Exit 0 = clean, 1 = a text finding, 2 = could not check (no browser or bad input).
// Needs the `playwright` package, resolved from this script's location or a global install; set
// PLAYWRIGHT_FROM_CWD=1 to use the copy in the current directory instead. CHROMIUM_PATH picks a browser.
// A local file is served, with the files beside it, from 127.0.0.1 for the run only; the page may
// reach that server and the CDN hosts artifacts allow, nothing else.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";

const args = process.argv.slice(2);
const target = args.find((a, i) => !a.startsWith("--") && !(args[i - 1] || "").startsWith("--"));
const clicks = args.flatMap((a, i) => (a === "--click" ? [args[i + 1]] : []));
const wi = args.indexOf("--widths");
const widths = wi >= 0 ? args[wi + 1].split(",").map(Number) : [1440, 320];
if (!target) { console.error("usage: audit-design-floor.mjs <page.html | URL> [--click selector]... [--widths 1440,320]"); process.exit(2); }

let chromium;
try {
  if (process.env.PLAYWRIGHT_FROM_CWD === "1") {
    const req = createRequire(path.join(process.cwd(), "noop.js"));
    console.log("playwright: " + req.resolve("playwright"));
    chromium = req("playwright").chromium;
  } else chromium = (await import("playwright")).chromium;
} catch { console.error("could not check: install the playwright package (npm i -g playwright), or run from a project that has it with PLAYWRIGHT_FROM_CWD=1"); process.exit(2); }

// A local page is served with the files beside it (data, scripts) from 127.0.0.1 for the run only.
// An artifact page is a fragment, so it gets the publish skeleton to render in standards mode.
let url = target, server = null, origin = null;
if (!/^https?:/.test(target)) {
  const file = path.resolve(target);
  if (!fs.existsSync(file)) { console.error("could not check: no such file " + file); process.exit(2); }
  const root = fs.realpathSync(path.dirname(file)), html = fs.readFileSync(file, "utf8");
  const token = randomBytes(16).toString("hex");
  const entry = /^\s*<!doctype/i.test(html) ? html : "<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'><style>[hidden]{display:none!important}body{margin:0}</style></head><body>" + html + "</body></html>";
  const types = { ".json": "application/json", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2" };
  // Only this run's browser can use the server: exact Host header, and a random token as the first path segment.
  const refuse = (res) => { res.writeHead(404); res.end(); };
  server = http.createServer((req, res) => {
    if (req.method !== "GET" || req.headers.host !== `127.0.0.1:${server.address().port}`) return refuse(res);
    let rel;
    try { rel = decodeURIComponent(new URL(req.url, "http://x").pathname); } catch { return refuse(res); }
    if (!rel.startsWith(`/${token}/`) || rel.includes("\\") || rel.includes("\0")) return refuse(res);
    rel = rel.slice(token.length + 2);
    if (!rel || rel === "index.html") { res.writeHead(200, { "content-type": "text/html; charset=utf-8" }); return res.end(entry); }
    if (rel.split("/").some((seg) => !seg || seg.startsWith("."))) return refuse(res);
    let real;
    try { real = fs.realpathSync(path.resolve(root, rel)); } catch { return refuse(res); }
    if (!real.startsWith(root + path.sep) || !fs.statSync(real).isFile()) return refuse(res);
    res.writeHead(200, { "content-type": types[path.extname(real)] || "application/octet-stream" }); fs.createReadStream(real).pipe(res);
  });
  await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
  origin = `http://127.0.0.1:${server.address().port}`;
  url = `${origin}/${token}/`;
}
const ALLOWED = new Set(["cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "cdn.tailwindcss.com", "code.jquery.com", "fonts.googleapis.com", "fonts.gstatic.com"]);
// Requests may go to this run's server (exact origin), the target's own origin, or an allowed CDN over https.
const allowed = (u) => {
  let x; try { x = new URL(u); } catch { return false; }
  if (x.protocol === "data:" || x.protocol === "blob:") return true;
  if (origin) return x.origin === origin || (x.protocol === "https:" && ALLOWED.has(x.hostname));
  return x.origin === new URL(target).origin || (x.protocol === "https:" && ALLOWED.has(x.hostname));
};
const LAUNCH = ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--webrtc-ip-handling-policy=disable_non_proxied_udp"];

const AUDIT = () => {
  const parse = (c) => { const m = (c || "").match(/rgba?\(([^)]+)\)/); if (!m) return null; const v = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
  const lum = (c) => { const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const over = (top, bot) => ({ r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1 });
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const pageBg = (el) => {
    const stack = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (n instanceof SVGElement && n.tagName !== "svg") continue;
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
    }
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
    return base;
  };
  // In an SVG, a filled shape painted earlier under the text's centre is part of its background.
  const svgBg = (e, base) => {
    const tb = e.getBoundingClientRect(), cx = tb.left + tb.width / 2, cy = tb.top + tb.height / 2;
    let bg = base;
    for (const sh of e.ownerSVGElement.querySelectorAll("rect, circle, path")) {
      if (sh === e || !(sh.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
      const f = parse(getComputedStyle(sh).fill); if (!f || f.a === 0 || sh.getAttribute("fill") === "transparent") continue;
      const sb = sh.getBoundingClientRect(); if (cx >= sb.left && cx <= sb.right && cy >= sb.top && cy <= sb.bottom) bg = over(f, bg);
    }
    return bg;
  };
  // Opacity multiplies down the tree, so a faded parent fades its text and marks too.
  const opacityOf = (e) => { let o = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) o *= parseFloat(getComputedStyle(n).opacity); return o; };
  // A horizontal or vertical line has no height or width, so a mark only needs one of them.
  const visible = (e) => { const r = e.getBoundingClientRect(); if (!r.width && !r.height) return false; const cs = getComputedStyle(e); return cs.visibility !== "hidden" && cs.display !== "none" && !e.closest("[hidden]"); };
  const out = { texts: 0, small: [], low: [], weakMarks: 0, marks: 0 };
  for (const e of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "TITLE", "NOSCRIPT"].includes(e.tagName)) continue;
    if (![...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()) || !visible(e)) continue;
    const cs = getComputedStyle(e), size = parseFloat(cs.fontSize), isSvg = e instanceof SVGElement;
    const fg = parse(isSvg ? cs.fill : cs.color); if (!fg) continue;
    fg.a *= opacityOf(e);
    const base = pageBg(e), bg = isSvg && e.ownerSVGElement ? svgBg(e, base) : base;
    const cr = ratio(over(fg, bg), bg), large = size >= 24 || (parseInt(cs.fontWeight) >= 600 && size >= 18.66);
    const label = e.textContent.trim().replace(/\s+/g, " ").slice(0, 40);
    out.texts++;
    if (size < 14) out.small.push(`${label} (${size}px)`);
    if (cr < (large ? 3 : 4.5)) out.low.push(`${label} (${cr.toFixed(2)}:1)`);
  }
  for (const m of document.querySelectorAll("svg rect, svg circle, svg ellipse, svg line, svg path, svg polygon, svg polyline")) {
    if (!visible(m)) continue;
    const cs = getComputedStyle(m), f = parse(cs.fill), s = parse(cs.stroke);
    // Lines and polylines draw only their stroke; their default black fill is never painted.
    const filled = !["line", "polyline"].includes(m.tagName) && f && f.a > 0 && m.getAttribute("fill") !== "transparent";
    const paint = filled ? f : s && s.a > 0 && parseFloat(cs.strokeWidth) >= 1.5 ? s : null;
    if (!paint) continue;
    out.marks++;
    const bg = pageBg(m.ownerSVGElement || m);
    const own = parseFloat((paint === s ? cs.strokeOpacity : cs.fillOpacity) || 1);
    if (ratio(over({ ...paint, a: Math.min(1, paint.a * own * opacityOf(m)) }, bg), bg) < 3) out.weakMarks++;
  }
  out.small = [...new Set(out.small)]; out.low = [...new Set(out.low)];
  return out;
};

let browser;
try { browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: LAUNCH }); }
catch { try { browser = await chromium.launch({ channel: "chrome", args: LAUNCH }); } catch (e) { console.error("could not check: no Chromium found; run `npx playwright install chromium` or set CHROMIUM_PATH"); if (server) server.close(); process.exit(2); } }

let findings = 0, unchecked = 0;
for (const width of widths) for (const scheme of ["light", "dark"]) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: scheme });
  const errors = []; page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) => (allowed(route.request().url()) ? route.continue() : route.abort()));
  if (page.routeWebSocket) await page.routeWebSocket(/.*/, (ws) => ws.close());
  const loaded = await page.goto(url, { waitUntil: "networkidle" }).then((r) => !r || r.ok(), (e) => { errors.push(String(e)); return false; });
  if (!loaded) { unchecked++; console.log(`${scheme} ${width}px: could not load the page`); if (errors.length) console.log("   " + errors[0]); await page.close(); continue; }
  await page.waitForTimeout(800);
  for (const step of [null, ...clicks]) {
    if (step) { const ok = await page.evaluate((s) => { const el = document.querySelector(s); if (el) el.click(); return !!el; }, step); if (!ok) { unchecked++; console.log(`${scheme} ${width}px: could not check, no element for --click ${step}`); continue; } await page.waitForTimeout(400); }
    const r = await page.evaluate(AUDIT);
    findings += r.small.length + r.low.length;
    const where = `${scheme.padEnd(5)} ${String(width).padStart(4)}px ${step ? "after " + step : "on load"}`;
    console.log(`${where}: ${r.texts} texts, ${r.small.length} under 14px, ${r.low.length} under contrast; ${r.weakMarks} of ${r.marks} chart marks under 3:1`);
    for (const s of r.small.slice(0, 8)) console.log("   small: " + s);
    for (const s of r.low.slice(0, 8)) console.log("   contrast: " + s);
  }
  if (errors.length) console.log("   page errors: " + errors.slice(0, 3).join(" | "));
  await page.close();
}
await browser.close();
if (server) server.close();
if (findings) console.log(`${findings} text finding(s). Marks under 3:1 are fine only for context marks whose values are printed or not needed.`);
if (unchecked) console.log(`${unchecked} page state(s) could not be checked.`);
if (!findings && !unchecked) console.log("Clean: no text under 14px or under contrast.");
process.exit(findings ? 1 : unchecked ? 2 : 0);
