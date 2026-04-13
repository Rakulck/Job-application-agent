"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";

const DEFAULT_PERSONAL: Record<string, string> = {
  name: "Rakul C Kandavel",
  email: "rakulck31@gmail.com",
  phone: "+1 7038593589",
  linkedin: "www.linkedin.com/in/rakul-c-kandavel-9011b0191/",
  portfolio: "rakulck31.vercel.app/",
  github: "github.com/Rakulck",
  location: "Seattle, WA",
  address_line_1: "",
  address_line_2: "",
  city: "",
  state: "",
  zip_code: "",
};

const DEFAULT_SCREENING: Record<string, string> = {
  years_of_experience: "3",
  work_authorization: "Yes",
  require_sponsorship: "No",
  expected_salary: "100000",
  notice_period: "2 weeks",
  willing_to_relocate: "Yes",
  remote_preference: "Yes",
  degree: "Bachelor's",
  gender: "Male",
  ethnicity: "Asian",
  veteran_status: "I am not a veteran",
  disability_status: "No, I don't have a disability",
};

const DEFAULT_TITLES = ["Frontend Developer", "Software Developer", "Web Developer", "React Developer", "Full Stack Developer"];

const ROLE_SLUGS: Record<string, string> = {
  "frontend developer": "frontend_developer",
  "front-end developer": "frontend_developer",
  "software developer": "software_developer",
  "software engineer": "software_developer",
  "web developer": "web_developer",
  "react developer": "react_developer",
  "full stack developer": "fullstack_developer",
  "fullstack developer": "fullstack_developer",
  "full-stack developer": "fullstack_developer",
};

const roleKey = (title: string): string =>
  ROLE_SLUGS[title.toLowerCase()] ?? title.toLowerCase().replace(/\s+/g, "_");

const PERSONAL_FIELDS = [
  { key: "name", label: "Full Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "linkedin", label: "LinkedIn URL" },
  { key: "portfolio", label: "Portfolio URL" },
  { key: "github", label: "GitHub URL" },
  { key: "location", label: "Location" },
  { key: "address_line_1", label: "Address Line 1" },
  { key: "address_line_2", label: "Address Line 2" },
  { key: "city", label: "City" },
  { key: "state", label: "State" },
  { key: "zip_code", label: "ZIP Code" },
];

const SCREENING_FIELDS = [
  { key: "years_of_experience", label: "Years of Experience" },
  { key: "expected_salary", label: "Expected Salary" },
  { key: "work_authorization", label: "Work Authorization" },
  { key: "require_sponsorship", label: "Require Sponsorship" },
  { key: "notice_period", label: "Notice Period" },
  { key: "willing_to_relocate", label: "Willing to Relocate" },
  { key: "remote_preference", label: "Remote Preference" },
  { key: "degree", label: "Highest Degree" },
  { key: "gender", label: "Gender" },
  { key: "ethnicity", label: "Ethnicity" },
  { key: "veteran_status", label: "Veteran Status" },
  { key: "disability_status", label: "Disability Status" },
];

export default function ProfileForm() {
  const [personal, setPersonal] = useState<Record<string, string>>(DEFAULT_PERSONAL);
  const [screening, setScreening] = useState<Record<string, string>>(DEFAULT_SCREENING);
  const [titles, setTitles] = useState<string[]>(DEFAULT_TITLES);
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [roleResumes, setRoleResumes] = useState<Record<string, Record<string, unknown>>>({});
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [roleResumeErrors, setRoleResumeErrors] = useState<Record<string, string>>({});
  const [roleResumeUploading, setRoleResumeUploading] = useState<Record<string, boolean>>({});

  useEffect(() => {
    supabase.from("profile").select("*").eq("id", 1).single().then(({ data }) => {
      if (data) {
        if (data.personal_info && Object.keys(data.personal_info).length > 0)
          setPersonal(data.personal_info);
        if (data.screening_answers && Object.keys(data.screening_answers).length > 0)
          setScreening(data.screening_answers);
        if (data.job_titles && data.job_titles.length > 0)
          setTitles(data.job_titles);
        if (data.role_resumes)
          setRoleResumes(data.role_resumes);
      }
      setLoading(false);
    });
  }, []);

  const save = async () => {
    setSaving(true);
    setMsg(null);
    const payload: Record<string, unknown> = {
      id: 1,
      personal_info: personal,
      screening_answers: { ...screening, salary_expectation: screening.expected_salary },
      job_titles: titles,
      role_resumes: roleResumes,
      updated_at: new Date().toISOString(),
    };
    const { error } = await supabase.from("profile").upsert(payload);
    setSaving(false);
    setMsg(error ? { type: "error", text: error.message } : { type: "success", text: "Profile saved!" });
    setTimeout(() => setMsg(null), 3000);
  };

  const toggleTitle = (t: string) =>
    setTitles((prev) => prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]);

  const addTitle = () => {
    const t = newTitle.trim();
    if (t && !titles.includes(t)) setTitles((prev) => [...prev, t]);
    setNewTitle("");
  };

  const handleRoleResumeUpload = async (role: string, e: React.ChangeEvent<HTMLInputElement>) => {
    setRoleResumeErrors((prev) => ({ ...prev, [role]: "" }));
    setRoleResumeUploading((prev) => ({ ...prev, [role]: true }));
    const file = e.target.files?.[0];
    if (!file) {
      setRoleResumeUploading((prev) => ({ ...prev, [role]: false }));
      return;
    }

    // Accept .docx or .json files
    const isDocx = file.name.endsWith(".docx");
    const isJson = file.name.endsWith(".json");

    if (!isDocx && !isJson) {
      setRoleResumeErrors((prev) => ({ ...prev, [role]: "Please upload a .docx or .json resume file." }));
      setRoleResumeUploading((prev) => ({ ...prev, [role]: false }));
      return;
    }

    if (isJson) {
      // Handle JSON files directly
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const parsed = JSON.parse(ev.target?.result as string);
          setRoleResumes((prev) => ({ ...prev, [role]: parsed }));
        } catch {
          setRoleResumeErrors((prev) => ({ ...prev, [role]: "Invalid JSON file." }));
        }
        setRoleResumeUploading((prev) => ({ ...prev, [role]: false }));
      };
      reader.readAsText(file);
    } else {
      // Convert DOCX files via API
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("role", role);

        const response = await fetch("/api/convert-resume", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          setRoleResumeErrors((prev) => ({ ...prev, [role]: error.error || "Failed to convert resume." }));
          setRoleResumeUploading((prev) => ({ ...prev, [role]: false }));
          return;
        }

        const { resume } = await response.json();
        setRoleResumes((prev) => ({ ...prev, [role]: resume }));
      } catch (error) {
        setRoleResumeErrors((prev) => ({
          ...prev,
          [role]: `Error converting resume: ${error instanceof Error ? error.message : "Unknown error"}`,
        }));
      }
      setRoleResumeUploading((prev) => ({ ...prev, [role]: false }));
    }
  };

  const clearRoleResume = (role: string) => {
    setRoleResumes((prev) => {
      const next = { ...prev };
      delete next[role];
      return next;
    });
  };

  const inputClass = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-blue-300";

  if (loading) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="space-y-8">

      {/* Personal Info */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-4">Personal Info</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {PERSONAL_FIELDS.map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
              <input
                className={inputClass}
                value={personal[key] ?? ""}
                onChange={(e) => setPersonal((p) => ({ ...p, [key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
      </section>

      {/* Screening Answers */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-4">Screening Answers</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {SCREENING_FIELDS.map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
              <input
                className={inputClass}
                value={screening[key] ?? ""}
                onChange={(e) => setScreening((s) => ({ ...s, [key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
      </section>

      {/* Roles to Apply For with Per-Role Resume Accordion */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-1">Roles to Apply For</h2>
        <p className="text-xs text-gray-400 mb-4">Scraper searches LinkedIn for each role. The agent automatically tailors resumes per job. (Optional: upload a role-specific base to customize tailoring for that role.)</p>

        <div className="space-y-2 mb-4">
          {titles.map((t) => {
            const key = roleKey(t);
            const isOpen = expandedRole === key;
            const hasOverride = !!roleResumes[key];
            const err = roleResumeErrors[key];

            return (
              <div key={t} className="rounded-lg border border-blue-100 bg-blue-50 overflow-hidden">
                {/* Pill row */}
                <div className="flex items-center gap-2 px-3 py-2">
                  <span className="text-sm text-blue-700 font-medium flex-1">{t}</span>

                  {/* Resume status badge */}
                  {hasOverride ? (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 border border-green-200">
                      Custom base resume
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400">Auto-tailored per job</span>
                  )}

                  {/* Expand chevron */}
                  <button
                    onClick={() => setExpandedRole(isOpen ? null : key)}
                    className="p-1 rounded text-blue-300 hover:text-blue-600 hover:bg-blue-100 transition-colors duration-150"
                    aria-label={isOpen ? `Collapse resume settings for ${t}` : `Expand resume settings for ${t}`}
                    aria-expanded={isOpen}
                  >
                    <svg
                      className={`w-4 h-4 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
                      fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {/* Remove role */}
                  <button
                    onClick={() => {
                      setTitles(titles.filter((x) => x !== t));
                      clearRoleResume(key);
                      if (expandedRole === key) setExpandedRole(null);
                    }}
                    className="p-1 rounded text-blue-300 hover:text-red-400 transition-colors duration-150"
                    aria-label={`Remove role ${t}`}
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Sub-panel (accordion) */}
                <div
                  className={`transition-all duration-200 ease-out overflow-hidden ${isOpen ? "max-h-48" : "max-h-0"}`}
                >
                  <div className="px-3 pb-3 pt-1 border-t border-blue-100 bg-white">
                    {hasOverride ? (
                      <div className="flex items-center gap-2 mb-2 p-2 rounded-md border border-green-200 bg-green-50">
                        <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-xs text-green-700 font-medium flex-1">
                          {(roleResumes[key] as Record<string, unknown>).name as string
                            ? `${(roleResumes[key] as Record<string, unknown>).name} — custom base resume`
                            : "Custom base resume on file"}
                        </span>
                        <button
                          onClick={() => clearRoleResume(key)}
                          className="text-xs text-gray-400 hover:text-red-400 transition-colors"
                        >
                          Clear
                        </button>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 mb-2">
                        Resume will be auto-tailored per job. (Optional: upload a base resume to customize tailoring.)
                      </p>
                    )}

                    <label className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs cursor-pointer transition-colors duration-150 ${
                      roleResumeUploading[key]
                        ? "border-gray-300 bg-gray-100 text-gray-500 cursor-not-allowed"
                        : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                    }`}>
                      {roleResumeUploading[key] ? (
                        <>
                          <svg className="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Converting...
                        </>
                      ) : (
                        <>
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                          </svg>
                          {hasOverride ? "Replace resume (.docx or .json)" : "Upload resume (.docx or .json)"}
                        </>
                      )}
                      <input
                        type="file"
                        accept=".docx,.json"
                        className="hidden"
                        onChange={(e) => handleRoleResumeUpload(key, e)}
                        disabled={roleResumeUploading[key]}
                      />
                    </label>
                    {err && <p className="mt-1.5 text-xs text-red-500">{err}</p>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Add role input */}
        <div className="flex gap-2">
          <input
            className={`${inputClass} flex-1`}
            placeholder="Add a role (e.g. React Native Developer)"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addTitle()}
          />
          <button onClick={addTitle} className="px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200">
            Add
          </button>
        </div>
      </section>

      {/* Save */}
      <div className="flex items-center gap-4 pt-2">
        <button
          onClick={save}
          disabled={saving}
          className="px-6 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Profile"}
        </button>
        {msg && (
          <span className={`text-sm font-medium ${msg.type === "success" ? "text-green-600" : "text-red-600"}`}>
            {msg.text}
          </span>
        )}
      </div>
    </div>
  );
}
