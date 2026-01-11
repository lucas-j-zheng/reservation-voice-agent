-- MVP Database Schema
-- Run this on first startup to initialize tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table: Calls (Audit Log)
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twilio_sid TEXT UNIQUE,
    status TEXT CHECK (status IN ('ongoing', 'completed', 'failed')),
    transcript_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: Reservations (The Result)
CREATE TABLE IF NOT EXISTS reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    restaurant_name TEXT NOT NULL,
    party_size INT NOT NULL CHECK (party_size > 0 AND party_size <= 20),
    confirmed_time TIMESTAMPTZ NOT NULL,
    confirmation_code TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for looking up reservations by call
CREATE INDEX IF NOT EXISTS idx_reservations_call_id ON reservations(call_id);

-- Index for looking up calls by Twilio SID
CREATE INDEX IF NOT EXISTS idx_calls_twilio_sid ON calls(twilio_sid);
