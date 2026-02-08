/**
 * Seed script for dashboard demo data.
 * Run: npx tsx scripts/seed.ts
 *
 * Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.
 */

import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { createClient } from "@supabase/supabase-js";

// Load env file (Next.js does this automatically, but tsx doesn't)
const __dirname = dirname(fileURLToPath(import.meta.url));
const dashboardRoot = resolve(__dirname, "..");
for (const name of [".env.local", ".env"]) {
  try {
    const envContent = readFileSync(resolve(dashboardRoot, name), "utf-8");
    for (const line of envContent.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      const k = trimmed.slice(0, eqIdx);
      const v = trimmed.slice(eqIdx + 1);
      if (!process.env[k]) process.env[k] = v;
    }
    break;
  } catch {
    continue;
  }
}

const url = process.env.SUPABASE_URL;
const key = process.env.SUPABASE_SERVICE_KEY;

if (!url || !key) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY");
  process.exit(1);
}

const supabase = createClient(url, key);

async function seed() {
  console.log("Seeding restaurants...");

  const restaurants = [
    { name: "Nobu Malibu", phone: "+13103174903", address: "22706 Pacific Coast Hwy, Malibu, CA", cuisine_type: "Japanese", notes: "Celebrity hotspot, ocean views" },
    { name: "Sushi Roku", phone: "+13102587337", address: "8445 W 3rd St, Los Angeles, CA", cuisine_type: "Japanese", notes: "Trendy sushi bar" },
    { name: "Bestia", phone: "+12135145724", address: "2121 E 7th Pl, Los Angeles, CA", cuisine_type: "Italian", notes: "Reservations fill up fast" },
    { name: "Republique", phone: "+13103624115", address: "624 S La Brea Ave, Los Angeles, CA", cuisine_type: "French", notes: "Beautiful pastries, great brunch" },
    { name: "Gjelina", phone: "+13104501429", address: "1429 Abbot Kinney Blvd, Venice, CA", cuisine_type: "American", notes: "Walk-ins only, no reservations by phone" },
  ];

  const { data: insertedRestaurants, error: rError } = await supabase
    .from("restaurants")
    .insert(restaurants)
    .select();

  if (rError) {
    console.error("Restaurant insert error:", rError.message);
    // Continue - restaurants might already exist
  } else {
    console.log(`Inserted ${insertedRestaurants?.length ?? 0} restaurants`);
  }

  // Fetch all restaurants for reference
  const { data: allRestaurants } = await supabase
    .from("restaurants")
    .select("id, name")
    .order("created_at");

  if (!allRestaurants || allRestaurants.length === 0) {
    console.log("No restaurants found. Skipping request/reservation seeding.");
    return;
  }

  console.log("Seeding a sample reservation request...");

  // Create a reservation request
  const { data: req } = await supabase
    .from("requests")
    .insert({ type: "reservation", status: "completed" })
    .select()
    .single();

  if (req) {
    // Add details
    await supabase.from("reservation_details").insert({
      request_id: req.id,
      party_size: 4,
      requested_date: "2026-03-15",
      time_range_start: "19:00",
      time_range_end: "21:00",
      special_requests: "Window seat preferred",
    });

    // Add restaurants
    await supabase.from("request_restaurants").insert(
      allRestaurants.slice(0, 2).map((r, i) => ({
        request_id: req.id,
        restaurant_id: r.id,
        priority: i + 1,
      }))
    );

    // Create a mock call + reservation
    const { data: call } = await supabase
      .from("calls")
      .insert({
        twilio_sid: `SEED_${Date.now()}`,
        request_id: req.id,
        restaurant_id: allRestaurants[1].id,
        status: "completed",
        transcript_summary: "Booked table for 4 at 7:30 PM",
      })
      .select()
      .single();

    if (call) {
      await supabase.from("reservations").insert({
        call_id: call.id,
        request_id: req.id,
        restaurant_id: allRestaurants[1].id,
        restaurant_name: allRestaurants[1].name,
        party_size: 4,
        confirmed_date: "2026-03-15",
        confirmed_time: "19:30",
        confirmation_code: "SR-4821",
        status: "confirmed",
      });
    }

    console.log("Created reservation request + reservation");
  }

  // Create an info query request
  console.log("Seeding an info query request...");
  const { data: infoReq } = await supabase
    .from("requests")
    .insert({ type: "info_query", status: "completed" })
    .select()
    .single();

  if (infoReq) {
    await supabase.from("info_query_details").insert({
      request_id: infoReq.id,
      query_categories: ["hours", "menu", "dietary"],
      specific_questions: "Do they have a kids menu?",
    });

    await supabase.from("request_restaurants").insert(
      allRestaurants.slice(0, 2).map((r, i) => ({
        request_id: infoReq.id,
        restaurant_id: r.id,
        priority: i + 1,
      }))
    );

    // Mock info results
    const { data: infoCall } = await supabase
      .from("calls")
      .insert({
        twilio_sid: `SEED_INFO_${Date.now()}`,
        request_id: infoReq.id,
        restaurant_id: allRestaurants[0].id,
        status: "completed",
      })
      .select()
      .single();

    if (infoCall) {
      await supabase.from("info_results").insert({
        call_id: infoCall.id,
        request_id: infoReq.id,
        restaurant_id: allRestaurants[0].id,
        operating_hours: "Mon-Fri 11am-10pm, Sat-Sun 10am-11pm",
        wait_time_minutes: 15,
        menu_highlights: "Omakase, Black Cod Miso, Yellowtail Sashimi",
        pricing_info: "$$$ - Entrees $25-65",
        dietary_options: { vegan: true, gluten_free: true, halal: false, vegetarian: true },
        facilities: { outdoor: true, private_rooms: true, wheelchair: true, parking: true },
        raw_notes: "They do have a kids menu with smaller portions. Outdoor seating on the patio with ocean views.",
      });
    }

    console.log("Created info query request + results");
  }

  console.log("Seed complete!");
}

seed().catch(console.error);
