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
          currentRestaurantId = event.restaurant_id ?? null;
          break;
        case "call_completed_success":
        case "call_completed_failure":
        case "call_no_answer":
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

  // Try SSE first, fall back to simulator
  useEffect(() => {
    if (!requestId) return;

    // Reset state
    setState({ status: "idle", events: [], currentRestaurantId: null, error: null });

    // Try real SSE connection
    let eventSource: EventSource | null = null;
    let sseTimedOut = false;

    const sseTimeout = setTimeout(() => {
      sseTimedOut = true;
      if (eventSource) {
        eventSource.close();
      }
      // Fall back to simulator
      setUseSimulator(true);
    }, 3000);

    try {
      eventSource = new EventSource(`${VOICE_ENGINE_URL}/api/cascade/${requestId}/events`);

      eventSource.onmessage = (e) => {
        clearTimeout(sseTimeout);
        try {
          const event: CascadeEvent = JSON.parse(e.data);
          handleEvent(event);
        } catch {
          // Ignore parse errors
        }
      };

      eventSource.onerror = () => {
        if (!sseTimedOut) {
          clearTimeout(sseTimeout);
          eventSource?.close();
          setUseSimulator(true);
        }
      };

      eventSource.onopen = () => {
        clearTimeout(sseTimeout);
        setUseSimulator(false);
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

  const pause = useCallback(async () => {
    if (!requestId) return;
    try {
      await fetch(`${VOICE_ENGINE_URL}/api/cascade/${requestId}/pause`, { method: "POST" });
    } catch {
      // Simulate pause locally
      handleEvent({ event: "cascade_paused", request_id: requestId, request_type: requestType, timestamp: new Date().toISOString() });
    }
  }, [requestId, requestType, handleEvent]);

  const resume = useCallback(async () => {
    if (!requestId) return;
    try {
      await fetch(`${VOICE_ENGINE_URL}/api/cascade/${requestId}/resume`, { method: "POST" });
    } catch {
      handleEvent({ event: "cascade_resumed", request_id: requestId, request_type: requestType, timestamp: new Date().toISOString() });
    }
  }, [requestId, requestType, handleEvent]);

  const cancel = useCallback(async () => {
    if (!requestId) return;
    cleanupRef.current?.();
    try {
      await fetch(`${VOICE_ENGINE_URL}/api/cascade/${requestId}/cancel`, { method: "POST" });
    } catch {
      handleEvent({ event: "cascade_cancelled", request_id: requestId, request_type: requestType, timestamp: new Date().toISOString() });
    }
  }, [requestId, requestType, handleEvent]);

  const skip = useCallback(async () => {
    if (!requestId || !state.currentRestaurantId) return;
    try {
      await fetch(`${VOICE_ENGINE_URL}/api/cascade/${requestId}/skip`, { method: "POST" });
    } catch {
      handleEvent({
        event: "restaurant_skipped",
        request_id: requestId,
        request_type: requestType,
        restaurant_id: state.currentRestaurantId,
        timestamp: new Date().toISOString(),
      });
    }
  }, [requestId, requestType, state.currentRestaurantId, handleEvent]);

  return {
    ...state,
    isSimulated: useSimulator,
    pause,
    resume,
    cancel,
    skip,
  };
}
