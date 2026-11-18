#!/usr/bin/env node
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  assertPathWithinAllowedRoots,
  inspectVaultLayout,
  redactSecrets,
  resolveActiveConfig,
  resolveContainedVaultPath,
  sanitizeExternalUrl,
  sanitizeInlineText,
} from "../bin/core.mjs";
import { extractTicketsFromText, parseSessionTranscript, resolveNormalizedRepoName } from "../bin/transcript-parser.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = resolve(__dirname, "..");
const CLI_PATH = join(PLUGIN_ROOT, "bin", "turn-vault.mjs");
const HOOK_SH = join(PLUGIN_ROOT, "scripts", "run-cli.sh");

function makeSandbox() {
  const root = mkdtempSync(join(tmpdir(), "turn-vault-test-"));
  const stateHome = join(root, "state-home");
  const vaultDir = join(root, "vault");
  const claudeProjects = join(root, "claude-projects");
  mkdirSync(claudeProjects, { recursive: true });
  return {
    root,
    stateHome,
    vaultDir,
    claudeProjects,
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
}

function runCli(args, { stateHome, env = {}, input = "" } = {}) {
  return execFileSync(process.execPath, [CLI_PATH, ...args], {
    encoding: "utf8",
    input,
    env: {
      ...process.env,
      TURN_VAULT_HOME: stateHome,
      TURN_VAULT_DIR: "",
      TURN_VAULT_DISABLED: "",
      ...env,
    },
  });
}

function runHookSh(subcommand, payload, { stateHome, env = {} } = {}) {
  return execFileSync("/bin/sh", [HOOK_SH, subcommand], {
    encoding: "utf8",
    input: JSON.stringify(payload),
    env: {
      ...process.env,
      PLUGIN_ROOT,
      TURN_VAULT_HOME: stateHome,
      TURN_VAULT_DIR: "",
      TURN_VAULT_DISABLED: "",
      ...env,
    },
  });
}

function writeJsonl(filePath, entries) {
  const safeFile = assertPathWithinAllowedRoots(filePath);
  const safeDir = assertPathWithinAllowedRoots(dirname(safeFile));
  mkdirSync(safeDir, { recursive: true });
  writeFileSync(
    safeFile,
    `${entries.map((e) => JSON.stringify(e)).join("\n")}\n`,
    "utf8",
  );
}

test("hooks stay completely dormant before init (oracle: zero filesystem side effects in vault)", () => {
  const sb = makeSandbox();
  try {
    const transcript = join(sb.claudeProjects, "proj-a", "sess-1.jsonl");
    writeJsonl(transcript, [
      {
        type: "user",
        timestamp: "2026-11-16T10:00:00Z",
        cwd: "/tmp",
        message: { content: "Fix ENG-101 null pointer" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-16T10:02:00Z",
        message: {
          content: [
            { type: "tool_use", name: "Bash", input: { command: 'git commit -m "fix(ENG-101): guard null"' } },
          ],
        },
      },
    ]);

    runHookSh("hook-stop", { session_id: "sess-1", transcript_path: transcript, cwd: "/tmp" }, { stateHome: sb.stateHome });
    runHookSh("hook-flush", { session_id: "sess-1", transcript_path: transcript, cwd: "/tmp" }, { stateHome: sb.stateHome });

    assert.equal(existsSync(sb.vaultDir), false, "vaultDir must not be created when uninitialized");
  } finally {
    sb.cleanup();
  }
});

test("live hooks log only at task milestones and session wrap-ups, updating one consolidated session entry in place", () => {
  const sb = makeSandbox();
  try {
    const initOut = JSON.parse(runCli(["init", sb.vaultDir, "--topic-dirs", "src/integrations"], { stateHome: sb.stateHome }));
    assert.equal(initOut.ok, true);
    assert.match(initOut.howItRuns, /hooks/i);
    assert.equal(existsSync(join(sb.vaultDir, "Work-Map.md")), true);

    const fakeRepo = join(sb.root, "worktrees", "web-app", "web-app-ENG4184");
    mkdirSync(fakeRepo, { recursive: true });
    const transcript = join(sb.claudeProjects, "web-app", "sess-live-1.jsonl");

    // Turn 1: Read-only question -> Stop must NOT write anything
    const entries = [
      {
        type: "user",
        timestamp: "2026-11-16T14:00:00Z",
        cwd: fakeRepo,
        gitBranch: "fix/ENG-4184-null-scope",
        message: { content: "Investigate ENG-4184 null scope token response for PayFlow" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-16T14:01:00Z",
        message: {
          content: [{ type: "tool_use", name: "Read", input: { file_path: join(fakeRepo, "src/oauth.ts") } }],
        },
      },
    ];
    writeJsonl(transcript, entries);
    runHookSh("hook-stop", { session_id: "sess-live-1", transcript_path: transcript, cwd: fakeRepo }, { stateHome: sb.stateHome });
    assert.equal(readdirSync(join(sb.vaultDir, "Daily")).length, 0, "read-only turn must not create a daily log");

    // Turn 2: Intermediate code edit without a commit/PR milestone -> Stop still stays quiet
    entries.push({
      type: "assistant",
      timestamp: "2026-11-16T14:10:00Z",
      message: {
        content: [
          {
            type: "tool_use",
            name: "Edit",
            input: { file_path: join(fakeRepo, "src/integrations/payflow/oauth.ts") },
          },
        ],
      },
    });
    writeJsonl(transcript, entries);
    runHookSh("hook-stop", { session_id: "sess-live-1", transcript_path: transcript, cwd: fakeRepo }, { stateHome: sb.stateHome });
    assert.equal(readdirSync(join(sb.vaultDir, "Daily")).length, 0, "intermediate edit before task milestone must not spam Stop log");

    // Turn 3: Task milestone (git commit) -> Stop writes consolidated entry + backlinks
    entries.push({
      type: "assistant",
      timestamp: "2026-11-16T14:20:00Z",
      message: {
        content: [
          {
            type: "tool_use",
            name: "Bash",
            input: { command: 'git commit -m "fix(ENG-4184): handle null scope in token response"' },
          },
        ],
      },
    });
    writeJsonl(transcript, entries);
    runHookSh("hook-stop", { session_id: "sess-live-1", transcript_path: transcript, cwd: fakeRepo }, { stateHome: sb.stateHome });

    const dailyFiles = readdirSync(join(sb.vaultDir, "Daily"));
    assert.equal(dailyFiles.length, 1);
    const dailyPath = join(sb.vaultDir, "Daily", dailyFiles[0]);
    const dailyAfterCommit = readFileSync(dailyPath, "utf8");
    assert.match(dailyAfterCommit, /\[\[web-app\]\]/);
    assert.match(dailyAfterCommit, /\[\[ENG-4184\]\]/);
    assert.match(dailyAfterCommit, /\[\[payflow\]\]/);
    assert.match(dailyAfterCommit, /\(1 commit\)/);

    // Turn 4: PR opened in the SAME session -> updates existing bullet in place rather than duplicating
    entries.push(
      {
        type: "assistant",
        timestamp: "2026-11-16T14:35:00Z",
        message: {
          content: [
            {
              type: "tool_use",
              id: "toolu_pr_create",
              name: "Bash",
              input: { command: 'gh pr create --repo example-org/web-app --title "fix(ENG-4184): null scope"' },
            },
          ],
        },
      },
      {
        type: "user",
        timestamp: "2026-11-16T14:35:05Z",
        message: {
          content: [
            {
              type: "tool_result",
              tool_use_id: "toolu_pr_create",
              content: "https://github.com/example-org/web-app/pull/9696\n",
            },
          ],
        },
      },
    );
    writeJsonl(transcript, entries);
    runHookSh("hook-stop", { session_id: "sess-live-1", transcript_path: transcript, cwd: fakeRepo }, { stateHome: sb.stateHome });

    const dailyAfterPr = readFileSync(dailyPath, "utf8");
    const markerMatches = dailyAfterPr.match(/\^tv-s-sess-live-1\b/g) ?? [];
    assert.equal(markerMatches.length, 1, "same session must update in place without adding a second line");
    assert.match(dailyAfterPr, /opened \[web-app#9696\]\(https:\/\/github\.com\/example-org\/web-app\/pull\/9696\)/);

    // Verify bidirectional backlinks in Ticket, Repo, and Topic notes
    const ticketNote = readFileSync(join(sb.vaultDir, "Tickets", "ENG-4184.md"), "utf8");
    assert.match(ticketNote, /\[\[web-app\]\]/);
    assert.match(ticketNote, /\[\[payflow\]\]/);

    const repoNote = readFileSync(join(sb.vaultDir, "Repos", "web-app.md"), "utf8");
    assert.match(repoNote, /\[\[ENG-4184\]\]/);

    const topicNote = readFileSync(join(sb.vaultDir, "Topics", "payflow.md"), "utf8");
    assert.match(topicNote, /\[\[ENG-4184\]\]/);
    assert.match(topicNote, /\[\[web-app\]\]/);

    // Separate session with file edits that ends WITHOUT a commit -> flushed once on SessionEnd (hook-flush)
    const sess2 = join(sb.claudeProjects, "web-app", "sess-live-2.jsonl");
    writeJsonl(sess2, [
      {
        type: "user",
        timestamp: "2026-11-16T16:00:00Z",
        cwd: fakeRepo,
        message: { content: "Prototype retry backoff for WEB-566" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-16T16:05:00Z",
        message: {
          content: [{ type: "tool_use", name: "Write", input: { file_path: join(fakeRepo, "src/backoff.ts") } }],
        },
      },
    ]);
    runHookSh("hook-stop", { session_id: "sess-live-2", transcript_path: sess2, cwd: fakeRepo }, { stateHome: sb.stateHome });
    assert.equal(existsSync(join(sb.vaultDir, "Tickets", "WEB-566.md")), false, "uncommitted session waits until wrap-up");

    runHookSh("hook-flush", { session_id: "sess-live-2", transcript_path: sess2, cwd: fakeRepo }, { stateHome: sb.stateHome });
    assert.equal(existsSync(join(sb.vaultDir, "Tickets", "WEB-566.md")), true, "SessionEnd/PreCompact flushes substantive uncommitted work");
  } finally {
    sb.cleanup();
  }
});

test("adapts to custom existing Obsidian vault layouts (.obsidian/daily-notes.json, custom headings, preexisting notes, link-only folders)", () => {
  const sb = makeSandbox();
  try {
    // Simulate a user's existing custom Obsidian vault
    mkdirSync(join(sb.vaultDir, ".obsidian"), { recursive: true });
    mkdirSync(join(sb.vaultDir, "10 Calendar", "Daily"), { recursive: true });
    mkdirSync(join(sb.vaultDir, "50 Templates"), { recursive: true });
    mkdirSync(join(sb.vaultDir, "Active Work"), { recursive: true });

    writeFileSync(
      join(sb.vaultDir, ".obsidian", "daily-notes.json"),
      JSON.stringify({ folder: "10 Calendar/Daily", template: "50 Templates/Daily" }),
      "utf8",
    );
    writeFileSync(
      join(sb.vaultDir, "50 Templates", "Daily.md"),
      "---\ntype: daily\ndate: {{date}}\n---\n## My Personal Focus\n\nKeep this intact.\n\n## Activity\n",
      "utf8",
    );
    writeFileSync(
      join(sb.vaultDir, "10 Calendar", "Daily", "2026-11-15.md"),
      "---\ntype: daily\n---\n## Activity\n- 10:00 prior entry\n",
      "utf8",
    );
    writeFileSync(
      join(sb.vaultDir, "Active Work", "OPS-900.md"),
      "---\ntype: custom-ticket\nowner: cameron\n---\n# Custom Ticket Heading\n\nMy handwritten investigation notes.\n",
      "utf8",
    );

    mkdirSync(join(sb.vaultDir, "Reading"), { recursive: true });
    const unrelatedNote = "---\ntype: book\n---\n# Invoicing\n\nNotes on a book about invoicing.\n";
    writeFileSync(join(sb.vaultDir, "Reading", "Invoicing.md"), unrelatedNote, "utf8");

    const inspected = JSON.parse(runCli(["inspect", sb.vaultDir], { stateHome: sb.stateHome }));
    assert.equal(inspected.isObsidianVaultRoot, true);
    assert.equal(inspected.suggestedConfig.folders.daily, "10 Calendar/Daily");
    assert.equal(inspected.suggestedConfig.dailyTemplate, "50 Templates/Daily.md");
    assert.equal(inspected.suggestedConfig.dailySection, "Activity");

    // Initialize with repos disabled ("none" -> link-only) and map disabled ("none")
    runCli(
      ["init", sb.vaultDir, "--repos", "none", "--topics", "Domains", "--map", "none"],
      { stateHome: sb.stateHome },
    );

    runCli(
      [
        "log",
        "--date",
        "2026-11-16",
        "--summary",
        "Verified pagination cursor behavior on OPS-900",
        "--tickets",
        "OPS-900",
        "--repos",
        "api-server",
        "--topics",
        "Invoicing",
      ],
      { stateHome: sb.stateHome },
    );

    assert.equal(existsSync(join(sb.vaultDir, "Work-Map.md")), false, "map=none must not create Work-Map.md");
    assert.equal(existsSync(join(sb.vaultDir, "Repos")), false, "repos=none must not create Repos folder");
    assert.equal(existsSync(join(sb.vaultDir, "Tickets", "OPS-900.md")), false, "must reuse preexisting Active Work/OPS-900.md instead of duplicating");

    const updatedPreexisting = readFileSync(join(sb.vaultDir, "Active Work", "OPS-900.md"), "utf8");
    assert.match(updatedPreexisting, /My handwritten investigation notes\./, "human prose must remain intact");
    assert.match(updatedPreexisting, /owner: cameron/, "custom frontmatter must remain intact");
    assert.match(updatedPreexisting, /\[\[api-server\]\]/, "link-only repo still emits [[api-server]] wikilink");
    assert.match(updatedPreexisting, /\[\[Invoicing\]\]/);
    assert.equal(
      readFileSync(join(sb.vaultDir, "Reading", "Invoicing.md"), "utf8"),
      unrelatedNote,
      "a same-named note of another kind is linked to, never written into",
    );
    assert.equal(existsSync(join(sb.vaultDir, "Domains", "Invoicing.md")), false, "and no ambiguous duplicate is created");

    const createdDaily = readFileSync(join(sb.vaultDir, "10 Calendar", "Daily", "2026-11-16.md"), "utf8");
    assert.match(createdDaily, /Keep this intact\./, "daily note must render from detected .obsidian template");
    assert.match(createdDaily, /## Activity/);
    assert.match(createdDaily, /\[\[OPS-900\]\]/);
  } finally {
    sb.cleanup();
  }
});

test("historical backfill mines main + subagent transcripts, filters false-positive IDs, enriches tickets, and stays idempotent", () => {
  const sb = makeSandbox();
  try {
    runCli(["init", sb.vaultDir], { stateHome: sb.stateHome });

    // False-positive ID check on parser directly
    const extracted = extractTicketsFromText(
      "Use UTF-8 and SHA-256 with RFC-6749, CVE-2024, HTTP-401, NODE-22 on ENG-4184 and support #7706 (https://linear.app/example/issue/WEB-566/test, https://tracker.example.com/browse/QA2-31)",
    );
    assert.deepEqual(extracted.sort(), ["ENG-4184", "QA2-31", "WEB-566"]);
    const filtered = extractTicketsFromText("Touches ENG-4184, WEB-566 and https://linear.app/example/issue/OPS-9", { teamPrefixes: ["WEB"] });
    assert.deepEqual(filtered, ["WEB-566"], "teamPrefixes limits detection to the listed prefixes");

    // Main session + subagent transcript
    const mainSess = join(sb.claudeProjects, "proj-1", "sess-hist-1.jsonl");
    const subSess = join(sb.claudeProjects, "proj-1", "sess-hist-1", "subagents", "agent-a.jsonl");
    const repoDir = join(sb.root, "worktrees", "api-server", "api-server-OPS1200");
    mkdirSync(repoDir, { recursive: true });

    writeJsonl(mainSess, [
      {
        type: "user",
        timestamp: "2026-11-10T09:00:00Z",
        cwd: repoDir,
        message: { content: "Add invoices endpoint for support #7706 and OPS-1200 using UTF-8" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-10T09:05:00Z",
        message: {
          content: [{ type: "tool_use", name: "Agent", input: { prompt: "Implement action" } }],
        },
      },
    ]);
    writeJsonl(subSess, [
      {
        type: "assistant",
        timestamp: "2026-11-10T09:15:00Z",
        message: {
          content: [
            {
              type: "tool_use",
              name: "Write",
              input: { file_path: join(repoDir, "src/handlers/invoices.ts") },
            },
            {
              type: "tool_use",
              name: "Bash",
              input: { command: 'git commit -m "feat(OPS-1200): add invoices endpoint"' },
            },
          ],
        },
      },
    ]);

    const enrichFile = join(sb.root, "enrich.json");
    writeFileSync(
      enrichFile,
      JSON.stringify({
        tickets: {
          "OPS-1200": {
            title: "Invoices endpoint",
            status: "Merged",
            url: "https://linear.app/org/issue/OPS-1200",
            topics: ["Billing"],
          },
        },
      }),
      "utf8",
    );

    const firstRun = JSON.parse(
      runCli(
        ["backfill", "--claude-dir", sb.claudeProjects, "--enrich", enrichFile],
        { stateHome: sb.stateHome },
      ),
    );
    assert.equal(firstRun.ok, true);
    assert.equal(firstRun.stats.substantiveMatched, 1);

    // Incremental second run skips unchanged files
    const secondRun = JSON.parse(
      runCli(["backfill", "--claude-dir", sb.claudeProjects], { stateHome: sb.stateHome }),
    );
    assert.equal(secondRun.stats.skippedUnchanged, 1);
    assert.equal(secondRun.writtenNotesCount, 0);

    // Forced --full run re-processes without duplicating bullets
    runCli(["backfill", "--claude-dir", sb.claudeProjects, "--full", "--enrich", enrichFile], {
      stateHome: sb.stateHome,
    });

    const agiNote = readFileSync(join(sb.vaultDir, "Tickets", "OPS-1200.md"), "utf8");
    assert.equal((agiNote.match(/\^tv-s-sess-hist-1\b/g) ?? []).length, 1);
    assert.match(agiNote, /title: "Invoices endpoint"/);
    assert.match(agiNote, /\[\[Billing\]\]/);
    assert.match(agiNote, /\[\[api-server\]\]/);

    const checkReport = JSON.parse(runCli(["check", "--refresh-map"], { stateHome: sb.stateHome }));
    assert.equal(checkReport.ok, true);
    assert.equal(checkReport.unresolvedCount, 0);
    assert.ok(checkReport.edgesCount >= 8, "graph must contain bidirectional backlink edges");
  } finally {
    sb.cleanup();
  }
});

test("security: scrubs secrets, blocks symlinks & path traversal, neutralizes injections, and enforces private state permissions", () => {
  const sb = makeSandbox();
  try {
    runCli(["init", sb.vaultDir, "--exclude", "Confidential"], { stateHome: sb.stateHome });

    // 1. Private permissions on state dir and config.json (POSIX)
    if (process.platform !== "win32") {
      const dirMode = statSync(sb.stateHome).mode & 0o777;
      const cfgMode = statSync(join(sb.stateHome, "config.json")).mode & 0o777;
      assert.equal(dirMode, 0o700, "state directory must be 0700");
      assert.equal(cfgMode, 0o600, "config.json must be 0600");
    }

    // 2. Redaction of diverse credential shapes (constructed dynamically so static secret scanners are not tripped by test fixtures)
    const fakeJwt = ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJzdWIiOiIxMjM0NTY3ODkwIn0", "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"].join(".");
    const fakeAnt = ["sk", "ant", "api03", "x".repeat(24)].join("-");
    const fakeGhp = `ghp_${"a".repeat(28)}`;
    const fakeSlack = ["xoxb", "1234567890", "abcdefghijklmno"].join("-");
    const fakeAws = `AKIA${"Z".repeat(16)}`;
    const rawSecretPrompt = [
      `Debug ENG-777 with Authorization: Bearer ${fakeJwt}`,
      `api_key=${fakeAnt}`,
      fakeGhp,
      fakeSlack,
      fakeAws,
      "client_secret: superSecretValue999",
      "https://admin:hunter2@example.com/callback?token=mySecretToken&code=oauthCode123",
    ].join(" ");

    const scrubbed = redactSecrets(rawSecretPrompt);
    assert.equal(scrubbed.includes(fakeAnt), false);
    assert.equal(scrubbed.includes(fakeGhp), false);
    assert.equal(scrubbed.includes(fakeSlack), false);
    assert.equal(scrubbed.includes(fakeAws), false);
    assert.doesNotMatch(scrubbed, /superSecretValue999/);
    assert.doesNotMatch(scrubbed, /hunter2/);
    assert.doesNotMatch(scrubbed, /mySecretToken/);
    assert.doesNotMatch(scrubbed, /oauthCode123/);
    assert.doesNotMatch(scrubbed, /SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c/);

    // 3. Injection neutralization (YAML frontmatter, HTML/script, Templater, dangerous schemes, spoofed wikilinks)
    const hostile = sanitizeInlineText(
      "---\nevil: true\n---\n<script>alert(1)</script> <% tp.system.cmd() %> [[Spoof]] javascript:alert(1) obsidian://adv-uri",
      300,
    );
    assert.doesNotMatch(hostile, /<script/i);
    assert.doesNotMatch(hostile, /<%/);
    assert.doesNotMatch(hostile, /\[\[/);
    assert.doesNotMatch(hostile, /javascript:/i);
    assert.doesNotMatch(hostile, /obsidian:/i);
    const fakeEnvSecret = "q".repeat(16);
    const quoted = sanitizeInlineText(`{"password":"correct-horse-battery"} AWS_SECRET_ACCESS_KEY=${fakeEnvSecret}`, 300);
    assert.doesNotMatch(quoted, /correct-horse-battery/);
    assert.equal(quoted.includes(fakeEnvSecret), false);
    assert.doesNotMatch(sanitizeInlineText("Fix ![p](https://tracker.example/t.gif) <img src=x>", 300), /!\[|<img/i);
    const started = Date.now();
    sanitizeInlineText("a.".repeat(250_000), 160);
    assert.ok(Date.now() - started < 500, "redaction stays linear on adversarial input");
    const quotedMultiword = redactSecrets(`password: "correct horse battery" https://x.example/a?auth=s3cr3tA&session=s3cr3tB&X-Amz-Credential=s3cr3tC`);
    assert.doesNotMatch(quotedMultiword, /correct horse|s3cr3t/);
    for (const quote of ['"', "'"]) {
      const longValue = "k".repeat(8192);
      const assignment = "password: " + quote + longValue + "\\" + quote + "suffix";
      assert.equal(redactSecrets(assignment + quote + ", next"), "password: [REDACTED], next");
      assert.equal(redactSecrets(assignment), "password: [REDACTED]");
    }
    assert.equal(sanitizeExternalUrl("javascript:alert(1)"), null);
    assert.equal(sanitizeExternalUrl("http://insecure.example.com/pr/1"), null);
    assert.equal(
      sanitizeExternalUrl("https://user:pw@github.com/org/repo/pull/1?token=abc(1)"),
      "https://github.com/org/repo/pull/1?token=REDACTED",
    );

    // 4. End-to-end transcript with secrets + traversal attempt must never leak secrets or escape vault
    const hostileTranscript = join(sb.claudeProjects, "sec", "sess-sec.jsonl");
    writeJsonl(hostileTranscript, [
      {
        type: "user",
        timestamp: "2026-11-16T12:00:00Z",
        cwd: "/tmp",
        message: { content: `${rawSecretPrompt} <script>evil()</script>` },
      },
      {
        type: "assistant",
        timestamp: "2026-11-16T12:01:00Z",
        message: {
          content: [
            { type: "tool_use", name: "Bash", input: { command: 'git commit -m "fix(ENG-777): rotate client_secret=topsecretvalue123"' } },
            { type: "tool_use", name: "Write", input: { file_path: join(sb.vaultDir, "Plans", "roadmap.md") } },
            { type: "tool_use", name: "Write", input: { file_path: join(sb.vaultDir, "Confidential", "roadmap.md") } },
            { type: "tool_use", name: "Write", input: { file_path: join(sb.vaultDir, "Confidential", "merger-plan.md") } },
          ],
        },
      },
    ]);
    runCli(["backfill", "--claude-dir", sb.claudeProjects], { stateHome: sb.stateHome });

    const eng777 = readFileSync(join(sb.vaultDir, "Tickets", "ENG-777.md"), "utf8");
    assert.equal(eng777.includes(fakeAnt), false);
    assert.equal(eng777.includes(fakeGhp), false);
    assert.doesNotMatch(eng777, /hunter2|mySecretToken|topsecretvalue123|<script\b/i);
    assert.doesNotMatch(eng777, /merger-plan/, "notes written under an excluded path are never named");
    assert.match(eng777, /wrote \[\[roadmap\]\]/, "an excluded note never hides an included one with the same name");

    // 5. Path traversal & symlink escape blocks
    const vaultReal = JSON.parse(runCli(["status"], { stateHome: sb.stateHome })).config.vaultDir;
    assert.throws(() => resolveContainedVaultPath(vaultReal, "../../outside-probe.txt"), /outside configured vault/);

    const outsideDir = join(sb.root, "outside-target");
    mkdirSync(outsideDir, { recursive: true });
    symlinkSync(outsideDir, join(vaultReal, "EscapedLink"));
    assert.throws(() => resolveContainedVaultPath(vaultReal, "EscapedLink", "note.md"), /symbolic link/);

    // 6. Exclusion manifest fail-closed check
    mkdirSync(join(vaultReal, "Confidential"), { recursive: true });
    writeFileSync(join(vaultReal, "Confidential", "ENG-777.md"), "DO NOT TOUCH", "utf8");
    const checkAfterExclude = JSON.parse(runCli(["check"], { stateHome: sb.stateHome }));
    assert.equal(
      checkAfterExclude.duplicateBasenames.length,
      0,
      "excluded Confidential/ENG-777.md must never be indexed or read",
    );

    runCli(["configure", "--exclude-manifest", "corrupt-exclusions.json"], { stateHome: sb.stateHome });
    writeFileSync(join(vaultReal, "corrupt-exclusions.json"), "{not-valid-json", "utf8");
    assert.equal(
      resolveActiveConfig({ TURN_VAULT_HOME: sb.stateHome }, sb.stateHome),
      null,
      "corrupt exclusion manifest must fail closed",
    );
  } finally {
    sb.cleanup();
  }
});

test("command parser ignores heredoc bodies while capturing gh pr --repo shorthand and default HOME discovery", () => {
  const sb = makeSandbox();
  try {
    const defaultClaudeDir = join(sb.root, ".claude", "projects", "demo");
    mkdirSync(defaultClaudeDir, { recursive: true });
    writeJsonl(join(defaultClaudeDir, "sess-heredoc.jsonl"), [
      {
        type: "user",
        timestamp: "2026-11-16T08:00:00Z",
        cwd: "/tmp",
        message: { content: "Write a parser script and merge WEB-600 PR" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-16T08:01:00Z",
        message: {
          content: [
            {
              type: "tool_use",
              name: "Bash",
              input: {
                command: "cat <<'EOF' > /tmp/script.py\npats = ['gh pr merge', 'git commit']\nEOF",
              },
            },
          ],
        },
      },
    ]);

    const scan1 = JSON.parse(
      runCli(["scan", "--compact"], { stateHome: sb.stateHome, env: { HOME: sb.root } }),
    );
    assert.equal(scan1.units.length, 0, "heredoc mentioning gh pr merge / git commit must not trigger false milestones");

    writeJsonl(join(defaultClaudeDir, "sess-merge.jsonl"), [
      {
        type: "user",
        timestamp: "2026-11-16T09:00:00Z",
        cwd: "/tmp",
        message: { content: "Merge PR for WEB-600" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-16T09:02:00Z",
        message: {
          content: [
            {
              type: "tool_use",
              name: "Bash",
              input: {
                command: "gh pr merge 522 --repo example-org/plugins-repo --squash",
              },
            },
          ],
        },
      },
    ]);

    const scan2 = JSON.parse(
      runCli(["scan", "--compact"], { stateHome: sb.stateHome, env: { HOME: sb.root } }),
    );
    assert.equal(scan2.units.length, 1);
    assert.deepEqual(scan2.prs.map((p) => p.url), [
      "https://github.com/example-org/plugins-repo/pull/522",
    ]);
  } finally {
    sb.cleanup();
  }
});

test("security audit regressions: pure gitdir worktree parser, DB URI redaction, intermediate symlink block, .obsidian traversal guard, prototype key safety, and 0600 note permissions", () => {
  const sb = makeSandbox();
  try {
    // F-01: Pure filesystem .git / worktree gitdir resolution without spawning git
    const mainRepo = join(sb.root, "main-checkouts", "web-app");
    const mainGitWorktreeDir = join(mainRepo, ".git", "worktrees", "wt-1");
    const wtDir = join(sb.root, "detached-wt", "custom-checkout-name");
    mkdirSync(mainGitWorktreeDir, { recursive: true });
    mkdirSync(wtDir, { recursive: true });
    writeFileSync(join(mainGitWorktreeDir, "commondir"), "../..\n", "utf8");
    writeFileSync(join(wtDir, ".git"), `gitdir: ${mainGitWorktreeDir}\n`, "utf8");
    assert.equal(resolveNormalizedRepoName(wtDir), "web-app");

    // F-02: Non-HTTP connection URI credentials + extra token families
    const dbSecret = "postgres://dbadmin:SuperSecretDbPass99@db.example.internal:5432/app";
    const redisSecret = "redis://:RedisPass777@127.0.0.1:6379/0";
    const gitlabToken = `glpat-${"z".repeat(24)}`;
    const npmToken = `npm_${"n".repeat(30)}`;
    const redactedUris = redactSecrets(`${dbSecret} ${redisSecret} ${gitlabToken} ${npmToken} x-api-key: MySecretHeaderKey999`);
    assert.doesNotMatch(redactedUris, /SuperSecretDbPass99|RedisPass777|MySecretHeaderKey999/);
    assert.equal(redactedUris.includes(gitlabToken), false);
    assert.equal(redactedUris.includes(npmToken), false);

    // F-04: Hostile .obsidian/daily-notes.json with ../../ traversal must stay contained
    const outsideSecretDir = join(sb.root, "outside-secret");
    mkdirSync(outsideSecretDir, { recursive: true });
    writeFileSync(join(outsideSecretDir, "2026-11-16.md"), "## Activity\nTOP SECRET\n", "utf8");
    mkdirSync(join(sb.vaultDir, ".obsidian"), { recursive: true });
    writeFileSync(
      join(sb.vaultDir, ".obsidian", "daily-notes.json"),
      JSON.stringify({ folder: "../../outside-secret", template: "../../outside-secret/2026-11-16.md" }),
      "utf8",
    );
    const layout = inspectVaultLayout(sb.vaultDir);
    assert.equal(layout.suggestedConfig.folders.daily, "outside-secret", "traversal components stripped");
    assert.equal(layout.suggestedConfig.dailySection, "Work Log", "must not read outside-secret file to infer Activity heading");
    assert.equal(layout.suggestedConfig.dailyTemplate, null);

    // F-03, F-05, F-06, F-07
    runCli(["init", sb.vaultDir, "--daily", "Daily", "--exclude", "PrivateArea"], { stateHome: sb.stateHome });
    const vaultReal = JSON.parse(runCli(["status"], { stateHome: sb.stateHome })).config.vaultDir;
    mkdirSync(join(vaultReal, "PrivateArea", "Sub"), { recursive: true });
    symlinkSync(join(vaultReal, "PrivateArea"), join(vaultReal, "InternalAlias"));
    assert.throws(
      () => resolveContainedVaultPath(vaultReal, "InternalAlias", "Sub", "note.md"),
      /symbolic link/,
      "intermediate vault-internal symlink must be rejected",
    );

    // Prototype keys in sessionId and tickets must never pollute Object.prototype or crash
    runCli(
      [
        "log",
        "--date",
        "2026-11-16",
        "--session-id",
        "__proto__",
        "--tickets",
        "constructor,ENG-888",
        "--summary",
        "Verify prototype safety",
      ],
      { stateHome: sb.stateHome },
    );

    const eng888Path = join(vaultReal, "Tickets", "ENG-888.md");
    assert.equal(existsSync(eng888Path), true);
    if (process.platform !== "win32") {
      assert.equal(statSync(eng888Path).mode & 0o777, 0o600, "newly created vault notes default to 0600");
    }

    // Symlinked --enrich file and paths outside home/tmpdir must be rejected
    assert.throws(() => assertPathWithinAllowedRoots("/etc/hosts"), /outside user home or temp/);
    symlinkSync("/", join(sb.root, "root-link"));
    assert.throws(
      () => assertPathWithinAllowedRoots(join(sb.root, "root-link", "new-vault")),
      /canonical path outside/,
      "a missing folder under a symlinked ancestor resolves through that ancestor",
    );
    const realEnrich = join(sb.root, "real-enrich.json");
    const symEnrich = join(sb.root, "sym-enrich.json");
    writeFileSync(realEnrich, "{}", "utf8");
    symlinkSync(realEnrich, symEnrich);
    assert.throws(
      () => runCli(["backfill", "--claude-dir", sb.claudeProjects, "--enrich", symEnrich], { stateHome: sb.stateHome }),
      /symbolic link/,
    );
  } finally {
    sb.cleanup();
  }
});

test("tracker detection is generic: execute-style MCP action IDs, opt-in topic directories, no vendor-specific parsing", () => {
  const sb = makeSandbox();
  try {
    const repoDir = join(sb.root, "code", "web-app");
    mkdirSync(join(repoDir, ".git"), { recursive: true });
    const transcript = join(sb.claudeProjects, "web-app", "sess-generic.jsonl");
    writeJsonl(transcript, [
      {
        type: "user",
        timestamp: "2026-11-12T09:00:00Z",
        cwd: repoDir,
        message: { content: "Close OPS-12 after the payments fix, like https://github.com/example-org/web-app/pull/7 (see docs/notes#3)" },
      },
      {
        type: "assistant",
        timestamp: "2026-11-12T09:05:00Z",
        message: {
          content: [
            { type: "tool_use", name: "mcp__tracker__execute_action", input: { action_id: "issues_update_issue", id: "OPS-12" } },
            { type: "tool_use", name: "mcp__tracker__execute_action", input: { action_id: "issues_list_issues" } },
            { type: "tool_use", name: "Edit", input: { file_path: join(repoDir, "src/integrations/payments/client.ts") } },
            { type: "tool_use", id: "toolu_create", name: "Bash", input: { command: "gh pr create --fill" } },
            { type: "tool_use", id: "toolu_cat", name: "Bash", input: { command: "cat CHANGELOG.md" } },
          ],
        },
      },
      {
        type: "user",
        timestamp: "2026-11-12T09:06:00Z",
        message: {
          content: [
            { type: "tool_result", tool_use_id: "toolu_cat", content: "Fixed in example-org/web-app#5" },
            { type: "tool_result", tool_use_id: "toolu_create", content: "https://github.com/example-org/web-app/pull/8" },
          ],
        },
      },
    ]);

    const withoutTopicDirs = parseSessionTranscript(transcript, {});
    assert.deepEqual(withoutTopicDirs.tickets, ["OPS-12"]);
    assert.deepEqual(withoutTopicDirs.trackerActions, ["issues_update_issue"], "read-only actions are not milestones");
    assert.ok(withoutTopicDirs.milestones.includes("tracker_updated"));
    assert.deepEqual(withoutTopicDirs.topics, [], "file-path topics are opt-in");
    assert.deepEqual(withoutTopicDirs.repos, ["web-app"]);
    assert.deepEqual(
      withoutTopicDirs.prs.map((pr) => `${pr.number}:${pr.action}`).sort(),
      ["7:referenced", "8:opened"],
      "only the gh pr create result is mined, and prompt prose never yields owner/repo#N shorthand",
    );

    const withTopicDirs = parseSessionTranscript(transcript, { topicDirs: ["src/integrations"] });
    assert.deepEqual(withTopicDirs.topics, ["payments"]);

    assert.deepEqual(extractTicketsFromText("pylon #7706 and support ticket 4411"), [], "no vendor-specific ticket formats");
  } finally {
    sb.cleanup();
  }
});
