import { NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase/server";

const DETAIL_TABLE_MAP: Record<string, string> = {
  reservation: "reservation_details",
  info_query: "info_query_details",
  event_inquiry: "event_inquiry_details",
  cancellation: "cancellation_details",
};

const RESULT_TABLE_MAP: Record<string, string> = {
  reservation: "reservations",
  info_query: "info_results",
  event_inquiry: "event_inquiry_results",
  cancellation: "cancellation_results",
};

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = getSupabaseClient();

    // Fetch base request with restaurants
    const { data: req, error: reqError } = await supabase
      .from("requests")
      .select("*, request_restaurants(*, restaurants(*))")
      .eq("id", id)
      .single();

    if (reqError) throw reqError;
    if (!req) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    // Fetch type-specific details
    const detailTable = DETAIL_TABLE_MAP[req.type];
    let details = null;
    if (detailTable) {
      const { data } = await supabase
        .from(detailTable)
        .select("*")
        .eq("request_id", id)
        .single();
      details = data;
    }

    // Fetch results
    const resultTable = RESULT_TABLE_MAP[req.type];
    let results = null;
    if (resultTable) {
      const { data } = await supabase
        .from(resultTable)
        .select("*")
        .eq("request_id", id);
      results = data;
    }

    // Fetch calls
    const { data: calls } = await supabase
      .from("calls")
      .select("*")
      .eq("request_id", id)
      .order("created_at", { ascending: true });

    return NextResponse.json({
      ...req,
      details,
      results,
      calls,
    });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
