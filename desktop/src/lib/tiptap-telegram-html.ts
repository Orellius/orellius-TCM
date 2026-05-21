import type { Editor } from "@tiptap/core";
import type { Node, Mark } from "@tiptap/pm/model";

// ── Telegram HTML ← Tiptap editor ────────────────────────

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function markTag(mark: Mark): { open: string; close: string } | null {
  switch (mark.type.name) {
    case "bold":
      return { open: "<b>", close: "</b>" };
    case "italic":
      return { open: "<i>", close: "</i>" };
    case "underline":
      return { open: "<u>", close: "</u>" };
    case "strike":
      return { open: "<s>", close: "</s>" };
    case "code":
      return { open: "<code>", close: "</code>" };
    case "link":
      return {
        open: `<a href="${escapeHtml(mark.attrs.href ?? "")}">`,
        close: "</a>",
      };
    case "spoiler":
      return { open: "<tg-spoiler>", close: "</tg-spoiler>" };
    default:
      return null;
  }
}

function serializeNode(node: Node): string {
  if (node.isText) {
    let text = escapeHtml(node.text ?? "");
    const marks = node.marks ?? [];
    for (const mark of marks) {
      const tag = markTag(mark);
      if (tag) {
        text = tag.open + text + tag.close;
      }
    }
    return text;
  }

  if (node.type.name === "hardBreak") return "\n";

  let inner = "";
  node.forEach((child) => {
    inner += serializeNode(child);
  });

  if (node.type.name === "codeBlock") {
    return `<pre>${inner}</pre>`;
  }

  if (node.type.name === "paragraph") {
    return inner;
  }

  return inner;
}

export function tiptapToTelegramHtml(editor: Editor): string {
  const doc = editor.state.doc;
  const blocks: string[] = [];
  doc.forEach((node) => {
    blocks.push(serializeNode(node));
  });
  return blocks.join("\n\n");
}

// ── Editor HTML ← Telegram HTML ──────────────────────────

export function telegramHtmlToEditorHtml(html: string): string {
  // Convert <tg-spoiler> to <span data-spoiler> for Tiptap parsing
  const processed = html
    .replace(/<tg-spoiler>/g, '<span data-spoiler>')
    .replace(/<\/tg-spoiler>/g, "</span>");

  // If already wrapped in <p> tags (e.g. from a TipTap round-trip), pass through
  if (/<p[\s>]/i.test(processed)) return processed;

  // Split on double-newlines (paragraph breaks). Single newlines within a
  // paragraph become <br> so they don't each produce a full <p> with margins.
  const paragraphs = processed.split(/\n{2,}/);
  return paragraphs
    .map((para) => {
      const trimmed = para.trim();
      if (!trimmed) return "<p><br></p>";
      const content = trimmed.replace(/\n/g, "<br>");
      return `<p>${content}</p>`;
    })
    .join("");
}

// ── Detection helper ─────────────────────────────────────

const HTML_TAG_RE = /<\/?(b|i|u|s|code|pre|a|tg-spoiler)[\s>]/i;

export function hasTelegramHtml(text: string): boolean {
  return HTML_TAG_RE.test(text);
}
