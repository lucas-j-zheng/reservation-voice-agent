"use client";

import type { RequestType, Restaurant } from "@sam/api-contracts";
import type { ReservationFormData } from "./ReservationFields";
import type { InfoQueryFormData } from "./InfoQueryFields";
import type { EventInquiryFormData } from "./EventInquiryFields";
import type { CancellationFormData } from "./CancellationFields";
import { formatDate, formatTime } from "@/lib/utils";
import { QUERY_CATEGORIES, FACILITY_CATEGORIES, EVENT_TYPES } from "@/lib/constants";

type Props = {
  type: RequestType;
  details: ReservationFormData | InfoQueryFormData | EventInquiryFormData | CancellationFormData;
  restaurants: Restaurant[];
  onBack: () => void;
  onSubmit: () => void;
  submitting: boolean;
};

function labelFor(value: string, list: readonly { value: string; label: string }[]) {
  return list.find((i) => i.value === value)?.label ?? value;
}

export default function RequestSummary({ type, details, restaurants, onBack, onSubmit, submitting }: Props) {
  const typeLabels: Record<RequestType, string> = {
    reservation: "Reservation",
    info_query: "Info Query",
    event_inquiry: "Event Inquiry",
    cancellation: "Cancellation",
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 mb-2">
        <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
          {typeLabels[type]}
        </span>
      </div>

      {/* Type-specific details */}
      <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
        {type === "reservation" && (() => {
          const d = details as ReservationFormData;
          return (
            <>
              <Row label="Date" value={formatDate(d.requested_date)} />
              <Row label="Time" value={`${formatTime(d.time_range_start)} - ${formatTime(d.time_range_end)}`} />
              <Row label="Party Size" value={String(d.party_size)} />
              {d.special_requests && <Row label="Special Requests" value={d.special_requests} />}
              {d.contact_phone && <Row label="Contact" value={d.contact_phone} />}
            </>
          );
        })()}

        {type === "info_query" && (() => {
          const d = details as InfoQueryFormData;
          return (
            <>
              <Row label="Categories" value={d.query_categories.map((c) => labelFor(c, QUERY_CATEGORIES)).join(", ")} />
              {d.facility_categories.length > 0 && (
                <Row label="Facilities" value={d.facility_categories.map((c) => labelFor(c, FACILITY_CATEGORIES)).join(", ")} />
              )}
              {d.specific_questions && <Row label="Questions" value={d.specific_questions} />}
            </>
          );
        })()}

        {type === "event_inquiry" && (() => {
          const d = details as EventInquiryFormData;
          return (
            <>
              <Row label="Event Type" value={labelFor(d.event_type, EVENT_TYPES)} />
              {d.party_size > 0 && <Row label="Party Size" value={String(d.party_size)} />}
              {d.preferred_date && <Row label="Date" value={formatDate(d.preferred_date)} />}
              {d.budget_range && <Row label="Budget" value={d.budget_range} />}
              {d.details && <Row label="Details" value={d.details} />}
            </>
          );
        })()}

        {type === "cancellation" && (() => {
          const d = details as CancellationFormData;
          return (
            <>
              <Row label="Reservation" value={d.reservation_id} />
              {d.reason && <Row label="Reason" value={d.reason} />}
            </>
          );
        })()}
      </div>

      {/* Restaurants */}
      <div>
        <label className="block text-sm font-medium mb-2">
          {type === "cancellation" ? "Restaurant" : `Restaurants (${restaurants.length})`}
        </label>
        <div className="space-y-1">
          {restaurants.map((r, i) => (
            <div key={r.id} className="flex items-center gap-2 text-sm">
              {restaurants.length > 1 && (
                <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-xs flex items-center justify-center shrink-0">
                  {i + 1}
                </span>
              )}
              <span className="font-medium">{r.name}</span>
              <span className="text-[var(--color-text-secondary)]">{r.phone}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitting}
          className="px-5 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary-hover)] disabled:opacity-50 font-medium"
        >
          {submitting ? "Sending..." : "Send Agent"}
        </button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-[var(--color-text-secondary)] w-32 shrink-0">{label}</span>
      <span>{value}</span>
    </div>
  );
}
