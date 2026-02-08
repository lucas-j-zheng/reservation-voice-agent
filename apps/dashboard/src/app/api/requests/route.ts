import { NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase/server";
import { RequestTypeSchema } from "@sam/api-contracts";
import { VOICE_ENGINE_URL } from "@/lib/constants";

const DETAIL_TABLE_MAP: Record<string, string> = {
  reservation: "reservation_details",
  info_query: "info_query_details",
  event_inquiry: "event_inquiry_details",
  cancellation: "cancellation_details",
};

export async function GET(request: NextRequest) {
  try {
    const supabase = getSupabaseClient();
    const { searchParams } = new URL(request.url);
    const type = searchParams.get("type");
    const status = searchParams.get("status");

    let query = supabase
      .from("requests")
      .select("*, request_restaurants(*, restaurants(*))")
      .order("created_at", { ascending: false });

    if (type) query = query.eq("type", type);
    if (status) query = query.eq("status", status);

    const { data, error } = await query;
    if (error) throw error;
    return NextResponse.json(data);
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { type, details, restaurant_ids } = body;

    // Validate type
    RequestTypeSchema.parse(type);
    if (!restaurant_ids || !Array.isArray(restaurant_ids) || restaurant_ids.length === 0) {
      return NextResponse.json({ error: "At least one restaurant is required" }, { status: 400 });
    }

    const supabase = getSupabaseClient();

    // 1. Create base request
    const { data: req, error: reqError } = await supabase
      .from("requests")
      .insert({ type, status: "pending" })
      .select()
      .single();

    if (reqError) throw reqError;

    // 2. Create type-specific details
    const detailTable = DETAIL_TABLE_MAP[type];
    if (detailTable && details) {
      const { error: detailError } = await supabase
        .from(detailTable)
        .insert({ ...details, request_id: req.id });

      if (detailError) throw detailError;
    }

    // 3. Create request_restaurants with priority
    const restaurantRows = restaurant_ids.map((rid: string, i: number) => ({
      request_id: req.id,
      restaurant_id: rid,
      priority: i + 1,
    }));

    const { error: rrError } = await supabase
      .from("request_restaurants")
      .insert(restaurantRows);

    if (rrError) throw rrError;

    // 4. Try to proxy to voice-engine cascade API (best-effort)
    let cascadeStarted = false;
    try {
      const cascadeRes = await fetch(`${VOICE_ENGINE_URL}/api/cascade/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: req.id }),
        signal: AbortSignal.timeout(3000),
      });
      if (cascadeRes.ok) {
        cascadeStarted = true;
        await supabase
          .from("requests")
          .update({ status: "in_progress" })
          .eq("id", req.id);
      }
    } catch {
      // Voice engine not available - that's fine, request is saved
    }

    return NextResponse.json(
      { ...req, cascade_started: cascadeStarted },
      { status: 201 }
    );
  } catch (e: unknown) {
    if (e instanceof Error && e.name === "ZodError") {
      return NextResponse.json({ error: "Invalid input", details: e }, { status: 400 });
    }
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
