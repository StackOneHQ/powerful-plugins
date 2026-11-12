#!/usr/bin/env node
// Score a forge output against a replay case: is it at least as clean as the human-cleaned
// gold, no worse than its input on each measure checked below, and does it behave identically?
// usage: node score.mjs --case <name> --checkout <repo path> (--candidate <ref> | --worktree <path>) [--tests]
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const here = dirname(fileURLToPath(import.meta.url));
const { values: args } = parseArgs({
  options: {
    case: { type: 'string' }, checkout: { type: 'string' }, candidate: { type: 'string' },
    worktree: { type: 'string' }, tests: { type: 'boolean' },
  },
});
const kase = JSON.parse(readFileSync(join(here, 'cases.json'), 'utf8')).find((c) => c.name === args.case);
if (!kase || !args.checkout || !(args.candidate || args.worktree)) {
  console.error('usage: --case <name> --checkout <path> (--candidate <ref> | --worktree <path>) [--tests]');
  process.exit(2);
}
if (args.tests && !kase.tests?.length) { console.error(`${kase.name} lists no tests to run`); process.exit(2); }
const git = (...a) => spawnSync('git', ['-C', args.checkout, ...a], { encoding: 'utf8' }).stdout;

const meterRun = (repo, head) => JSON.parse(spawnSync('node', [join(here, '..', '..', 'scripts', 'slop-meter.mjs'),
  '--repo', repo, '--base', kase.base, ...(head ? ['--head', head] : []), '--json'], { encoding: 'utf8', maxBuffer: 64 << 20 }).stdout);
const meter = (head) => meterRun(args.checkout, head).totals;

// Test outcomes are compared as a set: the rewrite must pass and fail exactly what its input did.
const outcomesIn = (tree) => {
  if (!existsSync(join(tree, 'node_modules'))) symlinkSync(join(args.checkout, 'node_modules'), join(tree, 'node_modules'));
  const report = join(mkdtempSync(join(tmpdir(), 'forge-replay-report-')), 'vitest.json');
  spawnSync(join(tree, 'node_modules', '.bin', 'vitest'), ['run', '--reporter=json', `--outputFile=${report}`, ...kase.tests], { cwd: tree });
  // No report means vitest never ran; an empty set then fails the comparison below.
  if (!existsSync(report)) return [];
  return JSON.parse(readFileSync(report, 'utf8')).testResults.flatMap((f) => f.assertionResults.map((a) => `${a.status} ${a.fullName}`)).sort();
};
const outcomesAt = (ref) => {
  const tree = mkdtempSync(join(tmpdir(), 'forge-replay-'));
  git('worktree', 'add', '--detach', tree, ref);
  try { return outcomesIn(tree); } finally {
    git('worktree', 'remove', '--force', tree);
    rmSync(tree, { recursive: true, force: true });
  }
};

const input = meter(kase.input), gold = meter(kase.gold);
const candRun = args.worktree ? meterRun(args.worktree) : meterRun(args.checkout, args.candidate), cand = candRun.totals;
const checks = [
  ['added comment lines <= gold', cand.addedComments <= gold.addedComments],
  ['longest comment block <= gold', cand.longestCommentBlock <= gold.longestCommentBlock],
  ['type escapes <= input', cand.typeEscapes <= input.typeEscapes],
  ['added lines <= input', cand.added <= input.added],
  ['no ticket ids in comments', cand.ticketIdsInComments === 0],
  ['copied blocks <= input', cand.copies <= input.copies],
  ['defensive code (try, ?., ??) <= input', cand.tryBlocks <= input.tryBlocks && cand.optionalChains <= input.optionalChains && cand.nullishDefaults <= input.nullishDefaults],
  ['risky regexes <= input', cand.riskyRegexes <= input.riskyRegexes],
];
// Runtime dependencies stay as the input had them unless the hand cleanup changed them too.
const runtimeDeps = (read) => { const t = read('package.json'); return t ? JSON.stringify(JSON.parse(t).dependencies ?? {}) : '{}'; };
const readAt = (ref) => (f) => git('show', `${ref}:${f}`);
const readCandidate = args.worktree ? (f) => existsSync(join(args.worktree, f)) ? readFileSync(join(args.worktree, f), 'utf8') : '' : readAt(args.candidate);
const inputDeps = runtimeDeps(readAt(kase.input));
if (runtimeDeps(readAt(kase.gold)) === inputDeps) checks.push(['runtime dependencies unchanged', runtimeDeps(readCandidate) === inputDeps]);
if (args.tests) {
  const before = outcomesAt(kase.input), after = args.worktree ? outcomesIn(args.worktree) : outcomesAt(args.candidate);
  checks.push([`same test outcomes (${before.length} tests)`, before.length > 0 && JSON.stringify(before) === JSON.stringify(after)]);
}

const row = (label, t) => `${label.padEnd(10)} +${String(t.added).padEnd(4)} -${String(t.removed).padEnd(4)} comments ${String(t.addedComments).padEnd(4)} block ${String(t.longestCommentBlock).padEnd(3)} escapes ${t.typeEscapes}`;
console.log(`${kase.name}\n${row('input', input)}\n${row('gold', gold)}\n${row('candidate', cand)}\n`);
for (const [label, ok] of checks) console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`);

const goldFiles = git('diff', '--name-only', `${kase.base}...${kase.gold}`).split('\n').filter(Boolean);
const commentLines = (read) => new Set(goldFiles.flatMap((f) => read(f).split('\n').map((l) => l.trim())
  .filter((l) => /^(\/\/|\*|\/\*\*)\s*\S{3}/.test(l) && !/^\/\/\s*(arrange|act|assert)/i.test(l))));
const goldComments = commentLines(readAt(kase.gold));
const candComments = commentLines(readCandidate);
const dropped = [...goldComments].filter((l) => !candComments.has(l));
console.log(`\ncomment lines the hand cleanup kept that the candidate does not have verbatim (${dropped.length}); read each, a rewrite is fine, a lost constraint is not:`);
for (const l of dropped) console.log(`  ${l.slice(0, 140)}`);
if (candRun.reuseCandidates.length) console.log(`\nreuse candidates still present:\n  ${candRun.reuseCandidates.join('\n  ')}`);
process.exit(checks.every(([, ok]) => ok) ? 0 : 1);
