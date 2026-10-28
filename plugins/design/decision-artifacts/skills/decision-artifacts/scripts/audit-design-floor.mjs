#!/usr/bin/env node
// Design-floor audit for a decision page: every visible text node's computed size and its contrast
// against what is actually behind it, plus chart-mark contrast, in light and dark at each width.
//
//   node audit-design-floor.mjs <page.html | URL> [--click "<css selector>"]... [--widths 1440,320]
//
// Each --click is run in order after the first audit (open a panel, switch a tab) and the page is
// audited again. Exit 0 = clean, 1 = a text finding, 2 = could not check (no browser or bad input).
// Needs the `playwright` package; set CHROMIUM_PATH to use a specific Chromium or Chrome binary.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const target = args.find((a, i) => !a.startsWith("--") && !(args[i - 1] || "").startsWith("--"));
const clicks = args.flatMap((a, i) => (a === "--click" ? [args[i + 1]] : []));
const wi = args.indexOf("--widths");
const widths = wi >= 0 ? args[wi + 1].split(",").map(Number) : [1440, 320];
if (!target) { console.error("usage: audit-design-floor.mjs <page.html | URL> [--click selector]... [--widths 1440,320]"); process.exit(2); }

let chromium;
try { chromium = createRequire(path.join(process.cwd(), "noop.js"))("playwright").chromium; }
catch { try { chromium = (await import("playwright")).chromium; } catch { console.error("could not check: install the playwright package (npm i -D playwright)"); process.exit(2); } }

// An artifact page is a fragment; give it the publish skeleton so it renders in standards mode.
let url = target, wrapper = null;
if (!/^https?:/.test(target)) {
  const file = path.resolve(target);
  if (!fs.existsSync(file)) { console.error("could not check: no such file " + file); process.exit(2); }
  const html = fs.readFileSync(file, "utf8");
  const page = /^\s*<!doctype/i.test(html) ? file : path.join(path.dirname(file), ".audit-" + path.basename(file));
  if (page !== file) { wrapper = page; fs.writeFileSync(page, "<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'><style>[hidden]{display:none!important}body{margin:0}</style></head><body>" + html + "</body></html>"); }
  url = pathToFileURL(page).href;
}

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
  const visible = (e) => { const r = e.getBoundingClientRect(); if (!r.width || !r.height) return false; const cs = getComputedStyle(e); return cs.visibility !== "hidden" && cs.display !== "none" && !e.closest("[hidden]"); };
  const out = { texts: 0, small: [], low: [], weakMarks: 0, marks: 0 };
  for (const e of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "TITLE", "NOSCRIPT"].includes(e.tagName)) continue;
    if (![...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()) || !visible(e)) continue;
    const cs = getComputedStyle(e), size = parseFloat(cs.fontSize), isSvg = e instanceof SVGElement;
    const fg = parse(isSvg ? cs.fill : cs.color); if (!fg) continue;
    if (parseFloat(cs.opacity) < 1) fg.a *= parseFloat(cs.opacity);
    const base = pageBg(e), bg = isSvg && e.ownerSVGElement ? svgBg(e, base) : base;
    const cr = ratio(over(fg, bg), bg), large = size >= 24 || (parseInt(cs.fontWeight) >= 600 && size >= 18.66);
    const label = e.textContent.trim().replace(/\s+/g, " ").slice(0, 40);
    out.texts++;
    if (size < 14) out.small.push(`${label} (${size}px)`);
    if (cr < (large ? 3 : 4.5)) out.low.push(`${label} (${cr.toFixed(2)}:1)`);
  }
  for (const m of document.querySelectorAll("svg rect, svg circle, svg path")) {
    if (!visible(m)) continue;
    const cs = getComputedStyle(m), f = parse(cs.fill), s = parse(cs.stroke);
    const paint = f && f.a > 0 && m.getAttribute("fill") !== "transparent" ? f : s && s.a > 0 && parseFloat(cs.strokeWidth) >= 1.5 ? s : null;
    if (!paint) continue;
    out.marks++;
    const bg = pageBg(m.ownerSVGElement || m);
    if (ratio(over({ ...paint, a: Math.min(1, paint.a * parseFloat(cs.fillOpacity || 1)) }, bg), bg) < 3) out.weakMarks++;
  }
  out.small = [...new Set(out.small)]; out.low = [...new Set(out.low)];
  return out;
};

let browser;
try { browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ["--allow-file-access-from-files"] }); }
catch { try { browser = await chromium.launch({ channel: "chrome", args: ["--allow-file-access-from-files"] }); } catch (e) { console.error("could not check: no Chromium found; run `npx playwright install chromium` or set CHROMIUM_PATH"); process.exit(2); } }

let findings = 0;
for (const width of widths) for (const scheme of ["light", "dark"]) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: scheme });
  const errors = []; page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url, { waitUntil: "networkidle" }).catch((e) => errors.push(String(e)));
  await page.waitForTimeout(800);
  for (const step of [null, ...clicks]) {
    if (step) { const ok = await page.evaluate((s) => { const el = document.querySelector(s); if (el) el.click(); return !!el; }, step); if (!ok) { console.log(`${scheme} ${width}px: no element for --click ${step}`); continue; } await page.waitForTimeout(400); }
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
if (wrapper) fs.rmSync(wrapper, { force: true });
console.log(findings ? `${findings} text finding(s). Marks under 3:1 are fine only for context marks whose values are printed or not needed.` : "Clean: no text under 14px or under contrast.");
process.exit(findings ? 1 : 0);
