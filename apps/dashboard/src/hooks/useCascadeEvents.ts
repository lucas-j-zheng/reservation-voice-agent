"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { VOICE_ENGINE_URL } from "@/lib/constants";
import { startSimulation, type CascadeEvent } from "@/lib/cascade-simulator";

type CascadeState = {
  status: "idle" | "running" | "paused" | "completed" | "exhausted" | "cancelled";
  events: CascadeEvent[];
  currentRestaurantId: string | null;
  error: string | null;
};

export function useCascadeEvents(
  requestId: string | null,
  requestType: string,
  restaurants: { id: string; name: string }[]
) {
  const [state, setState] = useState<CascadeState>({
    status: "idle",
    events: [],
    currentRestaurantId: null,
    error: null,
  });
  const [useSimulator, setUseSimulator] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const receivedRealEvent = useRef(false);

  const handleEvent = useCallback((event: CascadeEvent) => {
    setState((prev) => {
      const events = [...prev.events, event];
      let status = prev.status;
      let currentRestaurantId = prev.currentRestaurantId;

      switch (event.event) {
        case "cascade_started":
          status = "running";
          break;
        case "calling_restaurant":
        case "restaurant_calling":
          currentRestaurantId = event.restaurant_id ?? null;
          break;
        case "call_completed_success":
        case "restaurant_succeeded":
          if (currentRestaurantId === event.restaurant_id) {
            currentRestaurantId = null;
          }
          break;
        case "call_completed_failure":
        case "restaurant_failed":
          if (currentRestaurantId === event.restaurant_id) {
            currentRestaurantId = null;
          }
          break;
        case "call_no_answer":
        case "restaurant_no_answer":
          if (currentRestaurantId === event.restaurant_id) {
            currentRestaurantId = null;
          }
          break;
        case "cascade_paused":
          status = "paused";
          break;
        case "cascade_resumed":
          status = "running";
          break;
        case "cascade_completed":
          status = "completed";
          currentRestaurantId = null;
          break;
        case "cascade_exhausted":
          status = "exhausted";
          currentRestaurantId = null;
          break;
        case "cascade_cancelled":
          status = "cancelled";
          currentRestaurantId = null;
          break;
      }

      return { status, events, currentRestaurantId, error: null };
    });
  }, []);

  // Try SSE first, fall back to simulator only if SSE never delivers data
  useEffect(() => {
    if (!requestId) return;

    // Reset state
    setState({ status: "idle", events: [], currentRestaurantId: null, error: null });
    receivedRealEvent.current = false;
    setUseSimulator(false);

    let eventSource: EventSource | null = null;
    let failCount = 0;

    // Only fall back to simulator after repeated failures with no data
    const sseTimeout = setTimeout(() => {
      if (!receivedRealEvent.current) {
        eventSource?.close();
        setUseSimulator(true);
      }
    }, 5000);

    try {
      eventSource = new EventSource(`${VOICE_ENGINE_URL}/api/cascade/events/${requestId}`);

      eventSource.onmessage = (e) => {
        clearTimeout(sseTimeout);
        receivedRealEvent.current = true;
        failCount = 0;
        try {
          const event: CascadeEvent = JSON.parse(e.data);
          handleEvent(event);
        } catch {
          // Ignore parse errors
        }
      };

      eventSource.onerror = () => {
        failCount++;
        // If we already received real events, don't switch to simulator.
        // EventSource auto-reconnects. Only give up after many failures with no data.
        if (!receivedRealEvent.current && failCount >= 3) {
          clearTimeout(sseTimeout);
          eventSource?.close();
          setUseSimulator(true);
        }
      };

    } catch {
      clearTimeout(sseTimeout);
      setUseSimulator(true);
    }

    return () => {
      clearTimeout(sseTimeout);
      eventSource?.close();
    };
  }, [requestId, handleEvent]);

  // Start simulator when SSE fails
  useEffect(() => {
    if (!useSimulator || !requestId || restaurants.length === 0) return;

    setState({ status: "idle", events: [], currentRestaurantId: null, error: null });

    cleanupRef.current = startSimulation({
      requestId,
      requestType,
      restaurants,
      onEvent: handleEvent,
    });

    return () => {
      cleanupRef.current?.();
    };
  }, [useSimulator, requestId, requestType, restaurants, handleEvent]);

  const cascadePost = useCallback(async (action: string, body: Record<string, string>) => {
    return fetch(`${VOICE_ENGINE_URL}/api/cascade/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }, []);

  const pause = useCallback(async () => {
    if (!requestId) return;
    try {
      await cascadePost("pause", { request_id: requestId });
    } catch {
      handleEvent({ event: "cascade_paused", request_id: requestId, request_type: requestType, timestamp: new Date().toISOString() });
    }
  }, [requestId, requestType, handleEvent, cascadePost]);

  const resume = useCallback(async () => {
    if (!requestId) return;
    try {
      await cascadePost("resume", { request_id: requestId });
    } catch {
      handleEvent({ event: "cascade_resumed", request_id: requestId, request_type: requestType, timestamp: new Date().toISOString() });
    }
  }, [requestId, requestType, handleEvent, cascadePost]);

  const cancel = useCallback(async () => {
    if (!requestId) return;
    cleanupRef.current?.();
    try {
      await cascadePost("cancel", { request_id: requestId });
    } catch {
      handleEvent({ event: "cascade_cancelled", request_id: requestId, request_type: requestType, timestamp: new Date().toISOString() });
    }
  }, [requestId, requestType, handleEvent, cascadePost]);

  const skip = useCallback(async () => {
    if (!requestId || !state.currentRestaurantId) return;
    try {
      await cascadePost("skip", { request_id: requestId });
    } catch {
      handleEvent({
        event: "restaurant_skipped",
        request_id: requestId,
        request_type: requestType,
        restaurant_id: state.currentRestaurantId,
        timestamp: new Date().toISOString(),
      });
    }
  }, [requestId, requestType, state.currentRestaurantId, handleEvent, cascadePost]);

  return {
    ...state,
    isSimulated: useSimulator,
    pause,
    resume,
    cancel,
    skip,
  };
}
