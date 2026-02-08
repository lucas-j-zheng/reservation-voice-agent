"use client";

import { useEffect, useState } from "react";

type Stats = {
  totalRequests: number;
  confirmedReservations: number;
  pendingRequests: number;
  totalRestaurants: number;
};

export default function DashboardStats() {
  const [stats, setStats] = useState<Stats>({
    totalRequests: 0,
    confirmedReservations: 0,
    pendingRequests: 0,
    totalRestaurants: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [reqRes, resRes, restRes] = await Promise.all([
          fetch("/api/requests"),
          fetch("/api/reservations"),
          fetch("/api/restaurants"),
        ]);

        const requests = reqRes.ok ? await reqRes.json() : [];
        const reservations = resRes.ok ? await resRes.json() : [];
        const restaurants = restRes.ok ? await restRes.json() : [];

        setStats({
          totalRequests: requests.length,
          confirmedReservations: reservations.filter(
            (r: { status: string }) => r.status === "confirmed"
          ).length,
          pendingRequests: requests.filter(
            (r: { status: string }) => r.status === "pending" || r.status === "in_progress"
          ).length,
          totalRestaurants: restaurants.length,
        });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const cards = [
    { label: "Total Requests", value: stats.totalRequests, color: "text-[var(--color-primary)]" },
    { label: "Confirmed Reservations", value: stats.confirmedReservations, color: "text-[var(--color-success)]" },
    { label: "Pending Requests", value: stats.pendingRequests, color: "text-[var(--color-warning)]" },
    { label: "Restaurants", value: stats.totalRestaurants, color: "text-[var(--color-text)]" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-white rounded-xl border border-[var(--color-border)] p-5">
          <p className="text-sm text-[var(--color-text-secondary)]">{card.label}</p>
          <p className={`text-3xl font-bold mt-1 ${card.color}`}>
            {loading ? "--" : card.value}
          </p>
        </div>
      ))}
    </div>
  );
}
