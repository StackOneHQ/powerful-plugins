#!/usr/bin/env npx tsx
/**
 * Forge Skill Evaluator v2
 *
 * Tests the forge skill against scenarios covering:
 * - True positives: issues forge MUST catch
 * - True negatives: clean code forge must NOT over-flag
 * - Adversarial: tricky cases that test calibration
 * - AI slop: agent-written diffs forge must deslop without flagging legitimate boundary code
 * - LLM-as-judge: subjective quality scoring
 * - Statistical reliability: 3 runs per scenario, majority vote
 *
 * Usage:
 *   npx tsx forge-eval.ts                        # Run all scenarios (3 runs each)
 *   npx tsx forge-eval.ts --scenario retry       # Run one scenario
 *   npm run eval:scenario -- retry               # The same, one run, through npm
 *   npx tsx forge-eval.ts --runs 1               # Single run (fast, less reliable)
 *   npx tsx forge-eval.ts --judge                 # Enable LLM-as-judge scoring
 */

import Anthropic from "@anthropic-ai/sdk";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { parseArgs } from "util";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_PATH = join(__dirname, "..", "skills", "forge", "SKILL.md");
const MODEL = process.env.FORGE_EVAL_MODEL ?? "claude-sonnet-5";
const JUDGE_MODEL = process.env.FORGE_EVAL_JUDGE ?? "claude-sonnet-5";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Scenario {
  name: string;
  description: string;
  category: "true-positive" | "true-negative" | "adversarial" | "calibration";
  input: string;
  mustCatch: { label: string; patterns: string[] }[];
  mustNotFlag: { label: string; patterns: string[] }[];
  structuralChecks: string[];
  /** Optional LLM-as-judge rubric for subjective quality */
  judgeRubric?: string;
}

interface RunResult {
  output: string;
  truePositives: { label: string; found: boolean }[];
  falsePositives: { label: string; triggered: boolean }[];
  structural: { check: string; passed: boolean }[];
  score: number;
  totalChecks: number;
  passed: boolean;
  judgeScore?: number;
  judgeReasoning?: string;
}

interface ScenarioResult {
  scenario: string;
  category: string;
  runs: RunResult[];
  majorityPassed: boolean;
  passRate: string;
  avgJudgeScore?: number;
}

// ─── Scenarios ───────────────────────────────────────────────────────────────

const scenarios: Scenario[] = [
  // ════════════════════════════════════════════════════════════════════════════
  // TRUE POSITIVES — Forge MUST catch these issues
  // ════════════════════════════════════════════════════════════════════════════

  {
    name: "retry-reinvented",
    category: "true-positive",
    description: "Reimplements retry when p-retry exists. Must catch Prior Art + Resilience gaps.",
    input: `## Plan: Add retry logic to API client

### Task 1: Create retry utility
File: src/utils/retry.ts

\`\`\`typescript
export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelay = 1000
): Promise<T> {
  let lastError: Error;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err as Error;
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 100;
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }
  throw lastError!;
}
\`\`\`

### Task 2: Apply to all API calls
File: src/api/client.ts
- Wrap every fetch call with withRetry()
- Use default 3 retries

\`p-retry\` is already a dependency in package.json.`,
    mustCatch: [
      { label: "Prior art: p-retry or similar", patterns: ["p-retry", "library", "Prior Art"] },
      // Which calls are safe to retry is this plan's subject. A circuit breaker or timeouts are not,
      // so forge names them as unfinished rather than building them.
      { label: "Retrying every call is unsafe for non-idempotent requests or ignores 429/Retry-After", patterns: ["idempoten", "429", "retry-after", "rate limit", "(timeout|circuit).*unfinished", "unfinished.*(timeout|circuit)"] },
    ],
    mustNotFlag: [
      { label: "Should not say backoff formula is wrong", patterns: ["backoff formula is incorrect", "Math.pow is wrong"] },
    ],
    structuralChecks: ["contains a concrete rewrite", "cites specific code"],
  },

  {
    name: "god-class",
    category: "true-positive",
    description: "SessionManager with 4 responsibilities. Must catch SRP + composability.",
    input: `## Plan: SessionManager refactor
File: src/session/session-manager.ts

\`\`\`typescript
export class SessionManager {
  private sessions = new Map<string, Session>();
  private db: D1Database;
  private slackClient: SlackClient;

  // Lifecycle
  async createSession(userId: string, config: SessionConfig): Promise<Session> { ... }
  async destroySession(id: string): Promise<void> { ... }
  async hibernateSession(id: string): Promise<void> { ... }
  async resumeSession(id: string): Promise<Session> { ... }

  // Messaging
  async sendMessage(sessionId: string, message: string): Promise<void> { ... }
  async handleIncomingMessage(sessionId: string, payload: SlackPayload): Promise<void> { ... }
  async broadcastToThread(sessionId: string, blocks: Block[]): Promise<void> { ... }

  // Persistence
  async persistToD1(session: Session): Promise<void> { ... }
  async loadFromD1(id: string): Promise<Session> { ... }
  async archiveSession(id: string): Promise<void> { ... }

  // Analytics
  async trackUsage(sessionId: string, tokens: number, cost: number): Promise<void> { ... }
  async getUsageReport(userId: string): Promise<UsageReport> { ... }
}
\`\`\``,
    mustCatch: [
      { label: "SRP violation", patterns: ["responsibilit", "concern", "SRP", "god class", "conflat", "split", "separate"] },
      { label: "Should suggest splitting", patterns: ["split", "separate class", "module", "composab"] },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite", "proposes concrete split"],
  },

  {
    name: "missed-dry",
    category: "true-positive",
    description: "Two near-identical validation functions. Must catch DRY + Prior Art.",
    input: `## Plan: Input validation for API endpoints

### Task 1: Validate create session request
File: src/api/handlers/create-session.ts
\`\`\`typescript
function validateCreateRequest(body: unknown): CreateSessionInput {
  if (!body || typeof body !== 'object') throw new HttpError(400, 'Invalid body');
  const b = body as Record<string, unknown>;
  if (!b.userId || typeof b.userId !== 'string') throw new HttpError(400, 'userId required');
  if (!b.provider || typeof b.provider !== 'string') throw new HttpError(400, 'provider required');
  if (b.config && typeof b.config !== 'object') throw new HttpError(400, 'config must be object');
  return { userId: b.userId, provider: b.provider, config: b.config as SessionConfig | undefined };
}
\`\`\`

### Task 2: Validate update session request
File: src/api/handlers/update-session.ts
\`\`\`typescript
function validateUpdateRequest(body: unknown): UpdateSessionInput {
  if (!body || typeof body !== 'object') throw new HttpError(400, 'Invalid body');
  const b = body as Record<string, unknown>;
  if (!b.sessionId || typeof b.sessionId !== 'string') throw new HttpError(400, 'sessionId required');
  if (!b.provider || typeof b.provider !== 'string') throw new HttpError(400, 'provider required');
  if (b.config && typeof b.config !== 'object') throw new HttpError(400, 'config must be object');
  return { sessionId: b.sessionId, provider: b.provider, config: b.config as SessionConfig | undefined };
}
\`\`\``,
    mustCatch: [
      { label: "DRY violation", patterns: ["DRY", "duplicat", "identical", "shared", "reuse", "schema", "zod"] },
      { label: "Prior Art: validation library", patterns: ["zod", "valibot", "typebox", "schema", "validation library"] },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
  },

  {
    name: "wrong-abstraction",
    category: "true-positive",
    description: "Sandi Metz's 'wrong abstraction' — shared function with behavioral flags. Must catch.",
    input: `## Plan: Unified user action handler

File: src/actions/process-user-action.ts
\`\`\`typescript
export async function processUserAction(
  type: 'signup' | 'invite' | 'password-reset' | 'deactivate',
  email: string,
  opts: {
    rateLimit?: boolean;
    audit?: boolean;
    skipNotification?: boolean;
    customTemplate?: string;
    inviterId?: string;
    deactivateReason?: string;
  } = {}
): Promise<ActionResult> {
  if (opts.rateLimit) await checkRateLimit(email);

  if (type === 'signup') {
    const user = await createUser(email);
    if (!opts.skipNotification) await sendEmail(email, opts.customTemplate || 'welcome');
    return { userId: user.id, action: 'signup' };
  }

  if (type === 'invite') {
    if (!opts.inviterId) throw new Error('inviterId required for invite');
    await createInvite(email, opts.inviterId);
    if (opts.audit) await auditLog('invite', { inviterId: opts.inviterId, email });
    if (!opts.skipNotification) await sendEmail(email, 'invite');
    return { action: 'invite' };
  }

  if (type === 'password-reset') {
    const token = await createResetToken(email);
    await sendEmail(email, 'reset', { token });
    return { action: 'reset' };
  }

  if (type === 'deactivate') {
    await deactivateUser(email, opts.deactivateReason);
    if (opts.audit) await auditLog('deactivate', { email, reason: opts.deactivateReason });
    return { action: 'deactivate' };
  }

  throw new Error(\`Unknown action: \${type}\`);
}
\`\`\`

This replaces four separate handler functions with one unified function.`,
    mustCatch: [
      {
        label: "Wrong abstraction: behavioral flags / options bag anti-pattern",
        patterns: ["wrong abstraction", "flag", "option", "switch", "routing", "dispatch", "conditional", "separate function"],
      },
      {
        label: "Simplicity: function is a routing switchboard",
        patterns: ["switch", "routing", "dispatch", "branch", "if.*type", "complex", "responsibilit"],
      },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
    judgeRubric: "Does the response identify that this 'shared' function is actually four unrelated functions duct-taped together with flags? Does it recommend separate focused functions with shared primitives (validateEmail, sendEmail) instead?",
  },

  {
    name: "silent-error-swallowing",
    category: "true-positive",
    description: "Catch blocks that silently swallow errors. Must catch resilience issue.",
    input: `## Plan: Add webhook delivery

File: src/webhooks/deliver.ts
\`\`\`typescript
export async function deliverWebhook(url: string, payload: unknown): Promise<void> {
  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    console.log('webhook failed', e);
  }
}

export async function deliverAllWebhooks(
  urls: string[],
  payload: unknown
): Promise<void> {
  for (const url of urls) {
    try {
      await deliverWebhook(url, payload);
    } catch {
      // continue to next webhook
    }
  }
}
\`\`\``,
    mustCatch: [
      { label: "Silent error swallowing", patterns: ["swallow", "silent", "ignor", "catch.*empty", "lost", "discard", "suppress"] },
      { label: "A 4xx/5xx reply counts as delivered, and the outer catch can never fire", patterns: ["res.ok", "response.ok", "non-2xx", "4xx", "5xx", "status code", "never throws", "never fire", "cannot fire", "can't fire", "unreachable"] },
    ],
    // Retries and a dead-letter queue are out of this change's scope: unfinished, not built.
    mustNotFlag: [
      { label: "Should not bolt a retry loop or queue onto delivery", patterns: ["for (let attempt", "maxretries", "p-retry(", "withretry(", "deadletterqueue"] },
    ],
    structuralChecks: ["contains a concrete rewrite"],
  },

  {
    name: "speculative-architecture",
    category: "true-positive",
    description: "Over-engineered plugin system for a single use case. Must catch YAGNI.",
    input: `## Plan: Event notification system

File: src/events/event-bus.ts
\`\`\`typescript
interface EventMiddleware<T = unknown> {
  name: string;
  priority: number;
  before?(event: T): T | Promise<T>;
  after?(event: T, result: unknown): void | Promise<void>;
}

interface EventHandler<T = unknown> {
  handle(event: T): Promise<unknown>;
}

interface EventSerializer<T = unknown> {
  serialize(event: T): string;
  deserialize(data: string): T;
}

class EventBus {
  private handlers = new Map<string, EventHandler[]>();
  private middleware: EventMiddleware[] = [];
  private serializers = new Map<string, EventSerializer>();
  private plugins: EventPlugin[] = [];

  use(middleware: EventMiddleware): void { /* ... */ }
  registerPlugin(plugin: EventPlugin): void { /* ... */ }
  registerSerializer(eventType: string, serializer: EventSerializer): void { /* ... */ }
  on<T>(eventType: string, handler: EventHandler<T>): void { /* ... */ }
  emit<T>(eventType: string, event: T): Promise<void> { /* ... */ }
  // ... 150 more lines of registration, ordering, error handling
}
\`\`\`

### Only use case so far:
\`\`\`typescript
// When a user signs up, send a welcome email
eventBus.on('user.signup', new WelcomeEmailHandler());
\`\`\``,
    mustCatch: [
      { label: "YAGNI: over-engineered for single use case", patterns: ["YAGNI", "over-engineer", "single use", "one use", "premature", "speculative", "no second consumer", "one consumer"] },
      { label: "Simplicity: just call the function directly", patterns: ["direct", "simple", "just call", "function call", "straightforward"] },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
    judgeRubric: "Does the response recognize that an event bus with middleware, plugins, and serializers is massive over-engineering for 'send welcome email on signup'? Does it recommend starting with a direct function call and extracting patterns only when actual complexity demands it?",
  },

  // ════════════════════════════════════════════════════════════════════════════
  // TRUE NEGATIVES — Clean code forge should NOT over-critique
  // ════════════════════════════════════════════════════════════════════════════

  {
    name: "good-design",
    category: "true-negative",
    description: "Clean focused module. Should be left essentially alone; at most raise the hardcoded pricing.",
    input: `## Plan: Token cost calculator
File: src/billing/token-cost.ts

\`\`\`typescript
/** Per-model pricing in USD per 1M tokens */
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  "claude-sonnet-5": { input: 3.0, output: 15.0 },
  "claude-haiku-4-5-20251001": { input: 1.0, output: 5.0 },
  "claude-opus-4-20250514": { input: 15.0, output: 75.0 },
};

export interface TokenUsage {
  model: string;
  inputTokens: number;
  outputTokens: number;
}

export function calculateCost(usage: TokenUsage): number {
  const pricing = MODEL_PRICING[usage.model];
  if (!pricing) return 0;
  return (
    (usage.inputTokens / 1_000_000) * pricing.input +
    (usage.outputTokens / 1_000_000) * pricing.output
  );
}

export function totalCost(usages: TokenUsage[]): number {
  return usages.reduce((sum, u) => sum + calculateCost(u), 0);
}
\`\`\``,
    mustCatch: [
      { label: "Hardcoded pricing should be configurable", patterns: ["hardcod", "config", "stale", "update", "pricing.*change", "fetch", "environment"] },
    ],
    mustNotFlag: [
      { label: "Should not call it over-engineered", patterns: ["over-engineer", "too complex for what it does", "unnecessary abstraction that should be removed"] },
    ],
    structuralChecks: ["leaves sound code alone"],
  },

  {
    name: "idiomatic-code",
    category: "true-negative",
    description: "Idiomatic TypeScript patterns. Should not invent problems.",
    input: `## Plan: Request context utility
File: src/utils/context.ts

\`\`\`typescript
export type RequestContext = {
  requestId: string;
  userId: string | null;
  startedAt: number;
  metadata: Record<string, string>;
};

export function createContext(requestId: string, userId?: string): RequestContext {
  return {
    requestId,
    userId: userId ?? null,
    startedAt: Date.now(),
    metadata: {},
  };
}

export function withMetadata(ctx: RequestContext, key: string, value: string): RequestContext {
  return { ...ctx, metadata: { ...ctx.metadata, [key]: value } };
}

export function elapsed(ctx: RequestContext): number {
  return Date.now() - ctx.startedAt;
}
\`\`\``,
    mustCatch: [],
    mustNotFlag: [
      { label: "Should not demand a class for this", patterns: ["should be a class", "convert to class", "use a class instead"] },
      { label: "Should not demand interface over type", patterns: ["should use interface instead", "interface instead of type"] },
      { label: "Should not flag immutable spread as perf issue", patterns: ["performance issue with spread", "spread is slow"] },
    ],
    structuralChecks: ["leaves sound code alone"],
    judgeRubric: "Does the response respect idiomatic TypeScript patterns (type aliases, nullish coalescing, immutable spread)? Does it avoid manufacturing issues with code that is genuinely clean and focused? A good response leaves the code essentially as it is, with at most one small, concrete fix.",
  },

  // ════════════════════════════════════════════════════════════════════════════
  // ADVERSARIAL — Edge cases that test forge's calibration
  // ════════════════════════════════════════════════════════════════════════════

  {
    name: "llm-slop-abstraction",
    category: "adversarial",
    description: "LLM anti-pattern: interface-for-one-class + wrapper-that-adds-nothing. Must catch.",
    input: `## Plan: API client layer

File: src/api/interfaces.ts
\`\`\`typescript
export interface IApiClient {
  get<T>(url: string): Promise<T>;
  post<T>(url: string, data: unknown): Promise<T>;
  put<T>(url: string, data: unknown): Promise<T>;
  delete(url: string): Promise<void>;
}
\`\`\`

File: src/api/client.ts
\`\`\`typescript
import axios, { AxiosInstance } from 'axios';
import { IApiClient } from './interfaces';

export class ApiClient implements IApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string) {
    this.client = axios.create({ baseURL });
  }

  async get<T>(url: string): Promise<T> {
    const response = await this.client.get(url);
    return response.data;
  }

  async post<T>(url: string, data: unknown): Promise<T> {
    const response = await this.client.post(url, data);
    return response.data;
  }

  async put<T>(url: string, data: unknown): Promise<T> {
    const response = await this.client.put(url, data);
    return response.data;
  }

  async delete(url: string): Promise<void> {
    await this.client.delete(url);
  }
}
\`\`\`

File: src/api/user-service.ts
\`\`\`typescript
export class UserService {
  constructor(private api: IApiClient) {}

  async getUser(id: string) { return this.api.get<User>(\`/users/\${id}\`); }
  async createUser(data: CreateUserInput) { return this.api.post<User>('/users', data); }
}
\`\`\`

This is the only implementation of IApiClient in the codebase.`,
    mustCatch: [
      {
        label: "Interface for single implementation adds nothing",
        patterns: ["single implementation", "one implementation", "only implementation", "unnecessary interface", "indirection", "no second"],
      },
      {
        label: "Wrapper adds no value over using axios directly",
        patterns: ["wrapper", "pass-through", "adds nothing", "no error handling", "no retry", "no auth", "thin wrapper", "just unwrap"],
      },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
    judgeRubric: "Does the response identify both the unnecessary IApiClient interface AND the pass-through ApiClient wrapper as classic LLM-generated abstraction-for-abstraction's-sake? Does it recommend either using axios directly or adding real value (auth headers, retry, error mapping) to justify the wrapper's existence?",
  },

  {
    name: "duplicate-of-existing-helper",
    description: "A new module re-implements a helper that already exists elsewhere in the repo, with a subtly different edge case",
    category: "true-positive",
    input: `
Two files. The first already exists in the repo; the second is the new change.

// src/lib/strings.ts (existing, unchanged)
export function slugify(input: string): string {
  return input
    .normalize('NFKD')
    .replace(/[\\u0300-\\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// src/connectors/catalog.ts (new in this change)
function toSlug(name: string): string {
  // Convert the name to a URL-friendly slug
  const lowered = name.toLowerCase();
  // Replace any non-alphanumeric characters with dashes
  const dashed = lowered.replace(/[^a-z0-9]+/g, '-');
  // Trim leading and trailing dashes
  return dashed.replace(/^-+|-+$/g, '');
}

export function catalogEntry(name: string, category: string) {
  return { id: toSlug(name), name, path: \`/connectors/\${toSlug(category)}/\${toSlug(name)}\` };
}
`,
    mustCatch: [
      { label: "reuses the existing slugify", patterns: ["slugify"] },
      { label: "notices the accent-stripping difference", patterns: ["normalize", "NFKD", "accent", "diacritic", "é"] },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
    judgeRubric: "Does forge replace toSlug with the existing slugify from src/lib/strings.ts rather than keeping a parallel helper, and before doing so state that the two differ on accented input (slugify strips diacritics via NFKD, toSlug turns them into dashes), naming which behaviour is correct instead of silently changing it? Does it delete the three restating comments? It must not extract a new shared helper, since this is the second copy, not the third.",
  },

  {
    name: "subtle-cascade-risk",
    category: "adversarial",
    description: "Looks clean but has a hidden cascade failure. Must catch the subtle resilience issue.",
    input: `## Plan: Health check endpoint

File: src/api/health.ts
\`\`\`typescript
export async function healthCheck(): Promise<HealthStatus> {
  const [db, redis, s3] = await Promise.all([
    checkDatabase(),
    checkRedis(),
    checkS3(),
  ]);

  return {
    status: db.ok && redis.ok && s3.ok ? 'healthy' : 'degraded',
    components: { db, redis, s3 },
    timestamp: Date.now(),
  };
}

async function checkDatabase(): Promise<ComponentStatus> {
  const start = Date.now();
  await db.query('SELECT 1');
  return { ok: true, latencyMs: Date.now() - start };
}

async function checkRedis(): Promise<ComponentStatus> {
  const start = Date.now();
  await redis.ping();
  return { ok: true, latencyMs: Date.now() - start };
}

async function checkS3(): Promise<ComponentStatus> {
  const start = Date.now();
  await s3.headBucket({ Bucket: process.env.S3_BUCKET! });
  return { ok: true, latencyMs: Date.now() - start };
}
\`\`\``,
    mustCatch: [
      {
        label: "No timeouts on health checks — a slow dependency hangs the health endpoint",
        patterns: ["timeout", "hang", "slow", "block", "deadline", "Promise.race"],
      },
      {
        label: "No individual try/catch — one failure rejects all via Promise.all",
        patterns: ["Promise.all", "reject", "catch", "allSettled", "individual", "fail.*all"],
      },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
    judgeRubric: "Does the response catch that (1) no timeouts means a hung DB connection blocks the health endpoint itself, and (2) Promise.all rejects on ANY failure so a Redis blip makes the entire health check throw instead of returning degraded status? These are classic cascade failure patterns from 'Release It!'",
  },

  // ════════════════════════════════════════════════════════════════════════════
  // AI SLOP — Agent-written diffs. Forge must catch the slop and spare the
  // legitimate boundary code that slop imitates.
  // ════════════════════════════════════════════════════════════════════════════

  {
    name: "deslop-diff",
    category: "true-positive",
    description: "Agent-written diff with comment slop, defensive overkill, log-and-rethrow, as-any, a compat shim, and async-without-await. Must catch all of it.",
    input: `## Diff: Add invoice total helper
File: src/billing/invoice.ts (rest of the file has no comments and no try/catch). \`calculateInvoiceTotal\` is new in this diff. Its only callers are \`renderInvoice\` and \`sendInvoiceEmail\` in this same file; both \`await\` it and pass an \`Invoice\` built from typed fields with no cast, and nothing else imports it.

\`\`\`typescript
+import { formatCurrency } from './format';
+import { logger } from '../logger';
+import { round } from '../utils/math';
+
+/**
+ * Calculates the total for an invoice.
+ * @param invoice - The invoice to calculate the total for
+ * @returns The total amount
+ */
+export async function calculateInvoiceTotal(invoice: Invoice): Promise<number> {
+  // Step 1: Validate the input
+  if (!invoice) {
+    throw new Error('Invoice is required');
+  }
+  if (!invoice.lines || !Array.isArray(invoice.lines)) {
+    return 0;
+  }
+  try {
+    // Step 2: Sum up all the line items
+    let total = 0;
+    for (const line of invoice.lines) {
+      // Add the line amount to the total
+      total += (line as any).amount ?? 0;
+    }
+    // Step 3: Apply the tax rate to ensure robust and accurate calculation
+    const withTax = round(total * (1 + invoice.taxRate));
+    logger.info('Calculated invoice total', { withTax });
+    return withTax;
+  } catch (error) {
+    logger.error('Error calculating invoice total', error);
+    throw error;
+  }
+}
+
+// Keep the old name for backwards compatibility
+export const getInvoiceTotal = calculateInvoiceTotal;
\`\`\`

\`Invoice\` is defined as \`{ id: string; lines: InvoiceLine[]; taxRate: number }\` and \`InvoiceLine\` as \`{ amount: number }\`. \`getInvoiceTotal\` never existed before this diff.`,
    mustCatch: [
      { label: "Comment slop: restating / step-numbered / JSDoc that repeats the signature", patterns: ["restat", "step 1", "step-number", "narrat", "comment slop", "jsdoc", "redundant comment"] },
      { label: "Defensive overkill on values the type already guarantees", patterns: ["defensive", "already guarantee", "type system", "trusted", "cannot be null", "non-null", "unnecessary check", "never undefined"] },
      { label: "Log-and-rethrow try/catch adds nothing", patterns: ["rethrow", "re-throw", "log.*throw", "logs and", "try/catch adds", "remove the try"] },
      { label: "as any hides a real shape mismatch", patterns: ["as any", "escape hatch", "cast"] },
      { label: "Compat shim nobody asked for", patterns: ["compat", "backward", "alias", "shim", "getInvoiceTotal", "never existed"] },
      // Dropping async changes an exported signature, so reporting it as unfinished passes too.
      { label: "async without await", patterns: ["async.*await", "no await", "without await", "needlessly async", "doesn't await", "async.*unfinished", "unfinished.*async"] },
      { label: "Silent fallback (return 0) is a fail, not a flag", patterns: ["return 0", "silent", "mask", "hides", "fallback"] },
    ],
    mustNotFlag: [
      { label: "Should not demand a class or interface for a 10-line function", patterns: ["should be a class", "extract an interface", "InvoiceCalculator interface"] },
    ],
    structuralChecks: ["contains a concrete rewrite", "cites specific code"],
    judgeRubric: "Does the response identify this as an agent-written diff that does not match its surroundings (no comments or try/catch elsewhere in the file), and list the slop concretely: JSDoc restating the signature, Step 1/2/3 comments, the null and Array.isArray checks on a typed non-null Invoice, the log-and-rethrow, the `as any`, the leftover logger.info, the needless async, and the backwards-compat alias for a name that never existed? The checks may go because the callers are named and typed. Dropping `async` changes an exported signature, so either dropping it with the two callers updated or keeping it and reporting it as unfinished is right. Does it treat the silent `return 0` as a behaviour-changing fail rather than a style flag? Does it return the rewritten code with the rest of that slop deleted?",
  },

  {
    name: "boundary-code-not-slop",
    category: "true-negative",
    description: "Boundary validation, error mapping, and a genuinely useful comment. Must NOT be flagged as slop.",
    input: `## Diff: Stripe webhook handler
File: src/webhooks/stripe.ts (other handlers in this directory use the same zod + mapError pattern)

\`\`\`typescript
+const eventSchema = z.object({
+  id: z.string(),
+  type: z.literal('invoice.paid'),
+  data: z.object({ object: z.object({ id: z.string(), amount_paid: z.number() }) }),
+});
+
+export async function handleStripeWebhook(req: Request): Promise<Response> {
+  const parsed = eventSchema.safeParse(await req.json());
+  if (!parsed.success) return new Response('bad payload', { status: 400 });
+
+  // Stripe redelivers the same event on any non-2xx, so a retry after a
+  // partial failure would double-credit — dedupe on event id before writing.
+  if (await events.seen(parsed.data.id)) return new Response('ok');
+
+  try {
+    await ledger.credit(parsed.data.data.object.id, parsed.data.data.object.amount_paid);
+  } catch (err) {
+    throw mapLedgerError(err);
+  }
+  await events.markSeen(parsed.data.id);
+  return new Response('ok');
+}
\`\`\``,
    mustCatch: [],
    mustNotFlag: [
      { label: "Should not call boundary validation defensive overkill", patterns: ["defensive overkill", "unnecessary validation", "remove the schema", "over-validat", "validation is slop"] },
      { label: "Should not call the error mapping a purposeless try/catch", patterns: ["purposeless try", "remove the try/catch", "try/catch adds nothing", "log-and-rethrow"] },
      { label: "Should not call the idempotency comment slop", patterns: ["delete the comment", "remove the comment", "comment restates", "comment slop"] },
    ],
    structuralChecks: ["leaves sound code alone"],
    judgeRubric: "Does the response recognise that schema validation at an HTTP boundary, a try/catch that maps a library error into a domain error, and a comment explaining a non-obvious redelivery invariant are exactly the legitimate patterns AI slop imitates — and leave them alone? A good response keeps all three, and at most raises the ordering of markSeen versus credit.",
  },

  {
    name: "test-slop",
    category: "adversarial",
    description: "Tests that mock the unit under test, assert toBeDefined, and mirror the implementation. Must catch as test slop that cannot fail.",
    input: `## Diff: Tests for the discount calculator
File: src/pricing/discount.test.ts

\`\`\`typescript
+import { applyDiscount } from './discount';
+
+jest.mock('./discount', () => ({
+  applyDiscount: jest.fn((price: number, pct: number) => price - price * pct),
+}));
+
+describe('applyDiscount', () => {
+  it('should be defined', () => {
+    expect(applyDiscount).toBeDefined();
+  });
+
+  it('should apply a 10% discount', () => {
+    const result = applyDiscount(100, 0.1);
+    expect(result).toBeTruthy();
+  });
+
+  it('should apply a 20% discount', () => {
+    const result = applyDiscount(100, 0.2);
+    expect(result).toBeTruthy();
+  });
+
+  it('should not throw', () => {
+    expect(() => applyDiscount(100, 0.5)).not.toThrow();
+  });
+});
\`\`\`

The real \`applyDiscount\` clamps pct to [0, 1] and rounds to cents; none of that is exercised.`,
    mustCatch: [
      { label: "Mocks the unit under test", patterns: ["mock.*under test", "mocking the", "mocks the function", "jest.mock", "never runs the real", "only the mock"] },
      { label: "Assertions that cannot fail", patterns: ["cannot fail", "can't fail", "toBeDefined", "toBeTruthy", "tautolog", "always pass", "not.toThrow"] },
      { label: "Mutation check / behaviour not stated", patterns: ["mutation", "flip", "would still pass", "clamp", "round", "actual value", "toBe(90)", "assert the value"] },
    ],
    mustNotFlag: [],
    structuralChecks: ["contains a concrete rewrite"],
    judgeRubric: "Does the response recognise that these tests exercise a mock rather than applyDiscount, that toBeDefined/toBeTruthy/not.toThrow can never fail, and that the clamp and rounding behaviour is untested — and treat it as slop to rewrite rather than a style note? Does it write concrete replacement assertions (e.g. expect(applyDiscount(100, 0.1)).toBe(90)) and removing the jest.mock?",
  },
];

// ─── Pattern Matching ────────────────────────────────────────────────────────

function checkPatternMatch(output: string, patterns: string[]): boolean {
  const lower = output.toLowerCase();
  return patterns.some((p) => {
    if (p.includes(".*")) return new RegExp(p, "i").test(output);
    return lower.includes(p.toLowerCase());
  });
}

function checkStructural(output: string, check: string): boolean {
  const lower = output.toLowerCase();
  switch (check) {
    case "contains a concrete rewrite":
      return output.includes("```") && /\b(delet|remov|inlin|replac|renam|collaps|reus|cut|drop|merg|extract|mov)\w*|\bgone\b/i.test(output);
    case "cites specific code":
      return lower.includes("```") || lower.includes("withretry") || lower.includes("file:") || lower.includes(".ts");
    case "proposes concrete split":
      return (lower.includes("split") || lower.includes("separate")) &&
        (lower.includes("class") || lower.includes("module") || lower.includes("interface"));
    case "leaves sound code alone": {
      const saysSound = /\b(no changes?|nothing to (change|remove)|leave (it|this|as)|already (clean|simple|idiomatic|sound|in good shape)|is fine|sound as|(almost|essentially) (exactly )?as (written|it (is|was))|as you wrote it|left (it|the rest) alone)\b/i.test(output);
      const codeBlocks = (output.match(/```/g) ?? []).length / 2;
      return saysSound && codeBlocks <= 1;
    }
    default:
      return false;
  }
}

// ─── LLM-as-Judge ────────────────────────────────────────────────────────────

async function judgeOutput(
  client: Anthropic,
  scenario: Scenario,
  forgeOutput: string
): Promise<{ score: number; reasoning: string }> {
  const response = await client.messages.create({
    model: JUDGE_MODEL,
    max_tokens: 1024,
    system: `You are a senior software architect evaluating the quality of a code design review.

Score the review from 1-5 on this rubric:
- 1: Missed critical issues OR manufactured fake problems
- 2: Caught some issues but missed important ones, or flagged irrelevant things
- 3: Adequate — caught main issues but lacked depth or specificity
- 4: Good — caught all important issues with specific, actionable fixes
- 5: Excellent — caught all issues, fixes are specific and cite real patterns/libraries, calibrated severity correctly

IMPORTANT: First, independently analyze what the correct findings should be for the code. Then compare against the review output. Then score. Do not let verbose or confident-sounding text inflate your score.`,
    messages: [
      {
        role: "user",
        content: `## Code Being Reviewed
${scenario.input}

## Review Criteria
${scenario.judgeRubric}

## Review Output to Judge
${forgeOutput}

Respond in exactly this format:
REASONING: [your analysis in 2-3 sentences]
SCORE: [1-5]`,
      },
    ],
  });

  const text = response.content[0].type === "text" ? response.content[0].text : "";
  const scoreMatch = text.match(/SCORE:\s*(\d)/);
  const reasoningMatch = text.match(/REASONING:\s*(.*?)(?=\nSCORE:|$)/s);

  return {
    score: scoreMatch ? parseInt(scoreMatch[1]) : 0,
    reasoning: reasoningMatch ? reasoningMatch[1].trim() : text,
  };
}

// ─── Runner ──────────────────────────────────────────────────────────────────

async function runOnce(
  client: Anthropic,
  skill: string,
  scenario: Scenario,
  useJudge: boolean
): Promise<RunResult> {
  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    system: `You are an expert software architect. You have been given a skill to follow.

<skill>
${skill}
</skill>

Apply this skill to the user's input. Follow the skill instructions exactly. There is no repository: the user's message is everything you have, and any code in it is the code to forge.`,
    messages: [{ role: "user", content: `forge this:\n${scenario.input}` }],
  });

  const output = response.content[0].type === "text" ? response.content[0].text : "";

  const truePositives = scenario.mustCatch.map((tc) => ({
    label: tc.label,
    found: checkPatternMatch(output, tc.patterns),
  }));

  const falsePositives = scenario.mustNotFlag.map((tn) => ({
    label: tn.label,
    triggered: checkPatternMatch(output, tn.patterns),
  }));

  const structural = scenario.structuralChecks.map((check) => ({
    check,
    passed: checkStructural(output, check),
  }));

  const tpScore = truePositives.filter((t) => t.found).length;
  const fpScore = falsePositives.filter((f) => !f.triggered).length;
  const structScore = structural.filter((s) => s.passed).length;
  const totalChecks = truePositives.length + falsePositives.length + structural.length;
  const score = tpScore + fpScore + structScore;

  let judgeScore: number | undefined;
  let judgeReasoning: string | undefined;

  if (useJudge && scenario.judgeRubric) {
    const judge = await judgeOutput(client, scenario, output);
    judgeScore = judge.score;
    judgeReasoning = judge.reasoning;
  }

  return {
    output,
    truePositives,
    falsePositives,
    structural,
    score,
    totalChecks,
    passed: score === totalChecks,
    judgeScore,
    judgeReasoning,
  };
}

async function runScenario(
  client: Anthropic,
  skill: string,
  scenario: Scenario,
  numRuns: number,
  useJudge: boolean
): Promise<ScenarioResult> {
  const runs: RunResult[] = [];

  for (let i = 0; i < numRuns; i++) {
    if (numRuns > 1) process.stdout.write(`  Run ${i + 1}/${numRuns}...`);
    const result = await runOnce(client, skill, scenario, useJudge);
    runs.push(result);
    if (numRuns > 1) console.log(` ${result.passed ? "✓" : "✗"} (${result.score}/${result.totalChecks})`);
  }

  // Majority vote: pass if more than half of runs pass
  const passCount = runs.filter((r) => r.passed).length;
  const majorityPassed = passCount > numRuns / 2;

  const judgeScores = runs.map((r) => r.judgeScore).filter((s): s is number => s !== undefined);
  const avgJudgeScore = judgeScores.length > 0
    ? judgeScores.reduce((a, b) => a + b, 0) / judgeScores.length
    : undefined;

  return {
    scenario: scenario.name,
    category: scenario.category,
    runs,
    majorityPassed,
    passRate: `${passCount}/${numRuns}`,
    avgJudgeScore,
  };
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  // Arguments first, so a typo fails before anything needs an API key.
  const args = (() => {
    try {
      return parseArgs({
        options: { scenario: { type: "string" }, runs: { type: "string", default: "3" }, judge: { type: "boolean", default: false } },
      }).values;
    } catch (err) {
      console.error(`${(err as Error).message}\nusage: forge-eval.ts [--scenario <name>] [--runs <n>] [--judge]  (npm: npm run eval:scenario -- <name>)`);
      process.exit(1);
    }
  })();
  const scenarioFilter = args.scenario;
  const numRuns = Number(args.runs);
  if (!Number.isInteger(numRuns) || numRuns < 1) {
    console.error(`--runs must be a positive integer, got ${args.runs}`);
    process.exit(1);
  }
  const useJudge = args.judge;

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    console.error("ANTHROPIC_API_KEY required");
    process.exit(1);
  }

  const client = new Anthropic({ apiKey });
  const skill = readFileSync(SKILL_PATH, "utf-8");

  const toRun = scenarioFilter
    ? scenarios.filter((s) => s.name.includes(scenarioFilter))
    : scenarios;

  if (toRun.length === 0) {
    console.error(`No scenarios match: ${scenarioFilter}`);
    process.exit(1);
  }

  const totalApiCalls = toRun.length * numRuns + (useJudge ? toRun.filter((s) => s.judgeRubric).length * numRuns : 0);

  console.log(`\n╔══ Forge Skill Eval v2 ═══════════════════════════════════════╗`);
  console.log(`║  Scenarios: ${String(toRun.length).padEnd(2)}  │  Runs: ${String(numRuns).padEnd(1)}x  │  Judge: ${useJudge ? "ON " : "OFF"}  │  Model: ${MODEL.slice(0, 20)}  ║`);
  console.log(`║  API calls: ~${String(totalApiCalls).padEnd(3)} │  Est. time: ~${Math.ceil(totalApiCalls * 8 / 60)}min${" ".repeat(25)}║`);
  console.log(`╚══════════════════════════════════════════════════════════════════╝`);

  const results: ScenarioResult[] = [];

  // Group by category for cleaner output
  const categories = ["true-positive", "true-negative", "adversarial", "calibration"] as const;

  for (const cat of categories) {
    const catScenarios = toRun.filter((s) => s.category === cat);
    if (catScenarios.length === 0) continue;

    console.log(`\n── ${cat.toUpperCase()} ${"─".repeat(50 - cat.length)}`);

    for (const scenario of catScenarios) {
      console.log(`\n  ${scenario.name} — ${scenario.description}`);
      const result = await runScenario(client, skill, scenario, numRuns, useJudge);
      results.push(result);
    }
  }

  // ── Results ──
  console.log(`\n${"═".repeat(66)}`);
  console.log("RESULTS\n");

  let totalScenarios = 0;
  let passedScenarios = 0;
  const judgeScores: number[] = [];

  for (const cat of categories) {
    const catResults = results.filter((r) => r.category === cat);
    if (catResults.length === 0) continue;

    console.log(`── ${cat.toUpperCase()} ──`);

    for (const r of catResults) {
      totalScenarios++;
      if (r.majorityPassed) passedScenarios++;

      const icon = r.majorityPassed ? "✅" : "❌";
      const judge = r.avgJudgeScore !== undefined ? ` │ Judge: ${r.avgJudgeScore.toFixed(1)}/5` : "";
      console.log(`${icon} ${r.scenario} (${r.passRate} runs passed${judge})`);

      // Show detailed checks from the best (or worst) run
      const detailRun = r.runs[0];
      for (const tp of detailRun.truePositives) {
        console.log(`   ${tp.found ? "✓" : "✗"} Must catch: ${tp.label}`);
      }
      for (const fp of detailRun.falsePositives) {
        console.log(`   ${!fp.triggered ? "✓" : "✗"} Must NOT flag: ${fp.label}`);
      }
      for (const s of detailRun.structural) {
        console.log(`   ${s.passed ? "✓" : "✗"} Structure: ${s.check}`);
      }
      if (detailRun.judgeReasoning) {
        console.log(`   Judge: ${detailRun.judgeReasoning.slice(0, 120)}`);
      }
      console.log();

      if (r.avgJudgeScore !== undefined) judgeScores.push(r.avgJudgeScore);
    }
  }

  // ── Summary ──
  const passRate = Math.round((passedScenarios / totalScenarios) * 100);
  const avgJudge = judgeScores.length > 0
    ? (judgeScores.reduce((a, b) => a + b, 0) / judgeScores.length).toFixed(1)
    : "N/A";

  console.log(`${"─".repeat(66)}`);
  console.log(`Scenarios: ${passedScenarios}/${totalScenarios} passed (${passRate}%)`);
  if (judgeScores.length > 0) console.log(`Judge avg: ${avgJudge}/5`);

  // Statistical confidence (only meaningful with 3+ runs)
  if (numRuns >= 3) {
    const runPassRates = results.map((r) => {
      const passes = r.runs.filter((run) => run.passed).length;
      return passes / r.runs.length;
    });
    const mean = runPassRates.reduce((a, b) => a + b, 0) / runPassRates.length;
    const variance = runPassRates.reduce((sum, r) => sum + (r - mean) ** 2, 0) / runPassRates.length;
    const sem = Math.sqrt(variance / runPassRates.length);
    const ci95 = 1.96 * sem;
    console.log(`Pass rate: ${(mean * 100).toFixed(0)}% ± ${(ci95 * 100).toFixed(0)}% (95% CI)`);
  }

  const allPass = results.every((r) => r.majorityPassed);
  console.log(`\nVerdict: ${allPass ? "ALL PASS ✅" : "ISSUES FOUND ❌"}\n`);

  process.exit(allPass ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
