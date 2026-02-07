export default function ReservationsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Reservations</h1>
      <p className="text-[var(--color-text-secondary)]">
        Your confirmed, upcoming, and past reservations.
      </p>
      <div className="mt-8 bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No reservations yet.
      </div>
    </div>
  );
}
