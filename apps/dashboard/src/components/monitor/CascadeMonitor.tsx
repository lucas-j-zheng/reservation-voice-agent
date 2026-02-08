"use client";

import { useCascadeEvents } from "@/hooks/useCascadeEvents";
import CascadeStatus from "./CascadeStatus";
import CascadeControls from "./CascadeControls";
import RestaurantQueue from "./RestaurantQueue";
import EventLog from "./EventLog";
import ResultPreview from "./ResultPreview";

export default function CascadeMonitor({
  requestId,
  requestType,
  restaurants,
}: {
  requestId: string;
  requestType: string;
  restaurants: { id: string; name: string }[];
}) {
  const { status, events, currentRestaurantId, isSimulated, pause, resume, cancel, skip } =
    useCascadeEvents(requestId, requestType, restaurants);

  const currentRestaurant = restaurants.find((r) => r.id === currentRestaurantId);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <CascadeStatus
          status={status}
          currentRestaurantName={currentRestaurant?.name}
          isSimulated={isSimulated}
        />
        <CascadeControls
          status={status}
          onPause={pause}
          onResume={resume}
          onSkip={skip}
          onCancel={cancel}
          hasCurrentRestaurant={!!currentRestaurantId}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-4">
          <RestaurantQueue restaurants={restaurants} events={events} />
          <ResultPreview events={events} requestType={requestType} />
        </div>
        <EventLog events={events} />
      </div>
    </div>
  );
}
