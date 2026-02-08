"use client";

import type { RequestType } from "@sam/api-contracts";

const TYPES: { value: RequestType; label: string; description: string; icon: string }[] = [
  {
    value: "reservation",
    label: "Make a Reservation",
    description: "Book a table at one or more restaurants",
    icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  },
  {
    value: "info_query",
    label: "Ask a Question",
    description: "Get hours, menu, dietary options, and more",
    icon: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    value: "event_inquiry",
    label: "Plan an Event",
    description: "Inquire about event space, catering, or parties",
    icon: "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
  },
  {
    value: "cancellation",
    label: "Cancel a Reservation",
    description: "Cancel an existing confirmed reservation",
    icon: "M6 18L18 6M6 6l12 12",
  },
];

export default function RequestTypeSelector({
  selected,
  onSelect,
}: {
  selected: RequestType | null;
  onSelect: (type: RequestType) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-4">
      {TYPES.map((t) => (
        <button
          key={t.value}
          type="button"
          onClick={() => onSelect(t.value)}
          className={`p-5 rounded-xl border-2 text-left transition-all ${
            selected === t.value
              ? "border-[var(--color-primary)] bg-blue-50"
              : "border-[var(--color-border)] bg-white hover:border-gray-300"
          }`}
        >
          <div className="flex items-start gap-3">
            <svg
              className={`w-6 h-6 mt-0.5 shrink-0 ${
                selected === t.value ? "text-[var(--color-primary)]" : "text-[var(--color-text-secondary)]"
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d={t.icon} />
            </svg>
            <div>
              <div className="font-semibold">{t.label}</div>
              <div className="text-sm text-[var(--color-text-secondary)] mt-1">
                {t.description}
              </div>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
