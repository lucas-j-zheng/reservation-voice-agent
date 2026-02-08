"use client";

import { useEffect, useState } from "react";
import RequestCard from "./RequestCard";

type RequestWithRestaurants = {
  id: string;
  type: string;
  status: string;
  created_at: string;
  request_restaurants: {
    priority: number;
    restaurants: { id: string; name: string };
  }[];
};

type Filter = "all" | "reservation" | "info_query" | "event_inquiry" | "cancellation";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "reservation", label: "Reservations" },
  { value: "info_query", label: "Info Queries" },
  { value: "event_inquiry", label: "Events" },
  { value: "cancellation", label: "Cancellations" },
];

export default function ActivityTimeline() {
  const [requests, setRequests] = useState<RequestWithRestaurants[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/requests");
        if (res.ok) setRequests(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = filter === "all" ? requests : requests.filter((r) => r.type === filter);

  if (loading) {
    return <div className="text-center py-12 text-[var(--color-text-secondary)]">Loading history...</div>;
  }

  return (
    <div>
      <div className="flex gap-1 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              filter === f.value
                ? "bg-[var(--color-primary)] text-white"
                : "bg-white border border-[var(--color-border)] hover:bg-gray-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
          No activity yet.
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((r) => (
            <RequestCard key={r.id} request={r} />
          ))}
        </div>
      )}
    </div>
  );
}
