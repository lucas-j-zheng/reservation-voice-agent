"use client";

import { formatDateTime } from "@/lib/utils";

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

function BooleanTags({ data, label }: { data: Record<string, boolean> | null; label: string }) {
  if (!data) return null;
  const truthy = Object.entries(data).filter(([, v]) => v).map(([k]) => k);
  if (truthy.length === 0) return null;
  return (
    <div>
      <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">{label}</span>
      <div className="flex flex-wrap gap-1 mt-1">
        {truthy.map((k) => (
          <span key={k} className="px-2 py-0.5 rounded bg-green-100 text-green-800 text-xs">
            {k.replace(/_/g, " ")}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function InfoResultCard({ result }: { result: InfoResultWithRestaurant }) {
  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold">{result.restaurants?.name ?? "Unknown Restaurant"}</h3>
          <div className="text-xs text-[var(--color-text-secondary)]">
            {result.restaurants?.cuisine_type && `${result.restaurants.cuisine_type} · `}
            {formatDateTime(result.created_at)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        {result.operating_hours && (
          <div>
            <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">Hours</span>
            <div>{result.operating_hours}</div>
          </div>
        )}
        {result.wait_time_minutes != null && (
          <div>
            <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">Wait Time</span>
            <div>{result.wait_time_minutes} min</div>
          </div>
        )}
        {result.pricing_info && (
          <div>
            <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">Pricing</span>
            <div>{result.pricing_info}</div>
          </div>
        )}
        {result.menu_highlights && (
          <div className="col-span-2">
            <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">Menu Highlights</span>
            <div>{result.menu_highlights}</div>
          </div>
        )}
        {result.allergen_info && (
          <div className="col-span-2">
            <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">Allergen Info</span>
            <div>{result.allergen_info}</div>
          </div>
        )}
      </div>

      <div className="mt-3 space-y-2">
        <BooleanTags data={result.dietary_options} label="Dietary Options" />
        <BooleanTags data={result.facilities} label="Facilities" />
      </div>

      {result.raw_notes && (
        <div className="mt-3 text-sm">
          <span className="text-[var(--color-text-secondary)] text-xs uppercase tracking-wide">Notes</span>
          <div className="mt-1 text-[var(--color-text-secondary)]">{result.raw_notes}</div>
        </div>
      )}
    </div>
  );
}
