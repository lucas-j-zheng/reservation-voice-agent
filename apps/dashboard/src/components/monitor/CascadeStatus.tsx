"use client";

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  idle: { label: "Idle", color: "bg-gray-100 text-gray-700", dot: "bg-gray-400" },
  running: { label: "Running", color: "bg-blue-100 text-blue-800", dot: "bg-blue-500 animate-pulse" },
  paused: { label: "Paused", color: "bg-yellow-100 text-yellow-800", dot: "bg-yellow-500" },
  completed: { label: "Completed", color: "bg-green-100 text-green-800", dot: "bg-green-500" },
  exhausted: { label: "Exhausted", color: "bg-red-100 text-red-800", dot: "bg-red-500" },
  cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-600", dot: "bg-gray-400" },
};

export default function CascadeStatus({
  status,
  currentRestaurantName,
  isSimulated,
}: {
  status: string;
  currentRestaurantName?: string;
  isSimulated: boolean;
}) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.idle;

  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${config.dot}`} />
          <span className={`px-2.5 py-1 rounded-md text-sm font-medium ${config.color}`}>
            {config.label}
          </span>
          {isSimulated && (
            <span className="px-2 py-0.5 rounded text-xs bg-amber-50 text-amber-700 border border-amber-200">
              Simulated
            </span>
          )}
        </div>
        {currentRestaurantName && status === "running" && (
          <div className="text-sm text-[var(--color-text-secondary)]">
            Calling <span className="font-medium text-[var(--color-text)]">{currentRestaurantName}</span>
          </div>
        )}
      </div>
    </div>
  );
}
