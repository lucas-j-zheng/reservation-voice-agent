export type CascadeEventType =
  | "cascade_started"
  | "calling_restaurant"
  | "call_completed_success"
  | "call_completed_failure"
  | "call_no_answer"
  | "restaurant_skipped"
  | "cascade_paused"
  | "cascade_resumed"
  | "cascade_completed"
  | "cascade_exhausted"
  | "cascade_cancelled";

export type CascadeEvent = {
  event: CascadeEventType;
  request_id: string;
  request_type: string;
  restaurant_id?: string;
  restaurant_name?: string;
  timestamp: string;
  data?: Record<string, unknown>;
};

type ScenarioStep = {
  delay: number; // ms from start
  event: CascadeEventType;
  restaurantIndex?: number;
  data?: Record<string, unknown>;
};

const RESERVATION_SCENARIO: ScenarioStep[] = [
  { delay: 0, event: "cascade_started" },
  { delay: 2000, event: "calling_restaurant", restaurantIndex: 0 },
  { delay: 6000, event: "call_completed_failure", restaurantIndex: 0, data: { reason: "Fully booked for that date" } },
  { delay: 8000, event: "calling_restaurant", restaurantIndex: 1 },
  { delay: 12000, event: "call_completed_success", restaurantIndex: 1, data: { confirmation_code: "SR-4821", confirmed_time: "19:00" } },
  { delay: 13000, event: "cascade_completed" },
];

const INFO_QUERY_SCENARIO: ScenarioStep[] = [
  { delay: 0, event: "cascade_started" },
  { delay: 1000, event: "calling_restaurant", restaurantIndex: 0 },
  { delay: 1500, event: "calling_restaurant", restaurantIndex: 1 },
  { delay: 5000, event: "call_completed_success", restaurantIndex: 0, data: { hours: "Mon-Fri 11am-10pm", wait_time: "15 min" } },
  { delay: 7000, event: "call_completed_success", restaurantIndex: 1, data: { hours: "Daily 10am-11pm", wait_time: "No wait" } },
  { delay: 8000, event: "cascade_completed" },
];

const EVENT_INQUIRY_SCENARIO: ScenarioStep[] = [
  { delay: 0, event: "cascade_started" },
  { delay: 2000, event: "calling_restaurant", restaurantIndex: 0 },
  { delay: 7000, event: "call_completed_failure", restaurantIndex: 0, data: { reason: "No private dining available" } },
  { delay: 9000, event: "calling_restaurant", restaurantIndex: 1 },
  { delay: 14000, event: "call_completed_success", restaurantIndex: 1, data: { available: true, quoted_price: "$800-1200", capacity: 30 } },
  { delay: 15000, event: "cascade_completed" },
];

const CANCELLATION_SCENARIO: ScenarioStep[] = [
  { delay: 0, event: "cascade_started" },
  { delay: 1500, event: "calling_restaurant", restaurantIndex: 0 },
  { delay: 5000, event: "call_completed_success", restaurantIndex: 0, data: { confirmed: true, cancellation_code: "CX-9912" } },
  { delay: 6000, event: "cascade_completed" },
];

const SCENARIOS: Record<string, ScenarioStep[]> = {
  reservation: RESERVATION_SCENARIO,
  info_query: INFO_QUERY_SCENARIO,
  event_inquiry: EVENT_INQUIRY_SCENARIO,
  cancellation: CANCELLATION_SCENARIO,
};

export type SimulatorOptions = {
  requestId: string;
  requestType: string;
  restaurants: { id: string; name: string }[];
  onEvent: (event: CascadeEvent) => void;
};

export function startSimulation({ requestId, requestType, restaurants, onEvent }: SimulatorOptions): () => void {
  const scenario = SCENARIOS[requestType] ?? RESERVATION_SCENARIO;
  const timers: ReturnType<typeof setTimeout>[] = [];

  for (const step of scenario) {
    // Skip steps that reference restaurants we don't have
    if (step.restaurantIndex !== undefined && step.restaurantIndex >= restaurants.length) {
      continue;
    }

    const timer = setTimeout(() => {
      const restaurant = step.restaurantIndex !== undefined ? restaurants[step.restaurantIndex] : undefined;
      onEvent({
        event: step.event,
        request_id: requestId,
        request_type: requestType,
        restaurant_id: restaurant?.id,
        restaurant_name: restaurant?.name,
        timestamp: new Date().toISOString(),
        data: step.data,
      });
    }, step.delay);

    timers.push(timer);
  }

  // Return cleanup function
  return () => timers.forEach(clearTimeout);
}
