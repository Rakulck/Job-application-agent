"use client";

import { useState } from "react";
import StatsCards from "./StatsCards";
import JobsTable from "./JobsTable";

type Role = "all" | "frontend_developer" | "software_developer" | "web_developer" | "react_developer" | "fullstack_developer";

const TABS: { role: Role; label: string }[] = [
  { role: "all", label: "All Roles" },
  { role: "frontend_developer", label: "Frontend Developer" },
  { role: "software_developer", label: "Software Developer" },
  { role: "web_developer", label: "Web Developer" },
  { role: "react_developer", label: "React Developer" },
  { role: "fullstack_developer", label: "Full Stack Developer" },
];

interface Job {
  job_id: string;
  title: string;
  company: string;
  location: string;
  job_url: string;
  detected_role?: string;
  created_at: string;
}

interface Application {
  job_id: string;
  status: string;
  resume_pdf_url: string;
  error_message: string;
  applied_at: string;
}

interface Resume {
  job_id: string;
  pdf_url: string;
  ats_score?: number;
  missing_keywords?: string[];
}

export default function DashboardClient({
  jobs,
  applications,
  resumes,
  lastRefreshed,
}: {
  jobs: Job[];
  applications: Application[];
  resumes: Resume[];
  lastRefreshed: string;
}) {
  const [selectedRole, setSelectedRole] = useState<Role>("all");

  type PipelineStatus = "idle" | "loading" | "started" | "error" | "already_running";
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>("idle");
  const [pipelineMessage, setPipelineMessage] = useState<string>("");

  const filteredJobs =
    selectedRole === "all"
      ? jobs
      : jobs.filter((j) => j.detected_role === selectedRole);

  const filteredJobIds = new Set(filteredJobs.map((j) => j.job_id));
  const filteredApps = applications.filter((a) => filteredJobIds.has(a.job_id));

  const appMap = Object.fromEntries(filteredApps.map((a) => [a.job_id, a.status]));

  const stats = {
    total: filteredJobs.length,
    applied: filteredApps.filter((a) => a.status === "applied").length,
    pending: filteredJobs.filter((j) => !appMap[j.job_id]).length,
    skipped: filteredApps.filter((a) => a.status === "skipped").length,
    failed: filteredApps.filter((a) => a.status === "failed" || a.status === "captcha_blocked").length,
  };

  async function handleRunPipeline() {
    setPipelineStatus("loading");
    setPipelineMessage("");

    try {
      const res = await fetch("/api/run-pipeline", { method: "POST" });
      const data = await res.json();

      if (res.status === 409) {
        setPipelineStatus("already_running");
        setPipelineMessage("Pipeline is already running.");
      } else if (!res.ok) {
        setPipelineStatus("error");
        setPipelineMessage(data.message ?? "Failed to start pipeline.");
      } else {
        setPipelineStatus("started");
        setPipelineMessage("Pipeline started — dashboard updates automatically as jobs arrive.");
        // Auto-reset button after 6 seconds so it can be triggered again
        setTimeout(() => setPipelineStatus("idle"), 6000);
      }
    } catch {
      setPipelineStatus("error");
      setPipelineMessage("Network error — could not reach the API.");
    }
  }

  const getNextRunTime = () => {
    // Calculate next run as current time + 1 hour
    const now = new Date();
    const nextRun = new Date(now.getTime() + 60 * 60 * 1000); // Add 1 hour from now
    return nextRun.toLocaleString("en-US", {
      timeZone: "America/Los_Angeles",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Job Application Agent</h1>
          <p className="text-gray-500 text-sm mt-1">
            Last refreshed: {lastRefreshed} PST &mdash; updates live when pipeline runs
          </p>
          {pipelineMessage && (
            <p className={`text-sm mt-1 font-medium ${
              pipelineStatus === "started"
                ? "text-green-600"
                : pipelineStatus === "already_running"
                ? "text-yellow-600"
                : pipelineStatus === "error"
                ? "text-red-600"
                : "text-gray-500"
            }`}>
              {pipelineMessage}
            </p>
          )}
        </div>

        {/* Run Pipeline button and schedule */}
        <div className="shrink-0 flex flex-col items-end gap-2">
          <button
            onClick={handleRunPipeline}
            disabled={pipelineStatus === "loading" || pipelineStatus === "already_running"}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors
              ${
                pipelineStatus === "loading" || pipelineStatus === "already_running"
                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                  : pipelineStatus === "started"
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : pipelineStatus === "error"
                  ? "bg-red-50 text-red-700 border border-red-200 hover:bg-red-100"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
          >
            {pipelineStatus === "loading" ? (
              <>
                {/* Minimal inline spinner */}
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4l-3 3-3-3h4z"
                  />
                </svg>
                Starting…
              </>
            ) : pipelineStatus === "started" ? (
              "Pipeline Running"
            ) : pipelineStatus === "already_running" ? (
              "Already Running"
            ) : (
              "Run Pipeline"
            )}
          </button>
          <p className="text-xs text-gray-500">
            Next run: {getNextRunTime()} PST · Every 1 hour
          </p>
        </div>
      </div>

      {/* Role Tabs */}
      <div className="flex gap-0 mb-6 border-b border-gray-200">
        {TABS.map(({ role, label }) => (
          <button
            key={role}
            onClick={() => setSelectedRole(role)}
            className={`px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px
              ${selectedRole === role
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
          >
            {label}
            {role !== "all" && (
              <span className={`ml-1.5 text-xs rounded-full px-1.5 py-0.5
                ${selectedRole === role ? "bg-blue-100 text-blue-600" : "bg-gray-100 text-gray-500"}`}>
                {jobs.filter((j) => j.detected_role === role).length}
              </span>
            )}
          </button>
        ))}
      </div>

      <StatsCards stats={stats} />

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
        <JobsTable jobs={filteredJobs} applications={filteredApps} resumes={resumes} selectedRole={selectedRole} nextRunTime={getNextRunTime()} />
      </div>
    </div>
  );
}
