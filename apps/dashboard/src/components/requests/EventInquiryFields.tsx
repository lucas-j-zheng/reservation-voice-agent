"use client";

import { EVENT_TYPES } from "@/lib/constants";

export type EventInquiryFormData = {
  event_type: string;
  party_size: number;
  preferred_date: string;
  budget_range: string;
  details: string;
};

const INPUT = "w-full px-3 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]";

export default function EventInquiryFields({
  data,
  onChange,
}: {
  data: EventInquiryFormData;
  onChange: (data: EventInquiryFormData) => void;
}) {
  function set<K extends keyof EventInquiryFormData>(key: K, value: EventInquiryFormData[K]) {
    onChange({ ...data, [key]: value });
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">Event Type *</label>
        <select
          required
          value={data.event_type}
          onChange={(e) => set("event_type", e.target.value)}
          className={INPUT}
        >
          <option value="">Select event type</option>
          {EVENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Party Size</label>
          <input
            type="number"
            min={1}
            value={data.party_size || ""}
            onChange={(e) => set("party_size", parseInt(e.target.value) || 0)}
            className={INPUT}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Preferred Date</label>
          <input
            type="date"
            value={data.preferred_date}
            onChange={(e) => set("preferred_date", e.target.value)}
            className={INPUT}
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Budget Range</label>
        <input
          value={data.budget_range}
          onChange={(e) => set("budget_range", e.target.value)}
          placeholder="e.g. $500-$1000"
          className={INPUT}
        />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Details</label>
        <textarea
          value={data.details}
          onChange={(e) => set("details", e.target.value)}
          rows={3}
          placeholder="Describe your event needs..."
          className={INPUT}
        />
      </div>
    </div>
  );
}
