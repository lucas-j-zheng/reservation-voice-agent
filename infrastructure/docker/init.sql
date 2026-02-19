-- Database Schema for Voice Reservation Agent
-- Run this on first startup to initialize tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- CORE ENTITY TABLES
-- ============================================

-- Table: Users (for future auth/UI integration)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    name TEXT NOT NULL,
    phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: Restaurants (normalized restaurant data)
CREATE TABLE IF NOT EXISTS restaurants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT,
    cuisine_type TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- GENERALIZED REQUEST (replaces reservation_requests)
-- ============================================

CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    type TEXT NOT NULL CHECK (type IN ('reservation', 'info_query', 'event_inquiry', 'cancellation')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Junction table (now references requests)
CREATE TABLE IF NOT EXISTS request_restaurants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    restaurant_id UUID REFERENCES restaurants(id) ON DELETE CASCADE,
    priority INT NOT NULL DEFAULT 1,
    UNIQUE(request_id, restaurant_id)
);

-- ============================================
-- TYPE-SPECIFIC INPUT DETAIL TABLES (1:1 with requests)
-- ============================================

-- For type='reservation'
CREATE TABLE IF NOT EXISTS reservation_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    party_size INT NOT NULL CHECK (party_size > 0 AND party_size <= 20),
    requested_date DATE NOT NULL,
    time_range_start TIME NOT NULL,
    time_range_end TIME NOT NULL,
    special_requests TEXT,
    contact_phone TEXT
);

-- For type='info_query'
CREATE TABLE IF NOT EXISTS info_query_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    query_categories TEXT[] NOT NULL,
    specific_questions TEXT,
    facility_categories TEXT[]
);

-- For type='event_inquiry'
CREATE TABLE IF NOT EXISTS event_inquiry_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('birthday', 'anniversary', 'large_party', 'catering', 'event_space')),
    party_size INT CHECK (party_size > 0),
    preferred_date DATE,
    budget_range TEXT,
    details TEXT
);

-- ============================================
-- OPERATIONAL TABLES
-- ============================================

-- Table: Calls (Audit Log with enhanced context)
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twilio_sid TEXT UNIQUE,
    request_id UUID REFERENCES requests(id),
    restaurant_id UUID REFERENCES restaurants(id),
    status TEXT CHECK (status IN ('ongoing', 'completed', 'failed')),
    twilio_status TEXT,
    attempt_number INT NOT NULL DEFAULT 1,
    failure_reason TEXT,
    duration_seconds INT,
    transcript_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TYPE-SPECIFIC OUTCOME/RESULT TABLES
-- ============================================

-- Table: Reservations (outcome of type='reservation')
CREATE TABLE IF NOT EXISTS reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    request_id UUID REFERENCES requests(id),
    restaurant_id UUID REFERENCES restaurants(id),
    user_id UUID REFERENCES users(id),
    restaurant_name TEXT NOT NULL,
    party_size INT NOT NULL CHECK (party_size > 0 AND party_size <= 20),
    confirmed_date DATE NOT NULL,
    confirmed_time TIME NOT NULL,
    confirmation_code TEXT,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled', 'completed', 'no_show')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- For type='cancellation' (placed after reservations since it references it)
CREATE TABLE IF NOT EXISTS cancellation_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    reservation_id UUID REFERENCES reservations(id),
    reason TEXT
);

-- Outcome of type='info_query'
CREATE TABLE IF NOT EXISTS info_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    request_id UUID REFERENCES requests(id),
    restaurant_id UUID REFERENCES restaurants(id),
    operating_hours TEXT,
    wait_time_minutes INT,
    menu_highlights TEXT,
    pricing_info TEXT,
    dietary_options JSONB,
    allergen_info TEXT,
    facilities JSONB,
    raw_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Outcome of type='event_inquiry'
CREATE TABLE IF NOT EXISTS event_inquiry_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    request_id UUID REFERENCES requests(id),
    restaurant_id UUID REFERENCES restaurants(id),
    available BOOLEAN NOT NULL,
    quoted_price TEXT,
    capacity INT,
    details TEXT,
    contact_name TEXT,
    contact_info TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Outcome of type='cancellation'
CREATE TABLE IF NOT EXISTS cancellation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    request_id UUID REFERENCES requests(id),
    reservation_id UUID REFERENCES reservations(id),
    confirmed BOOLEAN NOT NULL,
    cancellation_code TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- CASCADE & NOTIFICATION TABLES
-- ============================================

-- Table: Cascade Events (audit trail for cascade orchestration)
CREATE TABLE IF NOT EXISTS cascade_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES reservation_requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    restaurant_id UUID REFERENCES restaurants(id),
    call_id UUID REFERENCES calls(id),
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: Notifications (SMS/push sent to users)
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES reservation_requests(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    channel TEXT NOT NULL DEFAULT 'sms' CHECK (channel IN ('sms', 'push', 'email')),
    notification_type TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

-- Calls indexes
CREATE INDEX IF NOT EXISTS idx_calls_twilio_sid ON calls(twilio_sid);
CREATE INDEX IF NOT EXISTS idx_calls_request_id ON calls(request_id);
CREATE INDEX IF NOT EXISTS idx_calls_restaurant_id ON calls(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);

-- Reservations indexes
CREATE INDEX IF NOT EXISTS idx_reservations_call_id ON reservations(call_id);
CREATE INDEX IF NOT EXISTS idx_reservations_request_id ON reservations(request_id);
CREATE INDEX IF NOT EXISTS idx_reservations_restaurant_id ON reservations(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_reservations_user_id ON reservations(user_id);
CREATE INDEX IF NOT EXISTS idx_reservations_confirmed_date ON reservations(confirmed_date);

-- Requests indexes
CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_type ON requests(type);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at);

-- Request-Restaurant indexes
CREATE INDEX IF NOT EXISTS idx_request_restaurants_request_id ON request_restaurants(request_id);
CREATE INDEX IF NOT EXISTS idx_request_restaurants_restaurant_id ON request_restaurants(restaurant_id);

-- Detail table indexes
CREATE INDEX IF NOT EXISTS idx_reservation_details_request_id ON reservation_details(request_id);
CREATE INDEX IF NOT EXISTS idx_info_query_details_request_id ON info_query_details(request_id);
CREATE INDEX IF NOT EXISTS idx_event_inquiry_details_request_id ON event_inquiry_details(request_id);
CREATE INDEX IF NOT EXISTS idx_cancellation_details_request_id ON cancellation_details(request_id);

-- Result table indexes
CREATE INDEX IF NOT EXISTS idx_info_results_request_id ON info_results(request_id);
CREATE INDEX IF NOT EXISTS idx_info_results_restaurant_id ON info_results(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_event_inquiry_results_request_id ON event_inquiry_results(request_id);
CREATE INDEX IF NOT EXISTS idx_cancellation_results_request_id ON cancellation_results(request_id);

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Restaurants indexes
CREATE INDEX IF NOT EXISTS idx_restaurants_phone ON restaurants(phone);
CREATE INDEX IF NOT EXISTS idx_restaurants_name ON restaurants(name);

-- Cascade events indexes
CREATE INDEX IF NOT EXISTS idx_cascade_events_request_id ON cascade_events(request_id);
CREATE INDEX IF NOT EXISTS idx_cascade_events_event_type ON cascade_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cascade_events_created_at ON cascade_events(created_at);

-- Notifications indexes
CREATE INDEX IF NOT EXISTS idx_notifications_request_id ON notifications(request_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);

-- Request-Restaurant cascade indexes
CREATE INDEX IF NOT EXISTS idx_request_restaurants_attempt_status ON request_restaurants(attempt_status);
