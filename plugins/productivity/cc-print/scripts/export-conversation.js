#!/usr/bin/env node

/**
 * Claude Conversation Exporter
 * Converts Claude Code or Codex JSONL to terminal-styled PNG/SVG/PDF/HTML
 *
 * Usage: node export-conversation.js <jsonl-file> [options]
 * Options:
 *   --output <path>     Output path (default: ~/Desktop/claude-conversation-{timestamp}.png)
 *   --format <fmt>      Output format: png, svg, pdf, html (default: png)
 *   --include-thinking  Include assistant thinking blocks
 *   --include-tools     Show full tool inputs
 *   --light-theme       Use light theme instead of dark
 *   --from <text>       Start from message containing text
 *   --until <text>      Stop before message containing text
 *   --last <n>          Only include the last n exchanges (an exchange starts at a user prompt)
 *   --width <px>        Image width in pixels (default: 1200)
 *   --scale <n>         Pixel scale factor for PNG (default: 2)
 *   --include-self      Include /print invocations in export (excluded by default)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Puppeteer is optional and usually installed globally (npm install -g puppeteer), which
// Node's require() does not search, so fall back to npm's global folder.
function loadPuppeteer() {
  try {
    return require('puppeteer');
  } catch (e) {
    const globalRoot = require('child_process').execSync('npm root -g', { encoding: 'utf8' }).trim();
    return require(path.join(globalRoot, 'puppeteer'));
  }
}

const FORMATS = ['png', 'svg', 'pdf', 'html'];

function usage() {
  console.error('Usage: node export-conversation.js <jsonl-file> [options]');
  console.error('Options:');
  console.error('  --output <path>     Output path');
  console.error('  --format <fmt>      png, svg, pdf, html (default: png)');
  console.error('  --include-thinking  Include thinking blocks');
  console.error('  --include-tools     Show full tool inputs');
  console.error('  --light-theme       Use light theme');
  console.error('  --from <text>       Start from message containing text');
  console.error('  --until <text>      Stop before message containing text');
  console.error('  --last <n>          Only the last n exchanges');
  console.error('  --width <px>        Image width (default: 1200)');
  console.error('  --scale <n>         PNG scale factor (default: 2)');
  console.error('  --include-self      Include /print invocations (excluded by default)');
  process.exit(1);
}

function positiveNumber(flag, value, { integer }) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0 || (integer && !Number.isInteger(n))) {
    console.error(`${flag} needs a positive ${integer ? 'whole ' : ''}number, got "${value}"`);
    process.exit(1);
  }
  return n;
}

const VALUE_FLAGS = ['--output', '--format', '--from', '--until', '--last', '--width', '--scale'];

// Parse arguments
const args = process.argv.slice(2);
const options = {
  input: null,
  output: null,
  format: 'png',
  includeThinking: false,
  includeTools: false,
  lightTheme: false,
  fromText: null,
  untilText: null,
  lastN: null,
  width: 1200,
  scale: 2,
  includeSelf: false,
};

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '--output' && args[i + 1]) {
    options.output = args[++i];
  } else if (arg === '--format' && args[i + 1]) {
    options.format = args[++i];
  } else if (arg === '--include-thinking') {
    options.includeThinking = true;
  } else if (arg === '--include-tools') {
    options.includeTools = true;
  } else if (arg === '--light-theme') {
    options.lightTheme = true;
  } else if (arg === '--from' && args[i + 1]) {
    options.fromText = args[++i];
  } else if (arg === '--until' && args[i + 1]) {
    options.untilText = args[++i];
  } else if (arg === '--last' && args[i + 1]) {
    options.lastN = positiveNumber('--last', args[++i], { integer: true });
  } else if (arg === '--width' && args[i + 1]) {
    options.width = positiveNumber('--width', args[++i], { integer: true });
  } else if (arg === '--scale' && args[i + 1]) {
    options.scale = positiveNumber('--scale', args[++i], { integer: false });
  } else if (arg === '--include-self') {
    options.includeSelf = true;
  } else if (!arg.startsWith('--')) {
    options.input = arg;
  } else if (VALUE_FLAGS.includes(arg)) {
    console.error(`${arg} needs a value`);
    process.exit(1);
  } else {
    console.error(`Unknown option: ${arg}`);
    usage();
  }
}

if (!options.input) usage();
if (!FORMATS.includes(options.format)) {
  console.error(`--format must be one of ${FORMATS.join(', ')}, got "${options.format}"`);
  process.exit(1);
}

// Default output path: the Desktop when there is one, otherwise the current folder.
if (!options.output) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const desktop = path.join(os.homedir(), 'Desktop');
  const folder = fs.existsSync(desktop) ? desktop : process.cwd();
  options.output = path.join(folder, `claude-conversation-${timestamp}.${options.format}`);
}

// Terminal color themes - matching Claude Code's actual terminal output
const darkTheme = {
  bg: '#0d1117',           // GitHub dark background
  text: '#e6edf3',         // Primary text
  textMuted: '#7d8590',    // Muted text
  userPrompt: '#3fb950',   // Green prompt symbol
  userText: '#58a6ff',     // Blue user input
  assistantText: '#e6edf3', // White assistant text
  codeBg: '#161b22',       // Code block background
  codeBorder: '#30363d',   // Code block border
  codeText: '#e6edf3',     // Code text
  toolText: '#7d8590',     // Tool calls (muted)
  thinkingBg: '#1c2128',   // Thinking block background
  headerText: '#f0883e',   // Orange headers
  linkText: '#58a6ff',     // Links
  bold: '#ffffff',         // Bold text
  italic: '#e6edf3',       // Italic text
  inlineCode: '#ff7b72',   // Inline code
  inlineCodeBg: '#343942', // Inline code background
  highlightCss: 'github-dark',
};

const lightTheme = {
  bg: '#ffffff',
  text: '#1f2328',
  textMuted: '#656d76',
  userPrompt: '#1a7f37',
  userText: '#0969da',
  assistantText: '#1f2328',
  codeBg: '#f6f8fa',
  codeBorder: '#d0d7de',
  codeText: '#1f2328',
  toolText: '#656d76',
  thinkingBg: '#f6f8fa',
  headerText: '#953800',
  linkText: '#0969da',
  bold: '#000000',
  italic: '#1f2328',
  inlineCode: '#cf222e',
  inlineCodeBg: '#eff1f3',
  highlightCss: 'github',
};

// Both transcript formats parse to one shape:
//   { role: 'user' | 'assistant', blocks: [{ kind: 'text' | 'thinking' | 'tool', ... }] }

// Text the harness injects into the user role. None of it was typed by the user.
const HARNESS_TEXT = [
  /^<task-notification>/,
  /^<local-command-(stdout|stderr|caveat)>/,
  /^\[Request interrupted by user/,
  /^Caveat: The messages below were generated by the user while running local commands/,
];

function textOf(content, types) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content
    .filter((part) => types.includes(part.type))
    .map((part) => part.text || '')
    .join('\n');
}

// Claude Code records a slash command as XML tags; show it the way the user typed it.
function claudeUserText(raw) {
  const text = raw.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '').trim();
  const command = text.match(/<command-name>([\s\S]*?)<\/command-name>/);
  if (command) {
    const commandArgs = text.match(/<command-args>([\s\S]*?)<\/command-args>/);
    return [command[1].trim(), commandArgs ? commandArgs[1].trim() : ''].filter(Boolean).join(' ');
  }
  if (HARNESS_TEXT.some((pattern) => pattern.test(text))) return '';
  return text;
}

function parseClaudeEntry(entry) {
  if (entry.type === 'user') {
    // isMeta marks skill bodies, expanded command prompts and hook feedback; tool results
    // arrive as user entries whose content has no text part.
    if (entry.isMeta || entry.isCompactSummary) return null;
    const text = claudeUserText(textOf(entry.message?.content, ['text']));
    return text ? { role: 'user', blocks: [{ kind: 'text', text }] } : null;
  }
  // A message typed while the assistant is still working is stored as a queued attachment.
  if (entry.type === 'attachment' && entry.attachment?.type === 'queued_command' && entry.attachment.humanTurn !== false) {
    const text = typeof entry.attachment.prompt === 'string' ? entry.attachment.prompt.trim() : '';
    return text ? { role: 'user', blocks: [{ kind: 'text', text }] } : null;
  }
  if (entry.type === 'assistant') {
    const content = entry.message?.content;
    if (typeof content === 'string') return { role: 'assistant', blocks: [{ kind: 'text', text: content }] };
    const blocks = [];
    for (const block of content || []) {
      if (block.type === 'text' && block.text) blocks.push({ kind: 'text', text: block.text });
      else if (block.type === 'thinking' && block.thinking) blocks.push({ kind: 'thinking', text: block.thinking });
      else if (block.type === 'tool_use') blocks.push({ kind: 'tool', name: block.name, input: block.input });
    }
    return blocks.length ? { role: 'assistant', blocks } : null;
  }
  return null;
}

// Codex puts context of its own in the user role, each block opening with one of these tags.
const CODEX_CONTEXT = /^\s*(<(environment_context|goal_context|objective|recommended_plugins|guardian_tool_descriptions|node_repl_review_evidence|skill|user_instructions|user_shell_command|turn_aborted)>|# AGENTS\.md instructions)/;

// response_item holds the whole conversation. Its event_msg copies are missing from many
// sessions, so they are read only from a rollout that has no response_item messages at all.
function parseCodex(entries) {
  const messages = [];
  for (const { type, payload } of entries) {
    if (type !== 'response_item' || !payload) continue;
    if (payload.type === 'message' && payload.role === 'user') {
      const parts = (payload.content || [])
        .filter((part) => part.type === 'input_text' && part.text && !CODEX_CONTEXT.test(part.text))
        .map((part) => part.text.trim());
      if (parts.length) messages.push({ role: 'user', blocks: [{ kind: 'text', text: parts.join('\n') }] });
    } else if (payload.type === 'message' && payload.role === 'assistant') {
      const text = textOf(payload.content, ['output_text']);
      if (text) messages.push({ role: 'assistant', blocks: [{ kind: 'text', text }] });
    } else if (payload.type === 'function_call' || payload.type === 'custom_tool_call') {
      messages.push({ role: 'assistant', blocks: [{ kind: 'tool', name: payload.name, input: payload.arguments ?? payload.input }] });
    }
  }
  if (messages.some((msg) => msg.blocks.some((b) => b.kind === 'text'))) return messages;

  const roles = { user_message: 'user', agent_message: 'assistant' };
  return entries
    .filter(({ type, payload }) => type === 'event_msg' && roles[payload?.type] && payload.message)
    .map(({ payload }) => ({ role: roles[payload.type], blocks: [{ kind: 'text', text: payload.message }] }));
}

// Consecutive assistant entries are one reply: Claude Code writes each content block of a
// message as its own line, and Codex interleaves tool calls with text.
function mergeAssistantRuns(messages) {
  const merged = [];
  for (const msg of messages) {
    const last = merged[merged.length - 1];
    if (msg.role === 'assistant' && last?.role === 'assistant') last.blocks.push(...msg.blocks);
    else merged.push(msg);
  }
  return merged;
}

function parseConversation(filePath) {
  const entries = [];
  for (const line of fs.readFileSync(filePath, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    try {
      entries.push(JSON.parse(line));
    } catch (e) {
      // A transcript being written can end in a partial line; skip it.
    }
  }
  const isCodex = entries.some((e) => e.type === 'session_meta' || e.type === 'response_item' || e.type === 'event_msg');
  const messages = isCodex ? parseCodex(entries) : entries.map(parseClaudeEntry).filter(Boolean);
  return mergeAssistantRuns(messages);
}

function plainText(msg) {
  return msg.blocks.filter((b) => b.kind === 'text').map((b) => b.text).join('\n');
}

// A user prompt that runs this exporter; it and the reply to it are left out.
const SELF_PATTERNS = [
  /^\/(cc-print:)?print\b/i,
  /^\$(cc-print:)?codex-print\b/i,
  /^export this conversation to a terminal-styled/i,
];

function filterSelfReferences(messages) {
  const filtered = [];
  let skipping = false;
  for (const msg of messages) {
    if (msg.role === 'user') skipping = SELF_PATTERNS.some((p) => p.test(plainText(msg).trim()));
    if (!skipping) filtered.push(msg);
  }
  return filtered;
}

function filterMessages(messages) {
  let filtered = options.includeSelf ? messages : filterSelfReferences(messages);
  const indexOf = (needle) => filtered.findIndex((msg) => plainText(msg).toLowerCase().includes(needle.toLowerCase()));

  if (options.fromText) {
    const start = indexOf(options.fromText);
    if (start >= 0) filtered = filtered.slice(start);
    else console.warn(`--from: no message contains "${options.fromText}"; exporting from the start`);
  }
  if (options.untilText) {
    const end = indexOf(options.untilText);
    if (end >= 0) filtered = filtered.slice(0, end);
    else console.warn(`--until: no message contains "${options.untilText}"; exporting to the end`);
  }
  if (options.lastN) {
    const userIndexes = filtered.flatMap((msg, i) => (msg.role === 'user' ? [i] : []));
    if (userIndexes.length > options.lastN) filtered = filtered.slice(userIndexes[userIndexes.length - options.lastN]);
  }
  return filtered;
}

// Fenced code is cut out before any Markdown rule runs, so nothing inside it is ever rewritten;
// inline code spans are protected the same way within a line.

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderInline(text) {
  const spans = [];
  const protect = (html) => `\u0000${spans.push(html) - 1}\u0000`;
  let html = escapeHtml(text).replace(/`([^`\n]+)`/g, (_, code) => protect(`<code class="inline">${code}</code>`));
  html = html
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => protect(`<a href="${url}">${label}</a>`))
    .replace(/\*\*(?=\S)([^*\n]*?\S)\*\*/g, '<strong>$1</strong>')
    // Emphasis needs text hugging both asterisks, so arithmetic like 2 * 3 stays as written.
    .replace(/(^|[^\w*])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![\w*])/g, '$1<em>$2</em>');
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => spans[Number(i)]);
}

function renderTable(rows) {
  const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map((cell) => renderInline(cell.trim()));
  const [header, , ...body] = rows;
  const head = cells(header).map((c) => `<th>${c}</th>`).join('');
  const bodyHtml = body.map((row) => `<tr>${cells(row).map((c) => `<td>${c}</td>`).join('')}</tr>`).join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
}

// A table's second row: every cell is dashes, optionally colon-aligned.
function isTableDivider(line) {
  if (!line.includes('|')) return false; // a bare --- is a horizontal rule
  const cells = line.trim().replace(/^\||\|$/g, '').split('|');
  return cells.every((cell) => /^\s*:?-{3,}:?\s*$/.test(cell));
}

function renderMarkdown(text) {
  const html = [];
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  let paragraph = [];
  const flush = () => {
    if (paragraph.length) html.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`);
    paragraph = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const fence = line.match(/^\s*(`{3,}|~{3,})\s*([\w+#.-]*)/);
    if (fence) {
      flush();
      const code = [];
      const close = new RegExp(`^\\s*${fence[1][0]}{${fence[1].length},}\\s*$`);
      while (++i < lines.length && !close.test(lines[i])) code.push(lines[i]);
      const lang = fence[2];
      html.push(`<div class="code-block"><div class="code-header">${escapeHtml(lang || 'code')}</div>` +
        `<pre><code class="${lang ? `language-${escapeHtml(lang)}` : 'nohighlight'}">${escapeHtml(code.join('\n'))}</code></pre></div>`);
      continue;
    }
    if (line.includes('|') && isTableDivider(lines[i + 1] || '')) {
      flush();
      const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(lines[i++]);
      i--;
      html.push(renderTable(rows));
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    const item = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
    if (heading) {
      flush();
      const level = Math.min(heading[1].length, 3);
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
    } else if (item) {
      flush();
      const marker = /\d/.test(item[2]) ? item[2] : '•';
      const indent = Math.floor(item[1].length / 2);
      html.push(`<div class="list-item" style="margin-left:${indent * 20}px"><span class="marker">${marker}</span>${renderInline(item[3])}</div>`);
    } else if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flush();
      html.push('<hr>');
    } else if (!line.trim()) {
      flush();
    } else {
      paragraph.push(line);
    }
  }
  flush();
  return html.join('\n');
}

function renderToolInput(input) {
  if (input === undefined) return '';
  const body = typeof input === 'string' ? input : JSON.stringify(input, null, 2);
  return `<pre class="tool-input">${escapeHtml(body)}</pre>`;
}

function renderMessage(msg) {
  if (msg.role === 'user') {
    return `<div class="message user-message"><span class="prompt">❯</span><div class="user-content">${escapeHtml(plainText(msg))}</div></div>`;
  }
  const parts = [];
  for (const block of msg.blocks) {
    if (block.kind === 'text') {
      parts.push(`<div class="assistant-text">${renderMarkdown(block.text)}</div>`);
    } else if (block.kind === 'thinking' && options.includeThinking) {
      parts.push(`<div class="thinking"><div class="thinking-label">Thinking...</div>${escapeHtml(block.text)}</div>`);
    } else if (block.kind === 'tool') {
      const name = `<span class="tool-name">${escapeHtml(block.name || 'tool')}</span>`;
      parts.push(options.includeTools
        ? `<div class="tool-use"><span class="tool-icon">⚡</span> ${name}${renderToolInput(block.input)}</div>`
        : `<div class="tool-use"><span class="tool-icon">⚡</span> Used ${name}</div>`);
    }
  }
  return parts.length ? `<div class="message assistant-message">${parts.join('\n')}</div>` : '';
}

// Generate HTML that looks like terminal
function generateHtml(messages) {
  const theme = options.lightTheme ? lightTheme : darkTheme;
  const messagesHtml = messages.map(renderMessage).join('\n');
  const highlightJs = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0';

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Claude Conversation</title>
  <link rel="stylesheet" href="${highlightJs}/styles/${theme.highlightCss}.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    html, body {
      background: ${theme.bg};
      color: ${theme.text};
      font-family: 'JetBrains Mono', 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
      font-size: 13px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    body {
      padding: 24px 32px;
      min-height: 100vh;
    }

    .message {
      margin-bottom: 24px;
    }

    /* User message styling */
    .user-message {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
      color: ${theme.userText};
    }

    .user-content {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .prompt {
      color: ${theme.userPrompt};
      font-weight: 600;
    }

    /* Assistant message styling */
    .assistant-text {
      color: ${theme.assistantText};
      overflow-wrap: anywhere;
    }

    .assistant-text p {
      margin: 0 0 10px 0;
    }

    a {
      color: ${theme.linkText};
    }

    /* Headers */
    h1, h2, h3 {
      color: ${theme.headerText};
      font-weight: 600;
      margin: 16px 0 8px 0;
    }

    h1 { font-size: 1.4em; }
    h2 { font-size: 1.2em; }
    h3 { font-size: 1.1em; }

    /* Code blocks */
    .code-block {
      background: ${theme.codeBg};
      border: 1px solid ${theme.codeBorder};
      border-radius: 6px;
      margin: 12px 0;
      overflow: hidden;
    }

    .code-header {
      background: ${theme.codeBorder};
      color: ${theme.textMuted};
      padding: 6px 12px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .code-block pre {
      margin: 0;
      padding: 12px 16px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .code-block code, .code-block code.hljs {
      background: transparent;
      padding: 0;
      color: ${theme.codeText};
      font-size: 12px;
      line-height: 1.5;
    }

    /* Inline code */
    code.inline {
      background: ${theme.inlineCodeBg};
      color: ${theme.inlineCode};
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
    }

    /* Tables */
    table {
      border-collapse: collapse;
      margin: 12px 0;
    }

    th, td {
      border: 1px solid ${theme.codeBorder};
      padding: 4px 10px;
      text-align: left;
      vertical-align: top;
    }

    th {
      color: ${theme.bold};
      background: ${theme.codeBg};
    }

    /* Tool usage */
    .tool-use {
      color: ${theme.toolText};
      font-size: 12px;
      border-left: 2px solid ${theme.codeBorder};
      padding: 4px 0 4px 12px;
      margin: 8px 0;
    }

    .tool-icon {
      color: ${theme.userPrompt};
    }

    .tool-name {
      color: ${theme.linkText};
      font-weight: 500;
    }

    .tool-input {
      margin-top: 8px;
      padding: 8px;
      background: ${theme.codeBg};
      border-radius: 4px;
      font-size: 11px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    /* Thinking blocks */
    .thinking {
      background: ${theme.thinkingBg};
      border-radius: 6px;
      padding: 12px 16px;
      margin: 12px 0;
      font-size: 12px;
      color: ${theme.textMuted};
      white-space: pre-wrap;
    }

    .thinking-label {
      color: ${theme.textMuted};
      font-size: 11px;
      margin-bottom: 8px;
      font-style: italic;
    }

    /* Lists */
    .list-item {
      display: flex;
      gap: 8px;
      margin: 4px 0 4px 8px;
    }

    .list-item .marker {
      color: ${theme.textMuted};
      flex: none;
    }

    /* Typography */
    strong {
      color: ${theme.bold};
      font-weight: 600;
    }

    em {
      font-style: italic;
      color: ${theme.italic};
    }

    hr {
      border: none;
      border-top: 1px solid ${theme.codeBorder};
      margin: 16px 0;
    }
  </style>
</head>
<body>
  <div class="conversation">
    ${messagesHtml}
  </div>
  <script src="${highlightJs}/highlight.min.js"></script>
  <script>window.hljs && hljs.highlightAll();</script>
</body>
</html>`;
}

// Main function
async function main() {
  console.log('Reading conversation...');
  const messages = parseConversation(options.input);
  console.log(`Found ${messages.length} messages`);

  const filtered = filterMessages(messages);
  console.log(`Exporting ${filtered.length} messages${!options.includeSelf ? ' (self-references excluded)' : ''}`);
  if (!filtered.length) {
    console.error('Nothing to export: no user or assistant messages matched.');
    process.exit(1);
  }

  const html = generateHtml(filtered);

  // HTML-only output
  if (options.format === 'html') {
    fs.writeFileSync(options.output, html);
    console.log(`HTML saved to: ${options.output}`);
    return;
  }

  const tempHtml = path.join(os.tmpdir(), `cc-print-${process.pid}.html`);
  fs.writeFileSync(tempHtml, html);

  let browser;
  try {
    const puppeteer = loadPuppeteer();
    console.log('Launching browser...');
    browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();

    // Set viewport for consistent rendering
    await page.setViewport({
      width: options.width,
      height: 800,
      deviceScaleFactor: options.scale,
    });

    await page.goto(`file://${tempHtml}`, { waitUntil: 'networkidle0' });

    // Wait for fonts to load
    await page.evaluate(() => document.fonts.ready);

    if (options.format === 'png') {
      console.log('Generating PNG...');
      await page.screenshot({
        path: options.output,
        fullPage: true,
        type: 'png',
      });
      console.log(`PNG saved to: ${options.output}`);
    } else if (options.format === 'svg') {
      console.log('Generating SVG...');
      // The SVG wraps the full-page PNG at device scale, so its text is not selectable.
      const dimensions = await page.evaluate(() => ({
        width: document.body.scrollWidth,
        height: document.body.scrollHeight,
      }));
      const screenshot = await page.screenshot({
        fullPage: true,
        type: 'png',
        encoding: 'base64',
      });

      const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="${dimensions.width}" height="${dimensions.height}"
     viewBox="0 0 ${dimensions.width} ${dimensions.height}">
  <image width="100%" height="100%" xlink:href="data:image/png;base64,${screenshot}"/>
</svg>`;

      fs.writeFileSync(options.output, svg);
      console.log(`SVG saved to: ${options.output}`);
    } else if (options.format === 'pdf') {
      console.log('Generating PDF...');
      await page.pdf({
        path: options.output,
        format: 'A4',
        printBackground: true,
        margin: { top: '1cm', bottom: '1cm', left: '1cm', right: '1cm' },
      });
      console.log(`PDF saved to: ${options.output}`);
    }
  } catch (e) {
    const htmlFallback = options.output.replace(/(\.(png|svg|pdf))?$/, '.html');
    fs.copyFileSync(tempHtml, htmlFallback);
    console.error('Export failed:', e.message);
    if (e.message.includes('Cannot find module')) {
      console.error('Install puppeteer: npm install -g puppeteer');
    }
    console.error(`HTML saved to: ${htmlFallback}`);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    fs.rmSync(tempHtml, { force: true });
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
