"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";

const PAGE_SIZE = 10;

interface Job {
  job_id: string;
  title: string;
  company: string;
  location: string;
  job_url: string;
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

export default function JobsTable({
  jobs,
  applications,
  resumes,
  selectedRole,
  nextRunTime,
}: {
  jobs: Job[];
  applications: Application[];
  resumes: Resume[];
  selectedRole?: string;
  nextRunTime: string;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [popup, setPopup] = useState<{ reason: string; label: string } | null>(null);
  const [unansweredQuestions, setUnansweredQuestions] = useState<Map<string, number>>(new Map());
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [questionsModal, setQuestionsModal] = useState<{ jobId: string; jobTitle: string } | null>(null);
  const [jobQuestions, setJobQuestions] = useState<any[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [answerInputs, setAnswerInputs] = useState<Record<string, string>>({});

  useEffect(() => { setPage(1); }, [search]);
  useEffect(() => { setSearch(""); setPage(1); }, [selectedRole]);

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

  async function handleOpenQuestions(jobId: string, jobTitle: string) {
    setQuestionsModal({ jobId, jobTitle });
    setLoadingQuestions(true);
    setAnswerInputs({});

    try {
      const { data, error } = await supabase
        .from("unknown_questions")
        .select("*")
        .eq("job_id", jobId)
        .is("answer", null)
        .order("detected_at", { ascending: false });

      if (error) {
        console.error("Failed to load questions:", error);
        setJobQuestions([]);
      } else {
        setJobQuestions(data || []);
      }
    } catch (err) {
      console.error("Error loading questions:", err);
      setJobQuestions([]);
    } finally {
      setLoadingQuestions(false);
    }
  }

  async function handleSaveAnswer(questionId: string, questionLabel: string, answer: string) {
    if (!answer.trim()) {
      alert("Please provide an answer");
      return;
    }

    try {
      // Update the unknown_questions row
      const { error } = await supabase
        .from("unknown_questions")
        .update({ answer: answer.trim() })
        .eq("id", questionId);

      if (error) throw error;

      // Merge into profile.screening_answers
      const { data: profileData } = await supabase
        .from("profile")
        .select("screening_answers")
        .eq("id", 1)
        .single();

      const existing = profileData?.screening_answers ?? {};
      const key = questionLabel.toLowerCase().trim().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
      const updated = { ...existing, [key]: answer.trim() };

      const { error: mergeErr } = await supabase
        .from("profile")
        .update({ screening_answers: updated })
        .eq("id", 1);

      if (mergeErr) throw mergeErr;

      // Remove from local list
      setJobQuestions((prev) => prev.filter((q) => q.id !== questionId));
    } catch (err) {
      alert(`Error saving answer: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  }

  async function handleRetry(jobId: string) {
    setRetryingJobId(jobId);
    setQuestionsModal(null);

    try {
      const response = await fetch("/api/retry-application", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId }),
      });

      const result = await response.json();
      if (response.ok) {
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } else {
        alert(`Retry failed: ${result.error}`);
        setRetryingJobId(null);
      }
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
      setRetryingJobId(null);
    }
  }

  const appMap = Object.fromEntries(applications.map((a) => [a.job_id, a]));
  const resumeMap = Object.fromEntries(resumes.map((r) => [r.job_id, { pdf_url: r.pdf_url, ats_score: r.ats_score, missing_keywords: r.missing_keywords }]));
  const [hoverScore, setHoverScore] = useState<string | null>(null);

  const filtered = jobs.filter(
    (j) =>
      j.title.toLowerCase().includes(search.toLowerCase()) ||
      j.company.toLowerCase().includes(search.toLowerCase())
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const atsBadge = (jobId: string) => {
    const resume = resumeMap[jobId];
    const score = resume?.ats_score;
    const keywords = resume?.missing_keywords || [];

    if (score === undefined || score === null) {
      return <span className="text-xs text-gray-400">—</span>;
    }

    let color = "";
    if (score >= 80) color = "text-green-700 bg-green-50 border-green-200";
    else if (score >= 65) color = "text-yellow-700 bg-yellow-50 border-yellow-200";
    else color = "text-red-600 bg-red-50 border-red-200";

    const hasKeywords = keywords && keywords.length > 0;

    return (
      <div className="relative inline-block group">
        <span className={`text-xs px-2 py-0.5 rounded-full border ${color} ${hasKeywords ? "cursor-help" : ""}`}>
          {score}/100
        </span>
        {hasKeywords && (
          <div className="invisible group-hover:visible absolute bottom-full left-0 mb-2 bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10">
            Missing: {keywords.slice(0, 3).join(", ")}
            {keywords.length > 3 && ` +${keywords.length - 3}`}
            <div className="absolute top-full left-0 w-0 h-0 border-4 border-transparent border-t-gray-800 ml-1"></div>
          </div>
        )}
      </div>
    );
  };

  const statusBadge = (jobId: string) => {
    const app = appMap[jobId];
    const s = app?.status;
    const reason = app?.error_message || s || "";
    const clickable = s && s !== "applied" && s !== "pending";

    const cls = (color: string) =>
      `text-xs px-2 py-0.5 rounded-full border ${color} ${clickable ? "cursor-pointer hover:opacity-80" : ""}`;

    const wrap = (label: string, color: string) =>
      clickable ? (
        <span className={cls(color)} onClick={() => setPopup({ label, reason })}>
          {label}
        </span>
      ) : (
        <span className={cls(color)}>{label}</span>
      );

    if (!s) return wrap("Pending", "text-yellow-600 bg-yellow-50 border-yellow-200");
    if (s === "applied") return wrap("Applied", "text-green-700 bg-green-50 border-green-200");
    if (s === "skipped") return wrap("Skipped", "text-gray-500 bg-gray-50 border-gray-200");
    if (s === "captcha_blocked") return wrap("Captcha", "text-orange-600 bg-orange-50 border-orange-200");
    return wrap("Failed", "text-red-600 bg-red-50 border-red-200");
  };

  return (
    <div>
      {popup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setPopup(null)}>
          <div className="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full mx-4"
            onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-gray-800 mb-2">{popup.label} — Reason</h3>
            <p className="text-sm text-gray-600 break-words">{popup.reason || "No reason recorded."}</p>
            <button onClick={() => setPopup(null)}
              className="mt-4 text-xs text-blue-600 hover:underline">
              Close
            </button>
          </div>
        </div>
      )}

      {/* Questions Modal */}
      {questionsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setQuestionsModal(null)}>
          <div className="bg-white rounded-2xl shadow-xl p-6 max-w-lg w-full mx-4 max-h-96 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              Answer Questions — {questionsModal.jobTitle}
            </h3>

            {loadingQuestions ? (
              <div className="text-center py-8 text-gray-500">Loading questions...</div>
            ) : jobQuestions.length === 0 ? (
              <div className="text-center py-8 text-gray-500">✓ All questions answered!</div>
            ) : (
              <div className="space-y-4">
                {jobQuestions.map((q) => (
                  <div key={q.id} className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                    <label className="text-sm font-medium text-gray-700 block mb-2">
                      {q.question_label}
                    </label>

                    {/* Radio/Select options */}
                    {q.options && q.options.length > 0 && (
                      <div className="mb-3 space-y-2">
                        {q.field_type === "select" ? (
                          <select
                            value={answerInputs[q.id] || ""}
                            onChange={(e) =>
                              setAnswerInputs({ ...answerInputs, [q.id]: e.target.value })
                            }
                            className="w-full px-3 py-2 text-sm text-black border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="" className="text-black">Select option...</option>
                            {q.options.map((opt: string) => (
                              <option key={opt} value={opt} className="text-black">
                                {opt}
                              </option>
                            ))}
                          </select>
                        ) : (
                          q.options.map((opt: string) => (
                            <label key={opt} className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="radio"
                                name={q.id}
                                value={opt}
                                checked={answerInputs[q.id] === opt}
                                onChange={(e) =>
                                  setAnswerInputs({ ...answerInputs, [q.id]: e.target.value })
                                }
                                className="w-4 h-4 text-blue-600"
                              />
                              <span className="text-sm text-black">{opt}</span>
                            </label>
                          ))
                        )}
                      </div>
                    )}

                    {/* Free-text input fallback */}
                    {q.field_type !== "select" && q.field_type !== "radio" && (
                      <input
                        type={["number", "email", "tel"].includes(q.field_type) ? q.field_type : "text"}
                        placeholder="Enter your answer..."
                        value={answerInputs[q.id] || ""}
                        onChange={(e) =>
                          setAnswerInputs({ ...answerInputs, [q.id]: e.target.value })
                        }
                        className="w-full px-3 py-2 text-sm text-black border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-400"
                      />
                    )}

                    {(q.field_type === "radio" || q.field_type === "select") && (
                      <input
                        type="text"
                        placeholder="Or type custom answer..."
                        value={answerInputs[q.id] || ""}
                        onChange={(e) =>
                          setAnswerInputs({ ...answerInputs, [q.id]: e.target.value })
                        }
                        className="w-full mt-2 px-3 py-2 text-sm text-black border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-400"
                      />
                    )}

                    <button
                      onClick={() =>
                        handleSaveAnswer(q.id, q.question_label, answerInputs[q.id] || "")
                      }
                      disabled={!answerInputs[q.id]?.trim()}
                      className="mt-2 w-full px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                    >
                      Save Answer
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-2 mt-6">
              <button
                onClick={() => handleRetry(questionsModal.jobId)}
                disabled={jobQuestions.length > 0 || retryingJobId === questionsModal.jobId}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                {retryingJobId === questionsModal.jobId ? "Retrying..." : "Retry Application"}
              </button>
              <button
                onClick={() => setQuestionsModal(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-800">Applications</h2>
        <input
          type="text"
          placeholder="Search by company name"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-blue-300 rounded-lg px-3 py-1.5 text-sm w-60 text-black placeholder-black focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Title</th>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Location</th>
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Resume</th>
              <th className="px-4 py-3 font-medium">ATS Score</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Unanswered Q</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400">No jobs found.</td>
              </tr>
            )}
            {paginated.map((job) => {
              const app = appMap[job.job_id];
              const resume = resumeMap[job.job_id];
              const pdfUrl = resume?.pdf_url || app?.resume_pdf_url;
              return (
                <tr key={job.job_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <a href={job.job_url} target="_blank" rel="noopener noreferrer"
                      className="text-blue-600 hover:underline font-medium">
                      {job.title}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{job.company}</td>
                  <td className="px-4 py-3 text-gray-500">{job.location || "—"}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {job.created_at ? new Date(job.created_at).toLocaleString("en-US", {
                      month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: true
                    }) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {pdfUrl ? (
                      <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs">View PDF</a>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">{atsBadge(job.job_id)}</td>
                  <td className="px-4 py-3">{statusBadge(job.job_id)}</td>
                  <td className="px-4 py-3">
                    {(() => {
                      const unansweredCount = unansweredQuestions.get(job.job_id) || 0;
                      return unansweredCount > 0 ? (
                        <button
                          onClick={() => handleOpenQuestions(job.job_id, job.title)}
                          className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-1 rounded-full hover:bg-amber-200 cursor-pointer transition-colors"
                        >
                          {unansweredCount}
                        </button>
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-3">
                    {(() => {
                      const isFailed = !app || app.status === "failed" || app.status === "captcha_blocked" || app.status === "skipped";
                      const unansweredCount = unansweredQuestions.get(job.job_id) || 0;
                      return isFailed && unansweredCount > 0 ? (
                        <button
                          onClick={() => handleRetry(job.job_id)}
                          disabled={retryingJobId === job.job_id}
                          className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {retryingJobId === job.job_id ? "Retrying..." : "Retry"}
                        </button>
                      ) : isFailed ? (
                        <a
                          href={job.job_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Apply Manually
                        </a>
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      );
                    })()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
        <span>{filtered.length} jobs total</span>
        <div className="flex items-center gap-2">
          <button onClick={() => setPage(p => p - 1)} disabled={page === 1}
            className="px-2 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">&#8249;</button>
          <span>{page} of {totalPages}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}
            className="px-2 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">&#8250;</button>
        </div>
      </div>
      <p className="text-xs text-gray-400 mt-2">
        Next scrape: {nextRunTime} PST · Every 1 hour
      </p>
    </div>
  );
}
