import InfoResultList from "@/components/info-results/InfoResultList";

export default function InfoResultsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Info Results</h1>
      <p className="text-[var(--color-text-secondary)] mb-6">
        Information gathered from your restaurant queries.
      </p>
      <InfoResultList />
    </div>
  );
}
