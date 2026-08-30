/**
 * DeepSeek Vision Tool
 *
 * 注册一个 `vision` 工具，让 pi 具备图片理解能力。
 * 通过 DeepSeek 的 deepseek-v4-flash-vision-exp 模型分析图片。
 *
 * 文档: https://api-docs.deepseek.com/zh-cn/guides/vision
 *
 * 依赖环境变量: DEEPSEEK_API_KEY
 *
 * 用法（由 LLM 自动调用，也可在提示中明确要求）:
 *   "看看 logs/character_sprite_sheet.png 里有什么"
 */

import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API_URL = "https://api.deepseek.com/chat/completions";
const MODEL = "deepseek-v4-flash-vision-exp";

/** 通过文件魔数判断真实图片格式（不看扩展名）。 */
function detectMime(buf: Buffer): string {
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) {
    return "image/jpeg";
  }
  if (
    buf.length >= 8 &&
    buf[0] === 0x89 &&
    buf[1] === 0x50 &&
    buf[2] === 0x4e &&
    buf[3] === 0x47 &&
    buf[4] === 0x0d &&
    buf[5] === 0x0a &&
    buf[6] === 0x1a &&
    buf[7] === 0x0a
  ) {
    return "image/png";
  }
  if (buf.length >= 6 && buf[0] === 0x47 && buf[1] === 0x49 && buf[2] === 0x46) {
    return "image/gif";
  }
  if (
    buf.length >= 12 &&
    buf.toString("ascii", 0, 4) === "RIFF" &&
    buf.toString("ascii", 8, 12) === "WEBP"
  ) {
    return "image/webp";
  }
  return "image/jpeg"; // 兜底，服务端按实际内容判断
}

const visionTool = defineTool({
  name: "vision",
  label: "Vision",
  description:
    "Analyze an image using the DeepSeek vision model (deepseek-v4-flash-vision-exp). " +
    "Use this whenever you need to understand an image file: describe it, read text (OCR), " +
    "analyze charts/diagrams/screenshots, identify characters/objects, etc. " +
    "Accepts a local file path or a public http(s) URL.",
  parameters: Type.Object({
    image: Type.String({
      description: "Local image file path (e.g. logs/a.png) or a public http(s) URL.",
    }),
    question: Type.Optional(
      Type.String({
        description:
          "What to ask about the image. Defaults to a general description of its content.",
      }),
    ),
    detail: Type.Optional(
      Type.Enum({
        low: "low",
        high: "high",
        original: "original",
        auto: "auto",
      }),
    ),
  }),

  async execute(_toolCallId, params, signal, _onUpdate, _ctx) {
    const apiKey = process.env.DEEPSEEK_API_KEY;
    if (!apiKey) {
      return {
        content: [
          {
            type: "text",
            text: "缺少 DEEPSEEK_API_KEY 环境变量，无法调用视觉模型。请在环境中设置后重试。",
          },
        ],
        details: { error: "missing_api_key" },
        isError: true,
      };
    }

    const question = params.question?.trim() || "请描述这张图片的内容。";
    const detail = params.detail ?? "auto";

    // 构造 image_url：本地路径 -> base64 data URL；http(s) -> 直接透传
    let imageUrl: string;
    if (/^https?:\/\//i.test(params.image)) {
      imageUrl = params.image;
    } else {
      const buf = readFileSync(params.image);
      const mime = detectMime(buf);
      const b64 = buf.toString("base64");
      imageUrl = `data:${mime};base64,${b64}`;
    }

    const payload = {
      model: MODEL,
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: question },
            { type: "image_url", image_url: { url: imageUrl, detail } },
          ],
        },
      ],
    };

    const resp = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (!resp.ok) {
      const errText = await resp.text().catch(() => "");
      return {
        content: [
          {
            type: "text",
            text: `DeepSeek 视觉 API 返回错误 ${resp.status}: ${errText.slice(0, 1000)}`,
          },
        ],
        details: { status: resp.status },
        isError: true,
      };
    }

    const data = (await resp.json()) as {
      choices?: Array<{ message?: { content?: string; reasoning_content?: string } }>;
      usage?: Record<string, unknown>;
    };

    const msg = data.choices?.[0]?.message;
    const text = msg?.content?.trim() ?? "(模型未返回文本内容)";

    return {
      content: [{ type: "text", text }],
      details: {
        model: MODEL,
        source: basename(params.image),
        usage: data.usage,
      },
    };
  },
});

export default function (pi: ExtensionAPI) {
  pi.registerTool(visionTool);
}
