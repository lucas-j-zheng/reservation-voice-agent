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

-- Table: Reservation Requests (user intent from UI)
CREATE TABLE IF NOT EXISTS reservation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    party_size INT NOT NULL CHECK (party_size > 0 AND party_size <= 20),
    requested_date DATE NOT NULL,
    time_range_start TIME NOT NULL,
    time_range_end TIME NOT NULL,
    special_requests TEXT,
    contact_phone TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: Request-Restaurant Junction (priority ordering)
CREATE TABLE IF NOT EXISTS request_restaurants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES reservation_requests(id) ON DELETE CASCADE,
    restaurant_id UUID REFERENCES restaurants(id) ON DELETE CASCADE,
    priority INT NOT NULL DEFAULT 1,
    UNIQUE(request_id, restaurant_id)
);

-- ============================================
-- OPERATIONAL TABLES
-- ============================================

-- Table: Calls (Audit Log with enhanced context)
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twilio_sid TEXT UNIQUE,
    request_id UUID REFERENCES reservation_requests(id),
    restaurant_id UUID REFERENCES restaurants(id),
    status TEXT CHECK (status IN ('ongoing', 'completed', 'failed')),
    failure_reason TEXT,
    duration_seconds INT,
    transcript_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: Reservations (The Result with richer data)
CREATE TABLE IF NOT EXISTS reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    request_id UUID REFERENCES reservation_requests(id),
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

-- Reservation requests indexes
CREATE INDEX IF NOT EXISTS idx_reservation_requests_user_id ON reservation_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_reservation_requests_status ON reservation_requests(status);
CREATE INDEX IF NOT EXISTS idx_reservation_requests_requested_date ON reservation_requests(requested_date);

-- Request-Restaurant indexes
CREATE INDEX IF NOT EXISTS idx_request_restaurants_request_id ON request_restaurants(request_id);
CREATE INDEX IF NOT EXISTS idx_request_restaurants_restaurant_id ON request_restaurants(restaurant_id);

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Restaurants indexes
CREATE INDEX IF NOT EXISTS idx_restaurants_phone ON restaurants(phone);
CREATE INDEX IF NOT EXISTS idx_restaurants_name ON restaurants(name);
