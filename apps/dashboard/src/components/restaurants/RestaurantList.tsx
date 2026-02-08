"use client";

import { useEffect, useState } from "react";
import type { Restaurant } from "@sam/api-contracts";
import RestaurantCard from "./RestaurantCard";
import RestaurantForm from "./RestaurantForm";

export default function RestaurantList() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Restaurant | undefined>();

  useEffect(() => {
    fetchRestaurants();
  }, []);

  async function fetchRestaurants() {
    try {
      const res = await fetch("/api/restaurants");
      if (res.ok) {
        setRestaurants(await res.json());
      }
    } finally {
      setLoading(false);
    }
  }

  function handleSave(saved: Restaurant) {
    if (editing) {
      setRestaurants((prev) =>
        prev.map((r) => (r.id === saved.id ? saved : r))
      );
    } else {
      setRestaurants((prev) => [saved, ...prev]);
    }
    setShowForm(false);
    setEditing(undefined);
  }

  function handleEdit(restaurant: Restaurant) {
    setEditing(restaurant);
    setShowForm(true);
  }

  function handleDelete(id: string) {
    setRestaurants((prev) => prev.filter((r) => r.id !== id));
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-[var(--color-text-secondary)]">
        Loading restaurants...
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Restaurants</h1>
          <p className="text-[var(--color-text-secondary)]">
            Manage your restaurant directory.
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => {
              setEditing(undefined);
              setShowForm(true);
            }}
            className="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary-hover)]"
          >
            + Add Restaurant
          </button>
        )}
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            {editing ? "Edit Restaurant" : "Add Restaurant"}
          </h2>
          <RestaurantForm
            restaurant={editing}
            onSave={handleSave}
            onCancel={() => {
              setShowForm(false);
              setEditing(undefined);
            }}
          />
        </div>
      )}

      {restaurants.length === 0 ? (
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
          No restaurants yet. Add one to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {restaurants.map((r) => (
            <RestaurantCard
              key={r.id}
              restaurant={r}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
