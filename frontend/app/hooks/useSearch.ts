// hooks/useSearch.ts
"use client";

import { useState } from "react";

export function useSearch(apiUrl: string) {
  const [input, setInput] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/search?query=${encodeURIComponent(input)}`);
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      // Expecting the response to be a JSON array of search objects.
      const data = await response.json();
      setSearchResults(data.results);
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, searchResults, loading, error, search };
}
