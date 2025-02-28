// SearchContext.tsx
import React, { createContext, useContext, useState , ReactNode} from 'react';

export type LayerType = 'geojson' | 'png';

export interface SearchResult {
    id: number;
    source_type: string;
    access_url: string;
    llm_description: string;
    bounding_box: string;
    score: number;
  }
  

interface SearchContextValue {
  selectedResult: SearchResult | null;
  setSelectedResult: (result: SearchResult) => void;
}

const SearchContext = createContext<SearchContextValue | undefined>(undefined);

export const SearchProvider = ({ children }: {children: ReactNode }) => {
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);
  return (
    <SearchContext.Provider value={{ selectedResult, setSelectedResult }}>
      {children}
    </SearchContext.Provider>
  );
};

export const useSearch = () => {
  const context = useContext(SearchContext);
  if (!context) throw new Error("useSearch must be used within a SearchProvider");
  return context;
};
