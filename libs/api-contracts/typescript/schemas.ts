/**
 * Shared Zod schemas for API contracts.
 * These schemas ensure data consistency between dashboard and voice-engine.
 */

import { z } from "zod";

export const CallStatusSchema = z.enum(["ongoing", "completed", "failed"]);
export type CallStatus = z.infer<typeof CallStatusSchema>;

export const CallSchema = z.object({
  id: z.string().uuid(),
  twilio_sid: z.string(),
  status: CallStatusSchema,
  transcript_summary: z.string().nullable(),
});
export type Call = z.infer<typeof CallSchema>;

export const ReservationSchema = z.object({
  id: z.string().uuid(),
  call_id: z.string().uuid(),
  restaurant_name: z.string(),
  party_size: z.number().int().min(1).max(20),
  confirmed_time: z.string().datetime(),
  confirmation_code: z.string().nullable(),
});
export type Reservation = z.infer<typeof ReservationSchema>;

export const ReservationRequestSchema = z.object({
  user_name: z.string().min(1),
  restaurant_phone: z.string(),
  party_size: z.number().int().min(1).max(20),
  preferred_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  preferred_time: z.string().regex(/^\d{2}:\d{2}$/),
  contact_phone: z.string(),
});
export type ReservationRequest = z.infer<typeof ReservationRequestSchema>;
