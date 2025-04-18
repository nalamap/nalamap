// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";

export function useGeoweaverAgent(apiUrl: string) {
  const [input, setInput] = useState("");
  const [geoweaverAgentResults, setGeoweaverAgentResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function queryGeoweaverAgent(endpoint: string = "search") {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/${endpoint}?query=${encodeURIComponent(input)}`);
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      // Expecting the response to be a JSON array of search objects.
      const data = await response.json();
      // TODO: Handle different result data
      setGeoweaverAgentResults(data.results);
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, geoweaverAgentResults, loading, error, queryGeoweaverAgent };
}
