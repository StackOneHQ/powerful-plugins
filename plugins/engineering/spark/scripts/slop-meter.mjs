#!/usr/bin/env node
// Measure the slop a diff adds, relative to what the touched files and the repo at base already contain.
// usage: node slop-meter.mjs --repo <path> --base <ref> [--head <ref>] [--exclude <glob>]... [--json]
// Without --head it measures the working tree, untracked files included, so it can run mid-rewrite.
// Either way it measures from the merge base of --base and the head, so a base that moved on adds nothing.
// Files marked `linguist-generated` in .gitattributes, or matched by --exclude, are not measured and
// are never named as the original that a copy or a reuse candidate repeats.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseArgs } from 'node:util';

const { values: args } = parseArgs({
  options: {
    repo: { type: 'string' }, base: { type: 'string' }, head: { type: 'string' },
    exclude: { type: 'string', multiple: true, default: [] }, json: { type: 'boolean' },
  },
});
for (const k of ['repo', 'base']) if (!args[k]) { console.error(`missing --${k}`); process.exit(2); }

// git reports paths from the repository root, so every later lookup runs from there too.
const repo = spawnSync('git', ['-C', args.repo, 'rev-parse', '--show-toplevel'], { encoding: 'utf8' }).stdout?.trim();
if (!repo) { console.error(`not a git repository: ${args.repo}`); process.exit(2); }
// A failed git would read as an empty result and hide the whole file, so any failure stops the run.
// The one expected non-zero status is `git grep` finding nothing. core.quotePath=false prints non-ASCII
// paths as-is, so they can be read back.
const git = (a, okStatus = [0], input = undefined) => {
  const r = spawnSync('git', ['-C', repo, '-c', 'core.quotePath=false', ...a], { encoding: 'utf8', maxBuffer: 256 << 20, input });
  if (r.error || r.stdout == null || !okStatus.includes(r.status)) {
    console.error(`slop-meter: git ${a.join(' ')} failed: ${r.error?.message ?? r.stderr?.trim() ?? 'no output'}`);
    process.exit(2);
  }
  return r.stdout;
};
// Measure from where the branch left the base, not from the base's tip: a base that moved on would
// otherwise show its own new commits as removed by this change, and baselines would read files the
// branch never saw.
const mergeBase = spawnSync('git', ['-C', repo, 'merge-base', args.base, args.head ?? 'HEAD'], { encoding: 'utf8' }).stdout?.trim();
if (!mergeBase) { console.error(`no merge base between ${args.base} and ${args.head ?? 'HEAD'}`); process.exit(2); }
const base = mergeBase;
const range = args.head ? [base, args.head] : [base];
const CODE = /\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|kt|rb|swift|cs|sh)$/;
const GENERATED = /(-lock\.json|\.lock|\.snap|\.min\.js)$|(^|\/)(dist|build|vendor|__generated__)\//;
const IS_TEST = (f) => /(^|[/._-])(spec|test)s?\.[a-z]+$|(^|\/)test_[^/]*\.py$|(^|\/)(__tests__|tests?)\//.test(f);
const SECTION = '(arrange|act|assert|given|when|then|setup|teardown)';
const TEST_SECTION_MARKER = new RegExp(`^\\s*(//|#)\\s*${SECTION}(\\s*([/&,]|and)\\s*${SECTION})*\\s*$`, 'i');

const syntaxOf = (file) => {
  const ext = file.slice(file.lastIndexOf('.') + 1);
  const js = /^(ts|tsx|js|jsx|mjs|cjs)$/.test(ext);
  return {
    py: ext === 'py', js,
    hash: /^(py|rb|sh)$/.test(ext),
    // In shell, `#` opens a comment only at the start of a word: `$#` and `${#x}` are code.
    hashAnywhere: /^(py|rb)$/.test(ext),
    tripleQuotes: ext === 'py' ? ['"""', "'''"] : /^(java|kt|swift|cs)$/.test(ext) ? ['"""'] : [],
    multiLineBacktick: js || ext === 'go',
    rust: ext === 'rs',
  };
};
// `</` and `} />` are JSX tags, so `<` and `}` never open a regex literal, and `>` does only in `=>`.
const REGEX_CAN_START = /(^|[(,=:[!&|?{;+\-*%~^]|=>|\b(return|typeof|case|do|else|in|of|void|yield|await|delete|throw|new))\s*$/;
// One pass over the whole file, tracking comments and strings across lines, so a `# note` inside a
// string is code and an unmarked line inside a block comment is prose. Per line: whether it starts in
// a comment, its code with comments and string and regex contents blanked, and its comment text.
const scan = (file, text) => {
  const syn = syntaxOf(file);
  const out = [];
  // mode: code | block (comment) | doc (docstring) | str | tmpl (JS template literal)
  let mode = 'code', close = '', multi = false, escapes = true, depth = 0, continued = false, before = '';
  const templates = [];
  text.split('\n').forEach((line, li) => {
    if (li === 0 && line.startsWith('#!')) { out.push({ text: line, comment: false, code: line, notes: '' }); return; }
    const code = line.split(''), notes = code.map(() => ' ');
    const blank = (from, to) => { for (let k = from; k < Math.min(to, line.length); k++) code[k] = ' '; };
    const note = (from, to) => { for (let k = from; k < Math.min(to, line.length); k++) notes[k] = line[k]; blank(from, to); };
    let comment = mode === 'block' || mode === 'doc';
    const first = mode === 'code' ? line.search(/\S/) : -1;
    let i = 0, joined = false;
    while (i < line.length) {
      const c = line[i], rest = line.slice(i);
      if (mode === 'block' || mode === 'doc') {
        const end = line.indexOf(close, i);
        note(i, end < 0 ? line.length : end + close.length);
        if (end < 0) break;
        i = end + close.length; mode = 'code'; continue;
      }
      if (mode === 'str' || mode === 'tmpl') {
        if (c === '\\' && escapes) { joined = i === line.replace(/\r$/, '').length - 1; blank(i, i + 2); i += 2; continue; }
        if (mode === 'tmpl' && rest.startsWith('${')) { templates.push(depth); blank(i, i + 2); i += 2; mode = 'code'; continue; }
        if (rest.startsWith(close)) { i += close.length; mode = 'code'; continue; }
        blank(i, i + 1); i++; continue;
      }
      const opens = (kind) => { if (i === first) comment = kind === 'comment'; };
      if ((syn.hash && c === '#' && (syn.hashAnywhere || i === 0 || /\s/.test(line[i - 1]))) || (!syn.hash && rest.startsWith('//'))) {
        opens('comment'); note(i, line.length); break;
      }
      if (!syn.hash && rest.startsWith('/*')) { opens('comment'); mode = 'block'; close = '*/'; note(i, i + 2); i += 2; continue; }
      const triple = syn.tripleQuotes.find((q) => rest.startsWith(q));
      if (triple) {
        // A triple-quoted string that opens a Python statement is a docstring; anywhere else it is a value.
        const prefix = line.slice(0, i).trimStart();
        if (syn.py && /^[rRuUbBfF]{0,2}$/.test(prefix) && depth === 0 && !continued) { comment = true; mode = 'doc'; note(i, i + 3); }
        else { opens('code'); mode = 'str'; multi = true; escapes = true; }
        close = triple; i += 3; continue;
      }
      opens('code');
      const raw = syn.rust && !/[\w$]/.test(line[i - 1] ?? '') && rest.match(/^b?r(#*)"/);
      if (raw) { mode = 'str'; close = `"${raw[1]}`; multi = true; escapes = false; i += raw[0].length; continue; }
      if (c === '"' || (c === "'" && (!syn.rust || /^'(\\.[^']*|[^\\'])'/.test(rest)))) {
        mode = 'str'; close = c; multi = c === '"' && syn.rust; escapes = true; i++; continue;
      }
      if (c === '`' && syn.multiLineBacktick) {
        mode = syn.js ? 'tmpl' : 'str'; close = '`'; multi = true; escapes = syn.js; i++; continue;
      }
      if (syn.js && c === '/' && REGEX_CAN_START.test(code.slice(0, i).join('').trim() || before)) {
        let j = i + 1, inClass = false;
        for (; j < line.length; j++) {
          if (line[j] === '\\') j++;
          else if (line[j] === '[') inClass = true;
          else if (line[j] === ']') inClass = false;
          else if (line[j] === '/' && !inClass) break;
        }
        if (j < line.length) { blank(i + 1, j); i = j + 1; continue; }
      }
      if ('([{'.includes(c)) depth++;
      else if (')]}'.includes(c)) {
        if (c === '}' && templates.length && templates[templates.length - 1] === depth) { templates.pop(); mode = 'tmpl'; close = '`'; escapes = true; blank(i, i + 1); i++; continue; }
        depth = Math.max(0, depth - 1);
      }
      i++;
    }
    // A string ends with its line unless it spans lines by nature or the newline is escaped.
    if (mode === 'str' && !multi && !joined) mode = 'code';
    const kept = code.join('');
    if (kept.trim()) before = kept.trim();
    continued = mode === 'code' && /\\\s*$/.test(line);
    out.push({ text: line, comment, code: kept, notes: notes.join('') });
  });
  return out;
};
const proseOf = (lexed) => lexed.map((l) => l.comment && !TEST_SECTION_MARKER.test(l.text));
const TICKET = /\b(?!(?:UTF|SHA|AES|ISO|RFC|RSA|HMAC|PBKDF|TLS|SSL|HTTP|IPV|ECMA|MD|CRC|UTC|GMT|BASE|ED|HS|RS|ES|PS|CP)-\d)[A-Z][A-Z0-9]{1,9}-\d{1,6}\b/;
const LLM_WORDS = /\b(robust|seamless(ly)?|comprehensive|gracefully|leverag(e|es|ing)|enhanced|crucial|streamlined?|utiliz(e|es|ing)|delve)\b/i;
// A quantified group that itself contains a quantifier, e.g. (a+)+ or (.*)*: catastrophic backtracking.
// A group that opens with a literal separator, like (-[a-z]+)*, cannot match the same text two ways.
const QUANTIFIED_GROUP = /\(((?:[^()\\]|\\.)*)\)[+*{]/g;
const LEADING_SEPARATOR = /^(\?:)?(\\[-./:,_ ]|[-/:,_ ])/;
const isRisky = (body) => [...body.matchAll(QUANTIFIED_GROUP)].some(([, g]) => /[+*]/.test(g) && !LEADING_SEPARATOR.test(g));
// Regex literals start where an expression can, never after a value, so `a / b / c` is not one.
const REGEX_LITERAL = /(?:^|[=(,:!&|?{};]|\breturn)\s*\/((?:\\.|\[(?:\\.|[^\]])*\]|[^/\\\n])+)\/[dgimsuy]*/g;
const REGEXP_CALL = /RegExp\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g;
const regexBodies = (l) => [...l.matchAll(REGEX_LITERAL)].map((m) => m[1]).concat([...l.matchAll(REGEXP_CALL)].map((m) => m[2]));
const count = (lines, re) => lines.reduce((n, l) => n + (l.match(re)?.length ?? 0), 0);
const squash = (l) => l.trim().replace(/\s+/g, ' ');

// A renamed file is diffed against its old path, so only its changed lines count as added.
const renamedFrom = new Map();
const tracked = git(['diff', '-M', '--name-status', ...range]).split('\n').map((l) => {
  const [status, from, to] = l.split('\t');
  if (status?.startsWith('R')) { renamedFrom.set(to, from); return to; }
  return from;
});
const untracked = args.head ? [] : git(['ls-files', '--others', '--exclude-standard']).split('\n');
// A repo declares its generated files with the `linguist-generated` attribute; --exclude adds globs,
// matched like .gitignore patterns: one without a slash matches the file name at any depth.
const globRe = (glob) => new RegExp(`^${glob.replace(/[.+^${}()|[\]\\]/g, '\\$&')
  .replace(/\*\*\/|\*\*|\*|\?/g, (t) => ({ '**/': '(?:.*/)?', '**': '.*', '*': '[^/]*', '?': '[^/]' })[t])}$`);
const excludes = args.exclude.map((g) => ({ re: globRe(g.endsWith('/') ? `${g}**` : g), anyDepth: !g.includes('/') }));
const generated = new Map();
const markGenerated = (paths) => {
  const todo = [...new Set(paths)].filter((p) => p && !generated.has(p));
  if (!todo.length) return;
  const fields = git(['check-attr', '-z', '--stdin', 'linguist-generated'], [0], `${todo.join('\0')}\0`).split('\0');
  for (let k = 0; k + 2 < fields.length; k += 3) generated.set(fields[k], fields[k + 2] === 'set' || fields[k + 2] === 'true');
};
const isSkipped = (p) => GENERATED.test(p) || generated.get(p) ||
  excludes.some(({ re, anyDepth }) => re.test(p) || (anyDepth && re.test(p.slice(p.lastIndexOf('/') + 1))));
const changed = [...new Set([...tracked, ...untracked])].filter((f) => f && CODE.test(f));
markGenerated(changed);
const skipped = changed.filter(isSkipped);
const files = changed.filter((f) => !isSkipped(f));
const isUntracked = new Set(untracked);
const basePathOf = (file) => renamedFrom.get(file) ?? file;
// A path the change added or deleted is missing on one side; it reads as empty there, not as a git failure.
// `ls-tree <rev> -- <path>` prints nothing for a missing path and still fails on a bad revision.
// File names are passed with --literal-pathspecs, so a name like `:(exclude)x.js` is not pathspec magic.
const showAt = (rev, file) => git(['--literal-pathspecs', 'ls-tree', '--name-only', rev, '--', file]).trim() ? git(['show', `${rev}:${file}`]) : '';

const headText = (file) => {
  if (args.head) return showAt(args.head, file);
  const onDisk = join(repo, file);
  return existsSync(onDisk) ? readFileSync(onDisk, 'utf8') : '';
};

// The diff as hunks of numbered lines. `---`/`+++` are file headers only before the first `@@`;
// after it they are a removed `--i;` or an added `++i;`.
const patchOf = (file) => {
  if (isUntracked.has(file)) return [readFileSync(join(repo, file), 'utf8').split('\n').map((text, i) => ({ sign: '+', text, ln: i + 1 }))];
  const hunks = [];
  let hunk = null, oldLn = 0, newLn = 0;
  for (const l of git(['--literal-pathspecs', 'diff', '-M', '-U0', ...range, '--', ...new Set([basePathOf(file), file])]).split('\n')) {
    const h = l.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (h) { hunk = []; hunks.push(hunk); oldLn = +h[1]; newLn = +h[2]; continue; }
    if (l.startsWith('diff --git ')) { hunk = null; continue; }
    if (!hunk) continue;
    if (l.startsWith('+')) hunk.push({ sign: '+', text: l.slice(1), ln: newLn++ });
    else if (l.startsWith('-')) hunk.push({ sign: '-', text: l.slice(1), ln: oldLn++ });
  }
  return hunks;
};

// A line that moved or was re-indented shows up as both removed and added; count only what is new.
// Comment blocks are counted within one hunk, over new lines only.
const additionsOf = (hunks, isProseAt) => {
  const pool = new Map();
  for (const { sign, text } of hunks.flat()) if (sign === '-') pool.set(squash(text), (pool.get(squash(text)) ?? 0) + 1);
  const added = [];
  let longestCommentBlock = 0;
  for (const hunk of hunks) {
    let run = 0;
    for (const { sign, text, ln } of hunk) {
      if (sign !== '+') continue;
      const left = pool.get(squash(text));
      if (left) { pool.set(squash(text), left - 1); run = 0; continue; }
      const prose = isProseAt(ln);
      added.push({ text, prose, ln });
      run = prose ? run + 1 : 0;
      longestCommentBlock = Math.max(longestCommentBlock, run);
    }
  }
  return { added, longestCommentBlock };
};
const densityOf = (file, text) => {
  const lexed = scan(file, text), prose = proseOf(lexed);
  const nonBlank = lexed.flatMap((l, i) => (l.text.trim() ? [prose[i]] : []));
  return nonBlank.length ? nonBlank.filter(Boolean).length / nonBlank.length : 0;
};
const siblingBaseline = (file) => {
  const dir = file.includes('/') ? file.slice(0, file.lastIndexOf('/')) : '.';
  const ext = file.slice(file.lastIndexOf('.'));
  const ds = git(['--literal-pathspecs', 'ls-tree', '--name-only', base, `${dir}/`]).split('\n')
    .filter((f) => f && f.endsWith(ext) && IS_TEST(f) === IS_TEST(file)).slice(0, 12)
    .map((f) => densityOf(f, git(['show', `${base}:${f}`])));
  return ds.length ? ds.reduce((a, b) => a + b, 0) / ds.length : null;
};

const STRUCTURAL = (l) => l.length <= 3 || /^[{}()[\];,]+$/.test(l) || /^(import|export \{|from |\} from )/.test(l);
const codeLines = (lines) => lines.map(squash).filter((l) => !STRUCTURAL(l));

// Batch every pattern into one `git grep` rather than one search per line. The patterns go through a
// file: a large added file has thousands of them, past what one command line can carry.
const grepCache = new Map();
const scratch = mkdtempSync(join(tmpdir(), 'slop-meter-'));
process.on('exit', () => rmSync(scratch, { recursive: true, force: true }));
const grepAll = (ext, patterns) => {
  const todo = [...new Set(patterns)].filter((p) => !grepCache.has(`${ext}\0${p}`));
  for (const p of todo) grepCache.set(`${ext}\0${p}`, []);
  if (todo.length) {
    const patternFile = join(scratch, 'patterns');
    writeFileSync(patternFile, `${todo.join('\n')}\n`);
    const hits = git(['grep', '-n', '-F', '-f', patternFile, base, '--', `*${ext}`], [0, 1]).split('\n');
    const parsed = hits.map((hit) => hit.match(/^[^:]+:([^:]+):(\d+):(.*)$/)).filter(Boolean);
    markGenerated(parsed.map((m) => m[1]));
    for (const m of parsed) {
      const hit = { path: m[1], ln: +m[2], text: m[3], skipped: isSkipped(m[1]) };
      for (const p of todo) if (m[3].includes(p)) grepCache.get(`${ext}\0${p}`).push(hit);
    }
  }
  return (p) => grepCache.get(`${ext}\0${p}`);
};
const cachedCodeLines = (load) => {
  const cache = new Map();
  return (path) => {
    if (!cache.has(path)) cache.set(path, codeLines(load(path).split('\n')));
    return cache.get(path);
  };
};
const baseCodeLines = cachedCodeLines((path) => git(['show', `${base}:${path}`]));
const baseLexed = new Map();
// A grep hit's line with comments and string contents blanked, so a call written in prose is no call.
const baseCodeAt = ({ path, ln }) => {
  if (!baseLexed.has(path)) baseLexed.set(path, scan(path, git(['show', `${base}:${path}`])));
  return baseLexed.get(path)[ln - 1]?.code ?? '';
};
const headCodeLines = cachedCodeLines(headText);

const OWN_REPEAT = 'a block this change already wrote';
// Copies: three consecutive added lines that already sit, in order, somewhere else in the repo at base.
const copiesOf = (file, added) => {
  const code = codeLines(added), ext = file.slice(file.lastIndexOf('.'));
  const windows = [];
  for (let i = 0; i + 2 < code.length; i++) {
    const win = code.slice(i, i + 3), anchor = [...win].sort((x, y) => y.length - x.length)[0];
    if (anchor.length >= 25) windows.push({ win, anchor });
  }
  const lookup = grepAll(ext, windows.map((w) => w.anchor));
  const found = new Set();
  // The change repeating its own lines is a copy too, except in tests, which stay readable by repeating.
  if (!IS_TEST(file)) {
    const firstAt = new Map();
    let inRun = false;
    code.forEach((_, i) => {
      if (i + 2 >= code.length) return;
      const win = code.slice(i, i + 3), key = win.join('\n'), first = firstAt.get(key);
      const repeats = first !== undefined && i - first >= 3 && win.some((l) => l.length >= 25);
      if (repeats && !inRun) found.add(`${OWN_REPEAT} (${found.size + 1})`);
      inRun = repeats;
      if (first === undefined) firstAt.set(key, i);
    });
  }
  for (const { win, anchor } of windows) {
    for (const { path, ln } of lookup(anchor).filter((h) => !h.skipped).slice(0, 20)) {
      if (path === file) continue;
      const body = baseCodeLines(path), off = win.indexOf(anchor);
      const inBase = body.some((l, k) => l === anchor && win.every((w, j) => body[k - off + j] === w));
      // A block whose original the change deleted was moved, not copied.
      if (inBase && headCodeLines(path).includes(anchor)) { found.add(`${path}:${ln}`); break; }
    }
  }
  return [...found];
};

// Reuse candidates: a call the diff adds with the same trailing configuration as a call already in the
// repo, e.g. redactFields(x, CensorType.FULL, true), and only to a function the repo defines: a library
// idiom like isinstance(x, dict) leaves nothing to reuse. Not proof of duplication, but worth opening.
const LITERALS = new Set(['null', 'undefined', 'true', 'false', 'this', 'None', 'True', 'False']);
const NOT_A_DEFINITION = /^\s*(if|elif|else|while|for|switch|return|match|await|new|catch|do)\b/;
const definesFn = (fn, line) => {
  const f = fn.replace(/\$/g, '\\$');
  return new RegExp(`\\b(def|function\\*?|func|fn|fun)\\s+${f}\\b|\\bfunc\\s*\\([^)]*\\)\\s*${f}\\b`).test(line) ||
    new RegExp(`(^|[^\\w$.])${f}\\s*[:=]\\s*(async\\s+)?(function\\b|\\([^)]*\\)\\s*(:[^=]+)?=>|[\\w$]+\\s*=>)`).test(line) ||
    (!NOT_A_DEFINITION.test(line) && new RegExp(`^[\\s\\w$<>,.?\\[\\]]*(?<![\\w$])${f}\\s*(<[^>]*>)?\\([^;]*\\)\\s*(:[^;={]+|throws[^;={]+)?\\{\\s*$`).test(line));
};
const reuseOf = (file, added, lexed) => {
  // Tests repeat setup calls by design; only source code that re-derives a configured call is a candidate.
  if (IS_TEST(file)) return [];
  const ext = file.slice(file.lastIndexOf('.'));
  const calls = new Map();
  // Calls are found in the line's code, so one written inside a string or a comment is not a call.
  for (const { text, ln, prose } of added) if (!prose) for (const m of (lexed[ln - 1]?.code ?? '').matchAll(/([A-Za-z_$][\w$]*)\(\s*[^,()]+(,[^()]*\))/g)) {
    const fn = m[1], tail = text.slice(m.index + m[0].length - m[2].length, m.index + m[0].length);
    // The shared configuration must name something (CensorType.FULL), not just repeat a string literal.
    const named = (tail.replace(/(['"`])(?:\\.|(?!\1).)*\1/g, '').match(/[A-Za-z_$][\w$.]{2,}/g) ?? []).some((t) => !LITERALS.has(t));
    if (fn.length >= 4 && named && tail.replace(/[\s,)]/g, '').length >= 4) calls.set(`${fn}${squash(tail)}`, { fn, tail: squash(tail) });
  }
  const fns = [...new Set([...calls.values()].map((c) => c.fn))];
  const lookup = grepAll(ext, fns.flatMap((fn) => [`${fn}(`, `${fn} =`, `${fn}:`]));
  const defined = new Set(fns.filter((fn) => [`${fn}(`, `${fn} =`, `${fn}:`].some((p) => lookup(p).some((h) => definesFn(fn, h.text) && definesFn(fn, baseCodeAt(h))))));
  const out = [];
  for (const { fn, tail } of calls.values()) {
    if (!defined.has(fn)) continue;
    for (const hit of lookup(`${fn}(`)) {
      const { path, ln, text, skipped } = hit;
      if (path !== file && !skipped && !IS_TEST(path) && squash(text).includes(tail) && baseCodeAt(hit).includes(`${fn}(`))
        out.push(`${fn}(…${tail} also at ${path}:${ln}`);
    }
  }
  return [...new Set(out)].slice(0, 8);
};

const ESCAPES = /\bas any\b|\bas unknown as\b|:\s*any\b/g;
// A test builds a partial fixture with `{ ... } as unknown as T`; there that double cast is the idiom.
const TEST_ESCAPES = /\bas any\b|:\s*any\b/g;
const rows = files.map((file) => {
  const hunks = patchOf(file);
  const baseText = showAt(base, basePathOf(file));
  // Comment status comes from the whole file, so a line inside a docstring counts as prose. Each side
  // uses its own path's syntax, since a rename can change the extension.
  const headLexed = scan(file, headText(file)), baseLexed = scan(basePathOf(file), baseText);
  const headProse = proseOf(headLexed);
  const proseAt = (ln) => headProse[ln - 1] ?? false;
  const lines = hunks.flat();
  // Pattern counts read only code: `as any` in a comment is prose about code, and one in a string or a
  // regex is data. `@ts-ignore` is the exception: it is a directive only where it opens a comment.
  const removed = lines.filter((l) => l.sign === '-').map((l) => l.text);
  const sideOf = (sign, key) => lines.filter((l) => l.sign === sign).map((l) => (sign === '+' ? headLexed : baseLexed)[l.ln - 1]?.[key] ?? '');
  const { added: addedLines, longestCommentBlock } = additionsOf(hunks, proseAt);

  const addedNonBlank = addedLines.filter((l) => l.text.trim());
  const addedCode = addedNonBlank.map((l) => l.text);
  const added = addedLines.map((l) => l.text);
  const addedComments = addedNonBlank.filter((l) => l.prose).map((l) => l.text);
  const netCount = (re, key = 'code') => Math.max(0, count(sideOf('+', key), re) - count(sideOf('-', key), re));
  const density = addedCode.length ? addedComments.length / addedCode.length : 0;
  const baseDensity = baseText ? densityOf(basePathOf(file), baseText) : siblingBaseline(file);

  return {
    file,
    added: addedCode.length,
    removed: removed.filter((l) => l.trim()).length,
    addedComments: addedComments.length,
    commentDensity: +density.toFixed(2),
    baseCommentDensity: baseDensity === null ? null : +baseDensity.toFixed(2),
    longestCommentBlock,
    ticketIdsInComments: addedComments.filter((l) => TICKET.test(l)).length,
    llmWordsInComments: addedComments.filter((l) => LLM_WORDS.test(l)).length,
    typeEscapes: netCount(IS_TEST(file) ? TEST_ESCAPES : ESCAPES) + netCount(/(\/\/|\/\*+)\s*@ts-ignore\b/g, 'notes'),
    tryBlocks: netCount(/\btry\s*\{/g),
    optionalChains: netCount(/\?\./g),
    nullishDefaults: netCount(/\?\?/g),
    riskyRegexes: addedNonBlank.filter((l) => !l.prose && regexBodies(l.text).some(isRisky)).length,
    copies: copiesOf(file, added),
    reuseCandidates: reuseOf(file, addedLines, headLexed),
  };
});

// Small hunks swing density wildly (one comment on two lines is 50%), so require a few lines first.
const drift = (r) => r.added >= 6 && r.addedComments >= 3 &&
  (r.baseCommentDensity === null ? r.commentDensity > 0.25 : r.commentDensity > r.baseCommentDensity + 0.10);
const SUMS = ['added', 'removed', 'addedComments', 'ticketIdsInComments', 'llmWordsInComments', 'typeEscapes', 'tryBlocks', 'optionalChains', 'nullishDefaults', 'riskyRegexes'];
const totals = Object.fromEntries(SUMS.map((k) => [k, rows.reduce((n, r) => n + r[k], 0)]));
totals.longestCommentBlock = Math.max(0, ...rows.map((r) => r.longestCommentBlock));
totals.copies = rows.reduce((n, r) => n + r.copies.length, 0);
const findings = [
  ...rows.filter(drift).map((r) => `${r.file}: comment density ${r.commentDensity} vs baseline ${r.baseCommentDensity ?? 'none'}`),
  ...rows.filter((r) => r.longestCommentBlock > 6).map((r) => `${r.file}: a ${r.longestCommentBlock}-line comment block`),
  ...rows.filter((r) => r.ticketIdsInComments).map((r) => `${r.file}: ${r.ticketIdsInComments} ticket id(s) in comments`),
  // One such word is noise; three in a file is a fingerprint.
  ...rows.filter((r) => r.llmWordsInComments >= 3).map((r) => `${r.file}: ${r.llmWordsInComments} comment line(s) with LLM vocabulary`),
  ...rows.filter((r) => r.typeEscapes).map((r) => `${r.file}: ${r.typeEscapes} type escape(s)`),
  ...rows.filter((r) => r.riskyRegexes).map((r) => `${r.file}: ${r.riskyRegexes} regex(es) with a nested quantifier`),
  ...rows.flatMap((r) => r.copies.map((c) => `${r.file}: repeats ${c.startsWith(OWN_REPEAT) ? c : `three or more lines already at ${c}`}`)),
];
const reuse = rows.flatMap((r) => r.reuseCandidates.map((c) => `${r.file}: ${c}`));
const out = { base: args.base, mergeBase: base, head: args.head ?? 'working tree', totals, findings, reuseCandidates: reuse, skipped, files: rows };

if (args.json) { console.log(JSON.stringify(out, null, 2)); process.exit(0); }
const pad = (s, n) => String(s).padEnd(n);
console.log(`${pad('file', 58)}${pad('+', 5)}${pad('-', 5)}${pad('cmt', 5)}${pad('dens', 6)}${pad('base', 6)}${pad('blk', 5)}${pad('esc', 5)}dup`);
for (const r of rows) console.log(`${pad(r.file.slice(-57), 58)}${pad(r.added, 5)}${pad(r.removed, 5)}${pad(r.addedComments, 5)}${pad(r.commentDensity, 6)}${pad(r.baseCommentDensity ?? 'new', 6)}${pad(r.longestCommentBlock, 5)}${pad(r.typeEscapes, 5)}${r.copies.length}`);
if (skipped.length) console.log(`\nskipped ${skipped.length} generated or excluded file(s): ${skipped.join(', ')}`);
console.log(`\ntotal +${totals.added} -${totals.removed}, ${totals.addedComments} added comment lines, longest block ${totals.longestCommentBlock}, ${totals.copies} copied block(s)`);
console.log(findings.length ? `findings:\n  ${findings.join('\n  ')}` : 'findings: none');
if (reuse.length) console.log(`reuse candidates (open each one):\n  ${reuse.join('\n  ')}`);
