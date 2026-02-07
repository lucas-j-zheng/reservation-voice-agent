export const VOICE_ENGINE_URL =
  process.env.VOICE_ENGINE_URL || "http://localhost:8000";

export const REQUEST_TYPES = [
  { value: "reservation", label: "Make a Reservation", icon: "calendar" },
  { value: "info_query", label: "Ask a Question", icon: "info" },
  { value: "event_inquiry", label: "Plan an Event", icon: "party" },
  { value: "cancellation", label: "Cancel a Reservation", icon: "x" },
] as const;

export const REQUEST_STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const REQUEST_STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  in_progress: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
};

export const QUERY_CATEGORIES = [
  { value: "hours", label: "Hours" },
  { value: "wait_times", label: "Wait Times" },
  { value: "menu", label: "Menu" },
  { value: "pricing", label: "Pricing" },
  { value: "dietary", label: "Dietary Options" },
  { value: "allergens", label: "Allergens" },
  { value: "facilities", label: "Facilities" },
] as const;

export const FACILITY_CATEGORIES = [
  { value: "outdoor", label: "Outdoor Seating" },
  { value: "private_rooms", label: "Private Rooms" },
  { value: "wheelchair", label: "Wheelchair Accessible" },
  { value: "high_chairs", label: "High Chairs" },
  { value: "pet_friendly", label: "Pet Friendly" },
  { value: "parking", label: "Parking" },
] as const;

export const EVENT_TYPES = [
  { value: "birthday", label: "Birthday" },
  { value: "anniversary", label: "Anniversary" },
  { value: "large_party", label: "Large Party" },
  { value: "catering", label: "Catering" },
  { value: "event_space", label: "Event Space" },
] as const;

export const NAV_ITEMS = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/restaurants", label: "Restaurants", icon: "store" },
  { href: "/new-request", label: "New Request", icon: "plus" },
  { href: "/monitor", label: "Monitor", icon: "activity" },
  { href: "/reservations", label: "Reservations", icon: "calendar" },
  { href: "/info-results", label: "Info Results", icon: "info" },
  { href: "/history", label: "History", icon: "clock" },
] as const;
