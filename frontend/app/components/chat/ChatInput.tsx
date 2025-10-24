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
        className="w-full border border-primary-300 bg-neutral-50 rounded-lg px-4 py-3 pr-12 focus:outline-none focus:ring-2 focus:ring-secondary-300 resize-none overflow-hidden text-primary-900 text-base"
        style={{ minHeight: "56px", maxHeight: "200px" }}
        rows={1}
      />
      {isStreaming ? (
        <button
          type="submit"
          onClick={onCancel}
          className="absolute right-3 bottom-3 p-2 bg-red-600 text-white rounded-full hover:bg-red-700 transition-colors"
          title="Cancel request"
        >
          <X size={20} />
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="absolute right-3 bottom-3 p-2 bg-secondary-600 text-white rounded-full hover:bg-secondary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Send message"
        >
          <ArrowUp size={20} />
        </button>
      )}
    </form>
  );
}
