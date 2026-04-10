"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AutoRefresh() {
  const router = useRouter();

  useEffect(() => {
    const channel = supabase
      .channel("pipeline-updates")
      .on("postgres_changes", { event: "*", schema: "public", table: "jobs" }, () => {
        router.refresh();
      })
      .on("postgres_changes", { event: "*", schema: "public", table: "applications" }, () => {
        router.refresh();
      })
      .on("postgres_changes", { event: "*", schema: "public", table: "resumes" }, () => {
        router.refresh();
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [router]);

  return null;
}
