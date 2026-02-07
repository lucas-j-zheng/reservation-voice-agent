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
// GENERALIZED REQUEST SCHEMAS
// ============================================

export const RequestTypeSchema = z.enum([
  "reservation",
  "info_query",
  "event_inquiry",
  "cancellation",
]);
export type RequestType = z.infer<typeof RequestTypeSchema>;

export const RequestStatusSchema = z.enum([
  "pending",
  "in_progress",
  "completed",
  "failed",
  "cancelled",
]);
export type RequestStatus = z.infer<typeof RequestStatusSchema>;

export const RequestCreateSchema = z.object({
  user_id: z.string().uuid().nullable().optional(),
  type: RequestTypeSchema,
});
export type RequestCreate = z.infer<typeof RequestCreateSchema>;

export const RequestSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid().nullable(),
  type: RequestTypeSchema,
  status: RequestStatusSchema,
  created_at: z.string().datetime(),
});
export type Request = z.infer<typeof RequestSchema>;

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
// TYPE-SPECIFIC DETAIL SCHEMAS
// ============================================

export const ReservationDetailsCreateSchema = z.object({
  request_id: z.string().uuid(),
  party_size: z.number().int().min(1).max(20),
  requested_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  time_range_start: z.string().regex(/^\d{2}:\d{2}$/),
  time_range_end: z.string().regex(/^\d{2}:\d{2}$/),
  special_requests: z.string().nullable().optional(),
  contact_phone: z.string().nullable().optional(),
});
export type ReservationDetailsCreate = z.infer<typeof ReservationDetailsCreateSchema>;

export const ReservationDetailsSchema = z.object({
  id: z.string().uuid(),
  request_id: z.string().uuid(),
  party_size: z.number().int(),
  requested_date: z.string(),
  time_range_start: z.string(),
  time_range_end: z.string(),
  special_requests: z.string().nullable(),
  contact_phone: z.string().nullable(),
});
export type ReservationDetails = z.infer<typeof ReservationDetailsSchema>;

export const QueryCategorySchema = z.enum([
  "hours",
  "wait_times",
  "menu",
  "pricing",
  "dietary",
  "allergens",
  "facilities",
]);
export type QueryCategory = z.infer<typeof QueryCategorySchema>;

export const FacilityCategorySchema = z.enum([
  "outdoor",
  "private_rooms",
  "wheelchair",
  "high_chairs",
  "pet_friendly",
  "parking",
]);
export type FacilityCategory = z.infer<typeof FacilityCategorySchema>;

export const InfoQueryDetailsCreateSchema = z.object({
  request_id: z.string().uuid(),
  query_categories: z.array(QueryCategorySchema).min(1),
  specific_questions: z.string().nullable().optional(),
  facility_categories: z.array(FacilityCategorySchema).optional(),
});
export type InfoQueryDetailsCreate = z.infer<typeof InfoQueryDetailsCreateSchema>;

export const InfoQueryDetailsSchema = z.object({
  id: z.string().uuid(),
  request_id: z.string().uuid(),
  query_categories: z.array(z.string()),
  specific_questions: z.string().nullable(),
  facility_categories: z.array(z.string()).nullable(),
});
export type InfoQueryDetails = z.infer<typeof InfoQueryDetailsSchema>;

export const EventTypeSchema = z.enum([
  "birthday",
  "anniversary",
  "large_party",
  "catering",
  "event_space",
]);
export type EventType = z.infer<typeof EventTypeSchema>;

export const EventInquiryDetailsCreateSchema = z.object({
  request_id: z.string().uuid(),
  event_type: EventTypeSchema,
  party_size: z.number().int().min(1).optional(),
  preferred_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  budget_range: z.string().optional(),
  details: z.string().optional(),
});
export type EventInquiryDetailsCreate = z.infer<typeof EventInquiryDetailsCreateSchema>;

export const EventInquiryDetailsSchema = z.object({
  id: z.string().uuid(),
  request_id: z.string().uuid(),
  event_type: z.string(),
  party_size: z.number().int().nullable(),
  preferred_date: z.string().nullable(),
  budget_range: z.string().nullable(),
  details: z.string().nullable(),
});
export type EventInquiryDetails = z.infer<typeof EventInquiryDetailsSchema>;

export const CancellationDetailsCreateSchema = z.object({
  request_id: z.string().uuid(),
  reservation_id: z.string().uuid(),
  reason: z.string().optional(),
});
export type CancellationDetailsCreate = z.infer<typeof CancellationDetailsCreateSchema>;

export const CancellationDetailsSchema = z.object({
  id: z.string().uuid(),
  request_id: z.string().uuid(),
  reservation_id: z.string().uuid().nullable(),
  reason: z.string().nullable(),
});
export type CancellationDetails = z.infer<typeof CancellationDetailsSchema>;

// ============================================
// CALL SCHEMAS
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
// RESERVATION SCHEMAS (outcome of type='reservation')
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
// TYPE-SPECIFIC RESULT SCHEMAS
// ============================================

export const InfoResultCreateSchema = z.object({
  call_id: z.string().uuid(),
  request_id: z.string().uuid(),
  restaurant_id: z.string().uuid(),
  operating_hours: z.string().nullable().optional(),
  wait_time_minutes: z.number().int().nullable().optional(),
  menu_highlights: z.string().nullable().optional(),
  pricing_info: z.string().nullable().optional(),
  dietary_options: z.record(z.boolean()).nullable().optional(),
  allergen_info: z.string().nullable().optional(),
  facilities: z.record(z.boolean()).nullable().optional(),
  raw_notes: z.string().nullable().optional(),
});
export type InfoResultCreate = z.infer<typeof InfoResultCreateSchema>;

export const InfoResultSchema = z.object({
  id: z.string().uuid(),
  call_id: z.string().uuid(),
  request_id: z.string().uuid(),
  restaurant_id: z.string().uuid(),
  operating_hours: z.string().nullable(),
  wait_time_minutes: z.number().int().nullable(),
  menu_highlights: z.string().nullable(),
  pricing_info: z.string().nullable(),
  dietary_options: z.record(z.boolean()).nullable(),
  allergen_info: z.string().nullable(),
  facilities: z.record(z.boolean()).nullable(),
  raw_notes: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type InfoResult = z.infer<typeof InfoResultSchema>;

export const EventInquiryResultCreateSchema = z.object({
  call_id: z.string().uuid(),
  request_id: z.string().uuid(),
  restaurant_id: z.string().uuid(),
  available: z.boolean(),
  quoted_price: z.string().nullable().optional(),
  capacity: z.number().int().nullable().optional(),
  details: z.string().nullable().optional(),
  contact_name: z.string().nullable().optional(),
  contact_info: z.string().nullable().optional(),
});
export type EventInquiryResultCreate = z.infer<typeof EventInquiryResultCreateSchema>;

export const EventInquiryResultSchema = z.object({
  id: z.string().uuid(),
  call_id: z.string().uuid(),
  request_id: z.string().uuid(),
  restaurant_id: z.string().uuid(),
  available: z.boolean(),
  quoted_price: z.string().nullable(),
  capacity: z.number().int().nullable(),
  details: z.string().nullable(),
  contact_name: z.string().nullable(),
  contact_info: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type EventInquiryResult = z.infer<typeof EventInquiryResultSchema>;

export const CancellationResultCreateSchema = z.object({
  call_id: z.string().uuid(),
  request_id: z.string().uuid(),
  reservation_id: z.string().uuid(),
  confirmed: z.boolean(),
  cancellation_code: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
});
export type CancellationResultCreate = z.infer<typeof CancellationResultCreateSchema>;

export const CancellationResultSchema = z.object({
  id: z.string().uuid(),
  call_id: z.string().uuid(),
  request_id: z.string().uuid(),
  reservation_id: z.string().uuid().nullable(),
  confirmed: z.boolean(),
  cancellation_code: z.string().nullable(),
  notes: z.string().nullable(),
  created_at: z.string().datetime(),
});
export type CancellationResult = z.infer<typeof CancellationResultSchema>;

// ============================================
// CASCADE SCHEMAS
// ============================================

export const CascadeStatusSchema = z.enum([
  "idle",
  "running",
  "paused",
  "completed",
  "exhausted",
  "cancelled",
]);
export type CascadeStatus = z.infer<typeof CascadeStatusSchema>;

export const AttemptStatusSchema = z.enum([
  "pending",
  "calling",
  "succeeded",
  "failed",
  "skipped",
  "no_answer",
]);
export type AttemptStatus = z.infer<typeof AttemptStatusSchema>;

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
