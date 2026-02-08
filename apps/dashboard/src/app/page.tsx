import DashboardStats from "@/components/home/DashboardStats";

export default function HomePage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Dashboard</h1>
      <p className="text-[var(--color-text-secondary)] mb-6">
        Overview of your voice agent activity.
      </p>
      <DashboardStats />
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <a
          href="/new-request"
          className="bg-white rounded-xl border border-[var(--color-border)] p-6 hover:border-[var(--color-primary)] transition-colors"
        >
          <h2 className="font-semibold mb-1">New Request</h2>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Create a reservation, ask a question, plan an event, or cancel.
          </p>
        </a>
        <a
          href="/restaurants"
          className="bg-white rounded-xl border border-[var(--color-border)] p-6 hover:border-[var(--color-primary)] transition-colors"
        >
          <h2 className="font-semibold mb-1">Restaurants</h2>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Manage your restaurant directory.
          </p>
        </a>
        <a
          href="/reservations"
          className="bg-white rounded-xl border border-[var(--color-border)] p-6 hover:border-[var(--color-primary)] transition-colors"
        >
          <h2 className="font-semibold mb-1">Reservations</h2>
          <p className="text-sm text-[var(--color-text-secondary)]">
            View upcoming and past reservations.
          </p>
        </a>
        <a
          href="/history"
          className="bg-white rounded-xl border border-[var(--color-border)] p-6 hover:border-[var(--color-primary)] transition-colors"
        >
          <h2 className="font-semibold mb-1">History</h2>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Browse all past requests and their outcomes.
          </p>
        </a>
      </div>
    </div>
  );
}
