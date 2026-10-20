create table if not exists public.analytics_events (
    id bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    event_type text not null check (event_type in ('session', 'job')),
    session_id uuid not null,
    properties jsonb not null default '{}'::jsonb
);

create index if not exists analytics_events_created_at_idx
    on public.analytics_events (created_at desc);

alter table public.analytics_events enable row level security;
revoke all on public.analytics_events from anon, authenticated;
grant all on public.analytics_events to service_role;
grant usage, select on sequence public.analytics_events_id_seq to service_role;
