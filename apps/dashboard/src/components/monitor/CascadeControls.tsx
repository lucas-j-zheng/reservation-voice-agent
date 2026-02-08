"use client";

export default function CascadeControls({
  status,
  onPause,
  onResume,
  onSkip,
  onCancel,
  hasCurrentRestaurant,
}: {
  status: string;
  onPause: () => void;
  onResume: () => void;
  onSkip: () => void;
  onCancel: () => void;
  hasCurrentRestaurant: boolean;
}) {
  const isActive = status === "running" || status === "paused";
  const isDone = status === "completed" || status === "exhausted" || status === "cancelled";

  if (isDone) return null;

  return (
    <div className="flex gap-2">
      {status === "running" && (
        <button
          onClick={onPause}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-lg hover:bg-gray-50"
        >
          Pause
        </button>
      )}
      {status === "paused" && (
        <button
          onClick={onResume}
          className="px-3 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary-hover)]"
        >
          Resume
        </button>
      )}
      {isActive && hasCurrentRestaurant && (
        <button
          onClick={onSkip}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-lg hover:bg-gray-50"
        >
          Skip Restaurant
        </button>
      )}
      {isActive && (
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
