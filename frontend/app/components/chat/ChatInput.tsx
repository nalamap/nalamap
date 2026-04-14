"use client";

import { ArrowUp, X } from "lucide-react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel?: (e: React.FormEvent) => void;
  isStreaming?: boolean;
  placeholder?: string;
  disabled?: boolean;
}

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  onCancel,
  isStreaming = false,
  placeholder = "Type your message...",
  disabled = false,
}: ChatInputProps) {
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    // Auto-resize the textarea
    e.target.style.height = "auto";
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e);
    }
  };

  return (
    <form onSubmit={isStreaming ? onCancel : onSubmit} className="relative">
      <textarea
        value={value}
        onChange={handleTextareaChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || isStreaming}
        className="obsidian-textarea overflow-hidden pr-14 text-base"
        style={{ minHeight: "56px", maxHeight: "200px" }}
        rows={1}
      />
      {isStreaming ? (
        <button
          type="submit"
          onClick={onCancel}
          className="obsidian-button-danger absolute right-3 bottom-3 h-10 w-10 rounded-full p-0"
          title="Cancel request"
        >
          <X size={20} />
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="obsidian-button-primary absolute right-3 bottom-3 h-10 w-10 rounded-full p-0 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Send message"
        >
          <ArrowUp size={20} />
        </button>
      )}
    </form>
  );
}
