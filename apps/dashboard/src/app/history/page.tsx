import ActivityTimeline from "@/components/history/ActivityTimeline";

export default function HistoryPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">History</h1>
      <p className="text-[var(--color-text-secondary)] mb-6">
        All past requests across every type.
      </p>
      <ActivityTimeline />
    </div>
  );
}
