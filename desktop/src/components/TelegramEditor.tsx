import { useEffect, useRef } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import { Spoiler } from "../lib/tiptap-spoiler";
import {
  tiptapToTelegramHtml,
  telegramHtmlToEditorHtml,
} from "../lib/tiptap-telegram-html";

interface TelegramEditorProps {
  content: string;
  onChange: (html: string) => void;
  readOnly?: boolean;
  dir?: "rtl" | "ltr";
  rows?: number;
}

const ToolbarBtn = ({
  active,
  onClick,
  children,
  disabled,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) => (
  <button
    type="button"
    onMouseDown={(e) => {
      e.preventDefault();
      onClick();
    }}
    disabled={disabled}
    className={`rounded px-2 py-1 text-xs font-semibold transition-colors ${
      active
        ? "bg-[var(--accent-blue)] text-white"
        : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
    } disabled:pointer-events-none disabled:opacity-40`}
  >
    {children}
  </button>
);

export function TelegramEditor({
  content,
  onChange,
  readOnly = false,
  dir = "ltr",
  rows = 6,
}: TelegramEditorProps) {
  // Track whether the latest content change came from the editor itself
  // (user typing) vs an external source (template applied, message switch).
  const isInternalChange = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        bulletList: false,
        orderedList: false,
        blockquote: false,
        horizontalRule: false,
        codeBlock: false,
      }),
      Underline,
      Link.configure({ openOnClick: false }),
      Spoiler,
    ],
    content: telegramHtmlToEditorHtml(content),
    editable: !readOnly,
    onUpdate: ({ editor: e }) => {
      isInternalChange.current = true;
      onChange(tiptapToTelegramHtml(e));
    },
  });

  // Sync readOnly
  useEffect(() => {
    editor?.setEditable(!readOnly);
  }, [editor, readOnly]);

  // Sync external content changes (template applied, message switched).
  // Skip when the content change originated from the editor's own onUpdate
  // (user typing) to avoid resetting cursor position.
  useEffect(() => {
    if (!editor) return;
    if (isInternalChange.current) {
      isInternalChange.current = false;
      return;
    }
    editor.commands.setContent(telegramHtmlToEditorHtml(content), { emitUpdate: false });
  }, [editor, content]);

  if (!editor) return null;

  const minHeight = `${rows * 1.5}em`;

  return (
    <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] focus-within:border-[var(--accent-blue)]">
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex flex-wrap gap-0.5 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1">
          <ToolbarBtn active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}>
            B
          </ToolbarBtn>
          <ToolbarBtn active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}>
            I
          </ToolbarBtn>
          <ToolbarBtn active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()}>
            U
          </ToolbarBtn>
          <ToolbarBtn active={editor.isActive("strike")} onClick={() => editor.chain().focus().toggleStrike().run()}>
            S
          </ToolbarBtn>
          <ToolbarBtn active={editor.isActive("code")} onClick={() => editor.chain().focus().toggleCode().run()}>
            {"</>"}
          </ToolbarBtn>
          <ToolbarBtn
            active={editor.isActive("link")}
            onClick={() => {
              if (editor.isActive("link")) {
                editor.chain().focus().unsetLink().run();
                return;
              }
              const url = window.prompt("URL:");
              if (url) {
                editor.chain().focus().setLink({ href: url }).run();
              }
            }}
          >
            Link
          </ToolbarBtn>
          <ToolbarBtn
            active={editor.isActive("spoiler")}
            onClick={() => editor.chain().focus().toggleSpoiler().run()}
          >
            Spoiler
          </ToolbarBtn>
        </div>
      )}

      {/* Editor area */}
      <div dir={dir} className="px-4 py-3 text-sm leading-relaxed" style={{ minHeight }}>
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
