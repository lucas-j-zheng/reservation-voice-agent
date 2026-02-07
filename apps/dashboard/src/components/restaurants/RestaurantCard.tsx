"use client";

import { useState } from "react";
import type { Restaurant } from "@sam/api-contracts";

export default function RestaurantCard({
  restaurant,
  onEdit,
  onDelete,
}: {
  restaurant: Restaurant;
  onEdit: (r: Restaurant) => void;
  onDelete: (id: string) => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!confirm(`Delete ${restaurant.name}?`)) return;
    setDeleting(true);
    try {
      const res = await fetch(`/api/restaurants/${restaurant.id}`, {
        method: "DELETE",
      });
      if (res.ok) onDelete(restaurant.id);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 flex items-start justify-between">
      <div className="min-w-0">
        <h3 className="font-semibold text-lg truncate">{restaurant.name}</h3>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          {restaurant.phone}
        </p>
        {restaurant.address && (
          <p className="text-sm text-[var(--color-text-secondary)]">
            {restaurant.address}
          </p>
        )}
        {restaurant.cuisine_type && (
          <span className="inline-block mt-2 px-2.5 py-0.5 text-xs rounded-full bg-blue-50 text-blue-700">
            {restaurant.cuisine_type}
          </span>
        )}
      </div>
      <div className="flex gap-2 shrink-0 ml-4">
        <button
          onClick={() => onEdit(restaurant)}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-lg hover:bg-gray-50"
        >
          Edit
        </button>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50"
        >
          {deleting ? "..." : "Delete"}
        </button>
      </div>
    </div>
  );
}
