"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";

interface UnknownQuestion {
  id: string;
  job_id: string;
  question_label: string;
  field_type: string;
  options: string[];
  answer: string | null;
  detected_at: string;
}

interface QuestionGroup {
  label: string;
  field_type: string;
  options: string[];
  ids: string[];
  job_ids: string[];
  answer: string;
}

function buildGroups(rows: UnknownQuestion[]): QuestionGroup[] {
  const map = new Map<string, QuestionGroup>();
  for (const row of rows) {
    const key = row.question_label.toLowerCase().trim();
    if (!map.has(key)) {
      map.set(key, {
        label: row.question_label,
        field_type: row.field_type,
        options: [],
        ids: [],
        job_ids: [],
        answer: "",
      });
    }
    const g = map.get(key)!;
    g.ids.push(row.id);
    g.job_ids.push(row.job_id);
    // Merge options (deduplicate)
    for (const opt of row.options) {
      if (!g.options.includes(opt)) g.options.push(opt);
    }
  }
  return Array.from(map.values());
}

function normalizeToKey(label: string): string {
  return label.toLowerCase().trim().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
}

export default function UnknownQuestionsPanel() {
  const [groups, setGroups] = useState<QuestionGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadQuestions();
  }, []);

  async function loadQuestions() {
    try {
      setLoading(true);
      const { data, error: err } = await supabase
        .from("unknown_questions")
        .select("*")
        .is("answer", null)
        .order("detected_at", { ascending: false });

      if (err) throw err;
      const builtGroups = buildGroups(data || []);
      setGroups(builtGroups);
    } catch (e) {
      setError(`Failed to load questions: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  async function saveAnswer(group: QuestionGroup, answer: string) {
    if (!answer.trim()) {
      setError("Please provide an answer");
      return;
    }

    setSaving(group.label);
    try {
      // 1. Mark all matching unknown_questions rows as answered
      const { error: updateErr } = await supabase
        .from("unknown_questions")
        .update({ answer: answer.trim() })
        .in("id", group.ids);

      if (updateErr) throw updateErr;

      // 2. Merge into profile.screening_answers
      const { data: profileData, error: fetchErr } = await supabase
        .from("profile")
        .select("screening_answers")
        .eq("id", 1)
        .single();

      if (fetchErr) throw fetchErr;

      const existing = profileData?.screening_answers ?? {};
      const key = normalizeToKey(group.label);
      const updated = { ...existing, [key]: answer.trim() };

      const { error: mergeErr } = await supabase
        .from("profile")
        .update({ screening_answers: updated })
        .eq("id", 1);

      if (mergeErr) throw mergeErr;

      // 3. Persist to cached_answers so agent finds it at priority 1 (exact label match)
      // This ensures the answer persists across log_unknown_questions() deletes
      const { error: cacheErr } = await supabase
        .from("cached_answers")
        .upsert(
          {
            question_label: group.label,
            field_type: group.field_type,
            options: group.options,
            answer: answer.trim(),
          },
          { onConflict: "question_label" }
        );

      if (cacheErr) throw cacheErr;

      // Remove the answered group from the display
      setGroups((prev) => prev.filter((g) => g.label !== group.label));
      setSaving(null);
    } catch (e) {
      setError(`Failed to save answer: ${e instanceof Error ? e.message : String(e)}`);
      setSaving(null);
    }
  }

  async function deleteQuestion(group: QuestionGroup) {
    if (!confirm(`Remove "${group.label}" from unanswered questions?`)) {
      return;
    }

    try {
      // Delete all matching rows from unknown_questions
      const { error: deleteErr } = await supabase
        .from("unknown_questions")
        .delete()
        .in("id", group.ids);

      if (deleteErr) throw deleteErr;

      // Remove the group from the display
      setGroups((prev) => prev.filter((g) => g.label !== group.label));
    } catch (e) {
      setError(`Failed to delete question: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-gray-500 text-sm">Loading unanswered questions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        ✓ No unanswered questions. All form fields are covered!
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.label} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="mb-3">
            <h3 className="font-medium text-gray-900 mb-1">{group.label}</h3>
            <p className="text-xs text-gray-500">
              Seen in {group.job_ids.length} job{group.job_ids.length !== 1 ? "s" : ""} •{" "}
              {group.field_type === "select"
                ? `Dropdown (${group.options.length} options)`
                : group.field_type === "radio"
                  ? `Radio buttons (${group.options.length} options)`
                  : `Text input (${group.field_type || "text"})`}
            </p>
          </div>

          {/* Render inputs based on field_type */}
          {group.field_type === "radio" && group.options.length > 0 ? (
            <div className="mb-3 space-y-2">
              <label className="text-xs text-gray-600 block mb-1.5">Available options:</label>
              {group.options.map((opt) => (
                <label key={opt} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name={`radio-${group.label}`}
                    value={opt}
                    checked={group.answer === opt}
                    onChange={(e) => {
                      group.answer = e.target.value;
                      setGroups([...groups]);
                    }}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm text-gray-700">{opt}</span>
                </label>
              ))}
            </div>
          ) : group.field_type === "select" && group.options.length > 0 ? (
            <div className="mb-3">
              <label className="text-xs text-gray-600 block mb-1.5">Available options:</label>
              <select
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                onChange={(e) => {
                  group.answer = e.target.value;
                  setGroups([...groups]);
                }}
                value={group.answer}
              >
                <option value="">Select an option...</option>
                {group.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {/* Free-text input as fallback or for text/number/email/tel fields */}
          {group.field_type !== "radio" && group.field_type !== "select" && (
            <input
              type={["number", "email", "tel"].includes(group.field_type) ? group.field_type : "text"}
              placeholder="Enter your answer..."
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-3"
              value={group.answer}
              onChange={(e) => {
                group.answer = e.target.value;
                setGroups([...groups]);
              }}
              onKeyPress={(e) => {
                if (e.key === "Enter") {
                  saveAnswer(group, group.answer);
                }
              }}
            />
          )}

          {(group.field_type === "radio" || group.field_type === "select") && (
            <input
              type="text"
              placeholder="Or type a custom answer..."
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mt-2 mb-3"
              value={group.answer}
              onChange={(e) => {
                group.answer = e.target.value;
                setGroups([...groups]);
              }}
              onKeyPress={(e) => {
                if (e.key === "Enter") {
                  saveAnswer(group, group.answer);
                }
              }}
            />
          )}

          <div className="flex gap-2">
            <button
              onClick={() => saveAnswer(group, group.answer)}
              disabled={saving === group.label || !group.answer.trim()}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {saving === group.label ? "Saving..." : "Save answer"}
            </button>
            <button
              onClick={() => deleteQuestion(group)}
              title="Remove this question"
              className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-red-600 hover:bg-red-50 border border-gray-300 hover:border-red-300 rounded-lg transition-colors"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
