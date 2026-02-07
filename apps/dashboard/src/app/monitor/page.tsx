export default function MonitorPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Live Monitor</h1>
      <p className="text-[var(--color-text-secondary)]">
        Watch Sam work through your request in real time.
      </p>
      <div className="mt-8 bg-white rounded-xl border border-[var(--color-border)] p-12 text-center text-[var(--color-text-secondary)]">
        No active request. Start one from the New Request page.
      </div>
    </div>
  );
}
