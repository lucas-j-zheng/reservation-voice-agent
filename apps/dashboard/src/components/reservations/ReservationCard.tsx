"use client";

import type { Reservation } from "@sam/api-contracts";
import { formatDate, formatTime } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-600",
  completed: "bg-blue-100 text-blue-800",
  no_show: "bg-red-100 text-red-700",
};

export default function ReservationCard({
  reservation,
  onCancel,
}: {
  reservation: Reservation;
  onCancel?: (id: string) => void;
}) {
  const isUpcoming = reservation.status === "confirmed" &&
    new Date(`${reservation.confirmed_date}T${reservation.confirmed_time}`) > new Date();

  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold">{reservation.restaurant_name}</h3>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[reservation.status] ?? "bg-gray-100"}`}>
              {reservation.status}
            </span>
          </div>
          <div className="text-sm text-[var(--color-text-secondary)] space-y-0.5">
            <div>{formatDate(reservation.confirmed_date)} at {formatTime(reservation.confirmed_time)}</div>
            <div>Party of {reservation.party_size}</div>
            {reservation.confirmation_code && (
              <div>Confirmation: <span className="font-mono font-medium">{reservation.confirmation_code}</span></div>
            )}
            {reservation.notes && <div className="mt-1">{reservation.notes}</div>}
          </div>
        </div>
        {isUpcoming && onCancel && (
          <button
            onClick={() => onCancel(reservation.id)}
            className="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
