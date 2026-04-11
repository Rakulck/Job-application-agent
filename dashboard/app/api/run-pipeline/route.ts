import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export async function POST() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  const supabase = createClient(url, key);

  const { error } = await supabase
    .from("profile")
    .update({ pipeline_trigger: true })
    .eq("id", 1);

  if (error) {
    console.error("[run-pipeline] failed to set trigger:", error.message);
    return NextResponse.json({ status: "error", message: error.message }, { status: 500 });
  }

  return NextResponse.json({ status: "started", message: "Pipeline trigger set — local scheduler will pick it up within 15 seconds" });
}
