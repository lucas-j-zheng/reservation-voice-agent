export default function HistoryPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">History</h1>
      <p className="text-[var(--color-text-secondary)]">
        All past requests across every type.
      </p>
      <div className="mt-8 bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No activity yet.
      </div>
    </div>
  );
}
