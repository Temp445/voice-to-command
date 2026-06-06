import { useState, useEffect, useCallback } from "react";
import { useCommandStore } from "@/store/commandStore";

export interface SuggestionsResponse {
  domain: string;
  suggestions: string[];
}

export function useSuggestions(limit: number = 4) {
  const [data, setData] = useState<SuggestionsResponse>({ domain: "desktop", suggestions: [] });
  const [loading, setLoading] = useState(false);
  const history = useCommandStore((s) => s.history);

  const fetchSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/commands/suggestions?limit=${limit}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error("Failed to fetch command suggestions:", err);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  // Initial fetch
  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  // Re-fetch whenever a command is executed
  useEffect(() => {
    fetchSuggestions();
  }, [history, fetchSuggestions]);

  return { ...data, loading, refresh: fetchSuggestions };
}
