# Database Toolcalling Enhancement Plan

## Goal
Enhance the database schema and toolcalling to support UI-integrated reservation requests where users can specify time ranges across multiple restaurants.

**Scope**: Full schema enhancement with users, restaurants, reservation_requests tables + enhanced toolcalling.

---

## Current State

**Schema** (`infrastructure/docker/init.sql`):
- `calls`: id, twilio_sid, status, transcript_summary, created_at, updated_at
- `reservations`: id, call_id, restaurant_name, party_size, confirmed_time, confirmation_code, created_at

**Tool** (`apps/voice-engine/src/tools/save_booking.py`):
- `save_booking(restaurant_name, party_size, confirmed_time, confirmation_code)`

---

## Proposed Schema Enhancement

### New Tables

```sql
-- Users (for future auth/UI)
users (id, email, name, phone, created_at)

-- Restaurants (normalized)
restaurants (id, name, phone, address, cuisine_type, notes, created_at)

-- Reservation Requests (user intent)
reservation_requests (
  id, user_id, party_size,
  requested_date,           -- DATE: YYYY-MM-DD
  time_range_start,         -- TIME: 18:00
  time_range_end,           -- TIME: 20:00
  special_requests,         -- "outdoor seating", "birthday"
  contact_phone,
  status,                   -- pending/in_progress/completed/failed/cancelled
  created_at
)

-- Request-Restaurant junction (priority ordering)
request_restaurants (id, request_id, restaurant_id, priority)
```

### Enhanced Tables

```sql
-- calls (add context)
+ request_id UUID REFERENCES reservation_requests(id)
+ restaurant_id UUID REFERENCES restaurants(id)
+ failure_reason TEXT
+ duration_seconds INT

-- reservations (richer data)
+ request_id, restaurant_id, user_id
+ confirmed_date DATE (separate from time)
+ confirmed_time TIME
+ status (confirmed/cancelled/completed/no_show)
+ notes TEXT
```

---

## Updated Toolcalling

### Enhanced `save_booking` Tool
```python
SAVE_BOOKING_SCHEMA = {
    "name": "save_booking",
    "parameters": {
        "properties": {
            "confirmed_date": "string (YYYY-MM-DD)",
            "confirmed_time": "string (HH:MM)",
            "party_size": "integer",
            "confirmation_code": "string (optional)",
            "notes": "string (optional)"
        },
        "required": ["confirmed_date", "confirmed_time", "party_size"]
    }
}
```
- Restaurant derived from call context (no need to ask Gemini)
- Separate date/time for cleaner UI display

### New `report_no_availability` Tool
```python
# When restaurant can't accommodate
report_no_availability(reason, alternative_offered, should_try_alternative)
```

### New `end_call` Tool
```python
# Graceful call end without booking
end_call(reason, call_summary)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `infrastructure/docker/init.sql` | Add new tables, alter existing |
| `libs/api-contracts/python/schemas.py` | New Pydantic models |
| `libs/api-contracts/typescript/schemas.ts` | New Zod schemas |
| `apps/voice-engine/src/tools/save_booking.py` | Update schema, add context |
| `apps/voice-engine/src/tools/__init__.py` | Export new tools |
| `apps/voice-engine/src/brain/gemini_client.py` | Register multiple tools |
| `apps/voice-engine/src/stream/twilio_handler.py` | Handle new tools |

---

## UI Query Examples

```sql
-- Upcoming reservations for user
SELECT r.*, rest.name FROM reservations r
JOIN restaurants rest ON r.restaurant_id = rest.id
WHERE r.user_id = $1 AND r.confirmed_date >= CURRENT_DATE
ORDER BY confirmed_date, confirmed_time;

-- Request status with attempt count
SELECT rr.*, COUNT(c.id) as attempts
FROM reservation_requests rr
LEFT JOIN calls c ON rr.id = c.request_id
WHERE rr.user_id = $1
GROUP BY rr.id;
```

---

## Migration Strategy

**Phase 1**: Add new tables (non-breaking)
**Phase 2**: Add nullable columns to calls/reservations
**Phase 3**: Update application code
**Phase 4**: Backfill data, enforce constraints

---

## Implementation Steps

### Step 1: Database Migration
1. Create migration SQL file with new tables (users, restaurants, reservation_requests, request_restaurants)
2. Add new columns to calls and reservations tables
3. Create indexes for query performance

### Step 2: Python Schemas
1. Add new Pydantic models: User, Restaurant, ReservationRequest, RequestRestaurant
2. Update Call and Reservation models with new fields
3. Add ReservationWithDetails for UI responses

### Step 3: TypeScript Schemas
1. Add corresponding Zod schemas for all new types
2. Export inferred TypeScript types

### Step 4: Tool Implementation
1. Update `save_booking.py` with new schema (date/time split, context-aware)
2. Create `report_no_availability.py` tool
3. Create `end_call.py` tool
4. Update `__init__.py` exports

### Step 5: Gemini Integration
1. Update `gemini_client.py` to register all three tools
2. Update tool response handling

### Step 6: Handler Updates
1. Update `twilio_handler.py` with new tool handlers
2. Pass request context to tools (request_id, restaurant_id)

---

## Verification

1. Reset DB: `docker compose -f infrastructure/docker/docker-compose.yml down -v && docker compose -f infrastructure/docker/docker-compose.yml up -d`
2. Run tests: `cd apps/voice-engine && uv run pytest tests/ -v`
3. Start server: `cd apps/voice-engine && uv run python main.py`
4. Make test call to verify save_booking saves with new schema
5. Query DB to confirm: `SELECT * FROM reservations; SELECT * FROM users;`
