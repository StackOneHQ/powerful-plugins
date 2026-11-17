#!/usr/bin/env node
import { appendFileSync, existsSync, lstatSync, mkdirSync, readFileSync, readSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { join, parse as parsePath, resolve } from "node:path";
import {
  assertPathWithinAllowedRoots,
  configPath,
  expandTilde,
  hhmmString,
  hookLogPath,
  inspectVaultLayout,
  loadState,
  loadStoredConfig,
  localDateString,
  normalizeConfig,
  redactSecrets,
  resolveActiveConfig,
  resolveStateHome,
  safeNoteSlug,
  sanitizeExternalUrl,
  sanitizeInlineText,
  saveConfig,
  saveState,
  withVaultLock,
} from "./core.mjs";
import {
  checkVaultGraph,
  initializeVaultFolder,
  refreshWorkMap,
  writeWorkUnitsToVault,
} from "./graph-writer.mjs";
import {
  extractTicketsFromText,
  parseSessionTranscript,
  resolveNormalizedRepoName,
  scanTranscriptHistory,
} from "./transcript-parser.mjs";

function parseArgs(argv) {
  const positionals = [];
  const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      positionals.push(arg);
      continue;
    }
    const eqIdx = arg.indexOf("=");
    if (eqIdx >= 0) {
      flags[arg.slice(2, eqIdx)] = arg.slice(eqIdx + 1);
    } else {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        flags[key] = next;
        i += 1;
      } else {
        flags[key] = true;
      }
    }
  }
  return { positionals, flags };
}

function splitCsv(val) {
  if (typeof val !== "string" || !val.trim()) return [];
  return val
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function readStdinJson(maxBytes = 512 * 1024) {
  try {
    if (process.stdin.isTTY) return {};
    const chunks = [];
    let total = 0;
    const buf = Buffer.allocUnsafe(16 * 1024);
    while (total < maxBytes) {
      let n = 0;
      try {
        n = readSync(0, buf, 0, Math.min(buf.length, maxBytes - total), null);
      } catch (err) {
        if (err?.code === "EAGAIN") continue;
        break;
      }
      if (n <= 0) break;
      chunks.push(Buffer.from(buf.subarray(0, n)));
      total += n;
    }
    if (total === 0) return {};
    const raw = Buffer.concat(chunks, total).toString("utf8").trim();
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function logHookError(stateHome, err) {
  try {
    const safeHome = assertPathWithinAllowedRoots(stateHome);
    mkdirSync(safeHome, { recursive: true, mode: 0o700 });
    const safeLog = assertPathWithinAllowedRoots(hookLogPath(safeHome));
    const msg = err instanceof Error ? err.message : String(err);
    appendFileSync(
      safeLog,
      `${new Date().toISOString()} ${redactSecrets(msg)}\n`,
      { encoding: "utf8", mode: 0o600 },
    );
  } catch {
    // Best-effort hook diagnostics only
  }
}

function milestoneSignature(unit) {
  return JSON.stringify({
    milestones: unit.milestones,
    commitsCount: unit.commitsCount,
    prs: (unit.prs ?? []).map((p) => `${p.action}:${p.url}`),
    vaultNotes: (unit.vaultNotes ?? []).map((n) => n.title),
    trackerActions: unit.trackerActions ?? [],
  });
}

function assertSafeVaultRootTarget(candidateDir) {
  const abs = resolve(expandTilde(candidateDir));
  const rootPath = parsePath(abs).root;
  if (abs === rootPath) {
    throw new Error("Refusing to initialize filesystem root as an Obsidian vault folder.");
  }
  if (abs === resolve(homedir())) {
    throw new Error("Refusing to use your home directory directly; choose an Obsidian vault or subfolder (for example ~/Documents/Obsidian/Work).");
  }
  return abs;
}

function applyFlagOverridesToConfig(base, flags) {
  const folders = { ...(base.folders ?? {}) };
  if (flags.daily !== undefined) folders.daily = String(flags.daily);
  if (flags.tickets !== undefined) folders.tickets = String(flags.tickets);
  if (flags.repos !== undefined) folders.repos = String(flags.repos);
  if (flags.topics !== undefined) folders.topics = String(flags.topics);
  if (flags.notes !== undefined) folders.notes = String(flags.notes);

  const next = {
    ...base,
    folders,
  };
  if (flags.map !== undefined) next.mapFile = String(flags.map);
  if (flags["daily-section"] !== undefined) next.dailySection = String(flags["daily-section"]);
  if (flags["daily-template"] !== undefined) next.dailyTemplate = String(flags["daily-template"]);
  if (flags["team-prefixes"] !== undefined) next.teamPrefixes = splitCsv(String(flags["team-prefixes"]));
  if (flags["topic-dirs"] !== undefined) next.topicDirs = splitCsv(String(flags["topic-dirs"]));
  if (flags.exclude !== undefined) next.excludePaths = splitCsv(String(flags.exclude));
  if (flags["exclude-manifest"] !== undefined) next.excludeManifest = String(flags["exclude-manifest"]);
  return normalizeConfig(next);
}

async function handleHookEvent(mode, stateHome) {
  const payload = readStdinJson();
  if (payload.stop_hook_active) return;

  const activeConfig = resolveActiveConfig(process.env, stateHome);
  if (!activeConfig) return;

  const transcriptPath = typeof payload.transcript_path === "string" ? payload.transcript_path : "";
  if (!transcriptPath || !transcriptPath.endsWith(".jsonl") || !existsSync(transcriptPath)) return;

  const unit = parseSessionTranscript(transcriptPath, {
    sessionId: typeof payload.session_id === "string" ? payload.session_id : "",
    cwd: typeof payload.cwd === "string" ? payload.cwd : process.cwd(),
    vaultDir: activeConfig.vaultDir,
    teamPrefixes: activeConfig.teamPrefixes,
    topicDirs: activeConfig.topicDirs,
    excludePaths: activeConfig.excludePaths,
    includeSubagents: true,
  });

  if (!unit || !unit.isSubstantive) return;

  await withVaultLock(stateHome, "vault", async () => {
    const state = loadState(stateHome);
    const prev = Object.hasOwn(state.sessions, unit.sessionId) ? state.sessions[unit.sessionId] : {};
    const currentMilestoneSig = milestoneSignature(unit);

    if (mode === "hook-stop") {
      // On Stop: only write at genuine task milestones (commit, PR create/merge, tracker update,
      // or vault deliverable written), and only when a NEW milestone landed since the last checkpoint.
      if (!unit.hasMilestone) return;
      if (prev.lastMilestoneSig === currentMilestoneSig) return;
    } else {
      // On PreCompact / SessionEnd (hook-flush): wrap up the session/phase if anything substantive changed
      if (prev.lastWrittenFingerprint === unit.fingerprint) return;
    }

    writeWorkUnitsToVault(activeConfig.vaultDir, activeConfig, [unit]);
    state.sessions[unit.sessionId] = {
      lastWrittenFingerprint: unit.fingerprint,
      lastMilestoneSig: unit.hasMilestone ? currentMilestoneSig : (prev.lastMilestoneSig ?? ""),
      updatedAt: new Date().toISOString(),
      date: unit.date,
    };
    saveState(state, stateHome);
  }, { timeoutMs: mode === "hook-flush" ? 2_200 : 8_000 });
}

async function main() {
  const { positionals, flags } = parseArgs(process.argv.slice(2));
  const command = positionals[0] ?? "help";
  const stateHome = resolveStateHome();

  if (command === "hook-stop" || command === "hook-flush") {
    try {
      await handleHookEvent(command, stateHome);
    } catch (err) {
      logHookError(stateHome, err);
    }
    return;
  }

  if (command === "inspect") {
    const target = positionals[1] || process.env.TURN_VAULT_DIR || "";
    if (!target) {
      throw new Error("Usage: turn-vault.mjs inspect <obsidian-vault-or-folder>");
    }
    const layout = inspectVaultLayout(assertSafeVaultRootTarget(target));
    process.stdout.write(`${JSON.stringify(layout, null, 2)}\n`);
    return;
  }

  if (command === "init") {
    const target = positionals[1] || (typeof flags.vault === "string" ? flags.vault : "") || process.env.TURN_VAULT_DIR || "";
    if (!target) {
      throw new Error("Usage: turn-vault.mjs init <obsidian-vault-or-folder> [--daily <dir|none>] [--tickets <dir|none>] [--repos <dir|none>] [--topics <dir|none>] [--map <file|none>]");
    }
    const safeTarget = assertSafeVaultRootTarget(target);
    const inspected = inspectVaultLayout(safeTarget);

    if (existsSync(safeTarget) && lstatSync(safeTarget).isSymbolicLink()) {
      throw new Error(`Refusing to initialize symbolic link target: ${safeTarget}`);
    }
    mkdirSync(safeTarget, { recursive: true });
    const vaultReal = realpathSync(safeTarget);

    const existingStored = loadStoredConfig(stateHome);
    const seed = {
      ...(existingStored ?? {}),
      vaultDir: vaultReal,
      enabled: true,
      folders: { ...inspected.suggestedConfig.folders },
      mapFile: inspected.suggestedConfig.mapFile,
      dailySection: inspected.suggestedConfig.dailySection,
      dailyTemplate: inspected.suggestedConfig.dailyTemplate,
    };
    const finalConfig = applyFlagOverridesToConfig(seed, flags);
    const saved = saveConfig(finalConfig, stateHome);
    const initResult = await withVaultLock(stateHome, "vault", async () =>
      initializeVaultFolder(vaultReal, saved),
    );

    process.stdout.write(
      `${JSON.stringify(
        {
          ok: true,
          configFile: configPath(stateHome),
          vaultDir: saved.vaultDir,
          detectedObsidianVaultRoot: inspected.obsidianVaultRoot,
          detectedDailyNotesPlugin: inspected.obsidianDailyNotes,
          folders: saved.folders,
          mapFile: saved.mapFile,
          dailySection: saved.dailySection,
          dailyTemplate: saved.dailyTemplate,
          createdFolders: initResult.createdFolders,
          createdMap: initResult.createdMap,
          howItRuns:
            "Turn Vault runs automatically via the plugin's built-in hooks (Stop on task milestones such as commits/PRs/ticket updates, and PreCompact/SessionEnd when a session wraps up). No background daemon, cron job, or manual settings.json edit is required.",
        },
        null,
        2,
      )}\n`,
    );
    return;
  }

  if (command === "configure") {
    const stored = loadStoredConfig(stateHome);
    if (!stored?.vaultDir) {
      throw new Error("Turn Vault is not initialized yet. Run `init <obsidian-folder>` first.");
    }
    const updated = applyFlagOverridesToConfig(stored, flags);
    const saved = saveConfig(updated, stateHome);
    const initResult = await withVaultLock(stateHome, "vault", async () =>
      initializeVaultFolder(saved.vaultDir, saved),
    );
    process.stdout.write(
      `${JSON.stringify({ ok: true, configFile: configPath(stateHome), config: saved, createdFolders: initResult.createdFolders }, null, 2)}\n`,
    );
    return;
  }

  if (command === "pause" || command === "resume") {
    const stored = loadStoredConfig(stateHome);
    if (!stored?.vaultDir) {
      throw new Error("Turn Vault is not initialized yet. Run `init <obsidian-folder>` first.");
    }
    const saved = saveConfig({ ...stored, enabled: command === "resume" }, stateHome);
    process.stdout.write(`${JSON.stringify({ ok: true, enabled: saved.enabled, vaultDir: saved.vaultDir }, null, 2)}\n`);
    return;
  }

  if (command === "status") {
    const stored = loadStoredConfig(stateHome);
    const active = resolveActiveConfig(process.env, stateHome);
    const state = loadState(stateHome);
    const graph = active ? checkVaultGraph(active.vaultDir, active) : null;
    process.stdout.write(
      `${JSON.stringify(
        {
          initialized: Boolean(stored?.vaultDir || process.env.TURN_VAULT_DIR),
          active: Boolean(active),
          configFile: configPath(stateHome),
          config: active ?? stored,
          trackedSessionsCount: Object.keys(state.sessions ?? {}).length,
          scannedTranscriptFilesCount: Object.keys(state.scannedFiles ?? {}).length,
          graph: graph
            ? {
                notesCount: graph.notesCount,
                edgesCount: graph.edgesCount,
                orphanCount: graph.orphanCount,
                unresolvedCount: graph.unresolvedCount,
              }
            : null,
        },
        null,
        2,
      )}\n`,
    );
    return;
  }

  if (command === "scan") {
    const active = resolveActiveConfig(process.env, stateHome);
    const claudeDir = typeof flags["claude-dir"] === "string"
      ? flags["claude-dir"]
      : join(homedir(), ".claude", "projects");
    const limit = flags.limit ? Number(flags.limit) : 250;
    const since = typeof flags.since === "string" ? flags.since : "";

    // A preview reads every matching transcript and never touches the backfill cursor.
    const scanResult = scanTranscriptHistory({
      claudeProjectsDir: claudeDir,
      vaultDir: active?.vaultDir ?? "",
      teamPrefixes: active?.teamPrefixes ?? splitCsv(String(flags["team-prefixes"] ?? "")),
      topicDirs: active?.topicDirs ?? [],
      excludePaths: active?.excludePaths ?? [],
      since,
      limit,
      full: true,
    });

    const allTickets = [...new Set(scanResult.units.flatMap((u) => u.tickets))].sort();
    const allRepos = [...new Set(scanResult.units.flatMap((u) => u.repos))].sort();
    const allTopics = [...new Set(scanResult.units.flatMap((u) => u.topics))].sort();
    const allPrs = [...new Map(scanResult.units.flatMap((u) => u.prs).map((p) => [p.url, p])).values()];

    process.stdout.write(
      `${JSON.stringify(
        {
          stats: scanResult.stats,
          tickets: allTickets,
          repos: allRepos,
          topics: allTopics,
          prs: allPrs,
          units: flags.compact
            ? scanResult.units.map((u) => ({
                sessionId: u.sessionId,
                date: u.date,
                time: u.time,
                summary: u.summary,
                tickets: u.tickets,
                repos: u.repos,
                topics: u.topics,
                prs: u.prs,
                milestones: u.milestones,
              }))
            : scanResult.units,
        },
        null,
        2,
      )}\n`,
    );
    return;
  }

  if (command === "backfill") {
    const active = resolveActiveConfig(process.env, stateHome);
    if (!active) {
      throw new Error("Turn Vault is not active. Run `init <obsidian-folder>` (or set TURN_VAULT_DIR) first.");
    }

    const claudeDir = typeof flags["claude-dir"] === "string"
      ? flags["claude-dir"]
      : join(homedir(), ".claude", "projects");
    const limit = flags.limit ? Number(flags.limit) : 250;
    const since = typeof flags.since === "string" ? flags.since : "";
    const full = Boolean(flags.full);
    const dryRun = Boolean(flags["dry-run"]);

    let enrichments = {};
    if (typeof flags.enrich === "string" && flags.enrich.trim()) {
      const enrichPath = assertPathWithinAllowedRoots(flags.enrich.trim());
      const enrichSt = lstatSync(enrichPath);
      if (!enrichSt.isFile() || enrichSt.isSymbolicLink()) {
        throw new Error("Refusing non-regular or symbolic-link --enrich file.");
      }
      if (enrichSt.size > 4 * 1024 * 1024) {
        throw new Error("Refusing --enrich file larger than 4 MiB.");
      }
      const parsedEnrich = JSON.parse(readFileSync(enrichPath, "utf8"));
      if (parsedEnrich && typeof parsedEnrich === "object" && !Array.isArray(parsedEnrich)) {
        enrichments = parsedEnrich;
      }
    }

    const result = await withVaultLock(stateHome, "vault", async () => {
      const state = loadState(stateHome);
      const scanResult = scanTranscriptHistory({
        claudeProjectsDir: claudeDir,
        vaultDir: active.vaultDir,
        teamPrefixes: active.teamPrefixes,
        topicDirs: active.topicDirs,
        excludePaths: active.excludePaths,
        since,
        limit,
        full,
        previousScannedFiles: state.scannedFiles,
      });

      const writeRes = writeWorkUnitsToVault(active.vaultDir, active, scanResult.units, {
        enrichments,
        dryRun,
      });

      if (!dryRun) {
        state.scannedFiles = scanResult.scannedFiles;
        for (const u of scanResult.units) {
          state.sessions[u.sessionId] = {
            lastWrittenFingerprint: u.fingerprint,
            lastMilestoneSig: u.hasMilestone ? milestoneSignature(u) : "",
            updatedAt: new Date().toISOString(),
            date: u.date,
          };
        }
        saveState(state, stateHome);
      }

      return {
        ok: true,
        dryRun,
        vaultDir: active.vaultDir,
        stats: scanResult.stats,
        touchedEntities: writeRes.touchedEntities,
        writtenNotesCount: writeRes.writtenNotes.length,
        writtenNotes: writeRes.writtenNotes.slice(0, 100),
      };
    });

    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }

  if (command === "log") {
    const active = resolveActiveConfig(process.env, stateHome);
    if (!active) {
      throw new Error("Turn Vault is not active. Run `init <obsidian-folder>` (or set TURN_VAULT_DIR) first.");
    }
    const rawSummary = typeof flags.summary === "string"
      ? flags.summary
      : positionals.slice(1).join(" ");
    const summary = sanitizeInlineText(rawSummary, 180);
    if (!summary) {
      throw new Error("Usage: turn-vault.mjs log --summary \"<task summary>\" [--tickets PROJ-123] [--repos my-repo] [--topics OAuth] [--pr https://github.com/...]");
    }

    const now = new Date();
    const date = typeof flags.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(flags.date)
      ? flags.date
      : localDateString(now);
    const time = hhmmString(now);

    const explicitTickets = splitCsv(String(flags.tickets ?? "")).map((t) => safeNoteSlug(t, "")).filter(Boolean);
    const inferredTickets = extractTicketsFromText(rawSummary, { teamPrefixes: active.teamPrefixes });
    const tickets = [...new Set([...explicitTickets, ...inferredTickets])].sort();

    const explicitRepos = splitCsv(String(flags.repos ?? "")).map((r) => safeNoteSlug(r, "")).filter(Boolean);
    const cwdRepo = flags["no-cwd-repo"] ? null : resolveNormalizedRepoName(process.cwd());
    const repos = [...new Set([...explicitRepos, ...(cwdRepo ? [cwdRepo] : [])])].sort();

    const topics = splitCsv(String(flags.topics ?? "")).map((tp) => safeNoteSlug(tp, "")).filter(Boolean).sort();
    const prs = splitCsv(String(flags.pr ?? ""))
      .map((u) => {
        const safe = sanitizeExternalUrl(u);
        if (!safe) return null;
        const m = /github\.com\/([^/]+\/([^/]+))\/pull\/(\d+)/.exec(safe);
        return {
          url: safe,
          repoFull: m?.[1] ?? "",
          repo: m?.[2] ?? "",
          number: m?.[3] ? Number(m[3]) : 0,
          action: "referenced",
        };
      })
      .filter(Boolean);

    const rawSessionId = typeof flags["session-id"] === "string" && flags["session-id"].trim()
      ? flags["session-id"].trim().replace(/[^A-Za-z0-9._:-]+/g, "-").slice(0, 80)
      : `manual-${date}-${Date.now()}`;
    const sessionId = (!rawSessionId || rawSessionId === "__proto__" || rawSessionId === "constructor" || rawSessionId === "prototype")
      ? `manual-${date}-${Date.now()}`
      : rawSessionId;

    const unit = {
      sessionId,
      harness: "manual",
      date,
      time,
      startedAt: now.toISOString(),
      endedAt: now.toISOString(),
      summary,
      goal: summary,
      tickets,
      repos,
      topics,
      prs,
      commitsCount: 0,
      vaultNotes: [],
      filesChangedCount: 0,
      trackerActions: [],
      milestones: ["manual_checkpoint"],
      hasMilestone: true,
      isSubstantive: true,
    };

    const res = await withVaultLock(stateHome, "vault", async () =>
      writeWorkUnitsToVault(active.vaultDir, active, [unit]),
    );
    process.stdout.write(`${JSON.stringify({ ok: true, sessionId, writtenNotes: res.writtenNotes }, null, 2)}\n`);
    return;
  }

  if (command === "check") {
    const active = resolveActiveConfig(process.env, stateHome);
    if (!active) {
      throw new Error("Turn Vault is not active. Run `init <obsidian-folder>` (or set TURN_VAULT_DIR) first.");
    }
    if (flags["refresh-map"]) {
      await withVaultLock(stateHome, "vault", async () => refreshWorkMap(active.vaultDir, active));
    }
    const report = checkVaultGraph(active.vaultDir, active);
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    return;
  }

  process.stdout.write(
    [
      "Turn Vault CLI",
      "",
      "Commands:",
      "  inspect <vault-or-folder>        Detect existing Obsidian layout (.obsidian/daily-notes.json, folders, headings)",
      "  init <vault-or-folder> [flags]   Initialize folder & enable Turn Vault hooks",
      "  configure [flags]                Adjust folder mappings, daily section/template, or exclusions",
      "  status | pause | resume          Show status or toggle hook capture",
      "  scan [--since YYYY-MM-DD]        Preview substantive sessions, tickets, PRs, repos, and topics",
      "  backfill [--since ...] [--full]  Mine session history into backlinked Obsidian notes",
      "  log --summary \"...\" [flags]      Record an explicit end-of-task checkpoint",
      "  check [--refresh-map]            Audit [[wikilinks]], duplicate note names, orphans, and empty files",
      "",
    ].join("\n"),
  );
}

main().catch((err) => {
  process.stderr.write(`${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
});
