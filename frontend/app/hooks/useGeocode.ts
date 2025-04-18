// hooks/useGeocode.ts
"use client";

import { useState } from "react";

export function useGeocode(apiUrl: string) {
  const [geocodeInput, setGeocodeInput] = useState("");
  const [geocodeResults, setGeocodeResults] = useState<any[]>([]);
  const [geocodeLoading, setGeocodeLoading] = useState(false);
  const [geocodeError, setGeocodeError] = useState("");

  async function geocode() {
    setGeocodeLoading(true);
    setGeocodeError("");
    try {
      const response = await fetch(`${apiUrl}/geocode?query=${encodeURIComponent(geocodeInput)}`);
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      // Expecting the response to be a JSON array of geocode objects.
      const data = await response.json();
      setGeocodeResults(data.results);
    } catch (err: any) {
      setGeocodeError(err.message || "Something went wrong");
    } finally {
      setGeocodeLoading(false);
    }
  }

  return { geocodeInput, setGeocodeInput, geocodeResults, geocodeLoading, geocodeError, geocode };
}
