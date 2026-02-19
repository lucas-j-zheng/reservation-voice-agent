-- Migration: Add cascade orchestration support
-- Run this against your Supabase SQL editor

-- 1. Add cascade columns to request_restaurants
ALTER TABLE request_restaurants
  ADD COLUMN IF NOT EXISTS attempt_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS attempt_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_call_id UUID REFERENCES calls(id),
  ADD COLUMN IF NOT EXISTS failure_reason TEXT,
  ADD COLUMN IF NOT EXISTS attempted_at TIMESTAMPTZ;

-- 2. Add cascade columns to requests
ALTER TABLE requests
  ADD COLUMN IF NOT EXISTS cascade_status TEXT NOT NULL DEFAULT 'idle',
  ADD COLUMN IF NOT EXISTS current_restaurant_idx INT NOT NULL DEFAULT 0;

-- 3. Add columns to calls
ALTER TABLE calls
  ADD COLUMN IF NOT EXISTS twilio_status TEXT,
  ADD COLUMN IF NOT EXISTS attempt_number INT NOT NULL DEFAULT 1;

-- 4. Create cascade_events table
CREATE TABLE IF NOT EXISTS cascade_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    restaurant_id UUID REFERENCES restaurants(id),
    call_id UUID REFERENCES calls(id),
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    channel TEXT NOT NULL DEFAULT 'sms',
    notification_type TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Indexes
CREATE INDEX IF NOT EXISTS idx_cascade_events_request_id ON cascade_events(request_id);
CREATE INDEX IF NOT EXISTS idx_cascade_events_event_type ON cascade_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cascade_events_created_at ON cascade_events(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_request_id ON notifications(request_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_request_restaurants_attempt_status ON request_restaurants(attempt_status);
