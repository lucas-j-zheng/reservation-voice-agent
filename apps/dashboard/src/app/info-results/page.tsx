export default function InfoResultsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Info Results</h1>
      <p className="text-[var(--color-text-secondary)]">
        Information gathered from your restaurant queries.
      </p>
      <div className="mt-8 bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No info results yet. Send an info query to get started.
      </div>
    </div>
  );
}
