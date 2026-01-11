"use client";

/**
 * CallMonitor Component
 * MVP: Placeholder for live call monitoring interface.
 * Will display real-time call status and transcript.
 */
export function CallMonitor() {
  return (
    <div style={{ marginTop: "2rem", padding: "1rem", border: "1px solid #ccc" }}>
      <h2>Live Call Monitor</h2>
      <p>No active calls</p>
      {/* TODO: WebSocket connection to voice-engine for real-time updates */}
    </div>
  );
}
