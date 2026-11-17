import { randomUUID } from "node:crypto";
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  realpathSync,
  renameSync,
  rmdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir, platform, tmpdir } from "node:os";
import { basename, dirname, isAbsolute, join, normalize, parse as parsePath, relative, resolve, sep } from "node:path";

export const DEFAULT_FOLDERS = Object.freeze({
  daily: "Daily",
  tickets: "Tickets",
  repos: "Repos",
  topics: "Topics",
  notes: "Notes",
});

export const DEFAULT_MAP_FILE = "Work-Map.md";
export const DEFAULT_DAILY_SECTION = "Work Log";

const WINDOWS_RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;

const SENSITIVE_QUERY_KEYS = new Set([
  "token",
  "access_token",
  "refresh_token",
  "id_token",
  "api_key",
  "apikey",
  "key",
  "secret",
  "client_secret",
  "password",
  "passwd",
  "sig",
  "signature",
  "x-amz-signature",
  "x-amz-credential",
  "x-amz-security-token",
  "code",
  "session",
  "auth",
]);
const SENSITIVE_QUERY_PARAM_RE = new RegExp(`([?&](?:${[...SENSITIVE_QUERY_KEYS].join("|")})=)[^&#\\s'")\\]]+`, "gi");

export function resolveStateHome(env = process.env) {
  if (env.TURN_VAULT_HOME && env.TURN_VAULT_HOME.trim()) {
    return assertPathWithinAllowedRoots(env.TURN_VAULT_HOME.trim());
  }
  if (platform() === "darwin") {
    return join(homedir(), "Library", "Application Support", "turn-vault");
  }
  const xdg = env.XDG_CONFIG_HOME && env.XDG_CONFIG_HOME.trim()
    ? assertPathWithinAllowedRoots(env.XDG_CONFIG_HOME.trim())
    : join(homedir(), ".config");
  return join(xdg, "turn-vault");
}

export function expandTilde(inputPath) {
  if (typeof inputPath !== "string") return "";
  if (inputPath === "~") return homedir();
  if (inputPath.startsWith("~/") || inputPath.startsWith("~\\")) {
    return join(homedir(), inputPath.slice(2));
  }
  return inputPath;
}

export function localDateString(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function hhmmString(date = new Date()) {
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

// Bounds regex work on huge prompts; cutting at whitespace never leaves half a secret behind.
function capAtWordBoundary(text, limit) {
  if (text.length <= limit) return text;
  let end = limit;
  while (end > 0 && !/\s/.test(text[end])) end -= 1;
  return text.slice(0, end);
}

export function redactSecrets(raw) {
  if (typeof raw !== "string" || !raw) return "";
  let out = raw;

  // PEM blocks: the bounded body avoids a quadratic scan; an unterminated block is redacted to the end.
  out = out.replace(
    /-----BEGIN [A-Z0-9 _-]{1,64}-----[\s\S]{0,65536}?-----END [A-Z0-9 _-]{1,64}-----/g,
    "[REDACTED_PEM]",
  );
  out = out.replace(/-----BEGIN [A-Z0-9 _-]{1,64}-----[\s\S]*$/, "[REDACTED_PEM]");

  // URI userinfo credentials across all schemes (https://user:pass@host, postgres://user:pass@host, redis://:pass@host)
  out = out.replace(
    /\b([a-z][a-z0-9+.-]{0,31}:\/\/)([^/\s@]{0,256}:[^/\s@]{1,256})@/gi,
    "$1[REDACTED]@",
  );

  out = out.replace(SENSITIVE_QUERY_PARAM_RE, "$1[REDACTED]");

  out = out.replace(
    /\b(Authorization\s*[:=]\s*['"]?(?:Bearer|Basic|Token)\s+)[A-Za-z0-9._~+/=-]{8,}/gi,
    "$1[REDACTED]",
  );
  out = out.replace(
    /\b(Bearer\s+)[A-Za-z0-9._~+/=-]{16,}/g,
    "$1[REDACTED]",
  );
  out = out.replace(
    /\b((?:x-api-key|cookie|set-cookie)\s*[:=]\s*['"]?)[^\r\n'",;)\]}]{8,}/gi,
    "$1[REDACTED]",
  );

  out = out.replace(/\bsk-ant-[A-Za-z0-9_-]{12,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{20,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bwhsec_[A-Za-z0-9]{16,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bgh[pousr]_[A-Za-z0-9]{20,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bglpat-[A-Za-z0-9_-]{20,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bnpm_[A-Za-z0-9]{24,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bpypi-[A-Za-z0-9_-]{24,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g, "[REDACTED_TOKEN]");
  out = out.replace(/\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/g, "[REDACTED_AWS_KEY]");
  out = out.replace(/\bAIza[0-9A-Za-z_-]{30,}\b/g, "[REDACTED_GCP_KEY]");
  out = out.replace(
    /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g,
    "[REDACTED_JWT]",
  );

  // Key=value, key: value and "key": "value" assignments for sensitive names
  out = out.replace(
    /\b((?:[A-Za-z0-9_]{0,64}?(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|auth[_-]?token|private[_-]?key|secret[_-]?key|webhook[_-]?secret|signing[_-]?secret|secret[_-]?access[_-]?key|access[_-]?key|password|passwd|bearer[_-]?token|token|secret|credentials?))['"]?\s*[:=]\s*)(?:"[^"\n]{1,256}"|'[^'\n]{1,256}'|[^\s'",;)\]}[]{6,})/gi,
    "$1[REDACTED]",
  );

  return out;
}

export function sanitizeInlineText(raw, maxLen = 180) {
  if (typeof raw !== "string" || !raw) return "";
  let text = redactSecrets(capAtWordBoundary(raw, Math.max(maxLen * 8, 2048)));
  text = text.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
  text = text.replace(/<\/?command-[a-z-]+>/gi, " ").replace(/\s+/g, " ").trim();
  text = text
    .replace(/<%/g, "&lt;%")
    .replace(/%>/g, "%&gt;")
    .replace(/```+/g, "'''")
    .replace(/<(\/?(?:script|iframe|object|embed|style|svg|math|form|input|meta|link|base|img|video|audio)\b[^>]{0,200}?)>/gi, "&lt;$1&gt;")
    .replace(/\b(?:javascript|vbscript|data|obsidian|file):/gi, "[blocked-scheme]:")
    .replace(/!\[/g, "!\\[")
    .replace(/\[\[/g, "[")
    .replace(/\]\]/g, "]")
    .replace(/\x3c!--/g, "&lt;!--")
    .replace(/--\x3e/g, "--&gt;")
    .replace(/\s\^tv-[A-Za-z0-9-]+/g, "");

  if (text.startsWith("---") || text === "---") {
    text = text.replace(/^-+/, "");
  }
  text = text.trim();
  if (text.length > maxLen) {
    text = `${text.slice(0, Math.max(1, maxLen - 1)).trimEnd()}…`;
  }
  return text;
}

export function sanitizeExternalUrl(rawUrl) {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) return null;
  const cleaned = rawUrl.trim().replace(/[.,;:!?)'"\]]+$/, "");
  let parsed;
  try {
    parsed = new URL(cleaned);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  parsed.username = "";
  parsed.password = "";
  for (const key of [...parsed.searchParams.keys()]) {
    if (SENSITIVE_QUERY_KEYS.has(key.toLowerCase())) {
      parsed.searchParams.set(key, "REDACTED");
    }
  }
  return parsed.toString().replace(/\(/g, "%28").replace(/\)/g, "%29");
}

export function safeNoteSlug(raw, fallback = "Untitled") {
  if (typeof raw !== "string") return fallback;
  let cleaned = redactSecrets(capAtWordBoundary(raw, 1024))
    .replace(/[\u0000-\u001f\u007f]+/g, " ")
    .replace(/[\\/:*?"<>|#^[\]]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^\.+|\.+$/g, "")
    .trim();

  if (!cleaned || cleaned === "." || cleaned === ".." || WINDOWS_RESERVED.test(cleaned)) {
    cleaned = fallback;
  }
  if (cleaned.length > 80) {
    cleaned = cleaned.slice(0, 80).trim().replace(/\.+$/, "");
  }
  return cleaned || fallback;
}

export function sanitizeMarkerId(raw) {
  const s = String(raw ?? "")
    .replace(/[^A-Za-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
  return s || "entry";
}

function normalizeOptionalFolderRel(raw, fallback) {
  if (raw === null || raw === false) return null;
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed.toLowerCase() === "none" || trimmed.toLowerCase() === "off") return null;
    if (trimmed === "." || trimmed === "/") return "";
    if (!trimmed) return fallback;
    const parts = trimmed
      .split(/[\\/]+/)
      .map((p) => safeNoteSlug(p, ""))
      .filter((p) => p && !p.startsWith("."));
    return parts.length ? parts.join("/") : fallback;
  }
  return fallback;
}

function normalizeOptionalVaultFileRel(raw, fallback) {
  if (raw === null || raw === false) return null;
  if (typeof raw !== "string") return fallback;
  const trimmed = raw.trim();
  if (!trimmed) return fallback;
  if (trimmed.toLowerCase() === "none" || trimmed.toLowerCase() === "off") return null;

  const rawParts = trimmed.replace(/\.md$/i, "").split(/[\\/]+/).filter(Boolean);
  const safeParts = rawParts.map((p) => safeNoteSlug(p, "")).filter((p) => p && !p.startsWith("."));
  if (!safeParts.length) return fallback;
  return `${safeParts.join("/")}.md`;
}

export function normalizeConfig(raw = {}) {
  const folders = {
    daily: normalizeOptionalFolderRel(raw?.folders?.daily, DEFAULT_FOLDERS.daily),
    tickets: normalizeOptionalFolderRel(raw?.folders?.tickets, DEFAULT_FOLDERS.tickets),
    repos: normalizeOptionalFolderRel(raw?.folders?.repos, DEFAULT_FOLDERS.repos),
    topics: normalizeOptionalFolderRel(raw?.folders?.topics, DEFAULT_FOLDERS.topics),
    notes: normalizeOptionalFolderRel(raw?.folders?.notes, DEFAULT_FOLDERS.notes),
  };

  const mapFile = normalizeOptionalVaultFileRel(raw?.mapFile, DEFAULT_MAP_FILE);
  const dailyTemplate = normalizeOptionalVaultFileRel(raw?.dailyTemplate ?? null, null);
  const dailySectionRaw = typeof raw?.dailySection === "string" && raw.dailySection.trim()
    ? sanitizeInlineText(raw.dailySection.replace(/^#+\s*/, "").trim(), 60)
    : DEFAULT_DAILY_SECTION;

  const excludePaths = Array.isArray(raw?.excludePaths)
    ? raw.excludePaths.filter((p) => typeof p === "string" && p.trim()).map((p) => toPosixRel(p.trim()))
    : [];
  const excludeManifest = typeof raw?.excludeManifest === "string" && raw.excludeManifest.trim()
    ? toPosixRel(raw.excludeManifest.trim())
    : null;
  const teamPrefixes = Array.isArray(raw?.teamPrefixes)
    ? raw.teamPrefixes
        .filter((p) => typeof p === "string" && /^[A-Z]{2,8}$/i.test(p.trim()))
        .map((p) => p.trim().toUpperCase())
    : [];
  // Repo-relative directories whose child folders become topic hubs, e.g. "src/integrations".
  const topicDirs = Array.isArray(raw?.topicDirs)
    ? [...new Set(
        raw.topicDirs
          .filter((p) => typeof p === "string")
          .map((p) => toPosixRel(p.trim()).replace(/^\/+|\/+$/g, ""))
          .filter((p) => p && p.length <= 120 && /^[A-Za-z0-9_.\/-]+$/.test(p) && !p.split("/").includes("..")),
      )].slice(0, 20)
    : [];

  return {
    version: 1,
    vaultDir: typeof raw?.vaultDir === "string" && raw.vaultDir.trim()
      ? resolve(expandTilde(raw.vaultDir.trim()))
      : "",
    enabled: raw?.enabled !== false,
    folders,
    mapFile,
    dailySection: dailySectionRaw || DEFAULT_DAILY_SECTION,
    dailyTemplate,
    excludePaths,
    excludeManifest,
    teamPrefixes,
    topicDirs,
    updatedAt: typeof raw?.updatedAt === "string" ? raw.updatedAt : new Date().toISOString(),
  };
}

/**
 * Inspect an existing or candidate Obsidian folder so Turn Vault adapts to
 * however the user's vault already works (.obsidian/daily-notes.json, existing
 * folders, root rules, templates) instead of imposing a rigid hierarchy.
 */
export function inspectVaultLayout(targetDir) {
  const resolved = assertPathWithinAllowedRoots(targetDir);
  const exists = existsSync(resolved);
  const info = {
    targetDir: resolved,
    exists,
    isObsidianVaultRoot: false,
    obsidianVaultRoot: null,
    obsidianDailyNotes: null,
    hasGuidanceFiles: [],
    existingFolders: [],
    suggestedConfig: {
      folders: { ...DEFAULT_FOLDERS },
      mapFile: DEFAULT_MAP_FILE,
      dailySection: DEFAULT_DAILY_SECTION,
      dailyTemplate: null,
    },
  };

  if (!exists) return info;
  let resolvedReal;
  try {
    if (lstatSync(resolved).isSymbolicLink()) return info;
    resolvedReal = realpathSync(resolved);
  } catch {
    return info;
  }

  // Walk upward to see if targetDir is an Obsidian vault root or a subfolder inside one
  let probe = resolvedReal;
  while (true) {
    if (existsSync(join(probe, ".obsidian"))) {
      info.obsidianVaultRoot = probe;
      info.isObsidianVaultRoot = probe === resolvedReal;
      break;
    }
    const parent = dirname(probe);
    if (parent === probe) break;
    probe = parent;
  }

  if (info.isObsidianVaultRoot) {
    try {
      const dailyNotesCfgPath = assertPathWithinAllowedRoots(join(resolvedReal, ".obsidian", "daily-notes.json"));
      if (existsSync(dailyNotesCfgPath)) {
        const cfgSt = lstatSync(dailyNotesCfgPath);
        if (cfgSt.isFile() && !cfgSt.isSymbolicLink() && cfgSt.size <= 256 * 1024) {
          const dn = JSON.parse(readFileSync(dailyNotesCfgPath, "utf8"));
          const safeDailyFolder = typeof dn?.folder === "string" && dn.folder.trim()
            ? normalizeOptionalFolderRel(dn.folder, null)
            : null;
          const safeDailyTpl = typeof dn?.template === "string" && dn.template.trim()
            ? normalizeOptionalVaultFileRel(dn.template, null)
            : null;
          info.obsidianDailyNotes = {
            folder: safeDailyFolder,
            format: typeof dn?.format === "string" ? sanitizeInlineText(dn.format, 32) : null,
            template: safeDailyTpl,
          };
          if (safeDailyFolder) {
            info.suggestedConfig.folders.daily = safeDailyFolder;
          }
          if (safeDailyTpl) {
            try {
              const containedTpl = resolveContainedVaultPath(resolvedReal, safeDailyTpl);
              if (existsSync(containedTpl)) {
                info.suggestedConfig.dailyTemplate = safeDailyTpl;
              }
            } catch {
              // Ignore unsafe template path
            }
          }
        }
      }
    } catch {
      // Ignore malformed .obsidian config
    }
  }

  for (const name of ["AGENTS.md", "CLAUDE.md"]) {
    if (existsSync(join(resolvedReal, name))) {
      info.hasGuidanceFiles.push(name);
    }
  }

  try {
    const topDirs = readdirSync(resolvedReal, { withFileTypes: true })
      .filter((d) => d.isDirectory() && !d.isSymbolicLink() && !d.name.startsWith("."))
      .map((d) => d.name)
      .sort();
    info.existingFolders = topDirs;

    const allDirs = [...topDirs];
    for (const top of topDirs) {
      try {
        const children = readdirSync(join(resolvedReal, top), { withFileTypes: true })
          .filter((d) => d.isDirectory() && !d.isSymbolicLink() && !d.name.startsWith("."))
          .map((d) => `${top}/${d.name}`);
        allDirs.push(...children);
      } catch {
        // Ignore unreadable subdir
      }
    }

    const findMatch = (patterns) => {
      for (const pat of patterns) {
        const hit = allDirs.find((d) => pat.test(basename(d)) || pat.test(d));
        if (hit) return hit;
      }
      return null;
    };

    if (!info.obsidianDailyNotes?.folder) {
      const dailyHit = findMatch([/^daily$/i, /^daily notes$/i, /^journal$/i, /\/daily$/i]);
      if (dailyHit) info.suggestedConfig.folders.daily = dailyHit;
    }
    const ticketHit = findMatch([/^tickets$/i, /^issues$/i, /\/tickets$/i, /\/investigations$/i]);
    if (ticketHit) info.suggestedConfig.folders.tickets = ticketHit;

    const repoHit = findMatch([/^repos$/i, /^repositories$/i, /^projects$/i, /\/projects$/i, /\/repos$/i]);
    if (repoHit) info.suggestedConfig.folders.repos = repoHit;

    const topicHit = findMatch([/^topics$/i, /^areas$/i, /^wiki$/i, /^providers$/i, /\/topics$/i, /\/connectors$/i]);
    if (topicHit) info.suggestedConfig.folders.topics = topicHit;

    const notesHit = findMatch([/^notes$/i, /^inbox$/i, /^\d+\s+inbox$/i]);
    if (notesHit) info.suggestedConfig.folders.notes = notesHit;

    const mapsHit = findMatch([/^maps$/i, /^mocs$/i, /\/maps$/i]);
    if (mapsHit) {
      info.suggestedConfig.mapFile = `${mapsHit}/Work-Map.md`;
    } else if (info.hasGuidanceFiles.length > 0 && topDirs.length > 0) {
      // Existing structured vault with rules at root: place Work-Map inside notes/maps rather than cluttering root
      info.suggestedConfig.mapFile = `${info.suggestedConfig.folders.notes}/Work-Map.md`;
    }

    // Check if existing daily notes already use "## Activity" vs "## Work Log"
    if (info.suggestedConfig.folders.daily) {
      try {
        const dailyFolder = resolveContainedVaultPath(resolvedReal, info.suggestedConfig.folders.daily);
        if (existsSync(dailyFolder)) {
          const recentMd = readdirSync(dailyFolder, { withFileTypes: true })
            .filter((d) => d.isFile() && !d.isSymbolicLink() && d.name.endsWith(".md"))
            .map((d) => d.name)
            .sort()
            .slice(-3);
          for (const f of recentMd) {
            const samplePath = assertPathWithinAllowedRoots(resolveContainedVaultPath(dailyFolder, f));
            if (lstatSync(samplePath).size <= 256 * 1024) {
              const sample = readFileSync(samplePath, "utf8");
              if (/^##\s+Activity\s*$/m.test(sample)) {
                info.suggestedConfig.dailySection = "Activity";
                break;
              }
            }
          }
        }
      } catch {
        // Ignore sample read errors
      }
    }
  } catch {
    // Ignore directory scan errors
  }

  return info;
}

export function configPath(stateHome = resolveStateHome()) {
  return join(stateHome, "config.json");
}

export function stateFilePath(stateHome = resolveStateHome()) {
  return join(stateHome, "state.json");
}

export function hookLogPath(stateHome = resolveStateHome()) {
  return join(stateHome, "hook.log");
}

export function loadStoredConfig(stateHome = resolveStateHome()) {
  try {
    const safePath = assertPathWithinAllowedRoots(configPath(stateHome));
    if (!existsSync(safePath)) return null;
    const parsed = JSON.parse(readFileSync(safePath, "utf8"));
    return normalizeConfig(parsed);
  } catch {
    return null;
  }
}

function loadManifestExclusions(vaultReal, manifestRel) {
  if (!manifestRel) return null;
  try {
    const manifestPath = resolveContainedVaultPath(vaultReal, manifestRel);
    if (!existsSync(manifestPath)) return null;
    const parsed = JSON.parse(readFileSync(manifestPath, "utf8"));
    if (Array.isArray(parsed?.paths)) {
      return parsed.paths.filter((p) => typeof p === "string").map((p) => toPosixRel(p));
    }
    if (Array.isArray(parsed)) {
      return parsed.filter((p) => typeof p === "string").map((p) => toPosixRel(p));
    }
    return null;
  } catch {
    // Fail closed if an explicit exclusion manifest was configured and could not be parsed
    return null;
  }
}

// Same roots `init` accepts; never home or "/" itself, which would index every Markdown file.
export function isUsableVaultRoot(dir) {
  try {
    const abs = assertPathWithinAllowedRoots(dir);
    return abs !== resolve(homedir()) && abs !== parsePath(abs).root && existsSync(abs);
  } catch {
    return false;
  }
}

export function resolveActiveConfig(env = process.env, stateHome = resolveStateHome(env)) {
  if (env.TURN_VAULT_DISABLED === "1" || env.TURN_VAULT_DISABLED === "true") {
    return null;
  }
  const stored = loadStoredConfig(stateHome);
  const envVault = typeof env.TURN_VAULT_DIR === "string" && env.TURN_VAULT_DIR.trim()
    ? resolve(expandTilde(env.TURN_VAULT_DIR.trim()))
    : "";

  const base = stored ?? normalizeConfig({});
  const vaultDir = envVault || base.vaultDir;
  if (!vaultDir) return null;
  if (stored && stored.enabled === false) return null;
  if (!isUsableVaultRoot(vaultDir)) return null;

  let vaultReal;
  try {
    const st = statSync(vaultDir);
    if (!st.isDirectory()) return null;
    vaultReal = realpathSync(vaultDir);
  } catch {
    return null;
  }

  let mergedExcludes = [...base.excludePaths];
  if (base.excludeManifest) {
    const manifestPaths = loadManifestExclusions(vaultReal, base.excludeManifest);
    if (manifestPaths === null) return null;
    mergedExcludes = [...new Set([...mergedExcludes, ...manifestPaths])];
  }

  return {
    ...base,
    vaultDir: vaultReal,
    excludePaths: mergedExcludes,
  };
}

export function atomicWritePrivate(filePath, content) {
  const safeTarget = assertPathWithinAllowedRoots(filePath);
  const dir = assertPathWithinAllowedRoots(dirname(safeTarget));
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  if (existsSync(safeTarget) && lstatSync(safeTarget).isSymbolicLink()) {
    throw new Error(`Refusing to overwrite symbolic link: ${safeTarget}`);
  }
  const tmp = assertPathWithinAllowedRoots(join(dir, `.${process.pid}.${Date.now()}.${randomUUID()}.tmp`));
  writeFileSync(tmp, content, { encoding: "utf8", mode: 0o600 });
  renameSync(tmp, safeTarget);
}

export function saveConfig(config, stateHome = resolveStateHome()) {
  const normalized = normalizeConfig({
    ...config,
    updatedAt: new Date().toISOString(),
  });
  atomicWritePrivate(configPath(stateHome), `${JSON.stringify(normalized, null, 2)}\n`);
  return normalized;
}

export function loadState(stateHome = resolveStateHome()) {
  try {
    const safePath = assertPathWithinAllowedRoots(stateFilePath(stateHome));
    if (!existsSync(safePath)) {
      return { version: 1, sessions: {}, scannedFiles: {} };
    }
    const raw = JSON.parse(readFileSync(safePath, "utf8"));
    return {
      version: 1,
      sessions: raw?.sessions && typeof raw.sessions === "object" ? raw.sessions : {},
      scannedFiles: raw?.scannedFiles && typeof raw.scannedFiles === "object" ? raw.scannedFiles : {},
    };
  } catch {
    return { version: 1, sessions: {}, scannedFiles: {} };
  }
}

export function saveState(state, stateHome = resolveStateHome()) {
  const sessionEntries = Object.entries(state.sessions ?? {});
  const trimmedSessions = sessionEntries.length > 2000
    ? Object.fromEntries(
        sessionEntries
          .sort((a, b) => String(a[1]?.updatedAt ?? "").localeCompare(String(b[1]?.updatedAt ?? "")))
          .slice(-1500),
      )
    : state.sessions ?? {};

  const fileEntries = Object.entries(state.scannedFiles ?? {});
  const trimmedFiles = fileEntries.length > 5000
    ? Object.fromEntries(
        fileEntries
          .sort((a, b) => Number(a[1]?.mtimeMs ?? 0) - Number(b[1]?.mtimeMs ?? 0))
          .slice(-4000),
      )
    : state.scannedFiles ?? {};

  atomicWritePrivate(
    stateFilePath(stateHome),
    `${JSON.stringify({ version: 1, sessions: trimmedSessions, scannedFiles: trimmedFiles }, null, 2)}\n`,
  );
}

function isProcessAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err?.code === "EPERM";
  }
}

export async function withVaultLock(stateHome, lockName, fn, { timeoutMs = 10_000 } = {}) {
  const safeHome = assertPathWithinAllowedRoots(stateHome);
  mkdirSync(safeHome, { recursive: true, mode: 0o700 });
  const safeName = lockName.replace(/[^A-Za-z0-9_-]/g, "_");
  const lockDir = assertPathWithinAllowedRoots(join(safeHome, `${safeName}.lock`));
  const ownerFile = assertPathWithinAllowedRoots(join(lockDir, "owner.json"));
  const deadline = Date.now() + timeoutMs;

  while (true) {
    try {
      mkdirSync(lockDir, { mode: 0o700 });
      writeFileSync(
        assertPathWithinAllowedRoots(ownerFile),
        JSON.stringify({ pid: process.pid, createdAt: Date.now() }),
        { encoding: "utf8", mode: 0o600 },
      );
      break;
    } catch (err) {
      if (err?.code !== "EEXIST") throw err;
      let stale = false;
      try {
        const safeOwner = assertPathWithinAllowedRoots(ownerFile);
        if (existsSync(safeOwner)) {
          const info = JSON.parse(readFileSync(safeOwner, "utf8"));
          const age = Date.now() - Number(info?.createdAt ?? 0);
          // A live owner keeps its lock (backfill can run for minutes); the age cap only guards PID reuse.
          if (age > 600_000 || (age > 1_500 && !isProcessAlive(Number(info?.pid)))) {
            stale = true;
          }
        } else {
          const st = statSync(lockDir);
          if (Date.now() - st.mtimeMs > 30_000) stale = true;
        }
      } catch {
        // Concurrent unlock; retry next iteration
      }
      if (stale) {
        try {
          if (existsSync(ownerFile)) unlinkSync(ownerFile);
          rmdirSync(lockDir);
        } catch {
          // Another process cleaned it up
        }
        continue;
      }
      if (Date.now() >= deadline) {
        throw new Error(`Timed out acquiring Turn Vault lock (${safeName})`);
      }
      await new Promise((r) => setTimeout(r, 50));
    }
  }

  try {
    return await fn();
  } finally {
    try {
      if (existsSync(ownerFile)) unlinkSync(ownerFile);
      rmdirSync(lockDir);
    } catch {
      // Best-effort cleanup
    }
  }
}

export function toPosixRel(relPath) {
  return relPath.split(sep).join("/").replace(/^\/+/, "");
}

function isSubpath(parentReal, candidateReal) {
  const rel = relative(parentReal, candidateReal);
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

export function assertPathWithinAllowedRoots(rawPath) {
  const expanded = resolve(expandTilde(String(rawPath || "").trim()));
  const roots = [resolve(homedir()), resolve(tmpdir())];
  try {
    roots.push(realpathSync(homedir()), realpathSync(tmpdir()));
  } catch {
    // Ignore if temp root not yet materialized
  }

  if (!roots.some((r) => isSubpath(r, expanded))) {
    throw new Error(`Refusing path outside user home or temp directory: ${expanded}`);
  }

  if (existsSync(expanded) && lstatSync(expanded).isSymbolicLink()) {
    throw new Error(`Refusing symbolic link path: ${expanded}`);
  }
  // Missing folders get created under the nearest existing ancestor, so that ancestor must resolve inside the roots.
  let existing = expanded;
  while (!existsSync(existing) && dirname(existing) !== existing) existing = dirname(existing);
  const real = realpathSync(existing);
  if (!roots.some((r) => isSubpath(r, real))) {
    throw new Error(`Refusing canonical path outside user home or temp directory: ${real}`);
  }
  return expanded;
}

export function resolveContainedVaultPath(vaultRootReal, ...segments) {
  const joined = normalize(resolve(vaultRootReal, ...segments));
  if (!isSubpath(vaultRootReal, joined)) {
    throw new Error(`Refusing path outside configured vault directory: ${joined}`);
  }

  // Verify EVERY existing path segment from vaultRootReal down to target is not a symbolic link
  const rel = relative(vaultRootReal, joined);
  const parts = rel ? rel.split(sep).filter(Boolean) : [];
  let cursor = vaultRootReal;
  for (const part of parts) {
    cursor = join(cursor, part);
    if (!existsSync(cursor)) break;
    const lst = lstatSync(cursor);
    if (lst.isSymbolicLink()) {
      throw new Error(`Refusing to traverse or access symbolic link inside vault: ${cursor}`);
    }
    const real = realpathSync(cursor);
    if (!isSubpath(vaultRootReal, real)) {
      throw new Error(`Refusing symlink escape outside vault directory: ${cursor}`);
    }
  }

  return joined;
}

// Case-insensitive NFC, so exclusions hold on macOS filesystems and "./Private/" equals "Private".
function normalizeExclusionKey(relPath) {
  return toPosixRel(String(relPath).trim())
    .normalize("NFC")
    .toLowerCase()
    .replace(/^(?:\.\/)+/, "")
    .replace(/\/+$/, "");
}

export function isExcludedVaultPath(absOrRelPath, config, vaultRootReal = config?.vaultDir) {
  const relPosix = isAbsolute(absOrRelPath) && vaultRootReal
    ? toPosixRel(relative(vaultRootReal, absOrRelPath))
    : toPosixRel(String(absOrRelPath));

  if (!relPosix || relPosix.startsWith("..")) return true;
  const parts = relPosix.split("/");
  if (parts.some((segment) => segment.startsWith("."))) return true;

  const target = normalizeExclusionKey(relPosix);
  for (const entry of config?.excludePaths ?? []) {
    const prefix = normalizeExclusionKey(entry);
    if (prefix && (target === prefix || target.startsWith(`${prefix}/`))) return true;
  }
  return false;
}

export function readVaultNoteSafe(vaultRootReal, config, targetPath) {
  const safePath = resolveContainedVaultPath(vaultRootReal, relative(vaultRootReal, targetPath));
  if (isExcludedVaultPath(safePath, config, vaultRootReal)) {
    throw new Error(`Refusing to read excluded vault path: ${relative(vaultRootReal, safePath)}`);
  }
  if (!existsSync(safePath)) return null;
  return readFileSync(safePath, "utf8");
}

export function atomicWriteVaultNote(vaultRootReal, config, targetPath, content) {
  const safePath = resolveContainedVaultPath(vaultRootReal, relative(vaultRootReal, targetPath));
  if (isExcludedVaultPath(safePath, config, vaultRootReal)) {
    throw new Error(`Refusing to write excluded vault path: ${relative(vaultRootReal, safePath)}`);
  }
  let fileMode = 0o600;
  if (existsSync(safePath)) {
    try {
      fileMode = lstatSync(safePath).mode & 0o777;
    } catch {
      fileMode = 0o600;
    }
  }
  const dir = dirname(safePath);
  mkdirSync(dir, { recursive: true });
  // Re-verify full ancestor chain after mkdir
  resolveContainedVaultPath(vaultRootReal, relative(vaultRootReal, dir));
  const dirReal = realpathSync(dir);
  if (!isSubpath(vaultRootReal, dirReal)) {
    throw new Error(`Refusing write into directory outside vault: ${dir}`);
  }
  const tmp = join(dirReal, `.turn-vault-${process.pid}-${Date.now()}-${randomUUID()}.tmp`);
  writeFileSync(tmp, content, { encoding: "utf8", mode: fileMode });
  renameSync(tmp, safePath);
}

export function renderDailyTemplate(templateText, dateStr) {
  const [yyyy, mm, dd] = dateStr.split("-");
  return templateText
    .replace(/\{\{\s*date(?::([^}]+))?\s*\}\}/gi, (_match, fmt) => {
      if (!fmt) return dateStr;
      return String(fmt)
        .replace(/YYYY/g, yyyy)
        .replace(/MM/g, mm)
        .replace(/DD/g, dd);
    })
    .replace(/\{\{\s*title\s*\}\}/gi, dateStr);
}

// --- Frontmatter & Markdown section helpers (preserves user prose byte-for-byte) ---

export function splitFrontmatter(markdown) {
  if (typeof markdown !== "string") return null;
  const normalized = markdown.replace(/\r\n/g, "\n");
  if (!normalized.startsWith("---\n")) return null;
  const endIdx = normalized.indexOf("\n---", 3);
  if (endIdx === -1) return null;
  const afterClose = endIdx + 4;
  if (afterClose < normalized.length && normalized[afterClose] !== "\n") {
    return null;
  }
  const fmText = normalized.slice(4, endIdx);
  const body = afterClose < normalized.length ? normalized.slice(afterClose + 1) : "";
  return { fmText, body };
}

function formatYamlScalar(val) {
  if (val === null || val === undefined || val === "") return "";
  if (typeof val === "number" && Number.isFinite(val)) return String(val);
  if (typeof val === "boolean") return val ? "true" : "false";
  const s = String(val).replace(/[\r\n\u0000-\u001f\u007f]+/g, " ").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  if (/^[A-Za-z][A-Za-z0-9._/-]*$/.test(s)) return s;
  return JSON.stringify(s);
}

function parseFrontmatterBlocks(fmText) {
  if (!fmText.trim()) return [];
  const lines = fmText.split("\n");
  const blocks = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const keyMatch = /^([A-Za-z0-9_-]+):(.*)$/.exec(line);
    if (keyMatch) {
      const key = keyMatch[1];
      const rest = keyMatch[2];
      const blockLines = [line];
      // A key owns every following indented line and unindented "- item" (both valid YAML list styles).
      while (i + 1 < lines.length && /^(?:\s+\S|-(?:\s|$))/.test(lines[i + 1])) {
        i += 1;
        blockLines.push(lines[i]);
      }
      blocks.push({ key, rest, lines: blockLines });
    } else {
      blocks.push({ key: null, rest: "", lines: [line] });
    }
  }
  return blocks;
}

function extractBlockListValues(block) {
  const out = [];
  const inline = block.rest.trim();
  if (inline && !inline.startsWith("[") && !/^[|>]/.test(inline)) {
    out.push(inline.replace(/^(['"])(.*)\1$/, "$2"));
  } else if (inline.startsWith("[") && inline.endsWith("]")) {
    try {
      const parsed = JSON.parse(inline);
      if (Array.isArray(parsed)) {
        for (const item of parsed) {
          if (typeof item === "string" && item.trim()) out.push(item.trim());
        }
      }
    } catch {
      for (const part of inline.slice(1, -1).split(",")) {
        const v = part.trim().replace(/^['"]|['"]$/g, "");
        if (v) out.push(v);
      }
    }
  }
  for (const l of block.lines.slice(1)) {
    const m = /^\s*-\s+(.*)$/.exec(l);
    if (!m) continue;
    let raw = m[1].trim();
    if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) {
      try {
        raw = raw.startsWith('"') ? JSON.parse(raw) : raw.slice(1, -1);
      } catch {
        raw = raw.slice(1, -1);
      }
    }
    if (raw) out.push(raw);
  }
  return out;
}

// Values of one frontmatter key (a scalar comes back as a one-item list), or null when the key is absent.
export function frontmatterValues(markdown, key) {
  const parsed = splitFrontmatter(markdown);
  const block = parsed ? parseFrontmatterBlocks(parsed.fmText).find((b) => b.key === key) : null;
  return block ? extractBlockListValues(block) : null;
}

export function upsertFrontmatter(markdown, scalarUpdates = {}, listAdditions = {}) {
  const parsed = splitFrontmatter(markdown);
  const blocks = parsed ? parseFrontmatterBlocks(parsed.fmText) : [];
  const body = parsed ? parsed.body : (markdown ?? "").replace(/\r\n/g, "\n");

  for (const [key, value] of Object.entries(scalarUpdates)) {
    if (value === undefined) continue;
    const formatted = value === null || value === "" ? `${key}:` : `${key}: ${formatYamlScalar(value)}`;
    const idx = blocks.findIndex((b) => b.key === key);
    if (idx >= 0) {
      blocks[idx] = { key, rest: "", lines: [formatted] };
    } else {
      blocks.push({ key, rest: "", lines: [formatted] });
    }
  }

  for (const [key, additions] of Object.entries(listAdditions)) {
    if (!Array.isArray(additions)) continue;
    const idx = blocks.findIndex((b) => b.key === key);
    const existing = idx >= 0 ? extractBlockListValues(blocks[idx]) : [];
    const merged = [...new Set([...existing, ...additions.filter(Boolean)])];
    if (merged.length === 0 && idx === -1) continue;
    const renderedLines = merged.length === 0
      ? [`${key}: []`]
      : [`${key}:`, ...merged.map((v) => `  - ${JSON.stringify(String(v))}`)];
    if (idx >= 0) {
      blocks[idx] = { key, rest: "", lines: renderedLines };
    } else {
      blocks.push({ key, rest: "", lines: renderedLines });
    }
  }

  const fmOut = blocks.flatMap((b) => b.lines).join("\n");
  const cleanBody = body.startsWith("\n") ? body : (body ? body : "");
  return `---\n${fmOut}\n---\n${cleanBody}`;
}

export function upsertKeyedBulletInSection(
  markdown,
  primaryHeading,
  markerId,
  bulletLine,
  { fallbackHeadings = [] } = {},
) {
  const safeId = sanitizeMarkerId(markerId);
  const marker = `^tv-${safeId}`;
  const markerRe = new RegExp(`(?:^|\\s)\\^tv-${safeId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`);
  const fullLine = `${bulletLine.trimEnd()} ${marker}`;

  const normalized = (markdown ?? "").replace(/\r\n/g, "\n");
  const lines = normalized.replace(/\s+$/, "").split("\n");
  if (lines.length === 1 && lines[0] === "") lines.length = 0;

  const existingIdx = lines.findIndex((l) => markerRe.test(l));
  if (existingIdx >= 0) {
    lines[existingIdx] = fullLine;
    return `${lines.join("\n")}\n`;
  }

  const candidateHeadings = [...new Set([primaryHeading, ...fallbackHeadings].filter(Boolean))];
  let sectionStart = -1;
  for (const heading of candidateHeadings) {
    const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`^##\\s+${escaped}\\s*$`);
    sectionStart = lines.findIndex((l) => re.test(l));
    if (sectionStart >= 0) break;
  }

  if (sectionStart === -1) {
    if (lines.length > 0 && lines[lines.length - 1].trim() !== "") {
      lines.push("");
    }
    lines.push(`## ${primaryHeading}`, "", fullLine);
    return `${lines.join("\n")}\n`;
  }

  let sectionEnd = lines.findIndex((l, idx) => idx > sectionStart && /^#{1,2}\s+/.test(l));
  if (sectionEnd === -1) sectionEnd = lines.length;

  let insertAt = sectionEnd;
  while (insertAt > sectionStart + 1 && lines[insertAt - 1].trim() === "") {
    insertAt -= 1;
  }
  lines.splice(insertAt, 0, fullLine);
  return `${lines.join("\n")}\n`;
}

export function replaceManagedSection(markdown, heading, contentLines) {
  const normalized = (markdown ?? "").replace(/\r\n/g, "\n");
  const lines = normalized.replace(/\s+$/, "").split("\n");
  if (lines.length === 1 && lines[0] === "") lines.length = 0;

  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`^##\\s+${escaped}\\s*$`);
  const start = lines.findIndex((l) => re.test(l));
  const bodyBlock = ["", ...contentLines];

  if (start === -1) {
    if (lines.length > 0 && lines[lines.length - 1].trim() !== "") {
      lines.push("");
    }
    lines.push(`## ${heading}`, ...bodyBlock);
    return `${lines.join("\n")}\n`;
  }

  let end = lines.findIndex((l, idx) => idx > start && /^#{1,2}\s+/.test(l));
  if (end === -1) end = lines.length;
  const tail = end < lines.length ? ["", ...lines.slice(end)] : [];
  const next = [...lines.slice(0, start + 1), ...bodyBlock, ...tail];
  return `${next.join("\n")}\n`;
}
