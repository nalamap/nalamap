import React, { useState } from 'react';

interface SearchResult {
  id: number;
  source_type: string;
  access_url: string;
  llm_description: string;
  bounding_box: string;
  score: number;
}

interface BackendResponse {
  query: string;
  results: SearchResult[];
}

interface SearchPromptProps {
  // Optional callback to pass the results to the parent component
  onResults?: (results: SearchResult[]) => void;
}

const SearchPrompt: React.FC<SearchPromptProps> = ({ onResults }) => {
  const [inputValue, setInputValue] = useState<string>('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Update the input state as the user types
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  // Base URL for your FastAPI backend
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api';

  // Handle form submission and API call
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmedValue = inputValue.trim();
    if (!trimmedValue) return;

    setLoading(true);
    setError(null);

    try {
      // TODO: move into api.tsx
      const response = await fetch(`${API_BASE_URL}/search/?query=${encodeURIComponent(trimmedValue)}`);
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      const data: BackendResponse = await response.json();
      setResults(data.results);
      if (onResults) {
        onResults(data.results);
      }
    } catch (err) {
      console.error(err);
      setError('Failed to fetch results. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          placeholder="Type your question here..."
          style={{ padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}
        />
        <button
          type="submit"
          style={{
            padding: '10px 20px',
            borderRadius: '4px',
            border: 'none',
            backgroundColor: '#007bff',
            color: '#fff',
            cursor: 'pointer'
          }}
        >
          Submit
        </button>
      </form>

      {loading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {/* Display results if available */}
      {results.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          {results.map((result) => (
            <div key={result.id} style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '10px' }}>
              <h2>{result.source_type}</h2>
              <p>{result.llm_description}</p>
              <a href={result.access_url} target="_blank" rel="noopener noreferrer">
                View Data
              </a>
              <p><strong>Score:</strong> {result.score}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchPrompt;
