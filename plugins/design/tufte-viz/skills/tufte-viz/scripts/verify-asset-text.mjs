#!/usr/bin/env node
// Renders each .svg/.html asset in agent-browser and fails on text that overlaps, is clipped by its
// container, is covered by a shape painted after it, or is invisible. Exit 0 all clean, 1 a defect,
// 2 could not check: bad invocation, a missing file, no agent-browser, or an asset the browser could
// not open or measure. Uses a session of its own and closes only that one.
import { execFileSync } from "node:child_process";
import { basename, resolve, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdirSync, existsSync, statSync } from "node:fs";

const HERE = dirname(fileURLToPath(import.meta.url));
// Big enough for a full 8-slide 1200x1500 carousel to fit; beyond this the caller
// is told the screenshot is partial rather than being handed a silent crop.
const MAX_VIEWPORT = { w: 2400, h: 12600 };

function usage(msg) {
  if (msg) console.error(`error: ${msg}`);
  console.error(
    "usage: verify-asset-text.mjs [--out ABSOLUTE_DIR] <file.svg|file.html> [...]\n" +
      "       verify-asset-text.mjs --self-test",
  );
  process.exit(2);
}

const argv = process.argv.slice(2);
let out = "asset-verify";
let selfTest = false;
const files = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--out") {
    const v = argv[++i];
    if (v === undefined || v.startsWith("--")) usage("--out requires a directory path");
    out = v;
  } else if (a === "--self-test") {
    selfTest = true;
  } else if (a === "-h" || a === "--help") {
    usage();
  } else if (a.startsWith("--")) {
    usage(`unknown flag ${a}`);
  } else {
    files.push(a);
  }
}

// The defect classes each fixture must produce. A fixture listed with none must produce none;
// the others may produce more than they list.
const SELF_TEST = {
  "clean.svg": [],
  "clean-slide.html": [],
  "clean-prose.html": [],
  "clean-centred.html": [],
  "transformed-groups.svg": ["overlap", "clipped", "covered"],
  "overflowing-slide.html": ["clipped", "covered"],
  "clipped-beside-br.html": ["clipped"],
  "clipped-beside-span.html": ["clipped"],
  "clean-script-in-body.html": [],
  "inline-svg-covered.html": ["covered"],
  "clean-circle-corner.svg": [],
  "clean-scaled.svg": [],
  "clean-percent.svg": [],
  "clean-translucent-group.svg": [],
  "clean-translucent-overlay.html": [],
  "wrapped-line-covered.html": ["covered"],
};
if (selfTest) {
  const dir = join(HERE, "fixtures");
  if (!existsSync(dir)) usage(`self-test fixtures missing at ${dir}`);
  files.splice(0, files.length, ...Object.keys(SELF_TEST).map((f) => join(dir, f)));
}

if (!files.length) usage("no input files");

// agent-browser resolves relative paths against its own daemon working directory,
// not ours, so a relative --out silently writes somewhere else (or fails). Anchor it.
const outDir = resolve(out);
try {
  mkdirSync(outDir, { recursive: true });
} catch (e) {
  console.error(`error: cannot create --out directory ${outDir}: ${e.message}`);
  process.exit(2);
}

// Runs in the page and returns a JSON string: what it measured and every defect it found.
const PROBE = String.raw`(() => {
  // From the document element, not querySelector('svg'): an HTML slide with an inline <svg> logo
  // is still an HTML asset.
  const isSvgDoc = document.documentElement.tagName.toLowerCase() === 'svg';
  const svgRoot = isSvgDoc ? document.documentElement : null;

  // Measure with getBoundingClientRect, which applies every ancestor transform (getBBox does not),
  // then report in the space the author edits: viewBox units for SVG, page pixels for HTML.
  let toSpace = (r) => ({ x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height });
  let spaceUnit = 'px';

  if (isSvgDoc) {
    const ctm = svgRoot.getScreenCTM();
    if (ctm) {
      const inv = ctm.inverse();
      const map = (x, y) => new DOMPoint(x, y).matrixTransform(inv);
      toSpace = (r) => {
        const cs = [map(r.left, r.top), map(r.right, r.top), map(r.left, r.bottom), map(r.right, r.bottom)];
        const xs = cs.map(p => p.x), ys = cs.map(p => p.y);
        const x = Math.min(...xs), y = Math.min(...ys);
        return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
      };
      spaceUnit = 'user units';
    }
  }

  // A text node has no style or box of its own: read style from its element, and
  // measure it with a Range.
  const elOf = (n) => (n.nodeType === Node.TEXT_NODE ? n.parentElement : n);
  const rangeOver = (n) => {
    const rng = document.createRange();
    if (n.nodeType === Node.TEXT_NODE) rng.selectNode(n); else rng.selectNodeContents(n);
    return rng;
  };
  // One viewport rect per line of the node's glyphs. The element's box includes padding and
  // centring space, and the union box of wrapped text spans every line it touches.
  const fragsOf = (n) => {
    const rs = [...rangeOver(n).getClientRects()].filter((r) => r.width > 0 && r.height > 0);
    return rs.length || n.nodeType === Node.TEXT_NODE ? rs : [...n.getClientRects()];
  };

  let canvas;
  if (isSvgDoc) {
    const vb = svgRoot.viewBox.baseVal;
    canvas = (vb && vb.width)
      ? { x: vb.x, y: vb.y, w: vb.width, h: vb.height }
      : { x: 0, y: 0, w: svgRoot.width.baseVal.value, h: svgRoot.height.baseVal.value };
  } else {
    canvas = { x: 0, y: 0, w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight };
  }

  // HTML text is cut off by its nearest clipping ancestor, such as an overflow:hidden slide,
  // without the document ever growing.
  const clipBoundsFor = (n) => {
    if (isSvgDoc) return canvas;
    for (let el = n.parentElement; el; el = el.parentElement) {
      const cs = getComputedStyle(el);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const b = toSpace(el.getBoundingClientRect());
        return { x: b.x, y: b.y, w: b.w, h: b.h, via: el.tagName.toLowerCase() +
          (el.className && typeof el.className === 'string' && el.className.trim()
            ? '.' + el.className.trim().split(/\s+/)[0] : '') };
      }
    }
    return canvas;
  };

  // HTML text is collected as text nodes, not leaf elements, so text beside a <br> or <span> is
  // measured too; <text> in inline SVGs is collected as elements.
  const NOT_CONTENT = 'script, style, template, noscript, title, head';
  let nodes;
  if (isSvgDoc) {
    nodes = [...svgRoot.querySelectorAll('text')];
  } else {
    const runs = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (t) => {
        const p = t.parentElement;
        const skip = !t.nodeValue.trim() || p.closest(NOT_CONTENT) || p instanceof SVGElement;
        return skip ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      },
    });
    for (let t = walker.nextNode(); t; t = walker.nextNode()) runs.push(t);
    nodes = [...runs, ...[...document.querySelectorAll('svg text')].filter((n) => !n.closest(NOT_CONTENT))];
  }

  const hiddenSubtree = [];
  const items = [];
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const cs = getComputedStyle(elOf(n));
    const words = n.textContent.replace(/\s+/g, ' ').trim();
    const isText = n.nodeType === Node.TEXT_NODE;
    // Unrendered text whose own style is visible sits under a display:none ancestor, such as an
    // inactive slide. That is counted and reported, not flagged as invisible.
    const rendered = (isText ? rangeOver(n) : n).getClientRects().length > 0;
    if (!rendered && cs.display !== 'none' && cs.visibility !== 'hidden') {
      hiddenSubtree.push(words.slice(0, 40));
      continue;
    }
    // The union box is for cheap rejects and the invisible check; every other check compares lines.
    const client = (isText ? rangeOver(n) : n).getBoundingClientRect();
    const box = toSpace(client);
    const rawFrags = fragsOf(n);
    const frags = rawFrags.map(toSpace);
    items.push({
      i,
      node: n,
      text: words.slice(0, 60),
      box: { x: +box.x.toFixed(1), y: +box.y.toFixed(1), w: +box.w.toFixed(1), h: +box.h.toFixed(1) },
      frags: frags.length ? frags : [box],
      clientFrags: rawFrags.length ? rawFrags : [client],
      fontSize: parseFloat(cs.fontSize),
      opacity: parseFloat(cs.opacity),
      visibility: cs.visibility,
      display: cs.display,
    });
  }


  const problems = [];
  const EPS = 0.5; // boxes that only touch do not count
  const fmt = (b) => 'x[' + b.x.toFixed(1) + '..' + (b.x + b.w).toFixed(1) +
                     '] y[' + b.y.toFixed(1) + '..' + (b.y + b.h).toFixed(1) + ']';

  const intersect = (A, B) => {
    const ox = Math.min(A.x + A.w, B.x + B.w) - Math.max(A.x, B.x);
    const oy = Math.min(A.y + A.h, B.y + B.h) - Math.max(A.y, B.y);
    return ox > EPS && oy > EPS ? { ox, oy } : null;
  };
  const escapes = (b, c) => b.x < c.x - EPS || b.y < c.y - EPS ||
                            b.x + b.w > c.x + c.w + EPS || b.y + b.h > c.y + c.h + EPS;

  for (const it of items) {
    if (it.fontSize === 0 || it.opacity === 0 || it.visibility === 'hidden' ||
        it.display === 'none' || it.box.w === 0 || it.box.h === 0) {
      problems.push({ kind: 'invisible', a: it.text, i: it.i,
        detail: 'zero-size, hidden, or fully transparent text node' });
      it.dead = true;
      continue;
    }
    const c = clipBoundsFor(it.node);
    const out = it.frags.find((f) => escapes(f, c));
    if (out) {
      problems.push({ kind: 'clipped', a: it.text, i: it.i,
        detail: 'extends outside ' + (c.via ? 'its clipping container <' + c.via + '>' : 'the canvas') +
                ': ' + fmt(out) + ' vs ' + fmt(c) +
                (it.frags.length > 1 ? ' (1 of ' + it.frags.length + ' line fragments)' : '') });
    }
  }

  const live = items.filter(t => !t.dead);

  const SHAPES = ['rect', 'circle', 'ellipse', 'path', 'polygon'];
  // opacity is not inherited: a shape inside <g opacity="0.3"> computes 1 yet paints at 30%.
  const effectiveOpacity = (el) => {
    let o = 1;
    for (let a = el; a; a = a.parentElement) o *= parseFloat(getComputedStyle(a).opacity);
    return o;
  };
  // In both modes: an inline <svg> shape in a slide covers a label as surely as a <div> does.
  const solidShape = (n) => {
    if (!(n instanceof SVGGeometryElement) || !SHAPES.includes(n.tagName.toLowerCase())) return false;
    if (n.closest('defs, pattern, marker, clipPath, mask, symbol')) return false;
    const cs = getComputedStyle(n);
    const f = cs.fill;
    if (!f || f === 'none' || f.startsWith('url(')) return false;
    if (effectiveOpacity(n) < 0.9 || parseFloat(cs.fillOpacity) < 0.9) return false;
    const m = f.match(/rgba?\(([^)]+)\)/);
    if (m) { const p = m[1].split(','); if (p.length === 4 && parseFloat(p[3]) < 0.9) return false; }
    return true;
  };
  // Points inside each line fragment, inset from the edges so a shape that merely
  // touches the text box does not count.
  const samplePoints = (r) => {
    const pts = [];
    for (const fy of [0.35, 0.5, 0.65]) for (const fx of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      pts.push({ x: r.left + r.width * fx, y: r.top + r.height * fy });
    }
    return pts;
  };

  if (isSvgDoc) {
    // SVG paints in document order, so only a later shape can cover the text. A bounding box is
    // not a footprint (a circle's corners are empty), so sample points are tested against the fill.
    const all = [...svgRoot.querySelectorAll('*')];
    const order = new Map(all.map((n, idx) => [n, idx]));
    const opaque = all.filter(solidShape).map(n => ({ n, box: toSpace(n.getBoundingClientRect()) }));

    for (const it of live) {
      const ti = order.get(it.node);
      for (const sh of opaque) {
        if (order.get(sh.n) < ti) continue; // painted before the text, cannot cover it
        if (!it.frags.some((f) => intersect(f, sh.box))) continue; // cheap reject
        const ctm = sh.n.getScreenCTM();
        if (!ctm) continue;
        const inv = ctm.inverse();
        let hits = 0, sampled = 0;
        for (const r of it.clientFrags) {
          for (const p of samplePoints(r)) {
            sampled++;
            if (sh.n.isPointInFill(new DOMPoint(p.x, p.y).matrixTransform(inv))) hits++;
          }
        }
        if (hits) {
          problems.push({ kind: 'covered', a: it.text, i: it.i,
            detail: 'hidden behind a later-painted opaque <' + sh.n.tagName + '> (fill ' +
                    getComputedStyle(sh.n).fill + '): ' + hits + '/' + sampled + ' sample points inside its fill' });
          break;
        }
      }
    }
  } else {
    // HTML stacking is left to the browser: elementsFromPoint lists front to back, so anything
    // before the node is painted over it.
    const opaqueBg = (el) => {
      if (el instanceof SVGElement) return solidShape(el);
      const cs = getComputedStyle(el);
      const bg = cs.backgroundColor || '';
      const m = bg.match(/rgba?\(([^)]+)\)/);
      if (!m) return false;
      const p = m[1].split(',').map(s => parseFloat(s));
      const alpha = p.length === 4 ? p[3] : 1;
      return alpha >= 0.9 && effectiveOpacity(el) >= 0.9;
    };
    for (const it of live) {
      const el = elOf(it.node);
      // elementsFromPoint hit-tests only the viewport, so scroll the node into view and re-measure
      // its lines. The page-space boxes above were all taken before any scroll.
      el.scrollIntoView({ block: 'center', inline: 'center' });
      const lines = fragsOf(it.node);
      // Points between an SVG <text>'s glyphs miss it in the hit-test stack. Inside one <svg>,
      // document order is paint order, so a shape there is above the text only if it comes later.
      const svgOwner = it.node instanceof SVGElement ? it.node.ownerSVGElement : null;
      const isAbove = (other, stack, self) => {
        if (self !== -1) return stack.indexOf(other) < self;
        if (svgOwner && other instanceof SVGElement && svgOwner.contains(other)) {
          return !!(it.node.compareDocumentPosition(other) & Node.DOCUMENT_POSITION_FOLLOWING);
        }
        return true;
      };
      let hidden = 0, checked = 0;
      for (const r of lines) {
        const y = r.top + r.height / 2;
        let hits = 0, sampled = 0;
        for (const f of [0.15, 0.5, 0.85]) {
          const x = r.left + r.width * f;
          if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
          sampled++;
          const stack = document.elementsFromPoint(x, y);
          const self = stack.indexOf(el);
          if (stack.some(o => o !== el && !o.contains(it.node) && isAbove(o, stack, self) && opaqueBg(o))) hits++;
        }
        if (sampled) { checked++; if (hits === sampled) hidden++; }
      }
      if (hidden) {
        problems.push({ kind: 'covered', a: it.text, i: it.i,
          detail: 'painted underneath an opaque element (' + hidden + '/' + checked +
                  ' line fragments fully obscured)' });
      }
    }
  }

  for (let a = 0; a < live.length; a++) {
    for (let b = a + 1; b < live.length; b++) {
      // Nested text (a <span> inside a <p>) legitimately shares space.
      if (live[a].node.contains(live[b].node) || live[b].node.contains(live[a].node)) continue;
      if (!intersect(live[a].box, live[b].box)) continue; // cheap reject on the union
      let hit = null;
      for (const fa of live[a].frags) {
        for (const fb of live[b].frags) { hit = intersect(fa, fb); if (hit) break; }
        if (hit) break;
      }
      if (hit) {
        problems.push({ kind: 'overlap', a: live[a].text, b: live[b].text, i: live[a].i, j: live[b].i,
          detail: 'text boxes intersect by ' + hit.ox.toFixed(1) + 'x' + hit.oy.toFixed(1) });
      }
    }
  }

  // Visible text that produced no measurement means the collector missed it, and
  // "0 text nodes measured" must never read as a pass.
  if (!isSvgDoc && !items.length && !hiddenSubtree.length && document.body.innerText.trim()) {
    problems.push({ kind: 'unmeasured', a: document.body.innerText.trim().slice(0, 60),
      detail: 'the page shows text but no text node was measured, so nothing on it was checked' });
  }

  // The rendered size in CSS px against the viewport, so the caller can say when the screenshot crops.
  const rr = isSvgDoc ? svgRoot.getBoundingClientRect() : null;
  const frame = {
    w: Math.round(isSvgDoc ? rr.width : document.documentElement.scrollWidth),
    h: Math.round(isSvgDoc ? rr.height : document.documentElement.scrollHeight),
    vw: innerWidth,
    vh: innerHeight,
  };

  return JSON.stringify({
    mode: isSvgDoc ? 'svg' : 'html',
    frame,
    unit: spaceUnit,
    canvas: { w: +canvas.w.toFixed(1), h: +canvas.h.toFixed(1) },
    textCount: items.length,
    notRendered: hiddenSubtree.length,
    notRenderedSample: hiddenSubtree.slice(0, 3),
    problems,
  }, null, 2);
})()`;

// Size the viewport to the rendered asset, not its viewBox: <svg width="1200"
// viewBox="0 0 600 300"> draws at 1200px. A percentage size is a share of the
// viewport, not a size, so pick the viewport that draws the viewBox at 1:1: the
// default 100% gets the viewBox itself, 50% gets twice it.
const SIZE_PROBE = String.raw`JSON.stringify((() => {
  const d = document.documentElement;
  if (d.tagName.toLowerCase() === 'svg') {
    const pct = SVGLength.SVG_LENGTHTYPE_PERCENTAGE;
    const vb = d.viewBox.baseVal;
    const w = d.width.baseVal, h = d.height.baseVal;
    if (vb && vb.width && w.unitType === pct && h.unitType === pct &&
        w.valueInSpecifiedUnits > 0 && h.valueInSpecifiedUnits > 0) {
      return { w: vb.width * 100 / w.valueInSpecifiedUnits, h: vb.height * 100 / h.valueInSpecifiedUnits };
    }
    const r = d.getBoundingClientRect();
    return { w: r.width, h: r.height };
  }
  return { w: d.scrollWidth, h: d.scrollHeight };
})())`;

// agent-browser's default session is whatever the user is driving: opening a file there navigates
// their page away, and closing it kills their work.
const SESSION = `tufte-verify-${process.pid}`;

class BrowserError extends Error {}

function ab(...args) {
  try {
    return execFileSync("agent-browser", ["--session", SESSION, ...args], {
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (e) {
    if (e.code === "ENOENT") {
      console.error(
        "error: `agent-browser` is not on PATH, so no asset could be verified.\n" +
          "       Install it (`npm install -g agent-browser`) and re-run.\n" +
          "       Report these assets as UNVERIFIED — do not report them as done.",
      );
      process.exit(2);
    }
    throw new BrowserError(`agent-browser ${args[0]} failed: ${(e.stderr || e.message || "").toString().trim()}`);
  }
}

// agent-browser JSON-encodes an eval result, and both probes return a JSON string.
function parseEval(raw) {
  const once = JSON.parse(raw.trim());
  return typeof once === "string" ? JSON.parse(once) : once;
}

let failed = 0;
// Assets that are missing, or that the browser could not render or measure. These
// are "could not check", not defects: they exit 2, never 1, and never count as clean.
let unchecked = 0;
const shots = [];
try {
  for (const f of files) {
    const p = resolve(f);
    const name = basename(p).replace(/\.[^.]+$/, "");
    if (!existsSync(p) || !statSync(p).isFile()) {
      console.log(`\n### ${f} — NOT CHECKED\n  [missing] not a readable file`);
      unchecked++;
      continue;
    }

    let raw;
    const shot = `${outDir}/${name}.png`;
    let capped = null;
    try {
      // pathToFileURL percent-encodes spaces and other URL-significant characters.
      ab("open", pathToFileURL(p).href);
      // Grow the viewport to the asset so the screenshot shows all of it, capped because the
      // browser has to hold the whole page.
      try {
        const dims = parseEval(ab("eval", SIZE_PROBE));
        const want = { w: Math.round(dims.w), h: Math.round(dims.h) };
        const got = {
          w: Math.min(Math.max(want.w, 400), MAX_VIEWPORT.w),
          h: Math.min(Math.max(want.h, 300), MAX_VIEWPORT.h),
        };
        ab("set", "viewport", String(got.w), String(got.h));
        if (got.w < want.w || got.h < want.h) capped = { want, got };
      } catch {
        // Not fatal: the probe scrolls each node into view before hit-testing anyway.
      }
      raw = ab("eval", PROBE);
      ab("screenshot", shot);
      shots.push(shot);
    } catch (e) {
      if (!(e instanceof BrowserError)) throw e;
      console.log(`\n### ${name} — NOT CHECKED\n  [browser] ${e.message}`);
      unchecked++;
      continue;
    }

    let res;
    try {
      res = parseEval(raw);
    } catch {
      console.log(`\n### ${name} — NOT CHECKED\n  [probe] could not parse probe output:\n${raw.slice(0, 500)}`);
      unchecked++;
      continue;
    }

    // The screenshot is only the viewport; a capped one is already reported as partial.
    const cropped = !capped && res.frame && (res.frame.w > res.frame.vw + 1 || res.frame.h > res.frame.vh + 1);
    const ok = res.problems.length === 0;
    if (selfTest) {
      const want = SELF_TEST[basename(p)];
      // An SVG drawn smaller than its viewBox is screenshotted at reduced scale; clean-percent.svg pins this.
      const shrunk = res.mode === "svg" && res.frame.w + 1 < res.canvas.w;
      const got = [...new Set([
        ...res.problems.map((x) => x.kind),
        ...(cropped ? ["cropped"] : []),
        ...(shrunk ? ["shrunk"] : []),
      ])].sort();
      const missing = want.filter((k) => !got.includes(k));
      const spurious = want.length === 0 ? got : [];
      const pass = missing.length === 0 && spurious.length === 0;
      if (!pass) failed++;
      console.log(`\n### ${basename(p)} — self-test ${pass ? "OK" : "BROKEN"}`);
      console.log(`  expected [${want.join(", ") || "none"}]  got [${got.join(", ") || "none"}]`);
      if (missing.length) console.log(`  MISSED: ${missing.join(", ")} — the verifier no longer catches this`);
      if (spurious.length) console.log(`  FALSE POSITIVE: ${spurious.join(", ")} on a clean fixture`);
      for (const pr of res.problems) console.log(`    [${pr.kind}] "${pr.a}" — ${pr.detail}`);
      continue;
    }
    if (!ok) failed++;
    console.log(`\n### ${name} — ${ok ? "PASS" : "FAIL"}`);
    console.log(
      `${res.mode} asset, canvas ${res.canvas.w}x${res.canvas.h} ${res.unit}, ${res.textCount} text nodes measured`,
    );
    console.log(`screenshot: ${shot}`);
    if (capped) {
      console.log(
        `note: the screenshot covers ${capped.got.w}x${capped.got.h}px of a ${capped.want.w}x${capped.want.h}px asset — ` +
          `the rest is NOT in the frame.\n      Text geometry was still measured across the whole asset. ` +
          `To eyeball the remainder, split it into one file per slide/section and re-run.`,
      );
    }
    if (cropped) {
      console.log(
        `note: the asset renders at ${res.frame.w}x${res.frame.h}px but the screenshot is ${res.frame.vw}x${res.frame.vh}px — ` +
          `the rest is NOT in the frame.`,
      );
    }
    if (res.notRendered) {
      console.log(
        `note: ${res.notRendered} text nodes were not rendered (an ancestor is display:none) and were NOT checked` +
          (res.notRenderedSample.length ? ` — e.g. ${res.notRenderedSample.map((s) => `"${s}"`).join(", ")}` : "") +
          `\n      If those are inactive slides, render them one at a time or they ship unverified.`,
      );
    }
    for (const pr of res.problems) {
      const other = pr.b !== undefined ? `  <->  "${pr.b}"` : "";
      console.log(`  [${pr.kind}] "${pr.a}"${other}\n      ${pr.detail}`);
    }
  }
} finally {
  try {
    ab("close");
  } catch {}
}

if (selfTest) {
  if (unchecked) {
    console.log(`\nSELF-TEST NOT RUN: ${unchecked}/${files.length} fixtures could not be checked.`);
    process.exit(2);
  }
  console.log(
    `\n${failed ? "SELF-TEST FAILED" : "SELF-TEST PASSED"}: ${files.length - failed}/${files.length} fixtures behaved as expected.`,
  );
  process.exit(failed ? 1 : 0);
}

if (unchecked) {
  console.log(
    `\nNOT CHECKED: ${unchecked}/${files.length} assets could not be opened or measured` +
      (failed ? `, and ${failed} failed` : "") +
      ". Report the unchecked ones as UNVERIFIED, not as done.",
  );
  process.exit(2);
}

console.log(`\n${failed ? "FAILED" : "PASSED"}: ${files.length - failed}/${files.length} assets clean.`);
if (shots.length) {
  console.log("Now open every screenshot above and look at it. Geometry passing is not the same as reading well:");
  for (const s of shots) console.log(`  ${s}`);
}
process.exit(failed ? 1 : 0);
