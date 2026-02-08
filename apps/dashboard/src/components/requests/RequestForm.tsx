"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { RequestType, Restaurant } from "@sam/api-contracts";
import RequestTypeSelector from "./RequestTypeSelector";
import ReservationFields, { type ReservationFormData } from "./ReservationFields";
import InfoQueryFields, { type InfoQueryFormData } from "./InfoQueryFields";
import EventInquiryFields, { type EventInquiryFormData } from "./EventInquiryFields";
import CancellationFields, { type CancellationFormData } from "./CancellationFields";
import RestaurantPicker from "./RestaurantPicker";
import RequestSummary from "./RequestSummary";

type Step = "type" | "details" | "restaurants" | "review";

const INITIAL_RESERVATION: ReservationFormData = {
  party_size: 2,
  requested_date: "",
  time_range_start: "18:00",
  time_range_end: "20:00",
  special_requests: "",
  contact_phone: "",
};

const INITIAL_INFO: InfoQueryFormData = {
  query_categories: [],
  specific_questions: "",
  facility_categories: [],
};

const INITIAL_EVENT: EventInquiryFormData = {
  event_type: "",
  party_size: 0,
  preferred_date: "",
  budget_range: "",
  details: "",
};

const INITIAL_CANCEL: CancellationFormData = {
  reservation_id: "",
  reason: "",
};

export default function RequestForm() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("type");
  const [type, setType] = useState<RequestType | null>(null);
  const [reservationData, setReservationData] = useState(INITIAL_RESERVATION);
  const [infoData, setInfoData] = useState(INITIAL_INFO);
  const [eventData, setEventData] = useState(INITIAL_EVENT);
  const [cancelData, setCancelData] = useState(INITIAL_CANCEL);
  const [selectedRestaurantIds, setSelectedRestaurantIds] = useState<string[]>([]);
  const [allRestaurants, setAllRestaurants] = useState<Restaurant[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Load restaurants once for summary lookups
  useEffect(() => {
    fetch("/api/restaurants")
      .then((r) => r.ok ? r.json() : [])
      .then(setAllRestaurants)
      .catch(() => {});
  }, []);

  const handleTypeSelect = useCallback((t: RequestType) => {
    setType(t);
    setStep("details");
    setSelectedRestaurantIds([]);
    setError("");
  }, []);

  function getDetails() {
    switch (type) {
      case "reservation": return reservationData;
      case "info_query": return infoData;
      case "event_inquiry": return eventData;
      case "cancellation": return cancelData;
      default: return null;
    }
  }

  function validateDetails(): boolean {
    switch (type) {
      case "reservation":
        return !!(reservationData.requested_date && reservationData.party_size > 0 &&
          reservationData.time_range_start && reservationData.time_range_end);
      case "info_query":
        return infoData.query_categories.length > 0;
      case "event_inquiry":
        return !!eventData.event_type;
      case "cancellation":
        return !!cancelData.reservation_id;
      default:
        return false;
    }
  }

  function handleDetailsNext() {
    if (!validateDetails()) {
      setError("Please fill in required fields.");
      return;
    }
    setError("");
    // Cancellations auto-select restaurant, skip picker
    if (type === "cancellation") {
      setStep("review");
    } else {
      setStep("restaurants");
    }
  }

  function handleRestaurantsNext() {
    if (selectedRestaurantIds.length === 0) {
      setError("Select at least one restaurant.");
      return;
    }
    setError("");
    setStep("review");
  }

  // For cancellation: resolve restaurant from selected reservation
  const handleCancellationRestaurant = useCallback(
    (restaurantId: string | null) => {
      setSelectedRestaurantIds(restaurantId ? [restaurantId] : []);
    },
    []
  );

  async function handleSubmit() {
    if (!type) return;
    setSubmitting(true);
    setError("");

    // Build details payload (strip fields not in create schema)
    const details = getDetails();
    const payload = {
      type,
      details,
      restaurant_ids: selectedRestaurantIds,
    };

    try {
      const res = await fetch("/api/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to create request");
      }

      const result = await res.json();
      router.push(`/monitor?request_id=${result.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create request");
      setSubmitting(false);
    }
  }

  const selectedRestaurants = selectedRestaurantIds
    .map((id) => allRestaurants.find((r) => r.id === id))
    .filter(Boolean) as Restaurant[];

  const stepLabels: Record<Step, string> = {
    type: "Choose Type",
    details: "Details",
    restaurants: "Restaurants",
    review: "Review",
  };

  const steps: Step[] = type === "cancellation"
    ? ["type", "details", "review"]
    : ["type", "details", "restaurants", "review"];

  return (
    <div>
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            {i > 0 && <div className="w-8 h-px bg-[var(--color-border)]" />}
            <button
              type="button"
              onClick={() => {
                const currentIdx = steps.indexOf(step);
                if (steps.indexOf(s) < currentIdx) setStep(s);
              }}
              disabled={steps.indexOf(s) > steps.indexOf(step)}
              className={`text-sm px-3 py-1 rounded-full transition-colors ${
                s === step
                  ? "bg-[var(--color-primary)] text-white"
                  : steps.indexOf(s) < steps.indexOf(step)
                  ? "bg-blue-100 text-blue-700 hover:bg-blue-200"
                  : "bg-gray-100 text-gray-400"
              }`}
            >
              {stepLabels[s]}
            </button>
          </div>
        ))}
      </div>

      {/* Content card */}
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
        {step === "type" && (
          <div>
            <h2 className="text-lg font-semibold mb-4">What would you like to do?</h2>
            <RequestTypeSelector selected={type} onSelect={handleTypeSelect} />
          </div>
        )}

        {step === "details" && type && (
          <div>
            <h2 className="text-lg font-semibold mb-4">
              {type === "reservation" && "Reservation Details"}
              {type === "info_query" && "What to Ask"}
              {type === "event_inquiry" && "Event Details"}
              {type === "cancellation" && "Select Reservation"}
            </h2>

            {type === "reservation" && (
              <ReservationFields data={reservationData} onChange={setReservationData} />
            )}
            {type === "info_query" && (
              <InfoQueryFields data={infoData} onChange={setInfoData} />
            )}
            {type === "event_inquiry" && (
              <EventInquiryFields data={eventData} onChange={setEventData} />
            )}
            {type === "cancellation" && (
              <CancellationFields
                data={cancelData}
                onChange={setCancelData}
                onRestaurantResolved={handleCancellationRestaurant}
              />
            )}

            {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={() => setStep("type")}
                className="px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-gray-50"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleDetailsNext}
                className="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary-hover)]"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {step === "restaurants" && (
          <div>
            <h2 className="text-lg font-semibold mb-1">Select Restaurants</h2>
            <p className="text-sm text-[var(--color-text-secondary)] mb-4">
              {type === "info_query"
                ? "Sam will call all selected restaurants and gather info from each."
                : "Sam will try restaurants in order until one works. Drag to reorder priority."}
            </p>

            <RestaurantPicker
              selectedIds={selectedRestaurantIds}
              onChange={setSelectedRestaurantIds}
            />

            {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={() => setStep("details")}
                className="px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-gray-50"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleRestaurantsNext}
                className="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary-hover)]"
              >
                Review
              </button>
            </div>
          </div>
        )}

        {step === "review" && type && (
          <div>
            <h2 className="text-lg font-semibold mb-4">Review & Send</h2>
            <RequestSummary
              type={type}
              details={getDetails()!}
              restaurants={selectedRestaurants}
              onBack={() => setStep(type === "cancellation" ? "details" : "restaurants")}
              onSubmit={handleSubmit}
              submitting={submitting}
            />
            {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
