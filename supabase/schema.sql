-- Run this in the Supabase SQL editor

-- Migration: add base_resume column to profile table (run once)
-- alter table profile add column if not exists base_resume jsonb;

-- Migration: add role_resumes column to profile table (run once)
-- alter table profile add column if not exists role_resumes jsonb default '{}'::jsonb;

-- Unknown questions table (for tracking unrecognised form field labels)
create table unknown_questions (
  id             uuid default gen_random_uuid() primary key,
  job_id         text references jobs(job_id) on delete cascade,
  question_label text not null,
  field_type     text not null,       -- 'text' | 'select' | 'radio'
  options        text[] default '{}', -- available choices (select/radio only)
  answer         text,                -- null = unanswered; set by user via dashboard
  detected_at    timestamp default now()
);

create index idx_uq_unanswered on unknown_questions(answer) where answer is null;
create index idx_uq_job_id     on unknown_questions(job_id);

-- Jobs table
create table jobs (
  id uuid default gen_random_uuid() primary key,
  job_id text unique,
  title text,
  company text,
  location text,
  portal text default 'linkedin',
  jd_text text,
  num_applicants integer,
  job_url text,
  easy_apply boolean,
  detected_role text,         -- frontend / fullstack / mobile
  created_at timestamp default now()
);

-- Applications table
create table applications (
  id uuid default gen_random_uuid() primary key,
  job_id text references jobs(job_id),
  status text,                -- applied / failed / skipped / captcha_blocked
  resume_version text,        -- frontend / fullstack / mobile
  resume_pdf_url text,        -- Supabase storage URL
  error_message text,
  manual_apply_url text,      -- LinkedIn job URL for manual application fallback
  applied_at timestamp default now()
);

-- Resumes table (stores each tailored resume JSON)
create table resumes (
  id uuid default gen_random_uuid() primary key,
  job_id text references jobs(job_id),
  role text,
  tailored_json jsonb,
  pdf_url text,
  created_at timestamp default now()
);

-- Cached answers table (global, reusable answers to questions)
create table cached_answers (
  id uuid default gen_random_uuid() primary key,
  question_label text unique not null,
  field_type text not null,       -- 'text' | 'select' | 'radio'
  options text[] default '{}',    -- for select/radio fields
  answer text not null,
  saved_at timestamp default now(),
  updated_at timestamp default now()
);

create index idx_ca_question on cached_answers(question_label);
