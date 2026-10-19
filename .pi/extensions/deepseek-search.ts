/**
 * DeepSeek Search / Fetch Tools
 *
 * 注册两个工具，让 pi 具备实时联网检索能力：
 *   - `deepseek_search`: 按 query 搜索网页，返回结构化结果（标题、URL、摘要、正文等）。
 *   - `deepseek_fetch`:  抓取单个网页，以 Markdown 正文返回。
 *
 * 两者均由 DeepSeek 自研搜索引擎提供，使用与 DeepSeek API 相同的 Bearer 鉴权。
 *
 * 文档: https://api-docs.deepseek.com/zh-cn/guides/search/
 *
 * 依赖环境变量: DEEPSEEK_API_KEY
 *
 * 计费（按成功请求计次，与结果条数无关）:
 *   Search / Fetch 均为 5 元 / 1,000 次成功请求。
 * 限速: 每个账号 Search、Fetch 各自 5 QPS，超出返回 429。
 */

import { createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API_BASE = "https://api.deepseek.com/v1/tools";
const MAX_ATTEMPTS = 3;
const REQUEST_TIMEOUT_MS = 60_000;
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

const MAX_SEARCH_OUTPUT_CHARS = 60_000;
const MAX_SUMMARY_CHARS = 800;
const MAX_SEARCH_CONTENT_CHARS = 2_000;
const MAX_FETCH_CONTENT_CHARS = 30_000;

const NAMESPACE = {
  name: "deepseek",
  description:
    "DeepSeek 自研搜索引擎：实时网页搜索（Search）与网页正文抓取（Fetch）。",
  instructions:
    "Search 支持 site:、-site:、-、-\"...\"、\"...\"、lang:、after:、before: 等搜索语法；" +
    "需要完整网页内容时，先搜索拿到 URL，再调用 deepseek_fetch。",
} as const;

interface SearchResult {
  rerank_score?: number;
  title?: string;
  url?: string;
  snippet?: string;
  summary?: string;
  content?: string;
  site_name?: string | null;
  site_icon?: string | null;
  date?: string | null;
  authority?: number;
}

interface SearchResponse {
  results?: SearchResult[];
}

interface FetchResponse {
  title?: string;
  content?: string;
}

interface DeepSeekErrorBody {
  error?: {
    message?: string;
    type?: string;
    code?: string;
  };
}

interface SearchDetails {
  error?: string;
  status?: number;
  query?: string;
  count?: number;
  results?: Array<{
    title?: string;
    url?: string;
    site_name?: string | null;
    date?: string | null;
    rerank_score?: number;
    authority?: number;
  }>;
}

interface FetchDetails {
  error?: string;
  status?: number;
  url?: string;
  title?: string;
  chars?: number;
  truncated?: boolean;
  fullPath?: string;
}

class DeepSeekApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "DeepSeekApiError";
  }
}

const STATUS_HINTS: Record<number, string> = {
  400: "请求头或请求体不合法",
  401: "API Key 缺失或无效",
  402: "账号余额不足",
  403: "Fetch 请求被安全策略拒绝",
  404: "未能获取可用的网页内容（URL 不可用、被站点策略拦截、返回错误或无可提取正文）",
  408: "读取请求体超时",
  413: "请求体超过大小限制",
  429: "超过 QPS 限制",
  500: "服务器内部错误",
  504: "下游请求超时",
};

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

function sleep(ms: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new Error("请求已取消"));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal?.reason ?? new Error("请求已取消"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function parseErrorMessage(raw: string, status: number): string {
  let detail = raw.trim();
  try {
    const body = JSON.parse(raw) as DeepSeekErrorBody;
    if (body.error?.message) detail = body.error.message;
  } catch {
    // 非 JSON 错误体，保留原文
  }
  if (detail.length > 1_000) detail = `${detail.slice(0, 1_000)}…`;
  const hint = STATUS_HINTS[status];
  return `DeepSeek API 返回 HTTP ${status}${hint ? `（${hint}）` : ""}: ${detail || "(无错误详情)"}`;
}

/** 调用 Search / Fetch 接口；对 408/429/5xx 与网络错误做有限次退避重试。 */
async function postJson<T>(
  endpoint: "search" | "fetch",
  body: Record<string, unknown>,
  apiKey: string,
  signal: AbortSignal | undefined,
): Promise<T> {
  const url = `${API_BASE}/${endpoint}`;

  for (let attempt = 1; ; attempt++) {
    // 单次请求 60s 超时；同时响应外部取消信号。
    const controller = new AbortController();
    const timer = setTimeout(
      () => controller.abort(new Error(`请求超时（${REQUEST_TIMEOUT_MS / 1_000}s）`)),
      REQUEST_TIMEOUT_MS,
    );
    const onAbort = () => controller.abort(signal?.reason);
    signal?.addEventListener("abort", onAbort, { once: true });

    let resp: Response;
    let raw: string;
    try {
      resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      // 在超时/取消信号生效期间读完响应体。
      raw = await resp.text();
    } catch (err) {
      if (signal?.aborted) throw err; // 调用方主动取消，直接冒泡
      if (attempt >= MAX_ATTEMPTS) {
        throw new Error(
          `DeepSeek ${endpoint} 请求失败（已重试 ${MAX_ATTEMPTS} 次）: ${errorMessage(err)}`,
        );
      }
      await sleep(attempt * 1_000, signal);
      continue;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
    }

    if (resp.ok) {
      try {
        return JSON.parse(raw) as T;
      } catch {
        throw new Error(`DeepSeek ${endpoint} 返回了无法解析的 JSON: ${clip(raw, 500)}`);
      }
    }

    const message = parseErrorMessage(raw, resp.status);

    if (attempt < MAX_ATTEMPTS && RETRYABLE_STATUS.has(resp.status)) {
      const retryAfter = Number(resp.headers.get("retry-after"));
      const delayMs =
        Number.isFinite(retryAfter) && retryAfter > 0
          ? Math.min(retryAfter * 1_000, 10_000)
          : attempt * 1_000;
      await sleep(delayMs, signal);
      continue;
    }

    throw new DeepSeekApiError(message, resp.status);
  }
}

function clip(text: string, maxChars: number): string {
  const t = text.trim();
  if (t.length <= maxChars) return t;
  return `${t.slice(0, maxChars)}…（已截断，原文共 ${t.length} 字符）`;
}

function formatMeta(result: SearchResult): string {
  const meta: string[] = [];
  if (result.site_name) meta.push(`站点: ${result.site_name}`);
  if (result.date) meta.push(`发布: ${result.date}`);
  if (typeof result.authority === "number" && result.authority >= 0) {
    meta.push(`权威性: ${result.authority}/4`);
  }
  if (typeof result.rerank_score === "number") {
    meta.push(`相关度: ${result.rerank_score.toFixed(2)}`);
  }
  return meta.join(" | ");
}

function formatSearchResults(query: string, results: SearchResult[]): string {
  if (results.length === 0) {
    return `搜索 “${query}” 没有匹配结果。`;
  }

  const header = `搜索 “${query}” 返回 ${results.length} 条结果：`;
  const blocks: string[] = [];
  let used = header.length;
  let omitted = 0;

  results.forEach((result, index) => {
    const lines = [
      `${index + 1}. ${result.title?.trim() || "(无标题)"}`,
      `   URL: ${result.url ?? "(无链接)"}`,
    ];

    const meta = formatMeta(result);
    if (meta) lines.push(`   ${meta}`);

    const summary = result.summary?.trim() || result.snippet?.trim();
    if (summary) lines.push(`   摘要: ${clip(summary, MAX_SUMMARY_CHARS)}`);

    if (result.content?.trim()) {
      lines.push(`   正文: ${clip(result.content, MAX_SEARCH_CONTENT_CHARS)}`);
    }

    const block = lines.join("\n");
    if (used + block.length + 2 > MAX_SEARCH_OUTPUT_CHARS) {
      omitted++;
      return;
    }
    blocks.push(block);
    used += block.length + 2;
  });

  const parts = [header, "", blocks.join("\n\n")];
  if (omitted > 0) {
    parts.push(
      "",
      `还有 ${omitted} 条结果因长度限制未展示。可用更小的 count 或更精确的 query，` +
        `也可以直接对具体 URL 调用 deepseek_fetch。`,
    );
  }
  return parts.join("\n");
}

/** 校验 Fetch 的 URL：必须是含 host 的 HTTP/HTTPS 地址，且不能携带用户名或密码。 */
function validateFetchUrl(url: string): string | undefined {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return "url 不是合法的绝对地址。";
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "url 必须使用 http 或 https 协议。";
  }
  if (!parsed.hostname) return "url 必须包含主机名。";
  if (parsed.username || parsed.password) return "url 不能携带用户名或密码。";
  return undefined;
}

/** 正文过长时把完整 Markdown 落到临时文件，方便模型用 read/grep 继续处理。 */
function persistFullContent(url: string, content: string): string | undefined {
  try {
    const hash = createHash("sha1").update(url).digest("hex").slice(0, 12);
    const path = join(tmpdir(), `pi-deepseek-fetch-${hash}.md`);
    writeFileSync(path, content, "utf8");
    return path;
  } catch {
    return undefined;
  }
}

const searchParameters = Type.Object({
  query: Type.String({
    minLength: 1,
    maxLength: 128,
    description:
      "Search query, 1-128 characters. May combine operators such as site:, -site:, -, \"...\", " +
      "lang:, after:, before:.",
  }),
  count: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 50,
      description: "Number of results to return (1-50). Default: 10.",
    }),
  ),
  ori_question: Type.Optional(
    Type.String({
      maxLength: 128,
      description:
        "The user's original question that triggered this search (1-128 chars). " +
        "Helps the search engine understand intent.",
    }),
  ),
  localization: Type.Optional(
    Type.String({
      description:
        "IP address used to prefer localized search results (e.g. \"1.2.3.4\"). Usually omit.",
    }),
  ),
  need_content: Type.Optional(
    Type.Boolean({
      description:
        "Whether to include page body in each result's content field. Default: false. " +
        "Increases response size; use deepseek_fetch when you need one full page.",
    }),
  ),
});

const searchTool = defineTool<typeof searchParameters, SearchDetails>({
  name: "deepseek_search",
  label: "DeepSeek Search",
  description:
    "Search the live web with DeepSeek's own search engine and return structured results " +
    "(title, URL, snippet, long summary, and optionally page content). " +
    "Use it for current events, documentation, releases, prices, or any fact that may have changed. " +
    "Supports search operators in `query`: site:github.com, -site:example.com, -keyword, " +
    '-"exact phrase", "exact phrase", lang:zh,en, after:2025-01-01, before:2026-06-01. ' +
    "Results include a relevance score (rerank_score, >=1.5 is high quality) and an authority score " +
    "(authority 0-4, >=3 is highly authoritative). Set need_content=true only when you need the page " +
    "body; prefer deepseek_fetch for a specific URL.",
  parameters: searchParameters,
  annotations: { readOnlyHint: true, openWorldHint: true },
  namespace: NAMESPACE,

  async execute(_toolCallId, params, signal) {
    const apiKey = process.env.DEEPSEEK_API_KEY;
    if (!apiKey) {
      return {
        content: [
          {
            type: "text",
            text: "缺少 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek Search。请在环境中设置后重试。",
          },
        ],
        details: { error: "missing_api_key" },
        isError: true,
      };
    }

    const query = params.query.trim();
    if (!query) {
      return {
        content: [{ type: "text", text: "query 不能为空。" }],
        details: { error: "invalid_query" },
        isError: true,
      };
    }

    const body: Record<string, unknown> = { query };
    if (params.count !== undefined) body.count = params.count;
    if (params.ori_question?.trim()) body.ori_question = params.ori_question.trim();
    if (params.localization?.trim()) body.localization = params.localization.trim();
    if (params.need_content !== undefined) body.need_content = params.need_content;

    try {
      const data = await postJson<SearchResponse>("search", body, apiKey, signal);
      const results = Array.isArray(data.results) ? data.results : [];

      return {
        content: [{ type: "text", text: formatSearchResults(query, results) }],
        details: {
          query,
          count: results.length,
          results: results.map((result) => ({
            title: result.title,
            url: result.url,
            site_name: result.site_name,
            date: result.date,
            rerank_score: result.rerank_score,
            authority: result.authority,
          })),
        },
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: errorMessage(err) }],
        details: {
          error: "request_failed",
          status: err instanceof DeepSeekApiError ? err.status : undefined,
        },
        isError: true,
      };
    }
  },
});

const fetchParameters = Type.Object({
  url: Type.String({
    minLength: 1,
    maxLength: 8_192,
    description: "The HTTP/HTTPS URL to fetch. Must include a host; no username/password.",
  }),
});

const fetchTool = defineTool<typeof fetchParameters, FetchDetails>({
  name: "deepseek_fetch",
  label: "DeepSeek Fetch",
  description:
    "Fetch a single web page through DeepSeek and return its main content as Markdown " +
    "(plus the page title). Use it after deepseek_search when you need the full text of a result, " +
    "or when the user gives you a URL to read. Only HTTP/HTTPS URLs with a host are accepted. " +
    "Some sites are blocked by security policy or return no extractable content (HTTP 403/404).",
  parameters: fetchParameters,
  annotations: { readOnlyHint: true, openWorldHint: true },
  namespace: NAMESPACE,

  async execute(_toolCallId, params, signal) {
    const apiKey = process.env.DEEPSEEK_API_KEY;
    if (!apiKey) {
      return {
        content: [
          {
            type: "text",
            text: "缺少 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek Fetch。请在环境中设置后重试。",
          },
        ],
        details: { error: "missing_api_key" },
        isError: true,
      };
    }

    const url = params.url.trim();
    const invalidUrl = validateFetchUrl(url);
    if (invalidUrl) {
      return {
        content: [{ type: "text", text: invalidUrl }],
        details: { error: "invalid_url" },
        isError: true,
      };
    }

    try {
      const page = await postJson<FetchResponse>("fetch", { url }, apiKey, signal);
      const title = page.title?.trim() || "(无标题)";
      const content = page.content ?? "";

      if (!content.trim()) {
        return {
          content: [
            {
              type: "text",
              text: `已抓取 ${url}（标题: ${title}），但未返回可提取的正文内容。`,
            },
          ],
          details: { url, title, chars: 0 },
        };
      }

      let text: string;
      let fullPath: string | undefined;
      let truncated = false;

      if (content.length > MAX_FETCH_CONTENT_CHARS) {
        truncated = true;
        fullPath = persistFullContent(url, content);
        text =
          `# ${title}\n\nURL: ${url}\n\n` +
          `${content.slice(0, MAX_FETCH_CONTENT_CHARS)}\n\n` +
          `…（正文共 ${content.length} 字符，已截断）` +
          (fullPath
            ? `完整 Markdown 已保存到: ${fullPath}（可用 read/grep 继续处理）`
            : "未能保存完整正文，请缩小抓取范围后重试。");
      } else {
        text = `# ${title}\n\nURL: ${url}\n\n${content}`;
      }

      return {
        content: [{ type: "text", text }],
        details: { url, title, chars: content.length, truncated, fullPath },
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: errorMessage(err) }],
        details: {
          error: "request_failed",
          status: err instanceof DeepSeekApiError ? err.status : undefined,
        },
        isError: true,
      };
    }
  },
});

export default function (pi: ExtensionAPI) {
  pi.registerTool(searchTool);
  pi.registerTool(fetchTool);
}
