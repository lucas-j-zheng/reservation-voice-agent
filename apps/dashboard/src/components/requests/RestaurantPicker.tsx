"use client";

import { useEffect, useState, useCallback } from "react";
import type { Restaurant } from "@sam/api-contracts";

export default function RestaurantPicker({
  selectedIds,
  onChange,
  disabled,
}: {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
}) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/restaurants");
        if (res.ok) setRestaurants(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const toggleRestaurant = useCallback(
    (id: string) => {
      if (disabled) return;
      if (selectedIds.includes(id)) {
        onChange(selectedIds.filter((s) => s !== id));
      } else {
        onChange([...selectedIds, id]);
      }
    },
    [selectedIds, onChange, disabled]
  );

  const moveUp = useCallback(
    (index: number) => {
      if (index === 0) return;
      const next = [...selectedIds];
      [next[index - 1], next[index]] = [next[index], next[index - 1]];
      onChange(next);
    },
    [selectedIds, onChange]
  );

  const moveDown = useCallback(
    (index: number) => {
      if (index === selectedIds.length - 1) return;
      const next = [...selectedIds];
      [next[index], next[index + 1]] = [next[index + 1], next[index]];
      onChange(next);
    },
    [selectedIds, onChange]
  );

  if (loading) {
    return <div className="text-[var(--color-text-secondary)] py-4">Loading restaurants...</div>;
  }

  if (restaurants.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm">
        No restaurants yet. <a href="/restaurants" className="underline">Add some first.</a>
      </div>
    );
  }

  const selectedRestaurants = selectedIds
    .map((id) => restaurants.find((r) => r.id === id))
    .filter(Boolean) as Restaurant[];

  const unselected = restaurants.filter((r) => !selectedIds.includes(r.id));

  return (
    <div className="space-y-4">
      {/* Selected - ordered list with priority controls */}
      {selectedRestaurants.length > 0 && (
        <div>
          <label className="block text-sm font-medium mb-2">
            Priority Order ({selectedRestaurants.length} selected)
          </label>
          <div className="space-y-1">
            {selectedRestaurants.map((r, i) => (
              <div
                key={r.id}
                className="flex items-center gap-2 p-3 rounded-lg border-2 border-[var(--color-primary)] bg-blue-50"
              >
                <span className="w-6 h-6 rounded-full bg-[var(--color-primary)] text-white text-xs flex items-center justify-center shrink-0">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{r.name}</div>
                  <div className="text-xs text-[var(--color-text-secondary)] truncate">
                    {r.cuisine_type && `${r.cuisine_type} · `}{r.phone}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => moveUp(i)}
                    disabled={i === 0}
                    className="p-1 rounded hover:bg-blue-100 disabled:opacity-30"
                    title="Move up"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={() => moveDown(i)}
                    disabled={i === selectedRestaurants.length - 1}
                    className="p-1 rounded hover:bg-blue-100 disabled:opacity-30"
                    title="Move down"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleRestaurant(r.id)}
                    className="p-1 rounded hover:bg-red-100 text-red-500"
                    title="Remove"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available restaurants */}
      {unselected.length > 0 && (
        <div>
          <label className="block text-sm font-medium mb-2">
            {selectedIds.length > 0 ? "Add more restaurants" : "Select restaurants *"}
          </label>
          <div className="space-y-1">
            {unselected.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => toggleRestaurant(r.id)}
                disabled={disabled}
                className="w-full flex items-center gap-3 p-3 rounded-lg border border-[var(--color-border)] bg-white hover:border-gray-300 text-left transition-colors disabled:opacity-50"
              >
                <svg className="w-5 h-5 text-[var(--color-text-secondary)] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{r.name}</div>
                  <div className="text-xs text-[var(--color-text-secondary)] truncate">
                    {r.cuisine_type && `${r.cuisine_type} · `}{r.phone}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
