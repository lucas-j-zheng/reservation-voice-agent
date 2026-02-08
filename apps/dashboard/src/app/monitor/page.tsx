"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, useMemo, Suspense } from "react";
import Link from "next/link";
import CascadeMonitor from "@/components/monitor/CascadeMonitor";

type RequestData = {
  id: string;
  type: string;
  status: string;
  request_restaurants: {
    priority: number;
    restaurants: { id: string; name: string };
  }[];
};

function MonitorContent() {
  const searchParams = useSearchParams();
  const requestId = searchParams.get("request_id");
  const [request, setRequest] = useState<RequestData | null>(null);
  const [loading, setLoading] = useState(!!requestId);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!requestId) return;

    async function load() {
      try {
        const res = await fetch(`/api/requests/${requestId}`);
        if (!res.ok) throw new Error("Request not found");
        setRequest(await res.json());
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load request");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [requestId]);

  if (!requestId) {
    return (
      <div className="mt-8 bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No active request. Start one from the{" "}
        <Link href="/new-request" className="text-[var(--color-primary)] underline">
          New Request
        </Link>{" "}
        page.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-[var(--color-text-secondary)]">
        Loading request...
      </div>
    );
  }

  if (error || !request) {
    return (
      <div className="mt-8 p-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
        {error || "Request not found"}
      </div>
    );
  }

  const restaurants = useMemo(
    () =>
      (request.request_restaurants || [])
        .sort((a, b) => a.priority - b.priority)
        .map((rr) => ({
          id: rr.restaurants.id,
          name: rr.restaurants.name,
        })),
    [request]
  );

  const TYPE_LABELS: Record<string, string> = {
    reservation: "Reservation",
    info_query: "Info Query",
    event_inquiry: "Event Inquiry",
    cancellation: "Cancellation",
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
          {TYPE_LABELS[request.type] ?? request.type}
        </span>
        <span className="text-sm text-[var(--color-text-secondary)] font-mono">
          {request.id.slice(0, 8)}...
        </span>
      </div>
      <CascadeMonitor
        requestId={request.id}
        requestType={request.type}
        restaurants={restaurants}
      />
    </div>
  );
}

export default function MonitorPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Live Monitor</h1>
      <p className="text-[var(--color-text-secondary)] mb-6">
        Watch Sam work through your request in real time.
      </p>
      <Suspense fallback={<div className="text-center py-12 text-[var(--color-text-secondary)]">Loading...</div>}>
        <MonitorContent />
      </Suspense>
    </div>
  );
}
