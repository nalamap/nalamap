'use client'
// app/components/ChatPrompt.tsx
import { useState } from 'react'

export interface SearchResult {
    id: number;
    source_type: string;
    access_url: string;
    llm_description: string;
    bounding_box: string;
    score: number;
  }
  
export default function ChatPrompt() {
  const [inputValue, setInputValue] = useState("")
  const [chatHistory, setChatHistory] = useState<string[]>([])
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim()) return

    // Append user's message to chat history
    setChatHistory(prev => [...prev, `User: ${inputValue}`])
    
    // Simulate an agent response (replace this with actual LLM integration)
    setTimeout(() => {
      setChatHistory(prev => [...prev, `Agent: Response to "${inputValue}"`])
    }, 500)
    
    setInputValue("")
  }

  return (
    <div className="flex flex-col h-full">
      {/* Chat history */}
      <div className="flex-1 overflow-y-auto p-2 border-b">
        {chatHistory.map((msg, idx) => (
          <div key={idx} className="mb-2 text-sm">
            {msg}
          </div>
        ))}
      </div>
      {/* Input form */}
      <form onSubmit={handleSubmit} className="p-2">
        <input
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          placeholder="Type your message..."
          className="w-full border rounded p-2 focus:outline-none focus:ring"
        />
      </form>
    </div>
  )
}
