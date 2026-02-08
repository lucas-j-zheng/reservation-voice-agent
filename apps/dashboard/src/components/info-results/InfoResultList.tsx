"use client";

import { useEffect, useState } from "react";
import InfoResultCard from "./InfoResultCard";

type InfoResultWithRestaurant = {
  id: string;
  restaurant_id: string;
  operating_hours: string | null;
  wait_time_minutes: number | null;
  menu_highlights: string | null;
  pricing_info: string | null;
  dietary_options: Record<string, boolean> | null;
  allergen_info: string | null;
  facilities: Record<string, boolean> | null;
  raw_notes: string | null;
  created_at: string;
  restaurants: { name: string; phone: string; cuisine_type: string | null } | null;
};

export default function InfoResultList() {
  const [results, setResults] = useState<InfoResultWithRestaurant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/info-results");
        if (res.ok) setResults(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-[var(--color-text-secondary)]">Loading info results...</div>;
  }

  if (results.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No info results yet. Send an info query to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {results.map((r) => (
        <InfoResultCard key={r.id} result={r} />
      ))}
    </div>
  );
}
