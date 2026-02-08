"use client";

import { useEffect, useState } from "react";
import type { Reservation } from "@sam/api-contracts";
import ReservationCard from "./ReservationCard";

type Tab = "upcoming" | "past" | "cancelled";

export default function ReservationList() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("upcoming");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/reservations");
        if (res.ok) setReservations(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleCancel(id: string) {
    const res = await fetch(`/api/reservations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "cancelled" }),
    });
    if (res.ok) {
      setReservations((prev) =>
        prev.map((r) => (r.id === id ? { ...r, status: "cancelled" as const } : r))
      );
    }
  }

  const now = new Date();
  const filtered = reservations.filter((r) => {
    const dt = new Date(`${r.confirmed_date}T${r.confirmed_time}`);
    switch (tab) {
      case "upcoming":
        return r.status === "confirmed" && dt > now;
      case "past":
        return r.status === "completed" || (r.status === "confirmed" && dt <= now);
      case "cancelled":
        return r.status === "cancelled" || r.status === "no_show";
    }
  });

  if (loading) {
    return <div className="text-center py-12 text-[var(--color-text-secondary)]">Loading reservations...</div>;
  }

  const TABS: { value: Tab; label: string }[] = [
    { value: "upcoming", label: "Upcoming" },
    { value: "past", label: "Past" },
    { value: "cancelled", label: "Cancelled" },
  ];

  return (
    <div>
      <div className="flex gap-1 mb-6">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              tab === t.value
                ? "bg-[var(--color-primary)] text-white"
                : "bg-white border border-[var(--color-border)] hover:bg-gray-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
          No {tab} reservations.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((r) => (
            <ReservationCard
              key={r.id}
              reservation={r}
              onCancel={tab === "upcoming" ? handleCancel : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}
