import RequestForm from "@/components/requests/RequestForm";

export default function NewRequestPage() {
  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-2">New Request</h1>
      <p className="text-[var(--color-text-secondary)] mb-6">
        Create a new request and send Sam to handle it.
      </p>
      <RequestForm />
    </div>
  );
}
