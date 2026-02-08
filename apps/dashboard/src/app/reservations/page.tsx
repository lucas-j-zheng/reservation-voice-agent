import ReservationList from "@/components/reservations/ReservationList";

export default function ReservationsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Reservations</h1>
      <p className="text-[var(--color-text-secondary)] mb-6">
        Your confirmed, upcoming, and past reservations.
      </p>
      <ReservationList />
    </div>
  );
}
