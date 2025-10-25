"use client";

import { useEffect, useRef } from "react";
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
}

export default function ChatMessages({
  conversation,
  loading,
  showToolMessages = false,
  expandedToolMessage = {},
  onToggleToolMessage,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom with new entry
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation, loading]);

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
                <div className="max-w px-4 py-2 rounded-lg bg-primary-100 rounded-tl-none border border-primary-300">
                  <div className="text-sm font-medium text-primary-900">
                    Using tool '{call.function.name}' with arguments '{" "}
                    {call.function.arguments}'
                  </div>

                  <button
                    className="ml-2 px-2 py-1 bg-second-primary-600 text-white rounded text-xs hover:bg-second-primary-700"
                    onClick={() => onToggleToolMessage?.(idx)}
                  >
                    {isOpen ? "Hide result" : "Show result"}
                  </button>

                  {isOpen && conversation[idx + 1]?.type === "tool" && (
                    <div className="mt-2 text-sm break-words whitespace-pre-wrap text-primary-800">
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
                className={`max-w-[80%] px-4 py-2 rounded-lg ${
                  isHuman
                    ? "bg-second-primary-200 rounded-tr-none text-right border border-primary-300"
                    : "bg-neutral-50 rounded-tl-none border border-primary-200"
                }`}
              >
                {isHuman ? (
                  <div className="text-sm break-words text-primary-900">
                    {extractTextContent(msg.content)}
                  </div>
                ) : (
                  <div className="text-sm break-words chat-markdown text-primary-900">
                    <ReactMarkdown>
                      {extractTextContent(msg.content)}
                    </ReactMarkdown>
                  </div>
                )}
                <div className="text-xs text-primary-500 mt-1">
                  {isHuman ? "You" : msg.type === "ai" ? "Agent" : "Unknown"}
                </div>
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex justify-start mb-2">
            <div className="flex items-center space-x-2 max-w-[80%] px-4 py-2 rounded-lg bg-neutral-50 rounded-tl-none border border-primary-200">
              <Loader2 size={16} className="animate-spin text-second-primary-600" />
              <span className="text-sm text-primary-700">
                NaLaMap Agent is working on your request...
              </span>
            </div>
          </div>
        )}
        
        {/* Scroll target */}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
