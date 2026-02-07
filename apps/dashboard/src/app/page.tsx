export default function HomePage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Dashboard</h1>
      <p className="text-[var(--color-text-secondary)]">
        Overview of your voice agent activity.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Total Requests
          </p>
          <p className="text-3xl font-bold mt-1">--</p>
        </div>
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Confirmed Reservations
          </p>
          <p className="text-3xl font-bold mt-1">--</p>
        </div>
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Active Calls
          </p>
          <p className="text-3xl font-bold mt-1">--</p>
        </div>
      </div>
    </div>
  );
}
