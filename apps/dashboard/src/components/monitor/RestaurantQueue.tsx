"use client";

import type { CascadeEvent } from "@/lib/cascade-simulator";

type RestaurantStatus = "pending" | "calling" | "succeeded" | "failed" | "skipped" | "no_answer";

type QueueItem = {
  id: string;
  name: string;
  status: RestaurantStatus;
  data?: Record<string, unknown>;
};

const STATUS_STYLES: Record<RestaurantStatus, { bg: string; icon: string; label: string }> = {
  pending: { bg: "border-[var(--color-border)]", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z", label: "Waiting" },
  calling: { bg: "border-blue-400 bg-blue-50", icon: "M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z", label: "Calling" },
  succeeded: { bg: "border-green-400 bg-green-50", icon: "M5 13l4 4L19 7", label: "Success" },
  failed: { bg: "border-red-300 bg-red-50", icon: "M6 18L18 6M6 6l12 12", label: "Failed" },
  skipped: { bg: "border-gray-300 bg-gray-50", icon: "M13 5l7 7-7 7M5 5l7 7-7 7", label: "Skipped" },
  no_answer: { bg: "border-yellow-300 bg-yellow-50", icon: "M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636", label: "No Answer" },
};

export default function RestaurantQueue({
  restaurants,
  events,
}: {
  restaurants: { id: string; name: string }[];
  events: CascadeEvent[];
}) {
  // Derive status for each restaurant from events
  const queue: QueueItem[] = restaurants.map((r) => {
    let status: RestaurantStatus = "pending";
    let data: Record<string, unknown> | undefined;

    for (const e of events) {
      if (e.restaurant_id !== r.id) continue;
      switch (e.event) {
        case "calling_restaurant":
          status = "calling";
          break;
        case "call_completed_success":
          status = "succeeded";
          data = e.data;
          break;
        case "call_completed_failure":
          status = "failed";
          data = e.data;
          break;
        case "call_no_answer":
          status = "no_answer";
          break;
        case "restaurant_skipped":
          status = "skipped";
          break;
      }
    }

    return { id: r.id, name: r.name, status, data };
  });

  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
      <h3 className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">Restaurant Queue</h3>
      <div className="space-y-2">
        {queue.map((item, i) => {
          const style = STATUS_STYLES[item.status];
          return (
            <div
              key={item.id}
              className={`flex items-center gap-3 p-3 rounded-lg border-2 transition-all ${style.bg}`}
            >
              <span className="w-6 h-6 rounded-full bg-gray-200 text-gray-600 text-xs flex items-center justify-center shrink-0">
                {i + 1}
              </span>
              <svg
                className={`w-5 h-5 shrink-0 ${
                  item.status === "succeeded" ? "text-green-600" :
                  item.status === "failed" ? "text-red-500" :
                  item.status === "calling" ? "text-blue-600" :
                  "text-gray-400"
                }`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d={style.icon} />
              </svg>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{item.name}</div>
                {item.data && (
                  <div className="text-xs text-[var(--color-text-secondary)] truncate">
                    {item.status === "failed" && String(item.data.reason || "")}
                    {item.status === "succeeded" && (
                      item.data.confirmation_code
                        ? `Confirmed: ${item.data.confirmation_code}`
                        : "Info collected"
                    )}
                  </div>
                )}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${
                item.status === "calling" ? "bg-blue-100 text-blue-700" :
                item.status === "succeeded" ? "bg-green-100 text-green-700" :
                item.status === "failed" ? "bg-red-100 text-red-600" :
                "bg-gray-100 text-gray-500"
              }`}>
                {style.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
