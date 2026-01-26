/**
 * Shared Zod schemas for API contracts.
 * These schemas ensure data consistency between dashboard and voice-engine.
 */

import { z } from "zod";

// ============================================
// CORE ENTITY SCHEMAS
// ============================================

export const UserCreateSchema = z.object({
  email: z.string().email().nullable().optional(),
  name: z.string().min(1),
  phone: z.string().nullable().optional(),
});
export type UserCreate = z.infer<typeof UserCreateSchema>;

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email().nullable(),
  name: z.string(),
  phone: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type User = z.infer<typeof UserSchema>;

export const RestaurantCreateSchema = z.object({
  name: z.string().min(1),
  phone: z.string().min(1),
  address: z.string().nullable().optional(),
  cuisine_type: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
});
export type RestaurantCreate = z.infer<typeof RestaurantCreateSchema>;

export const RestaurantSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  phone: z.string(),
  address: z.string().nullable(),
  cuisine_type: z.string().nullable(),
  notes: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type Restaurant = z.infer<typeof RestaurantSchema>;

// ============================================
// RESERVATION REQUEST SCHEMAS (UI Intent)
// ============================================

export const ReservationRequestStatusSchema = z.enum([
  "pending",
  "in_progress",
  "completed",
  "failed",
  "cancelled",
]);
export type ReservationRequestStatus = z.infer<typeof ReservationRequestStatusSchema>;

export const ReservationRequestCreateSchema = z.object({
  user_id: z.string().uuid().nullable().optional(),
  party_size: z.number().int().min(1).max(20),
  requested_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  time_range_start: z.string().regex(/^\d{2}:\d{2}$/),
  time_range_end: z.string().regex(/^\d{2}:\d{2}$/),
  special_requests: z.string().nullable().optional(),
  contact_phone: z.string().nullable().optional(),
});
export type ReservationRequestCreate = z.infer<typeof ReservationRequestCreateSchema>;

export const ReservationRequestSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid().nullable(),
  party_size: z.number().int(),
  requested_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  time_range_start: z.string().regex(/^\d{2}:\d{2}$/),
  time_range_end: z.string().regex(/^\d{2}:\d{2}$/),
  special_requests: z.string().nullable(),
  contact_phone: z.string().nullable(),
  status: ReservationRequestStatusSchema,
  created_at: z.string().datetime(),
});
export type ReservationRequest = z.infer<typeof ReservationRequestSchema>;

export const RequestRestaurantCreateSchema = z.object({
  request_id: z.string().uuid(),
  restaurant_id: z.string().uuid(),
  priority: z.number().int().min(1).default(1),
});
export type RequestRestaurantCreate = z.infer<typeof RequestRestaurantCreateSchema>;

export const RequestRestaurantSchema = z.object({
  id: z.string().uuid(),
  request_id: z.string().uuid(),
  restaurant_id: z.string().uuid(),
  priority: z.number().int(),
});
export type RequestRestaurant = z.infer<typeof RequestRestaurantSchema>;

// ============================================
// CALL SCHEMAS (Enhanced with context)
// ============================================

export const CallStatusSchema = z.enum(["ongoing", "completed", "failed"]);
export type CallStatus = z.infer<typeof CallStatusSchema>;

export const CallCreateSchema = z.object({
  twilio_sid: z.string(),
  request_id: z.string().uuid().nullable().optional(),
  restaurant_id: z.string().uuid().nullable().optional(),
});
export type CallCreate = z.infer<typeof CallCreateSchema>;

export const CallSchema = z.object({
  id: z.string().uuid(),
  twilio_sid: z.string(),
  request_id: z.string().uuid().nullable(),
  restaurant_id: z.string().uuid().nullable(),
  status: CallStatusSchema,
  failure_reason: z.string().nullable(),
  duration_seconds: z.number().int().nullable(),
  transcript_summary: z.string().nullable(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});
export type Call = z.infer<typeof CallSchema>;

export const CallUpdateSchema = z.object({
  status: CallStatusSchema.optional(),
  failure_reason: z.string().nullable().optional(),
  duration_seconds: z.number().int().nullable().optional(),
  transcript_summary: z.string().nullable().optional(),
});
export type CallUpdate = z.infer<typeof CallUpdateSchema>;

// ============================================
// RESERVATION SCHEMAS (Enhanced with context)
// ============================================

export const ReservationStatusSchema = z.enum([
  "confirmed",
  "cancelled",
  "completed",
  "no_show",
]);
export type ReservationStatus = z.infer<typeof ReservationStatusSchema>;

export const ReservationCreateSchema = z.object({
  call_id: z.string().uuid(),
  request_id: z.string().uuid().nullable().optional(),
  restaurant_id: z.string().uuid().nullable().optional(),
  user_id: z.string().uuid().nullable().optional(),
  restaurant_name: z.string(),
  party_size: z.number().int().min(1).max(20),
  confirmed_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  confirmed_time: z.string().regex(/^\d{2}:\d{2}$/),
  confirmation_code: z.string().nullable().optional(),
  status: ReservationStatusSchema.default("confirmed"),
  notes: z.string().nullable().optional(),
});
export type ReservationCreate = z.infer<typeof ReservationCreateSchema>;

export const ReservationSchema = z.object({
  id: z.string().uuid(),
  call_id: z.string().uuid(),
  request_id: z.string().uuid().nullable(),
  restaurant_id: z.string().uuid().nullable(),
  user_id: z.string().uuid().nullable(),
  restaurant_name: z.string(),
  party_size: z.number().int(),
  confirmed_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  confirmed_time: z.string().regex(/^\d{2}:\d{2}$/),
  confirmation_code: z.string().nullable(),
  status: ReservationStatusSchema,
  notes: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type Reservation = z.infer<typeof ReservationSchema>;

export const ReservationWithDetailsSchema = z.object({
  id: z.string().uuid(),
  call_id: z.string().uuid(),
  request_id: z.string().uuid().nullable(),
  restaurant_id: z.string().uuid().nullable(),
  user_id: z.string().uuid().nullable(),
  restaurant_name: z.string(),
  restaurant_phone: z.string().nullable(),
  restaurant_address: z.string().nullable(),
  party_size: z.number().int(),
  confirmed_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  confirmed_time: z.string().regex(/^\d{2}:\d{2}$/),
  confirmation_code: z.string().nullable(),
  status: ReservationStatusSchema,
  notes: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type ReservationWithDetails = z.infer<typeof ReservationWithDetailsSchema>;

// ============================================
// TOOL RESPONSE SCHEMAS
// ============================================

export const SaveBookingResponseSchema = z.object({
  success: z.boolean(),
  reservation_id: z.string().nullable().optional(),
  message: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});
export type SaveBookingResponse = z.infer<typeof SaveBookingResponseSchema>;

export const NoAvailabilityResponseSchema = z.object({
  success: z.boolean(),
  reason: z.string(),
  alternative_offered: z.string().nullable().optional(),
  should_try_alternative: z.boolean().default(false),
});
export type NoAvailabilityResponse = z.infer<typeof NoAvailabilityResponseSchema>;

export const EndCallResponseSchema = z.object({
  success: z.boolean(),
  reason: z.string(),
  call_summary: z.string().nullable().optional(),
});
export type EndCallResponse = z.infer<typeof EndCallResponseSchema>;

// ============================================
// LEGACY SUPPORT (for backward compatibility)
// ============================================

export const LegacyReservationRequestSchema = z.object({
  user_name: z.string().min(1),
  restaurant_phone: z.string(),
  party_size: z.number().int().min(1).max(20),
  preferred_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  preferred_time: z.string().regex(/^\d{2}:\d{2}$/),
  contact_phone: z.string(),
});
export type LegacyReservationRequest = z.infer<typeof LegacyReservationRequestSchema>;
