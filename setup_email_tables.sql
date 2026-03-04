-- ============================================================
-- Email Feature: Tables for email templates and SMTP
-- ============================================================

-- 1. Email Templates (subject + body with variables)
create table public.email_templates (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  name text not null,           -- e.g. "Email classique", "Relance"
  subject text not null,        -- e.g. "Estimation {numero_devis} - {client_nom}"
  body text not null            -- e.g. "Bonjour {client_nom},\n\nVeuillez trouver ci-joint..."
);

-- RLS (open for prototyping)
alter table public.email_templates enable row level security;

create policy "Enable access for all users"
on "public"."email_templates"
as PERMISSIVE
for ALL
to public
using (true)
with check (true);

-- 2. Add 'emails' column to existing templates table
-- Stores contact emails associated with a visual template (company identity)
alter table public.templates
  add column if not exists emails text[] default '{}';
