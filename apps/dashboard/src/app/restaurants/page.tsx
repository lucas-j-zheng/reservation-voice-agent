export default function RestaurantsPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Restaurants</h1>
          <p className="text-[var(--color-text-secondary)]">
            Manage your restaurant directory.
          </p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No restaurants yet. Add one to get started.
      </div>
    </div>
  );
}
