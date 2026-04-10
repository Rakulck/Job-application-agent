import { supabase } from "@/lib/supabase";
import DashboardClient from "@/app/components/DashboardClient";
import AutoRefresh from "@/app/components/AutoRefresh";

export const dynamic = "force-dynamic";

async function getData() {
  const [{ data: applications }, { data: resumes }, { data: jobs }] = await Promise.all([
    supabase.from("applications").select("*").order("applied_at", { ascending: false }),
    supabase.from("resumes").select("job_id, pdf_url, ats_score, missing_keywords"),
    supabase.from("jobs").select("*").order("created_at", { ascending: false }),
  ]);

  return { jobs: jobs ?? [], applications: applications ?? [], resumes: resumes ?? [] };
}

export default async function Dashboard() {
  const { jobs, applications, resumes } = await getData();

  const lastRefreshed = new Date().toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <main className="min-h-screen bg-gray-50">
      <AutoRefresh />
      <DashboardClient
        jobs={jobs}
        applications={applications}
        resumes={resumes}
        lastRefreshed={lastRefreshed}
      />
    </main>
  );
}
