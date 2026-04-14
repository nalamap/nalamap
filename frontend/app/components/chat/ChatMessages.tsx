"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { hashString } from "../../utils/hashUtil";

// Helper function to extract text content from message content
const extractTextContent = (content: any): string => {
  if (typeof content === "string") {
    return content;
  }

  if (Array.isArray(content)) {
    return content
      .filter((block) => block.type === "text")
      .map((block) => block.text || "")
      .join("\n");
  }

  return String(content);
};

interface ChatMessagesProps {
  conversation: any[];
  loading: boolean;
  showToolMessages?: boolean;
  expandedToolMessage?: Record<number, boolean>;
  onToggleToolMessage?: (idx: number) => void;
  disableAutoScroll?: boolean;
}

export default function ChatMessages({
  conversation,
  loading,
  showToolMessages = false,
  expandedToolMessage = {},
  onToggleToolMessage,
  disableAutoScroll = false,
  scrollToBottom,
}: ChatMessagesProps & { scrollToBottom?: () => void }) {

  // Auto-scroll to bottom with new entry, unless scroll is locked
  useEffect(() => {
    if (!disableAutoScroll && scrollToBottom) {
      scrollToBottom();
    }
  }, [conversation, loading, disableAutoScroll, scrollToBottom]);

  return (
    <div className="flex-1 pb-2">
      <div className="flex flex-col space-y-3">
        {conversation.map((msg, idx) => {
          const msgKey =
            msg.id?.trim() || hashString(`${idx}:${msg.type}:${msg.content}`);

          // Handle AI message that kicked off a tool call
          if (
            msg.type === "ai" &&
            msg.additional_kwargs?.tool_calls?.length
          ) {
            if (!showToolMessages) return null;

            const call = msg.additional_kwargs.tool_calls[0];
            const isOpen = !!expandedToolMessage[idx];

            return (
              <div key={msgKey} className="flex justify-start">
                <div className="obsidian-message obsidian-message-ai">
                  <div className="text-sm font-medium">
                    Using tool '{call.function.name}' with arguments '{" "}
                    {call.function.arguments}'
                  </div>

                  <button
                    className="obsidian-button-primary ml-2 mt-2 px-2 py-1 text-xs"
                    onClick={() => onToggleToolMessage?.(idx)}
                  >
                    {isOpen ? "Hide result" : "Show result"}
                  </button>

                  {isOpen && conversation[idx + 1]?.type === "tool" && (
                    <div className="mt-2 text-sm break-words whitespace-pre-wrap obsidian-muted">
                      {conversation[idx + 1].content}
                    </div>
                  )}
                </div>
              </div>
            );
          }

          // Don't render standalone tool messages
          if (msg.type === "tool") {
            return null;
          }

          // Render human/AI messages
          const isHuman = msg.type === "human";
          return (
            <div
              key={msgKey}
              className={`flex ${isHuman ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`obsidian-message ${
                  isHuman ? "obsidian-message-human text-right" : "obsidian-message-ai"
                }`}
              >
                {isHuman ? (
                  <div className="text-sm break-words">
                    {extractTextContent(msg.content)}
                  </div>
                ) : (
                  <div className="chat-markdown text-sm break-words">
                    <ReactMarkdown>
                      {extractTextContent(msg.content)}
                    </ReactMarkdown>
                  </div>
                )}
                <div className="obsidian-message-meta">
                  {isHuman ? "You" : msg.type === "ai" ? "Agent" : "Unknown"}
                </div>
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex justify-start mb-2">
            <div className="obsidian-message obsidian-message-ai flex items-center space-x-2">
              <Loader2 size={16} className="animate-spin text-second-primary-600" />
              <span className="text-sm">
                NaLaMap Agent is working on your request...
              </span>
            </div>
          </div>
        )}
        
      </div>
    </div>
  );
}
