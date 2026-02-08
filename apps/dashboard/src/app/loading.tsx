export default function Loading() {
  return (
    <div className="p-8">
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-48 bg-gray-200 rounded" />
        <div className="h-4 w-72 bg-gray-100 rounded" />
        <div className="mt-6 h-48 bg-gray-100 rounded-xl" />
      </div>
    </div>
  );
}
