"use client";

import { QUERY_CATEGORIES, FACILITY_CATEGORIES } from "@/lib/constants";

export type InfoQueryFormData = {
  query_categories: string[];
  specific_questions: string;
  facility_categories: string[];
};

function toggle(arr: string[], val: string): string[] {
  return arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];
}

export default function InfoQueryFields({
  data,
  onChange,
}: {
  data: InfoQueryFormData;
  onChange: (data: InfoQueryFormData) => void;
}) {
  const showFacilities = data.query_categories.includes("facilities");

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium mb-2">What do you want to know? *</label>
        <div className="flex flex-wrap gap-2">
          {QUERY_CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              type="button"
              onClick={() =>
                onChange({ ...data, query_categories: toggle(data.query_categories, cat.value) })
              }
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                data.query_categories.includes(cat.value)
                  ? "bg-[var(--color-primary)] text-white border-[var(--color-primary)]"
                  : "bg-white border-[var(--color-border)] hover:border-gray-300"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {showFacilities && (
        <div>
          <label className="block text-sm font-medium mb-2">Which facilities?</label>
          <div className="flex flex-wrap gap-2">
            {FACILITY_CATEGORIES.map((cat) => (
              <button
                key={cat.value}
                type="button"
                onClick={() =>
                  onChange({ ...data, facility_categories: toggle(data.facility_categories, cat.value) })
                }
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  data.facility_categories.includes(cat.value)
                    ? "bg-[var(--color-primary)] text-white border-[var(--color-primary)]"
                    : "bg-white border-[var(--color-border)] hover:border-gray-300"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">Specific Questions</label>
        <textarea
          value={data.specific_questions}
          onChange={(e) => onChange({ ...data, specific_questions: e.target.value })}
          rows={3}
          placeholder="Any other questions you'd like Sam to ask?"
          className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
        />
      </div>
    </div>
  );
}
