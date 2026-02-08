"use client";

import Link from "next/link";
import { formatDateTime } from "@/lib/utils";
import { REQUEST_STATUS_COLORS, REQUEST_STATUS_LABELS } from "@/lib/constants";

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

const TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  reservation: { label: "Reservation", icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z", color: "text-blue-600" },
  info_query: { label: "Info Query", icon: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "text-purple-600" },
  event_inquiry: { label: "Event Inquiry", icon: "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z", color: "text-amber-600" },
  cancellation: { label: "Cancellation", icon: "M6 18L18 6M6 6l12 12", color: "text-red-500" },
};

export default function RequestCard({ request }: { request: RequestWithRestaurants }) {
  const config = TYPE_CONFIG[request.type] ?? TYPE_CONFIG.reservation;
  const restaurants = (request.request_restaurants || [])
    .sort((a, b) => a.priority - b.priority)
    .map((rr) => rr.restaurants?.name)
    .filter(Boolean);

  return (
    <Link
      href={`/monitor?request_id=${request.id}`}
      className="flex items-start gap-4 p-4 bg-white rounded-xl border border-[var(--color-border)] hover:border-gray-300 transition-colors"
    >
      <svg
        className={`w-5 h-5 mt-0.5 shrink-0 ${config.color}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d={config.icon} />
      </svg>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="font-medium text-sm">{config.label}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${REQUEST_STATUS_COLORS[request.status] ?? "bg-gray-100"}`}>
            {REQUEST_STATUS_LABELS[request.status] ?? request.status}
          </span>
        </div>
        {restaurants.length > 0 && (
          <div className="text-sm text-[var(--color-text-secondary)] truncate">
            {restaurants.join(", ")}
          </div>
        )}
        <div className="text-xs text-[var(--color-text-secondary)] mt-1">
          {formatDateTime(request.created_at)}
        </div>
      </div>
    </Link>
  );
}
