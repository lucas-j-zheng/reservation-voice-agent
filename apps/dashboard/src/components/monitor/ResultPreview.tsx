"use client";

import type { CascadeEvent } from "@/lib/cascade-simulator";

export default function ResultPreview({
  events,
  requestType,
}: {
  events: CascadeEvent[];
  requestType: string;
}) {
  const successEvents = events.filter((e) => e.event === "call_completed_success" || e.event === "restaurant_succeeded");

  if (successEvents.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
      <h3 className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">Results</h3>
      <div className="space-y-3">
        {successEvents.map((e, i) => (
          <div key={i} className="p-3 rounded-lg bg-green-50 border border-green-200">
            <div className="font-medium text-sm text-green-800 mb-1">
              {e.restaurant_name}
            </div>
            <div className="text-sm space-y-0.5">
              {requestType === "reservation" && e.data && (
                <>
                  {e.data.confirmation_code && (
                    <div>Confirmation: <span className="font-mono font-medium">{String(e.data.confirmation_code)}</span></div>
                  )}
                  {e.data.confirmed_time && <div>Time: {String(e.data.confirmed_time)}</div>}
                </>
              )}
              {requestType === "info_query" && e.data && (
                <>
                  {e.data.hours && <div>Hours: {String(e.data.hours)}</div>}
                  {e.data.wait_time && <div>Wait: {String(e.data.wait_time)}</div>}
                </>
              )}
              {requestType === "event_inquiry" && e.data && (
                <>
                  {e.data.available !== undefined && <div>Available: {e.data.available ? "Yes" : "No"}</div>}
                  {e.data.quoted_price && <div>Price: {String(e.data.quoted_price)}</div>}
                  {e.data.capacity && <div>Capacity: {String(e.data.capacity)}</div>}
                </>
              )}
              {requestType === "cancellation" && e.data && (
                <>
                  {e.data.confirmed !== undefined && <div>Cancelled: {e.data.confirmed ? "Yes" : "No"}</div>}
                  {e.data.cancellation_code && (
                    <div>Code: <span className="font-mono">{String(e.data.cancellation_code)}</span></div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
