"use client";

export type ReservationFormData = {
  party_size: number;
  requested_date: string;
  time_range_start: string;
  time_range_end: string;
  special_requests: string;
  contact_phone: string;
};

const INPUT = "w-full px-3 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]";

export default function ReservationFields({
  data,
  onChange,
}: {
  data: ReservationFormData;
  onChange: (data: ReservationFormData) => void;
}) {
  function set<K extends keyof ReservationFormData>(key: K, value: ReservationFormData[K]) {
    onChange({ ...data, [key]: value });
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Date *</label>
          <input
            type="date"
            required
            value={data.requested_date}
            onChange={(e) => set("requested_date", e.target.value)}
            className={INPUT}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Party Size *</label>
          <input
            type="number"
            required
            min={1}
            max={20}
            value={data.party_size || ""}
            onChange={(e) => set("party_size", parseInt(e.target.value) || 0)}
            className={INPUT}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Earliest Time *</label>
          <input
            type="time"
            required
            value={data.time_range_start}
            onChange={(e) => set("time_range_start", e.target.value)}
            className={INPUT}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Latest Time *</label>
          <input
            type="time"
            required
            value={data.time_range_end}
            onChange={(e) => set("time_range_end", e.target.value)}
            className={INPUT}
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Special Requests</label>
        <textarea
          value={data.special_requests}
          onChange={(e) => set("special_requests", e.target.value)}
          rows={2}
          placeholder="Outdoor seating, high chair, etc."
          className={INPUT}
        />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Contact Phone</label>
        <input
          type="tel"
          value={data.contact_phone}
          onChange={(e) => set("contact_phone", e.target.value)}
          placeholder="For callback if needed"
          className={INPUT}
        />
      </div>
    </div>
  );
}
