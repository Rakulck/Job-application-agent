"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";

const PAGE_SIZE = 10;

interface Application {
  id: string;
  job_id: string;
  status: string;
  resume_pdf_url: string;
  error_message: string;
  applied_at: string;
}

interface Job {
  job_id: string;
  title: string;
  company: string;
  job_url: string;
}

interface UnansweredQuestion {
  job_id: string;
  count: number;
}

export default function ApplicationsTable({
  applications,
  jobs,
}: {
  applications: Application[];
  jobs: Job[];
}) {
  const [page, setPage] = useState(1);
  const [unansweredQuestions, setUnansweredQuestions] = useState<Map<string, number>>(new Map());
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const jobMap = Object.fromEntries(jobs.map((j) => [j.job_id, j]));

  useEffect(() => {
    loadUnansweredQuestions();
  }, [applications]);

  async function loadUnansweredQuestions() {
    try {
      const { data, error } = await supabase
        .from("unknown_questions")
        .select("job_id")
        .is("answer", null);

      if (error) {
        console.error("Supabase error:", error);
        return;
      }

      const counts = new Map<string, number>();
      (data || []).forEach((q: { job_id: string }) => {
        counts.set(q.job_id, (counts.get(q.job_id) || 0) + 1);
      });
      console.log("Unanswered questions loaded:", Object.fromEntries(counts));
      setUnansweredQuestions(counts);
    } catch (err) {
      console.error("Failed to load unanswered questions:", err);
    }
  }

  async function handleRetry(jobId: string) {
    setRetryingJobId(jobId);
    try {
      const response = await fetch("/api/retry-application", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId }),
      });

      const result = await response.json();
      if (!response.ok) {
        alert(`Retry failed: ${result.error}`);
      } else {
        alert("Retry started! Check dashboard for updates.");
        // Refresh data after a delay
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      }
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setRetryingJobId(null);
    }
  }

  const statusBadge = (s: string) => {
    if (s === "applied") return <span className="text-xs text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full">Applied</span>;
    if (s === "skipped") return <span className="text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2 py-0.5 rounded-full">Skipped</span>;
    if (s === "captcha_blocked") return <span className="text-xs text-orange-600 bg-orange-50 border border-orange-200 px-2 py-0.5 rounded-full">Captcha</span>;
    return <span className="text-xs text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">Failed</span>;
  };

  const sorted = [...applications].sort(
    (a, b) => new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime()
  );
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Applications</h2>
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Posting</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Applied At</th>
              <th className="px-4 py-3 font-medium">Resume</th>
              <th className="px-4 py-3 font-medium">Unanswered Q</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">No applications yet.</td>
              </tr>
            )}
            {paginated.map((app) => {
              const job = jobMap[app.job_id];
              const unansweredCount = unansweredQuestions.get(app.job_id) || 0;
              const isFailed = app.status === "failed" || app.status === "captcha_blocked" || app.status === "skipped";
              return (
                <tr key={app.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-800">{job?.title ?? app.job_id}</td>
                  <td className="px-4 py-3 text-gray-600">{job?.company ?? "—"}</td>
                  <td className="px-4 py-3">
                    {job?.job_url ? (
                      <a
                        href={job.job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs"
                      >
                        View
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">{statusBadge(app.status)}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(app.applied_at).toISOString().replace("T", " ").slice(0, 16)} UTC
                  </td>
                  <td className="px-4 py-3">
                    {app.resume_pdf_url ? (
                      <a
                        href={app.resume_pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs"
                      >
                        View PDF
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {unansweredCount > 0 ? (
                      <span className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-1 rounded-full">
                        {unansweredCount}
                      </span>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {isFailed && unansweredCount > 0 ? (
                      <button
                        onClick={() => handleRetry(app.job_id)}
                        disabled={retryingJobId === app.job_id}
                        className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {retryingJobId === app.job_id ? "Retrying..." : "Retry"}
                      </button>
                    ) : isFailed ? (
                      <a
                        href={job?.job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Apply Manually
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
        <span>{applications.length} applications total</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(p => p - 1)}
            disabled={page === 1}
            className="px-2 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
          >&#8249;</button>
          <span>{page} of {totalPages}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= totalPages}
            className="px-2 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
          >&#8250;</button>
        </div>
      </div>

      {/* DEBUG: Show unanswered questions count */}
      {unansweredQuestions.size > 0 && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
          <strong>Debug:</strong> Found {unansweredQuestions.size} jobs with unanswered questions:{" "}
          {Array.from(unansweredQuestions.entries())
            .map(([jobId, count]) => `${jobId} (${count})`)
            .join(", ")}
        </div>
      )}
    </div>
  );
}
