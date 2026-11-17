import { existsSync, lstatSync, mkdirSync, readdirSync } from "node:fs";
import { basename, dirname, join, relative } from "node:path";
import {
  atomicWriteVaultNote,
  frontmatterValues,
  isExcludedVaultPath,
  localDateString,
  readVaultNoteSafe,
  renderDailyTemplate,
  replaceManagedSection,
  resolveContainedVaultPath,
  safeNoteSlug,
  sanitizeExternalUrl,
  sanitizeInlineText,
  splitFrontmatter,
  toPosixRel,
  upsertFrontmatter,
  upsertKeyedBulletInSection,
} from "./core.mjs";

export function indexVaultNotes(vaultRootReal, config) {
  const byLowerName = new Map(); // lower basename (no .md) -> array of { name, relPath, absPath }
  const allNotes = [];

  function walk(currentDir) {
    let entries = [];
    try {
      entries = readdirSync(currentDir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      if (ent.name.startsWith(".")) continue;
      if (ent.isSymbolicLink()) continue;
      const fullPath = join(currentDir, ent.name);
      const relPosix = toPosixRel(relative(vaultRootReal, fullPath));
      if (isExcludedVaultPath(relPosix, config, vaultRootReal)) continue;

      if (ent.isDirectory()) {
        walk(fullPath);
      } else if (ent.isFile() && ent.name.endsWith(".md")) {
        const name = ent.name.slice(0, -3);
        const record = { name, relPath: relPosix, absPath: fullPath };
        allNotes.push(record);
        const key = name.toLowerCase();
        if (!byLowerName.has(key)) byLowerName.set(key, []);
        byLowerName.get(key).push(record);
      }
    }
  }

  walk(vaultRootReal);
  return { byLowerName, allNotes };
}

function wikiLink(targetName, alias = "") {
  const cleanTarget = safeNoteSlug(targetName, "");
  if (!cleanTarget) return "";
  if (alias && alias !== cleanTarget) {
    const cleanAlias = sanitizeInlineText(alias, 80).replace(/\|/g, "-");
    return `[[${cleanTarget}|${cleanAlias}]]`;
  }
  return `[[${cleanTarget}]]`;
}

const NOTE_TYPE_BY_FOLDER_KEY = { daily: "daily", tickets: "ticket", repos: "repo", topics: "topic" };

function isNoteOfKind(vaultRootReal, config, note, folderKey, configuredFolder) {
  if (configuredFolder && note.relPath.toLowerCase().startsWith(`${configuredFolder.toLowerCase()}/`)) return true;
  // Ticket IDs are specific enough that a same-named note is that ticket's note.
  if (folderKey === "tickets") return true;
  try {
    const types = frontmatterValues(readVaultNoteSafe(vaultRootReal, config, note.absPath) ?? "", "type") ?? [];
    return types.includes(NOTE_TYPE_BY_FOLDER_KEY[folderKey]);
  } catch {
    return false;
  }
}

function resolveEntityNoteTarget(vaultRootReal, config, index, folderKey, rawSlug) {
  const slug = safeNoteSlug(rawSlug, "");
  if (!slug) return null;

  const configuredFolder = config.folders?.[folderKey];

  // A same-named note always wins (no duplicates), but is written to only if it is this kind of note.
  const existing = index.byLowerName.get(slug.toLowerCase())?.[0];
  if (existing) {
    return {
      slug: existing.name,
      absPath: existing.absPath,
      relPath: existing.relPath,
      canCreate: isNoteOfKind(vaultRootReal, config, existing, folderKey, configuredFolder),
      preexisting: true,
    };
  }

  if (configuredFolder === null) {
    // Link-only mode: emit [[slug]] wikilinks without creating a dedicated folder/note
    return {
      slug,
      absPath: null,
      relPath: null,
      canCreate: false,
      preexisting: false,
    };
  }

  const relPath = configuredFolder ? `${configuredFolder}/${slug}.md` : `${slug}.md`;
  const absPath = resolveContainedVaultPath(vaultRootReal, relPath);
  if (isExcludedVaultPath(relPath, config, vaultRootReal)) {
    return {
      slug,
      absPath: null,
      relPath: null,
      canCreate: false,
      preexisting: false,
    };
  }

  return {
    slug,
    absPath,
    relPath,
    canCreate: true,
    preexisting: false,
  };
}

function formatOutcomeTags(unit, selfNoteLower = "") {
  const parts = [];
  if (unit.commitsCount > 0) {
    parts.push(`${unit.commitsCount} commit${unit.commitsCount === 1 ? "" : "s"}`);
  }
  for (const pr of unit.prs ?? []) {
    const safeUrl = sanitizeExternalUrl(pr.url);
    if (!safeUrl) continue;
    const label = pr.repo ? `${pr.repo}#${pr.number}` : `PR #${pr.number}`;
    const verb = pr.action === "merged" ? "merged " : pr.action === "opened" ? "opened " : "";
    parts.push(`${verb}[${sanitizeInlineText(label, 60)}](${safeUrl})`);
  }
  for (const note of unit.vaultNotes ?? []) {
    if (!note?.title) continue;
    if (note.title.toLowerCase() === selfNoteLower) continue;
    if (/^\d{4}-\d{2}-\d{2}$/.test(note.title)) continue;
    parts.push(`wrote ${wikiLink(note.title)}`);
  }
  if (parts.length === 0 && unit.filesChangedCount > 0) {
    parts.push(`${unit.filesChangedCount} file${unit.filesChangedCount === 1 ? "" : "s"} updated`);
  }
  if (parts.length === 0 && (unit.trackerActions?.length ?? 0) > 0) {
    parts.push(unit.trackerActions.slice(0, 2).join(", "));
  }
  return parts.slice(0, 6).join(", ");
}

function ensureInitialDailyMarkdown(vaultRootReal, config, dateStr) {
  if (config.dailyTemplate) {
    try {
      const tplPath = resolveContainedVaultPath(vaultRootReal, config.dailyTemplate);
      if (!isExcludedVaultPath(tplPath, config, vaultRootReal) && existsSync(tplPath)) {
        const rawTpl = readVaultNoteSafe(vaultRootReal, config, tplPath);
        if (rawTpl && rawTpl.trim()) {
          return renderDailyTemplate(rawTpl, dateStr);
        }
      }
    } catch {
      // Fall back to default daily note skeleton
    }
  }
  return [
    "---",
    "type: daily",
    `date: ${dateStr}`,
    "---",
    "",
    `# ${dateStr}`,
    "",
    `## ${config.dailySection || "Work Log"}`,
    "",
  ].join("\n");
}

function ensureInitialEntityMarkdown(kind, slug, title = "") {
  const heading = title ? `${slug} — ${sanitizeInlineText(title, 100)}` : slug;
  return [
    "---",
    `type: ${kind}`,
    "---",
    "",
    `# ${heading}`,
    "",
    "## Work History",
    "",
  ].join("\n");
}

export function initializeVaultFolder(vaultRootReal, config) {
  const createdFolders = [];
  for (const [, folderRel] of Object.entries(config.folders ?? {})) {
    if (folderRel === null || folderRel === "") continue;
    const folderAbs = resolveContainedVaultPath(vaultRootReal, folderRel);
    if (!existsSync(folderAbs)) {
      mkdirSync(folderAbs, { recursive: true });
      createdFolders.push(folderRel);
    }
  }

  let createdMap = false;
  if (config.mapFile) {
    const mapAbs = resolveContainedVaultPath(vaultRootReal, config.mapFile);
    if (!isExcludedVaultPath(mapAbs, config, vaultRootReal) && !existsSync(mapAbs)) {
      const mapTitle = basename(config.mapFile, ".md");
      const initialMap = [
        "---",
        "type: work-map",
        `updated: ${localDateString()}`,
        "---",
        "",
        `# ${mapTitle}`,
        "",
        "Central map of coding sessions, tickets, repositories, and topics. Open Obsidian Graph View to explore connections.",
        "",
        "## Active Tickets",
        "",
        "_No tickets recorded yet. Complete a task or run `/turn-vault:backfill` to populate._",
        "",
        "## Repositories",
        "",
        "_No repositories recorded yet._",
        "",
        "## Topics & Domains",
        "",
        "_No topics recorded yet._",
        "",
        "## Recent Days",
        "",
        "_No daily logs recorded yet._",
        "",
      ].join("\n");
      atomicWriteVaultNote(vaultRootReal, config, mapAbs, initialMap);
      createdMap = true;
    }
  }

  return { createdFolders, createdMap };
}

export function refreshWorkMap(vaultRootReal, config) {
  if (!config.mapFile) return null;
  const mapAbs = resolveContainedVaultPath(vaultRootReal, config.mapFile);
  if (isExcludedVaultPath(mapAbs, config, vaultRootReal)) return null;

  const { allNotes } = indexVaultNotes(vaultRootReal, config);
  const mapRelPosix = toPosixRel(relative(vaultRootReal, mapAbs));

  const tickets = [];
  const repos = [];
  const topics = [];
  const days = [];

  for (const note of allNotes) {
    if (note.relPath === mapRelPosix) continue;
    let content = null;
    try {
      content = readVaultNoteSafe(vaultRootReal, config, note.absPath);
    } catch {
      continue;
    }
    if (!content) continue;
    const fm = splitFrontmatter(content);
    const fmText = fm?.fmText ?? "";
    const typeMatch = /^type:\s*["']?([A-Za-z0-9_-]+)["']?\s*$/m.exec(fmText);
    const noteType = typeMatch?.[1]?.toLowerCase() ?? "";
    const activeMatch = /^last_active:\s*["']?(\d{4}-\d{2}-\d{2})["']?\s*$/m.exec(fmText);
    const lastActive = activeMatch?.[1] ?? "";
    const titleMatch = /^title:\s*(.+)$/m.exec(fmText);
    let cleanTitle = "";
    if (titleMatch?.[1]) {
      cleanTitle = titleMatch[1].trim().replace(/^["']|["']$/g, "");
    }

    if (noteType === "ticket" || (config.folders.tickets && note.relPath.startsWith(`${config.folders.tickets}/`))) {
      tickets.push({ name: note.name, lastActive, title: cleanTitle });
    } else if (noteType === "repo" || (config.folders.repos && note.relPath.startsWith(`${config.folders.repos}/`))) {
      repos.push({ name: note.name, lastActive });
    } else if (noteType === "topic" || (config.folders.topics && note.relPath.startsWith(`${config.folders.topics}/`))) {
      topics.push({ name: note.name, lastActive });
    } else if (
      (noteType === "daily" || (config.folders.daily && note.relPath.startsWith(`${config.folders.daily}/`))) &&
      /^\d{4}-\d{2}-\d{2}$/.test(note.name)
    ) {
      days.push({ name: note.name });
    }
  }

  tickets.sort((a, b) => (b.lastActive || "").localeCompare(a.lastActive || "") || a.name.localeCompare(b.name));
  repos.sort((a, b) => (b.lastActive || "").localeCompare(a.lastActive || "") || a.name.localeCompare(b.name));
  topics.sort((a, b) => (b.lastActive || "").localeCompare(a.lastActive || "") || a.name.localeCompare(b.name));
  days.sort((a, b) => b.name.localeCompare(a.name));

  let existing = readVaultNoteSafe(vaultRootReal, config, mapAbs);
  if (!existing) {
    initializeVaultFolder(vaultRootReal, config);
    existing = readVaultNoteSafe(vaultRootReal, config, mapAbs) ?? "";
  }

  let updated = upsertFrontmatter(existing, {
    type: "work-map",
    updated: localDateString(),
  });

  updated = replaceManagedSection(
    updated,
    "Active Tickets",
    tickets.length
      ? tickets.slice(0, 80).map((t) =>
          t.title
            ? `- ${wikiLink(t.name)} — ${sanitizeInlineText(t.title, 100)}${t.lastActive ? ` _(${t.lastActive})_` : ""}`
            : `- ${wikiLink(t.name)}${t.lastActive ? ` _(${t.lastActive})_` : ""}`,
        )
      : ["_No tickets recorded yet._"],
  );

  updated = replaceManagedSection(
    updated,
    "Repositories",
    repos.length
      ? repos.slice(0, 60).map((r) => `- ${wikiLink(r.name)}${r.lastActive ? ` _(${r.lastActive})_` : ""}`)
      : ["_No repositories recorded yet._"],
  );

  updated = replaceManagedSection(
    updated,
    "Topics & Domains",
    topics.length
      ? topics.slice(0, 80).map((tp) => `- ${wikiLink(tp.name)}${tp.lastActive ? ` _(${tp.lastActive})_` : ""}`)
      : ["_No topics recorded yet._"],
  );

  updated = replaceManagedSection(
    updated,
    "Recent Days",
    days.length
      ? days.slice(0, 30).map((d) => `- ${wikiLink(d.name)}`)
      : ["_No daily logs recorded yet._"],
  );

  if (updated !== existing) {
    atomicWriteVaultNote(vaultRootReal, config, mapAbs, updated);
  }
  return mapAbs;
}

export function writeWorkUnitsToVault(vaultRootReal, config, units, { enrichments = {}, dryRun = false } = {}) {
  if (!Array.isArray(units) || units.length === 0) {
    return { writtenNotes: [], touchedEntities: { daily: 0, tickets: 0, repos: 0, topics: 0 } };
  }

  const index = indexVaultNotes(vaultRootReal, config);
  const writtenSet = new Set();
  const touchedCounts = { daily: new Set(), tickets: new Set(), repos: new Set(), topics: new Set() };
  const ticketMeta = enrichments?.tickets && typeof enrichments.tickets === "object" ? enrichments.tickets : {};

  // Register newly created notes into the in-memory index so subsequent units in the same batch resolve consistently
  function registerInIndex(slug, absPath, relPath) {
    if (!absPath || !relPath) return;
    const key = slug.toLowerCase();
    const existing = index.byLowerName.get(key) ?? [];
    if (!existing.some((x) => x.absPath === absPath)) {
      existing.push({ name: slug, absPath, relPath });
      index.byLowerName.set(key, existing);
    }
  }

  for (const unit of units) {
    const markerId = `s:${unit.sessionId}`;
    const summaryText = sanitizeInlineText(unit.summary || "Completed coding session", 160);
    const mapBaseName = config.mapFile ? basename(config.mapFile, ".md") : "";

    const unitTopicsSet = new Set(unit.topics ?? []);
    for (const tId of unit.tickets ?? []) {
      const meta = Object.hasOwn(ticketMeta, tId) ? ticketMeta[tId] : null;
      if (Array.isArray(meta?.topics)) {
        for (const extraTopic of meta.topics) {
          const tpSlug = safeNoteSlug(String(extraTopic), "");
          if (tpSlug) unitTopicsSet.add(tpSlug);
        }
      }
    }

    const repoTargets = (unit.repos ?? [])
      .map((r) => resolveEntityNoteTarget(vaultRootReal, config, index, "repos", r))
      .filter(Boolean);
    const ticketTargets = (unit.tickets ?? [])
      .map((t) => resolveEntityNoteTarget(vaultRootReal, config, index, "tickets", t))
      .filter(Boolean);
    const topicTargets = [...unitTopicsSet]
      .filter((tp) => tp.toLowerCase() !== mapBaseName.toLowerCase())
      .map((tp) => resolveEntityNoteTarget(vaultRootReal, config, index, "topics", tp))
      .filter(Boolean);

    const repoLinks = repoTargets.map((r) => wikiLink(r.slug)).filter(Boolean);
    const ticketLinks = ticketTargets.map((t) => wikiLink(t.slug)).filter(Boolean);
    const topicLinks = topicTargets.map((tp) => wikiLink(tp.slug)).filter(Boolean);
    const daySlug = safeNoteSlug(unit.date, localDateString());
    const dayLink = wikiLink(daySlug);

    // 1. Daily Note (when folders.daily is enabled)
    if (config.folders.daily !== null) {
      const dailyTarget = resolveEntityNoteTarget(vaultRootReal, config, index, "daily", daySlug);
      if (dailyTarget?.canCreate && dailyTarget.absPath) {
        const outcomes = formatOutcomeTags(unit, daySlug.toLowerCase());
        const contextLinks = [...repoLinks, ...ticketLinks, ...topicLinks];
        const prefix = contextLinks.length ? `${contextLinks.join(" · ")} — ` : "";
        const suffix = outcomes ? ` (${outcomes})` : "";
        const bullet = `- **${unit.time || "00:00"}** · ${prefix}${summaryText}${suffix}`;

        touchedCounts.daily.add(dailyTarget.relPath);
        if (!dryRun) {
          const current = readVaultNoteSafe(vaultRootReal, config, dailyTarget.absPath)
            ?? ensureInitialDailyMarkdown(vaultRootReal, config, daySlug);
          const withFm = upsertFrontmatter(
            current,
            { type: frontmatterValues(current, "type") ? undefined : "daily", date: daySlug },
            {
              tickets: ticketLinks,
              repos: repoLinks,
              topics: topicLinks,
            },
          );
          const next = upsertKeyedBulletInSection(
            withFm,
            config.dailySection || "Work Log",
            markerId,
            bullet,
            { fallbackHeadings: ["Work Log", "Activity", "Log"] },
          );
          if (next !== current) {
            atomicWriteVaultNote(vaultRootReal, config, dailyTarget.absPath, next);
            registerInIndex(dailyTarget.slug, dailyTarget.absPath, dailyTarget.relPath);
            writtenSet.add(dailyTarget.relPath);
          }
        }
      }
    }

    // 2. Ticket Notes
    for (const tTarget of ticketTargets) {
      if (!tTarget.canCreate || !tTarget.absPath) continue;
      const meta = Object.hasOwn(ticketMeta, tTarget.slug)
        ? ticketMeta[tTarget.slug]
        : Object.hasOwn(ticketMeta, tTarget.slug.toUpperCase())
          ? ticketMeta[tTarget.slug.toUpperCase()]
          : null;
      const outcomes = formatOutcomeTags(unit, tTarget.slug.toLowerCase());
      const peerLinks = [
        ...(config.folders.daily !== null ? [dayLink] : []),
        ...repoLinks,
        ...topicLinks,
      ].filter(Boolean);
      const prefix = peerLinks.length ? `${peerLinks.join(" · ")} — ` : "";
      const suffix = outcomes ? ` (${outcomes})` : "";
      const bullet = `- ${prefix}${summaryText}${suffix}`;

      touchedCounts.tickets.add(tTarget.relPath);
      if (!dryRun) {
        const current = readVaultNoteSafe(vaultRootReal, config, tTarget.absPath)
          ?? ensureInitialEntityMarkdown("ticket", tTarget.slug, meta?.title ?? "");

        const scalarUpdates = {
          type: frontmatterValues(current, "type") ? undefined : "ticket",
          ticket: tTarget.slug,
          last_active: unit.date,
        };
        if (meta?.title) scalarUpdates.title = sanitizeInlineText(meta.title, 120);
        if (meta?.status) scalarUpdates.status = sanitizeInlineText(meta.status, 40);
        if (meta?.url) {
          const safeUrl = sanitizeExternalUrl(meta.url);
          if (safeUrl) scalarUpdates.url = safeUrl;
        }

        const prUrls = (unit.prs ?? []).map((p) => sanitizeExternalUrl(p.url)).filter(Boolean);
        const withFm = upsertFrontmatter(
          current,
          scalarUpdates,
          {
            repos: repoLinks,
            topics: topicLinks,
            days: config.folders.daily !== null ? [dayLink] : [],
            prs: prUrls,
          },
        );
        const next = upsertKeyedBulletInSection(
          withFm,
          "Work History",
          markerId,
          bullet,
          { fallbackHeadings: ["Sessions", "Activity", "Work Log"] },
        );
        if (next !== current) {
          atomicWriteVaultNote(vaultRootReal, config, tTarget.absPath, next);
          registerInIndex(tTarget.slug, tTarget.absPath, tTarget.relPath);
          writtenSet.add(tTarget.relPath);
        }
      }
    }

    // 3. Repository Hub Notes
    for (const rTarget of repoTargets) {
      if (!rTarget.canCreate || !rTarget.absPath) continue;
      const outcomes = formatOutcomeTags(unit, rTarget.slug.toLowerCase());
      const peerLinks = [
        ...(config.folders.daily !== null ? [dayLink] : []),
        ...ticketLinks,
        ...topicLinks,
      ].filter(Boolean);
      const prefix = peerLinks.length ? `${peerLinks.join(" · ")} — ` : "";
      const suffix = outcomes ? ` (${outcomes})` : "";
      const bullet = `- ${prefix}${summaryText}${suffix}`;

      touchedCounts.repos.add(rTarget.relPath);
      if (!dryRun) {
        const current = readVaultNoteSafe(vaultRootReal, config, rTarget.absPath)
          ?? ensureInitialEntityMarkdown("repo", rTarget.slug);
        const withFm = upsertFrontmatter(
          current,
          {
            type: frontmatterValues(current, "type") ? undefined : "repo",
            repo: rTarget.slug,
            last_active: unit.date,
          },
          {
            tickets: ticketLinks,
            topics: topicLinks,
          },
        );
        const next = upsertKeyedBulletInSection(
          withFm,
          "Work History",
          markerId,
          bullet,
          { fallbackHeadings: ["Recent Work", "Activity", "Work Log"] },
        );
        if (next !== current) {
          atomicWriteVaultNote(vaultRootReal, config, rTarget.absPath, next);
          registerInIndex(rTarget.slug, rTarget.absPath, rTarget.relPath);
          writtenSet.add(rTarget.relPath);
        }
      }
    }

    // 4. Topic Hub Notes
    for (const tpTarget of topicTargets) {
      if (!tpTarget.canCreate || !tpTarget.absPath) continue;
      const outcomes = formatOutcomeTags(unit, tpTarget.slug.toLowerCase());
      const peerLinks = [
        ...(config.folders.daily !== null ? [dayLink] : []),
        ...ticketLinks,
        ...repoLinks,
      ].filter(Boolean);
      const prefix = peerLinks.length ? `${peerLinks.join(" · ")} — ` : "";
      const suffix = outcomes ? ` (${outcomes})` : "";
      const bullet = `- ${prefix}${summaryText}${suffix}`;

      touchedCounts.topics.add(tpTarget.relPath);
      if (!dryRun) {
        const current = readVaultNoteSafe(vaultRootReal, config, tpTarget.absPath)
          ?? ensureInitialEntityMarkdown("topic", tpTarget.slug);
        const withFm = upsertFrontmatter(
          current,
          {
            type: frontmatterValues(current, "type") ? undefined : "topic",
            topic: tpTarget.slug,
            last_active: unit.date,
          },
          {
            tickets: ticketLinks,
            repos: repoLinks,
          },
        );
        const next = upsertKeyedBulletInSection(
          withFm,
          "Work History",
          markerId,
          bullet,
          { fallbackHeadings: ["Related Work", "Activity", "Work Log"] },
        );
        if (next !== current) {
          atomicWriteVaultNote(vaultRootReal, config, tpTarget.absPath, next);
          registerInIndex(tpTarget.slug, tpTarget.absPath, tpTarget.relPath);
          writtenSet.add(tpTarget.relPath);
        }
      }
    }
  }

  if (!dryRun && writtenSet.size > 0 && config.mapFile) {
    const mapAbs = refreshWorkMap(vaultRootReal, config);
    if (mapAbs) {
      writtenSet.add(toPosixRel(relative(vaultRootReal, mapAbs)));
    }
  }

  return {
    writtenNotes: [...writtenSet].sort(),
    touchedEntities: {
      daily: touchedCounts.daily.size,
      tickets: touchedCounts.tickets.size,
      repos: touchedCounts.repos.size,
      topics: touchedCounts.topics.size,
    },
  };
}

function stripCodeFromMarkdown(md) {
  // Remove fenced code blocks and inline code spans before scanning [[wikilinks]]
  return md
    .replace(/```[\s\S]*?```/g, "")
    .replace(/~~~[\s\S]*?~~~/g, "")
    .replace(/`[^`\n]+`/g, "");
}

export function extractWikiLinkTargets(markdown) {
  if (typeof markdown !== "string" || !markdown) return [];
  const targets = new Set();
  const stripped = stripCodeFromMarkdown(markdown);
  for (const m of stripped.matchAll(/!?\[\[([^[\]\n]+)\]\]/g)) {
    let raw = m[1].trim();
    if (!raw) continue;
    // Strip alias |... and heading/block #...
    raw = raw.split("|")[0].split("#")[0].trim();
    if (!raw) continue;
    // Ignore non-markdown attachment embeds (.png, .jpg, .pdf, .canvas, .base)
    if (/\.(png|jpg|jpeg|gif|webp|svg|pdf|mp4|mov|canvas|base)$/i.test(raw)) continue;
    raw = raw.replace(/\.md$/i, "");
    targets.add(raw);
  }
  return [...targets];
}

export function checkVaultGraph(vaultRootReal, config) {
  const { byLowerName, allNotes } = indexVaultNotes(vaultRootReal, config);
  const byRelLower = new Map();
  for (const n of allNotes) {
    byRelLower.set(n.relPath.replace(/\.md$/i, "").toLowerCase(), n);
  }

  const duplicateBasenames = [];
  for (const [, list] of byLowerName.entries()) {
    if (list.length > 1) {
      duplicateBasenames.push({
        basename: list[0].name,
        paths: list.map((x) => x.relPath).sort(),
      });
    }
  }

  const emptyFiles = [];
  const unresolvedLinks = [];
  const incomingCounts = new Map(allNotes.map((n) => [n.relPath, 0]));
  const outgoingCounts = new Map(allNotes.map((n) => [n.relPath, 0]));
  let totalEdges = 0;

  for (const note of allNotes) {
    let content = "";
    try {
      content = readVaultNoteSafe(vaultRootReal, config, note.absPath) ?? "";
    } catch {
      continue;
    }
    if (!content.trim()) {
      emptyFiles.push(note.relPath);
      continue;
    }

    const targets = extractWikiLinkTargets(content);
    outgoingCounts.set(note.relPath, targets.length);
    for (const target of targets) {
      totalEdges += 1;
      const lower = target.toLowerCase();
      const resolved = byRelLower.get(lower) ?? byLowerName.get(lower)?.[0] ?? null;
      if (resolved) {
        incomingCounts.set(resolved.relPath, (incomingCounts.get(resolved.relPath) ?? 0) + 1);
      } else {
        unresolvedLinks.push({ from: note.relPath, target });
      }
    }
  }

  const mapRel = config.mapFile ? toPosixRel(config.mapFile) : "";
  const orphans = allNotes
    .filter(
      (n) =>
        n.relPath !== mapRel &&
        (incomingCounts.get(n.relPath) ?? 0) === 0 &&
        (outgoingCounts.get(n.relPath) ?? 0) === 0,
    )
    .map((n) => n.relPath)
    .sort();

  return {
    ok: duplicateBasenames.length === 0 && emptyFiles.length === 0,
    vaultDir: vaultRootReal,
    notesCount: allNotes.length,
    edgesCount: totalEdges,
    duplicateBasenames,
    emptyFiles,
    unresolvedLinks: unresolvedLinks.slice(0, 100),
    unresolvedCount: unresolvedLinks.length,
    orphans: orphans.slice(0, 100),
    orphanCount: orphans.length,
  };
}
