"use client";

import type { CascadeEvent } from "@/lib/cascade-simulator";

const EVENT_LABELS: Record<string, string> = {
  cascade_started: "Cascade started",
  calling_restaurant: "Calling",
  call_completed_success: "Call succeeded",
  call_completed_failure: "Call failed",
  call_no_answer: "No answer",
  restaurant_skipped: "Skipped",
  cascade_paused: "Paused",
  cascade_resumed: "Resumed",
  cascade_completed: "Completed",
  cascade_exhausted: "All restaurants tried",
  cascade_cancelled: "Cancelled",
};

const EVENT_COLORS: Record<string, string> = {
  cascade_started: "text-blue-600",
  calling_restaurant: "text-blue-600",
  call_completed_success: "text-green-600",
  call_completed_failure: "text-red-500",
  call_no_answer: "text-yellow-600",
  restaurant_skipped: "text-gray-500",
  cascade_paused: "text-yellow-600",
  cascade_resumed: "text-blue-600",
  cascade_completed: "text-green-600",
  cascade_exhausted: "text-red-500",
  cascade_cancelled: "text-gray-500",
};

function formatTimestamp(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

export default function EventLog({ events }: { events: CascadeEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
        <h3 className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">Event Log</h3>
        <p className="text-sm text-[var(--color-text-secondary)]">Waiting for events...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
      <h3 className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">Event Log</h3>
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {events.map((e, i) => (
          <div key={i} className="flex items-start gap-2 text-sm py-1">
            <span className="text-xs text-[var(--color-text-secondary)] font-mono w-20 shrink-0 pt-0.5">
              {formatTimestamp(e.timestamp)}
            </span>
            <span className={`font-medium ${EVENT_COLORS[e.event] ?? "text-gray-600"}`}>
              {EVENT_LABELS[e.event] ?? e.event}
            </span>
            {e.restaurant_name && (
              <span className="text-[var(--color-text-secondary)]">{e.restaurant_name}</span>
            )}
            {e.data?.reason ? (
              <span className="text-[var(--color-text-secondary)]">— {String(e.data.reason)}</span>
            ) : null}
            {e.data?.confirmation_code ? (
              <span className="text-green-600 font-medium">#{String(e.data.confirmation_code)}</span>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
