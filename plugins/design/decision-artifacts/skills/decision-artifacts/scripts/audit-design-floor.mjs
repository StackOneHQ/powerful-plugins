#!/usr/bin/env node
// Design-floor audit for a decision page: every visible text node's computed size and its contrast
// against what is actually behind it, plus chart-mark contrast, in light and dark at each width.
//
//   node audit-design-floor.mjs <page.html | URL> [--click "<css selector>"]... [--widths 1440,320] [--allow-cdn]
//
// Each --click is run in order after the first audit (open a panel, switch a tab) and the page is
// audited again. Exit 0 = clean, 1 = a text finding, 2 = could not check (no browser or bad input).
// Needs the `playwright` package (1.48 or later), resolved from this script's location or the global
// node_modules of the Node running it; set PLAYWRIGHT_FROM_CWD=1 to use the copy in the current directory.
// CHROMIUM_PATH picks a browser.
// A local file is served, with the files beside it, from 127.0.0.1 for the run only, and the page may
// reach only that server. Pass --allow-cdn when it loads libraries or fonts from the CDN hosts artifacts
// allow: the page can then send what it reads from those files to them, so use it on pages you wrote.
// A URL target may reach its own origin (https too, for a redirect) and those CDN hosts. A refused
// request or socket marks that state "could not check". Service workers and popups are blocked.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";

const args = process.argv.slice(2);
const target = args.find((a, i) => !a.startsWith("--") && !["--click", "--widths"].includes(args[i - 1]));
const allowCdn = args.includes("--allow-cdn");
const clicks = args.flatMap((a, i) => (a === "--click" ? [args[i + 1]] : []));
const wi = args.indexOf("--widths");
const widths = wi >= 0 ? args[wi + 1].split(",").map(Number) : [1440, 320];
if (!target) { console.error("usage: audit-design-floor.mjs <page.html | URL> [--click selector]... [--widths 1440,320] [--allow-cdn]"); process.exit(2); }

// A bare import doesn't search the global node_modules, so it is resolved by path, worked out here
// rather than by running npm, whose answer depends on config in the current directory.
const globalRoot = process.platform === "win32"
  ? path.join(process.env.APPDATA || path.dirname(process.execPath), process.env.APPDATA ? "npm" : "", "node_modules")
  : path.join(path.dirname(path.dirname(process.execPath)), "lib", "node_modules");
const fromDir = (dir) => {
  if (dir.includes("..")) throw new Error("unexpected .. in " + dir);
  const req = createRequire(path.join(dir, "noop.js")); const at = req.resolve("playwright"); console.log("playwright: " + at); return req(at).chromium; };
let chromium;
try {
  if (process.env.PLAYWRIGHT_FROM_CWD === "1") chromium = fromDir(process.cwd());
  else try { chromium = (await import("playwright")).chromium; }
  catch { chromium = fromDir(globalRoot); }
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
// Requests may go to this run's server (exact origin) or the target's own origin, and to an allowed
// CDN over https for a URL target or with --allow-cdn. "cdn" marks a CDN request that was refused.
// An http target's https origin is allowed only for the top-level navigation, so a redirect loads.
let home, upgrade;
try { home = origin || new URL(target).origin; upgrade = home.replace(/^http:/, "https:"); }
catch { console.error("could not check: invalid URL " + target); if (server) server.close(); process.exit(2); }
const allowed = (u, topNavigation = false) => {
  let x; try { x = new URL(u.replace(/^ws(s?):/, "http$1:")); } catch { return false; }
  if (x.protocol === "data:" || x.protocol === "blob:") return true;
  if (x.origin === home || (topNavigation && x.origin === upgrade)) return true;
  if (x.protocol !== "https:" || !ALLOWED.has(x.hostname)) return false;
  return !origin || allowCdn || "cdn";
};
const LAUNCH = ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--webrtc-ip-handling-policy=disable_non_proxied_udp", "--dns-prefetch-disable"];

const AUDIT = () => {
  const parse = (c) => { const m = (c || "").match(/rgba?\(([^)]+)\)/); if (!m) return null; const v = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
  const lum = (c) => { const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const T = { r: 0, g: 0, b: 0, a: 0 };
  const over = (top, bot) => {
    const a = top.a + bot.a * (1 - top.a); if (!a) return T;
    const mix = (k) => (top[k] * top.a + bot[k] * bot.a * (1 - top.a)) / a;
    return { r: mix("r"), g: mix("g"), b: mix("b"), a };
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const num = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : 1; };
  const fade = (c, k) => ({ ...c, a: c.a * k });
  // In an SVG, filled shapes painted earlier under the point are part of the background, at their own opacity.
  const shapesUnder = (e, svg) => {
    const tb = e.getBoundingClientRect(), cx = tb.left + tb.width / 2, cy = tb.top + tb.height / 2;
    let bg = T;
    for (const sh of svg.querySelectorAll("rect, circle, ellipse, path, polygon")) {
      if (sh === e || !(sh.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
      const cs = getComputedStyle(sh), f = parse(cs.fill); if (!f || f.a === 0 || sh.getAttribute("fill") === "transparent") continue;
      const sb = sh.getBoundingClientRect(); if (cx >= sb.left && cx <= sb.right && cy >= sb.top && cy <= sb.bottom) bg = over(fade(f, num(cs.fillOpacity) * num(cs.opacity)), bg);
    }
    return bg;
  };
  // What the screen shows when `top` is painted in element e: each ancestor paints its background, then
  // its content, and the whole group is composited at that ancestor's opacity, out to a white canvas.
  // render(fg) against render(T) compares the text with the surface actually behind it.
  const render = (e, top, withShapes) => {
    let px = top;
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      let under = n instanceof SVGElement && n.tagName !== "svg" ? T : parse(cs.backgroundColor) || T;
      if (withShapes && n === e.ownerSVGElement) under = over(shapesUnder(e, n), under);
      px = fade(over(px, under), num(cs.opacity));
    }
    return over(px, { r: 255, g: 255, b: 255, a: 1 });
  };
  // A horizontal or vertical line has no height or width, so a mark only needs one of them.
  const visible = (e) => { const r = e.getBoundingClientRect(); if (!r.width && !r.height) return false; const cs = getComputedStyle(e); return cs.visibility !== "hidden" && cs.display !== "none" && !e.closest("[hidden]"); };
  const out = { texts: 0, small: [], low: [], weakMarks: 0, marks: 0 };
  for (const e of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "TITLE", "NOSCRIPT"].includes(e.tagName)) continue;
    if (![...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()) || !visible(e)) continue;
    const cs = getComputedStyle(e), size = parseFloat(cs.fontSize), isSvg = e instanceof SVGElement;
    const fg = parse(isSvg ? cs.fill : cs.color); if (!fg) continue;
    if (isSvg) fg.a *= num(cs.fillOpacity);
    const shapes = isSvg && !!e.ownerSVGElement;
    const cr = ratio(render(e, fg, shapes), render(e, T, shapes)), large = size >= 24 || (parseInt(cs.fontWeight) >= 600 && size >= 18.66);
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
    const own = num(paint === s ? cs.strokeOpacity : cs.fillOpacity);
    if (ratio(render(m, fade(paint, own), false), render(m, T, false)) < 3) out.weakMarks++;
  }
  out.small = [...new Set(out.small)]; out.low = [...new Set(out.low)];
  return out;
};

let browser;
try { browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: LAUNCH }); }
catch { try { browser = await chromium.launch({ channel: "chrome", args: LAUNCH }); } catch (e) { console.error("could not check: no Chromium found; run `npx playwright install chromium` or set CHROMIUM_PATH"); if (server) server.close(); process.exit(2); } }

let findings = 0, unchecked = 0;
for (const width of widths) for (const scheme of ["light", "dark"]) {
  // The policy sits on the context so it covers every page in it; popups are closed as they open.
  const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: scheme, serviceWorkers: "block" });
  if (!context.routeWebSocket) { console.error("could not check: Playwright 1.48 or later is needed to control WebSockets"); await browser.close(); if (server) server.close(); process.exit(2); }
  const refused = [];
  const refuse = (u, ok) => { refused.push(ok === "cdn" ? "CDN " + new URL(u).hostname : u.slice(0, 80)); };
  await context.route("**/*", (route) => {
    const req = route.request(), u = req.url();
    let top = false; try { top = req.isNavigationRequest() && !req.frame().parentFrame(); } catch {}
    const ok = allowed(u, top); if (ok === true) return route.continue(); refuse(u, ok); return route.abort(); });
  await context.routeWebSocket(/.*/, (ws) => { const ok = allowed(ws.url()); if (ok === true) return ws.connectToServer(); refuse(ws.url(), ok); ws.close(); });
  const page = await context.newPage();
  context.on("page", (p) => { if (p !== page) { refuse(p.url() || "popup", false); p.close(); } });
  const errors = []; page.on("pageerror", (e) => errors.push(e.message));
  const loaded = await page.goto(url, { waitUntil: "networkidle" }).then((r) => !r || r.ok(), (e) => { errors.push(String(e)); return false; });
  if (!loaded) { unchecked++; console.log(`${scheme} ${width}px: could not load the page`); if (errors.length) console.log("   " + errors[0]); await context.close(); continue; }
  await page.waitForTimeout(800);
  // A refused script, style, font, data call or socket can leave the page half drawn, so it isn't audited.
  if (refused.length) {
    unchecked++; console.log(`${scheme} ${width}px: could not check, ${refused.length} request(s) refused: ${[...new Set(refused)].slice(0, 3).join(", ")}`);
    if (refused.some((r) => r.startsWith("CDN "))) console.log("   rerun with --allow-cdn if this is your page");
    await context.close(); continue;
  }
  for (const step of [null, ...clicks]) {
    if (step) { const ok = await page.evaluate((s) => { const el = document.querySelector(s); if (el) el.click(); return !!el; }, step); if (!ok) { unchecked++; console.log(`${scheme} ${width}px: could not check, no element for --click ${step}`); continue; } await page.waitForTimeout(400); }
    // A click that set off a refused request leaves this and later states incomplete, so stop here.
    if (refused.length) { unchecked++; console.log(`${scheme} ${width}px: could not check after ${step}, ${refused.length} request(s) refused: ${[...new Set(refused)].slice(0, 3).join(", ")}`); break; }
    const r = await page.evaluate(AUDIT);
    findings += r.small.length + r.low.length;
    const where = `${scheme.padEnd(5)} ${String(width).padStart(4)}px ${step ? "after " + step : "on load"}`;
    console.log(`${where}: ${r.texts} texts, ${r.small.length} under 14px, ${r.low.length} under contrast; ${r.weakMarks} of ${r.marks} chart marks under 3:1`);
    for (const s of r.small.slice(0, 8)) console.log("   small: " + s);
    for (const s of r.low.slice(0, 8)) console.log("   contrast: " + s);
  }
  if (errors.length) console.log("   page errors: " + errors.slice(0, 3).join(" | "));
  await context.close();
}
await browser.close();
if (server) server.close();
if (findings) console.log(`${findings} text finding(s). Marks under 3:1 are fine only for context marks whose values are printed or not needed.`);
if (unchecked) console.log(`${unchecked} page state(s) could not be checked.`);
if (!findings && !unchecked) console.log("Clean: no text under 14px or under contrast.");
process.exit(findings ? 1 : unchecked ? 2 : 0);
