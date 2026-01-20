-- 1. Create the 'templates' table
create table public.templates (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  name text not null, -- e.g. "Ma Société"
  company_name text,
  company_address text,
  primary_color text default '#000000',
  logo_url text,
  is_default boolean default false
);

-- 2. Disable RLS for now (Prototyping phase) 
-- OR Enable it but allow all access. We'll verify this later.
alter table public.templates enable row level security;

create policy "Enable access for all users"
on "public"."templates"
as PERMISSIVE
for ALL
to public
using (true)
with check (true);

-- 3. Storage Bucket for Logos
insert into storage.buckets (id, name, public)
values ('logos', 'logos', true);

-- 4. Storage Policy (Allow public uploads/downloads for 'logos')
create policy "Public Access Logos"
on storage.objects for all
to public
using ( bucket_id = 'logos' )
with check ( bucket_id = 'logos' );
