import { NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  try {
    const supabase = getSupabaseClient();
    const { searchParams } = new URL(request.url);
    const requestId = searchParams.get("request_id");

    let query = supabase
      .from("info_results")
      .select("*, restaurants(name, phone, cuisine_type)")
      .order("created_at", { ascending: false });

    if (requestId) query = query.eq("request_id", requestId);

    const { data, error } = await query;
    if (error) throw error;
    return NextResponse.json(data);
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
