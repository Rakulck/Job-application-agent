import { NextResponse } from "next/server";

const VM_API_URL = process.env.NEXT_PUBLIC_VM_API_URL || "http://35.188.135.12:8000";
const TRIGGER_API_KEY = process.env.TRIGGER_API_KEY || "";

export async function POST() {
  if (!TRIGGER_API_KEY) {
    console.error("[run-pipeline] TRIGGER_API_KEY not set");
    return NextResponse.json(
      { status: "error", message: "Server not configured: missing TRIGGER_API_KEY" },
      { status: 500 }
    );
  }

  try {
    console.log(`[run-pipeline] calling ${VM_API_URL}/trigger`);
    const res = await fetch(`${VM_API_URL}/trigger`, {
      method: "POST",
      headers: { "X-API-Key": TRIGGER_API_KEY },
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      console.error("[run-pipeline] remote error:", res.status, errorData);
      return NextResponse.json(
        { status: "error", message: errorData.detail || "Remote API error" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json({ status: "started", ...data }, { status: 200 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[run-pipeline] failed to call remote API:", message);
    return NextResponse.json(
      { status: "error", message },
      { status: 500 }
    );
  }
}
