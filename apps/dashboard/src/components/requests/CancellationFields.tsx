"use client";

import { useEffect, useState } from "react";
import type { Reservation } from "@sam/api-contracts";
import { formatDate, formatTime } from "@/lib/utils";

export type CancellationFormData = {
  reservation_id: string;
  reason: string;
};

export default function CancellationFields({
  data,
  onChange,
  onRestaurantResolved,
}: {
  data: CancellationFormData;
  onChange: (data: CancellationFormData) => void;
  onRestaurantResolved: (restaurantId: string | null) => void;
}) {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/reservations?status=confirmed");
        if (res.ok) setReservations(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleSelect(reservationId: string) {
    onChange({ ...data, reservation_id: reservationId });
    const rez = reservations.find((r) => r.id === reservationId);
    onRestaurantResolved(rez?.restaurant_id ?? null);
  }

  if (loading) {
    return <div className="text-[var(--color-text-secondary)] py-4">Loading reservations...</div>;
  }

  if (reservations.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm">
        No confirmed reservations to cancel.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-2">Select Reservation to Cancel *</label>
        <div className="space-y-2">
          {reservations.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => handleSelect(r.id)}
              className={`w-full p-3 rounded-lg border-2 text-left transition-all ${
                data.reservation_id === r.id
                  ? "border-red-400 bg-red-50"
                  : "border-[var(--color-border)] bg-white hover:border-gray-300"
              }`}
            >
              <div className="font-medium">{r.restaurant_name}</div>
              <div className="text-sm text-[var(--color-text-secondary)]">
                {formatDate(r.confirmed_date)} at {formatTime(r.confirmed_time)} &middot; Party of {r.party_size}
                {r.confirmation_code && ` &middot; ${r.confirmation_code}`}
              </div>
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Reason</label>
        <textarea
          value={data.reason}
          onChange={(e) => onChange({ ...data, reason: e.target.value })}
          rows={2}
          placeholder="Optional reason for cancellation"
          className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
        />
      </div>
    </div>
  );
}
