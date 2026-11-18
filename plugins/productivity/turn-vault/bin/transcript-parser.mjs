import { createHash } from "node:crypto";
import {
  closeSync,
  existsSync,
  fstatSync,
  lstatSync,
  openSync,
  readdirSync,
  readFileSync,
  readSync,
} from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import {
  assertPathWithinAllowedRoots,
  expandTilde,
  hhmmString,
  isExcludedVaultPath,
  localDateString,
  redactSecrets,
  safeNoteSlug,
  sanitizeExternalUrl,
  sanitizeInlineText,
  toPosixRel,
} from "./core.mjs";

const MAX_TRANSCRIPT_BYTES = 24 * 1024 * 1024; // Cap per-file read at 24 MiB (tail-safe)
const MAX_LINE_CHARS = 512 * 1024;

const NON_TICKET_PREFIXES = new Set([
  "AES",
  "AMD",
  "ANSI",
  "API",
  "ARM",
  "ASCII",
  "AST",
  "AWS",
  "BASE",
  "BCP",
  "CLI",
  "COM",
  "CPU",
  "CSS",
  "CSV",
  "CVE",
  "CWE",
  "DAY",
  "DEC",
  "DNS",
  "DOM",
  "ECMA",
  "EOF",
  "ERR",
  "FEB",
  "FIG",
  "GCC",
  "GCP",
  "GHSA",
  "GMT",
  "GNU",
  "GPT",
  "GPU",
  "HAIKU",
  "HTML",
  "HTTP",
  "HTTPS",
  "IDE",
  "IEEE",
  "IMAP",
  "IPV",
  "ISO",
  "JAN",
  "JDK",
  "JSON",
  "JUL",
  "JUN",
  "JWT",
  "KMS",
  "LINE",
  "LLM",
  "LPT",
  "MAC",
  "MAR",
  "MAX",
  "MAY",
  "MCP",
  "MD5",
  "MIN",
  "MIT",
  "MPC",
  "MSG",
  "NODE",
  "NOV",
  "NPM",
  "OAUTH",
  "OCT",
  "OIDC",
  "OPUS",
  "OSX",
  "PART",
  "PDF",
  "PEM",
  "PEP",
  "PHASE",
  "PID",
  "PNG",
  "POP",
  "PORT",
  "POSIX",
  "PR",
  "RAM",
  "RFC",
  "RGB",
  "RSA",
  "RULE",
  "SAML",
  "SDK",
  "SEC",
  "SEP",
  "SHA",
  "SIMD",
  "SLA",
  "SMTP",
  "SOC",
  "SONNET",
  "SQL",
  "SSH",
  "SSL",
  "STEP",
  "SVG",
  "TAB",
  "TCP",
  "TIER",
  "TLS",
  "TMP",
  "TOP",
  "TS",
  "TTL",
  "UDP",
  "UI",
  "URI",
  "URL",
  "USB",
  "UTC",
  "UTF",
  "UUID",
  "VAR",
  "VER",
  "VPC",
  "WSL",
  "X86",
  "XML",
  "YAML",
]);

const MUTATING_MCP_RE = /(?:^|__|_)(create|update|delete|close|resolve|merge|comment|transition|assign|archive)(?:_|$)/i;
// Some MCP servers expose one generic "execute" tool that takes an `action_id` argument; judge those by the action name.
const MUTATING_ACTION_ID_RE = /(?:^|_)(create|update|delete|close|add|post|archive|comment)(?:_|$)/i;

const gitCommonDirCache = new Map();

function readBoundedLines(filePath, maxBytes = MAX_TRANSCRIPT_BYTES) {
  let fd;
  try {
    const safeFile = assertPathWithinAllowedRoots(filePath);
    const lst = lstatSync(safeFile);
    if (!lst.isFile() || lst.isSymbolicLink()) return [];
    fd = openSync(safeFile, "r");
    const st = fstatSync(fd);
    if (st.size === 0) return [];

    if (st.size <= maxBytes) {
      const buf = Buffer.allocUnsafe(st.size);
      const bytesRead = readSync(fd, buf, 0, st.size, 0);
      return buf
        .subarray(0, bytesRead)
        .toString("utf8")
        .split("\n")
        .filter((l) => l.length > 0 && l.length <= MAX_LINE_CHARS);
    }

    // For oversized transcripts: keep first 2 MiB (initial prompt + context) + last (maxBytes - 2 MiB)
    const headBytes = 2 * 1024 * 1024;
    const tailBytes = maxBytes - headBytes;
    const headBuf = Buffer.allocUnsafe(headBytes);
    const tailBuf = Buffer.allocUnsafe(tailBytes);
    const hRead = readSync(fd, headBuf, 0, headBytes, 0);
    const tRead = readSync(fd, tailBuf, 0, tailBytes, st.size - tailBytes);

    const headLines = headBuf.subarray(0, hRead).toString("utf8").split("\n").slice(0, -1);
    const tailLines = tailBuf.subarray(0, tRead).toString("utf8").split("\n").slice(1);
    return [...headLines, ...tailLines].filter((l) => l.length > 0 && l.length <= MAX_LINE_CHARS);
  } catch {
    return [];
  } finally {
    if (fd !== undefined) {
      try {
        closeSync(fd);
      } catch {
        // Ignore close error
      }
    }
  }
}

function isScratchPath(absPath) {
  const norm = absPath.replace(/\\/g, "/");
  return (
    /^(?:\/private)?\/tmp\/[^/]+$/.test(norm) ||
    /^(?:\/private)?\/tmp\/claude-\d+\//.test(norm) ||
    norm.includes("/scratchpad/") ||
    norm.includes("/node_modules/")
  );
}

const GENERIC_WORKSPACE_DIRS = new Set([
  "projects",
  "repos",
  "repositories",
  "code",
  "src",
  "work",
  "workspace",
  "workspaces",
  "dev",
  "documents",
  "desktop",
  "downloads",
  "users",
  "home",
  "tmp",
  "var",
  "private",
]);

function stripWorktreeTicketSuffix(dirName) {
  // Normalize common worktree conventions that append a ticket ID to the repo folder:
  // "<repo>-<KEY><number>" or "<repo>-<KEY>-<number>" -> "<repo>"
  const m = /^(.+?)-[A-Z]{2,6}-?\d+(?:-.+)?$/.exec(dirName);
  if (m && m[1].length >= 2) {
    return m[1];
  }
  return dirName;
}

function inspectGitCommonRepoRoot(startDir) {
  // Pure read-only filesystem walk (no subprocess / git binary invocation in untrusted directories).
  let cursor = startDir;
  for (let depth = 0; depth < 16; depth++) {
    const dotGit = join(cursor, ".git");
    if (existsSync(dotGit)) {
      try {
        const st = lstatSync(dotGit);
        if (st.isDirectory() && !st.isSymbolicLink()) {
          return cursor;
        }
        if (st.isFile() && !st.isSymbolicLink() && st.size <= 4096) {
          // Worktree .git file format: "gitdir: /path/to/main-repo/.git/worktrees/<name>"
          const safeDotGit = assertPathWithinAllowedRoots(dotGit);
          const text = readFileSync(safeDotGit, "utf8").trim();
          const m = /^gitdir:\s*(.+)$/i.exec(text);
          if (m?.[1]) {
            const gitDir = assertPathWithinAllowedRoots(resolve(cursor, m[1].trim()));
            const commondirFile = assertPathWithinAllowedRoots(join(gitDir, "commondir"));
            if (existsSync(commondirFile) && lstatSync(commondirFile).size <= 1024) {
              const commonRel = readFileSync(commondirFile, "utf8").trim();
              const commonAbs = assertPathWithinAllowedRoots(resolve(gitDir, commonRel));
              return basename(commonAbs) === ".git" ? dirname(commonAbs) : commonAbs;
            }
            const wtMatch = /^(.+?)[\\/]\.git[\\/]worktrees[\\/][^\\/]+$/.exec(gitDir);
            if (wtMatch?.[1]) return wtMatch[1];
          }
          return cursor;
        }
      } catch {
        return null;
      }
    }
    const parent = dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  return null;
}

export function resolveNormalizedRepoName(cwdPath) {
  if (typeof cwdPath !== "string" || !cwdPath.trim()) return null;
  const resolved = resolve(expandTilde(cwdPath.trim()));
  if (isScratchPath(resolved)) return null;
  if (resolved === homedir()) return null;

  if (gitCommonDirCache.has(resolved)) {
    return gitCommonDirCache.get(resolved);
  }

  let repoName = null;
  if (existsSync(resolved)) {
    const repoRoot = inspectGitCommonRepoRoot(resolved);
    if (repoRoot) {
      const candidateName = basename(repoRoot);
      if (candidateName && !GENERIC_WORKSPACE_DIRS.has(candidateName.toLowerCase())) {
        repoName = stripWorktreeTicketSuffix(candidateName);
      }
    }
  }

  if (!repoName) {
    // Handle paths like .../worktrees/<repo>/<worktree-dir>/... or .../<repo>-<TICKET>/...
    const parts = resolved.split(/[\\/]+/).filter(Boolean);
    const wtIdx = parts.findIndex((p) => p.toLowerCase() === "worktrees");
    if (wtIdx >= 0 && parts[wtIdx + 1]) {
      repoName = stripWorktreeTicketSuffix(parts[wtIdx + 1]);
    } else {
      const leaf = parts[parts.length - 1] ?? "";
      if (leaf && !GENERIC_WORKSPACE_DIRS.has(leaf.toLowerCase()) && !leaf.startsWith(".")) {
        const stripped = stripWorktreeTicketSuffix(leaf);
        // Only treat non-git leaf directories as a repo when they look like a project slug
        if (stripped !== leaf || existsSync(join(resolved, ".git")) || existsSync(join(resolved, "package.json")) || existsSync(join(resolved, "pyproject.toml"))) {
          repoName = stripped;
        }
      }
    }
  }

  const finalName = repoName ? safeNoteSlug(repoName, "") || null : null;
  gitCommonDirCache.set(resolved, finalName);
  return finalName;
}

export function extractTicketsFromText(text, { teamPrefixes = [], allowCompactWorktree = false } = {}) {
  if (typeof text !== "string" || !text) return [];
  const allowedSet = teamPrefixes.length > 0 ? new Set(teamPrefixes.map((p) => p.toUpperCase())) : null;
  const tickets = new Set();

  // Issue-tracker URLs with the key in the path: linear.app/<org>/issue/<KEY>, <jira-host>/browse/<KEY>
  for (const m of text.matchAll(/(?:linear\.app\/[^\s/]+\/issue|\/browse)\/([A-Z][A-Z0-9]{1,9}-\d{1,7})\b/g)) {
    const prefix = m[1].split("-")[0].toUpperCase();
    if (allowedSet && !allowedSet.has(prefix)) continue;
    tickets.add(m[1].toUpperCase());
  }

  // Standard hyphenated ticket IDs: <PREFIX>-<number>
  for (const m of text.matchAll(/(?<![A-Za-z0-9_-])([A-Z]{2,7})-(\d{1,6})(?![A-Za-z0-9_])/g)) {
    const prefix = m[1].toUpperCase();
    const num = Number(m[2]);
    if (num <= 0) continue;
    if (NON_TICKET_PREFIXES.has(prefix)) continue;
    if (allowedSet && !allowedSet.has(prefix)) continue;
    tickets.add(`${prefix}-${m[2]}`);
  }

  // Compact worktree/branch suffixes without the hyphen: <repo>-<PREFIX><number>, fix/<PREFIX><number>
  if (allowCompactWorktree) {
    for (const m of text.matchAll(/(?:^|[\\/-])([A-Z]{2,6})(\d{2,6})(?:$|[\\/-])/g)) {
      const prefix = m[1].toUpperCase();
      if (NON_TICKET_PREFIXES.has(prefix)) continue;
      if (allowedSet && !allowedSet.has(prefix)) continue;
      tickets.add(`${prefix}-${m[2]}`);
    }
  }

  return [...tickets];
}

function splitHeredocHeader(command) {
  const idx = command.search(/<<-?\s*['"]?[A-Za-z_][A-Za-z0-9_]*['"]?/);
  return idx >= 0 ? command.slice(0, idx) : command;
}

function isCommandInvocation(cmdHeader, subcommandRegex) {
  // Match actual shell command segments (start of line or after ; && || | ( ) rather than quoted code strings
  return subcommandRegex.test(cmdHeader);
}

// The text of the first `-m "..."` / `--message "..."` argument, escapes kept; "" when unterminated.
function readDoubleQuotedMessage(header) {
  const open = /(?:-m|--message)[= ]\s*"/.exec(header);
  if (!open) return "";
  let i = open.index + open[0].length;
  let text = "";
  while (i < header.length && header[i] !== '"') {
    const step = header[i] === "\\" && i + 1 < header.length ? 2 : 1;
    text += header.slice(i, i + step);
    i += step;
  }
  return i < header.length ? text : "";
}

function extractCommitSubject(command) {
  const header = splitHeredocHeader(command);
  if (!isCommandInvocation(header, /(?:^|[;&|()\n]\s*)(?:env\s+\S+\s+)*git(?:\s+-C\s+\S+)?\s+commit\b/)) {
    return null;
  }
  const heredoc = /<<-?\s*['"]?[A-Za-z_][A-Za-z0-9_]*['"]?\s*\n([^\n]+)\n/.exec(command);
  if (heredoc?.[1]) return sanitizeInlineText(heredoc[1], 110);
  const dbl = readDoubleQuotedMessage(header);
  if (dbl) return sanitizeInlineText(dbl.split("\\n")[0], 110);
  const sgl = /(?:-m|--message)[= ]\s*'([^']+)'/.exec(header);
  if (sgl?.[1]) return sanitizeInlineText(sgl[1].split("\n")[0], 110);
  return "";
}

function extractBranchFromCommand(command) {
  const m =
    /\bgit\s+(?:checkout|switch)\b[^;&|\n]*?\s-(?:b|B|c|C)\s+['"]?([^\s'";&|]+)['"]?/.exec(command) ??
    /\bgit\s+worktree\s+add\b[^;&|\n]*?\s-(?:b|B)\s+['"]?([^\s'";&|]+)['"]?/.exec(command);
  return m?.[1] ?? null;
}

function pullRequestRef(repoFull, number) {
  const url = sanitizeExternalUrl(`https://github.com/${repoFull}/pull/${number}`);
  return url ? { url, repoFull, repo: repoFull.split("/")[1], number: Number(number) } : null;
}

const PR_URL_RE = /https:\/\/github\.com\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)\/pull\/(\d+)\b/g;
// gh CLI shorthand (owner/repo#123). In free prose it also matches issues and paths, so only gh commands and their output use it.
const PR_SHORTHAND_RE = /\b([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#(\d+)\b/g;

function extractPrUrls(text) {
  return collectPullRequests(text, [PR_URL_RE]);
}

function extractGhPullRequests(text) {
  return collectPullRequests(text, [PR_URL_RE, PR_SHORTHAND_RE]);
}

function collectPullRequests(text, patterns) {
  if (typeof text !== "string" || !text) return [];
  const byUrl = new Map();
  for (const re of patterns) {
    for (const m of text.matchAll(re)) {
      const ref = pullRequestRef(m[1], m[2]);
      if (ref && !byUrl.has(ref.url)) byUrl.set(ref.url, ref);
    }
  }
  return [...byUrl.values()];
}

function extractPrFromGhCommand(cmd) {
  // e.g. gh pr merge 522 --repo example-org/web-app
  const repoMatch = /(?:-R|--repo)[= ]\s*['"]?([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)['"]?/.exec(cmd);
  const numMatch = /\bgh\s+pr\s+(?:merge|create|view|ready|checks|edit)\s+(\d+)\b/.exec(cmd);
  return repoMatch?.[1] && numMatch?.[1] ? pullRequestRef(repoMatch[1], numMatch[1]) : null;
}

function extractTopicFromFilePath(absPath, topicDirs) {
  if (!Array.isArray(topicDirs)) return null;
  const norm = absPath.replace(/\\/g, "/");
  for (const dir of topicDirs) {
    const marker = `/${dir}/`;
    const idx = norm.indexOf(marker);
    if (idx < 0) continue;
    const rest = norm.slice(idx + marker.length);
    const slash = rest.indexOf("/");
    if (slash <= 0) continue;
    const slug = safeNoteSlug(rest.slice(0, slash), "");
    if (slug && slug.length >= 2) return slug;
  }
  return null;
}

function extractHumanPromptText(entry) {
  if (entry?.type !== "user") return null;
  const content = entry?.message?.content;
  let raw = "";
  if (typeof content === "string") {
    raw = content;
  } else if (Array.isArray(content)) {
    // Tool results are also user entries in Claude transcripts; skip them
    if (content.some((c) => c?.type === "tool_result")) return null;
    raw = content
      .filter((c) => c?.type === "text" && typeof c.text === "string")
      .map((c) => c.text)
      .join(" ");
  }
  if (!raw.trim()) return null;
  // Ignore synthetic local slash command outputs and system caveats
  if (/<local-command-(?:stdout|caveat)>/i.test(raw)) return null;
  if (/^<command-name>\/?(?:clear|compact|exit|status|login|logout|mcp|plugin|model)\b/i.test(raw.trim())) {
    return null;
  }

  // If invoked via a custom command with <command-args>, prefer the args or command name
  const argsMatch = /<command-args>([\s\S]*?)<\/command-args>/i.exec(raw);
  const cmdMatch = /<command-name>([^<]+)<\/command-name>/i.exec(raw);
  if (cmdMatch) {
    const cmdArgs = (argsMatch?.[1] ?? "").trim();
    raw = cmdArgs ? `${cmdMatch[1]} ${cmdArgs}` : cmdMatch[1];
  }

  const cleaned = sanitizeInlineText(raw, 140);
  if (!cleaned || cleaned.length < 3) return null;
  return cleaned;
}

function isInsideVault(absPath, vaultDirReal) {
  if (!vaultDirReal) return false;
  const rel = relative(vaultDirReal, absPath);
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
}

function findSubagentTranscripts(mainTranscriptPath) {
  const stem = mainTranscriptPath.replace(/\.jsonl$/i, "");
  const subDir = join(stem, "subagents");
  if (!existsSync(subDir)) return [];
  try {
    const lst = lstatSync(subDir);
    if (!lst.isDirectory() || lst.isSymbolicLink()) return [];
    return readdirSync(subDir)
      .filter((f) => f.endsWith(".jsonl"))
      .sort()
      .map((f) => join(subDir, f));
  } catch {
    return [];
  }
}

function safeSessionKey(raw) {
  const cleaned = String(raw ?? "")
    .replace(/[^A-Za-z0-9._:-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 96);
  if (!cleaned || cleaned === "__proto__" || cleaned === "constructor" || cleaned === "prototype") {
    return "session";
  }
  return cleaned;
}

export function parseSessionTranscript(
  transcriptPath,
  {
    sessionId: explicitSessionId = "",
    cwd: fallbackCwd = "",
    vaultDir = "",
    teamPrefixes = [],
    topicDirs = [],
    excludePaths = [],
    includeSubagents = true,
  } = {},
) {
  if (!transcriptPath || !transcriptPath.endsWith(".jsonl") || !existsSync(transcriptPath)) return null;

  const sessionId = safeSessionKey(
    explicitSessionId ||
    basename(transcriptPath).replace(/\.jsonl$/i, ""),
  );

  const filesToRead = [
    { path: transcriptPath, isSubagent: false },
    ...(includeSubagents
      ? findSubagentTranscripts(transcriptPath).map((p) => ({ path: p, isSubagent: true }))
      : []),
  ];

  let firstTimestamp = null;
  let lastTimestamp = null;
  let goal = "";
  let primaryCwd = fallbackCwd || "";
  const cwds = new Set();
  const branches = new Set();
  const tickets = new Set();
  const topics = new Set();
  const repos = new Set();
  const prMap = new Map(); // url -> { url, repo, number, action }
  const commits = [];
  const vaultNotesMap = new Map(); // title -> { title, relPath }
  const codeFilesChanged = new Set();
  const trackerActions = new Set();
  const milestones = new Set();
  let toolUseCount = 0;
  const pendingPrCommands = new Map();

  if (fallbackCwd) {
    cwds.add(fallbackCwd);
    for (const t of extractTicketsFromText(fallbackCwd, { teamPrefixes, allowCompactWorktree: true })) {
      tickets.add(t);
    }
  }

  for (const { path: currentFile, isSubagent } of filesToRead) {
    const lines = readBoundedLines(currentFile);
    for (const line of lines) {
      let entry;
      try {
        entry = JSON.parse(line);
      } catch {
        continue;
      }
      if (!entry || typeof entry !== "object") continue;

      if (typeof entry.timestamp === "string") {
        const ts = Date.parse(entry.timestamp);
        if (!Number.isNaN(ts)) {
          if (firstTimestamp === null || ts < firstTimestamp) firstTimestamp = ts;
          if (lastTimestamp === null || ts > lastTimestamp) lastTimestamp = ts;
        }
      }

      if (typeof entry.cwd === "string" && entry.cwd.trim()) {
        if (!primaryCwd && !isSubagent) primaryCwd = entry.cwd.trim();
        cwds.add(entry.cwd.trim());
        for (const t of extractTicketsFromText(entry.cwd, { teamPrefixes, allowCompactWorktree: true })) {
          tickets.add(t);
        }
      }

      if (typeof entry.gitBranch === "string" && entry.gitBranch.trim()) {
        const br = entry.gitBranch.trim();
        if (br !== "HEAD" && br !== "main" && br !== "master" && br !== "develop") {
          branches.add(br);
          for (const t of extractTicketsFromText(br, { teamPrefixes, allowCompactWorktree: true })) {
            tickets.add(t);
          }
        }
      }

      if (!isSubagent && entry.type === "user") {
        const promptText = extractHumanPromptText(entry);
        if (promptText) {
          if (!goal) goal = promptText;
          for (const t of extractTicketsFromText(promptText, { teamPrefixes })) {
            tickets.add(t);
          }
          for (const pr of extractPrUrls(promptText)) {
            if (!prMap.has(pr.url)) prMap.set(pr.url, { ...pr, action: "referenced" });
          }
        }
      }

      const content = Array.isArray(entry?.message?.content) ? entry.message.content : [];
      for (const block of content) {
        if (!block || typeof block !== "object") continue;

        // Only the result of a gh pr create/merge call is mined for PR URLs, never arbitrary tool output.
        const prAction = block.type === "tool_result" ? pendingPrCommands.get(block.tool_use_id) : undefined;
        if (entry.type === "user" && prAction) {
          const resultText = typeof block.content === "string"
            ? block.content
            : Array.isArray(block.content)
              ? block.content.map((x) => (typeof x?.text === "string" ? x.text : "")).join("\n")
              : "";
          for (const pr of extractGhPullRequests(resultText)) {
            prMap.set(pr.url, { ...pr, action: prAction });
            if (pr.repo) repos.add(safeNoteSlug(pr.repo, ""));
          }
          pendingPrCommands.delete(block.tool_use_id);
        }

        if (entry.type !== "assistant" || block.type !== "tool_use") continue;
        const toolName = String(block.name ?? "");
        toolUseCount += 1;
        const input = block.input && typeof block.input === "object" ? block.input : {};
        const effectiveCwd = primaryCwd || fallbackCwd || process.cwd();

        // File writes & edits (Claude Code + Codex tool names)
        const rawTargetFile =
          (toolName === "Write" || toolName === "Edit" || toolName === "MultiEdit"
            ? input.file_path ?? input.path
            : toolName === "NotebookEdit"
              ? input.notebook_path
              : null);

        if (typeof rawTargetFile === "string" && rawTargetFile.trim()) {
          const absFile = resolve(effectiveCwd, expandTilde(rawTargetFile.trim()));
          if (vaultDir && isInsideVault(absFile, vaultDir)) {
            if (absFile.endsWith(".md")) {
              const relVault = toPosixRel(relative(vaultDir, absFile));
              // Hidden and excluded vault paths are never named as deliverables.
              if (!isExcludedVaultPath(relVault, { excludePaths })) {
                const noteTitle = basename(absFile, ".md");
                vaultNotesMap.set(noteTitle, { title: noteTitle, relPath: relVault });
                milestones.add("vault_note_written");
              }
            }
          } else if (!isScratchPath(absFile)) {
            codeFilesChanged.add(absFile);
            const topic = extractTopicFromFilePath(absFile, topicDirs);
            if (topic) topics.add(topic);
            const fileRepo = resolveNormalizedRepoName(dirname(absFile));
            if (fileRepo) repos.add(fileRepo);
          }
        }

        // Bash commands: commits, PRs, branches (inspect command header before any heredoc body)
        if (toolName === "Bash" && typeof input.command === "string") {
          const cmd = input.command;
          const cmdHeader = splitHeredocHeader(cmd);
          const br = extractBranchFromCommand(cmdHeader);
          if (br) {
            branches.add(br);
            for (const t of extractTicketsFromText(br, { teamPrefixes, allowCompactWorktree: true })) {
              tickets.add(t);
            }
          }

          const commitSubject = extractCommitSubject(cmd);
          if (commitSubject !== null) {
            milestones.add("committed");
            if (commitSubject) {
              commits.push(commitSubject);
              for (const t of extractTicketsFromText(commitSubject, { teamPrefixes })) {
                tickets.add(t);
              }
            } else {
              commits.push("(commit)");
            }
          }

          if (isCommandInvocation(cmdHeader, /(?:^|[;&|()\n]\s*)gh\s+pr\s+create\b/)) {
            milestones.add("pr_opened");
            pendingPrCommands.set(block.id, "opened");
            for (const t of extractTicketsFromText(cmdHeader, { teamPrefixes })) {
              tickets.add(t);
            }
          } else if (isCommandInvocation(cmdHeader, /(?:^|[;&|()\n]\s*)gh\s+pr\s+merge\b/)) {
            milestones.add("pr_merged");
            pendingPrCommands.set(block.id, "merged");
            const cmdPr = extractPrFromGhCommand(cmdHeader);
            if (cmdPr) {
              prMap.set(cmdPr.url, { ...cmdPr, action: "merged" });
              if (cmdPr.repo) repos.add(safeNoteSlug(cmdPr.repo, ""));
            }
            for (const pr of extractGhPullRequests(cmdHeader)) {
              prMap.set(pr.url, { ...pr, action: "merged" });
            }
          } else if (isCommandInvocation(cmdHeader, /(?:^|[;&|()\n]\s*)gh\s+pr\s+(?:view|checks|ready)\b/)) {
            const cmdPr = extractPrFromGhCommand(cmdHeader);
            if (cmdPr && !prMap.has(cmdPr.url)) {
              prMap.set(cmdPr.url, { ...cmdPr, action: "referenced" });
              if (cmdPr.repo) repos.add(safeNoteSlug(cmdPr.repo, ""));
            }
            for (const pr of extractGhPullRequests(cmdHeader)) {
              if (!prMap.has(pr.url)) prMap.set(pr.url, { ...pr, action: "referenced" });
            }
          }
        }

        // MCP tool calls (issue trackers, GitHub and any other MCP server)
        if (toolName.startsWith("mcp__")) {
          const actionId = typeof input.action_id === "string" ? input.action_id : "";
          const isGenericExec = /(?:^|_)execute(?:_action)?$/i.test(toolName) && actionId !== "";
          const isMutating = isGenericExec
            ? MUTATING_ACTION_ID_RE.test(actionId)
            : MUTATING_MCP_RE.test(toolName);

          if (isMutating) {
            const label = isGenericExec ? actionId : toolName.replace(/^mcp__[^_]+__/, "");
            trackerActions.add(sanitizeInlineText(label, 60));
            milestones.add("tracker_updated");
          }

          // Ticket IDs passed into tracker lookups and updates
          const serializedArgs = JSON.stringify({
            id: input.id ?? input.issue_id ?? input.issueId ?? input.identifier ?? input.key ?? "",
            query: input.query ?? "",
            path: input.path ?? "",
            title: input.title ?? input?.body?.title ?? "",
          });
          for (const t of extractTicketsFromText(serializedArgs, { teamPrefixes })) {
            tickets.add(t);
          }

          if (typeof input.provider === "string" && input.provider.trim()) {
            const pSlug = safeNoteSlug(input.provider.trim(), "");
            if (pSlug && !["linear", "jira", "github", "gitlab", "gmail", "googlecalendar", "googledrive", "slack", "notion"].includes(pSlug.toLowerCase())) {
              topics.add(pSlug);
            }
          }
        }
      }
    }
  }

  for (const cwd of cwds) {
    if (vaultDir && isInsideVault(resolve(expandTilde(cwd)), vaultDir)) continue;
    const r = resolveNormalizedRepoName(cwd);
    if (r) repos.add(r);
  }

  repos.delete("");
  topics.delete("");
  // Avoid duplicating repo name as a topic
  const repoLower = new Set([...repos].map((r) => r.toLowerCase()));
  for (const t of [...topics]) {
    if (repoLower.has(t.toLowerCase())) topics.delete(t);
  }

  let fileMtimeMs = Date.now();
  try {
    fileMtimeMs = lstatSync(transcriptPath).mtimeMs;
  } catch {
    // Keep Date.now()
  }

  const endDateObj = new Date(lastTimestamp ?? fileMtimeMs);
  const startDateObj = new Date(firstTimestamp ?? lastTimestamp ?? fileMtimeMs);
  const date = localDateString(endDateObj);
  const time = hhmmString(endDateObj);

  const sortedTickets = [...tickets].sort();
  const sortedRepos = [...repos].sort();
  const sortedTopics = [...topics].sort();
  const sortedMilestones = [...milestones].sort();
  const prs = [...prMap.values()].sort((a, b) => a.url.localeCompare(b.url));
  const vaultNotes = [...vaultNotesMap.values()].sort((a, b) => a.title.localeCompare(b.title));
  const filesChangedCount = codeFilesChanged.size;

  const hasMilestone = sortedMilestones.length > 0;
  const isSubstantive =
    hasMilestone ||
    filesChangedCount > 0 ||
    (sortedTickets.length > 0 && toolUseCount >= 3);

  // Derive concise summary: prefer commit subject or goal
  let summary = goal;
  if (!summary && commits.length > 0 && commits[0] !== "(commit)") {
    summary = commits[0];
  }
  if (!summary && vaultNotes.length > 0) {
    summary = `Updated ${vaultNotes.map((n) => n.title).slice(0, 2).join(", ")}`;
  }
  if (!summary && sortedTickets.length > 0) {
    summary = `Worked on ${sortedTickets.join(", ")}`;
  }
  if (!summary && filesChangedCount > 0) {
    summary = `Updated ${filesChangedCount} file${filesChangedCount === 1 ? "" : "s"}${sortedRepos[0] ? ` in ${sortedRepos[0]}` : ""}`;
  }
  summary = redactSecrets(summary);

  const fingerprintPayload = JSON.stringify({
    date,
    summary,
    tickets: sortedTickets,
    repos: sortedRepos,
    topics: sortedTopics,
    prs,
    commitsCount: commits.length,
    commitSubjects: commits.slice(0, 5),
    vaultNotes: vaultNotes.map((n) => n.title),
    filesChangedCount,
    trackerActions: [...trackerActions].sort(),
    milestones: sortedMilestones,
  });
  const fingerprint = createHash("sha256").update(fingerprintPayload).digest("hex").slice(0, 16);

  return {
    sessionId,
    harness: "claude",
    transcriptPath,
    date,
    time,
    startedAt: startDateObj.toISOString(),
    endedAt: endDateObj.toISOString(),
    summary,
    goal,
    branches: [...branches].sort(),
    tickets: sortedTickets,
    repos: sortedRepos,
    topics: sortedTopics,
    prs,
    commitsCount: commits.length,
    commitSubjects: commits.filter((c) => c && c !== "(commit)").slice(0, 5),
    vaultNotes,
    filesChangedCount,
    trackerActions: [...trackerActions].sort(),
    milestones: sortedMilestones,
    hasMilestone,
    isSubstantive,
    toolUseCount,
    fingerprint,
  };
}

function discoverClaudeMainTranscripts(claudeProjectsDir) {
  if (!claudeProjectsDir || !existsSync(claudeProjectsDir)) return [];
  const results = [];
  let projectDirs = [];
  try {
    projectDirs = readdirSync(claudeProjectsDir, { withFileTypes: true })
      .filter((d) => d.isDirectory() && !d.isSymbolicLink() && !d.name.startsWith("."));
  } catch {
    return [];
  }

  for (const proj of projectDirs) {
    const projPath = join(claudeProjectsDir, proj.name);
    let entries = [];
    try {
      entries = readdirSync(projPath, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const ent of entries) {
      if (!ent.isFile() || ent.isSymbolicLink() || !ent.name.endsWith(".jsonl")) continue;
      const fullPath = join(projPath, ent.name);
      try {
        const st = lstatSync(fullPath);
        results.push({ path: fullPath, mtimeMs: st.mtimeMs, size: st.size });
      } catch {
        // Ignore vanished file
      }
    }
  }

  results.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return results;
}

export function scanTranscriptHistory({
  claudeProjectsDir = join(homedir(), ".claude", "projects"),
  vaultDir = "",
  teamPrefixes = [],
  topicDirs = [],
  excludePaths = [],
  since = "",
  limit = 250,
  full = false,
  previousScannedFiles = {},
} = {}) {
  const resolvedClaudeDir = resolve(expandTilde(claudeProjectsDir));
  const candidates = discoverClaudeMainTranscripts(resolvedClaudeDir);
  const maxFiles = Math.max(1, Math.min(Number(limit) || 250, 2000));
  const sinceDate = typeof since === "string" && /^\d{4}-\d{2}-\d{2}$/.test(since.trim())
    ? since.trim()
    : "";

  const units = [];
  const nextScannedFiles = { ...previousScannedFiles };
  let inspected = 0;
  let skippedUnchanged = 0;
  let skippedTrivial = 0;

  for (const item of candidates) {
    if (inspected >= maxFiles) break;

    if (sinceDate) {
      const mtimeDate = localDateString(new Date(item.mtimeMs));
      if (mtimeDate < sinceDate) continue;
    }

    // Also include max mtime/total size of subagent files so subagent updates invalidate cache
    let compositeMtime = Math.floor(item.mtimeMs);
    let compositeSize = item.size;
    for (const subPath of findSubagentTranscripts(item.path)) {
      try {
        const sst = lstatSync(subPath);
        if (sst.mtimeMs > compositeMtime) compositeMtime = Math.floor(sst.mtimeMs);
        compositeSize += sst.size;
      } catch {
        // Ignore
      }
    }

    const prev = Object.hasOwn(previousScannedFiles, item.path)
      ? previousScannedFiles[item.path]
      : null;
    if (
      !full &&
      prev &&
      prev.mtimeMs === compositeMtime &&
      prev.size === compositeSize
    ) {
      skippedUnchanged += 1;
      continue;
    }

    inspected += 1;
    const unit = parseSessionTranscript(item.path, {
      vaultDir,
      teamPrefixes,
      topicDirs,
      excludePaths,
      includeSubagents: true,
    });

    if (!unit || !unit.isSubstantive) {
      skippedTrivial += 1;
      nextScannedFiles[item.path] = {
        mtimeMs: compositeMtime,
        size: compositeSize,
        substantive: false,
      };
      continue;
    }

    if (sinceDate && unit.date < sinceDate) {
      continue;
    }

    nextScannedFiles[item.path] = {
      mtimeMs: compositeMtime,
      size: compositeSize,
      substantive: true,
      fingerprint: unit.fingerprint,
    };
    units.push(unit);
  }

  // Chronological order (oldest -> newest) so notes read naturally top-to-bottom
  units.sort((a, b) => a.startedAt.localeCompare(b.startedAt));

  return {
    units,
    scannedFiles: nextScannedFiles,
    stats: {
      discoveredTotal: candidates.length,
      inspected,
      skippedUnchanged,
      skippedTrivial,
      substantiveMatched: units.length,
    },
  };
}
