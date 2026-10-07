-- =====================================================================
-- SignalBridge — schema Supabase
-- Incolla tutto in: Supabase > SQL Editor > New query > Run
-- =====================================================================

-- ---------- IMPOSTAZIONI GLOBALI (una sola riga, id = 1) ----------
create table if not exists settings (
  id                    int primary key default 1 check (id = 1),
  trading_enabled       boolean not null default false,   -- interruttore generale
  allow_real_account    boolean not null default false,   -- se false opera SOLO su conto demo
  symbol_suffix         text    not null default '',      -- es. ".m" o "+" del broker
  symbol_aliases        jsonb   not null default '{"GOLD":"XAUUSD","XAU":"XAUUSD","SILVER":"XAGUSD","US30":"US30","DJ30":"US30","NAS100":"NAS100","NASDAQ":"NAS100","US100":"NAS100","SPX500":"US500","BTC":"BTCUSD","BITCOIN":"BTCUSD","ETH":"ETHUSD"}',
  max_open_positions    int     not null default 20,
  daily_loss_limit_pct  numeric not null default 5,       -- 0 = disattivato
  magic_number          int     not null default 770077,
  ai_enabled            boolean not null default true,
  -- default applicati ai nuovi gruppi
  default_risk_mode     text    not null default 'fixed_lot',
  default_risk_value    numeric not null default 0.01,
  updated_at            timestamptz not null default now()
);
insert into settings (id) values (1) on conflict do nothing;

-- ---------- GRUPPI / CANALI TELEGRAM ----------
create table if not exists channels (
  id                  bigint primary key,           -- chat id Telegram
  title               text not null,
  username            text,
  kind                text,                          -- channel | group
  enabled             boolean not null default false,
  risk_mode           text    not null default 'fixed_lot' check (risk_mode in ('fixed_lot','risk_pct','fixed_money')),
  risk_value          numeric not null default 0.01, -- lotto | % | €
  max_lot             numeric not null default 1,
  tp_mode             text    not null default 'split' check (tp_mode in ('split','first','last')),
  default_sl_pips     numeric not null default 40,   -- SL d'emergenza se il segnale non ha SL (0 = non aprire senza SL)
  max_slippage_pips   numeric not null default 0,    -- 0 = nessun controllo
  be_after_tp1        boolean not null default true, -- sposta SL a pareggio quando prende TP1
  follow_updates      boolean not null default true, -- esegui "chiudi", "BE", "modifica SL"...
  trades_count        int     not null default 0,
  last_message_at     timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

-- ---------- SEGNALI RICEVUTI ----------
create table if not exists signals (
  id            bigserial primary key,
  channel_id    bigint not null,
  channel_title text,
  message_id    bigint not null,
  reply_to_id   bigint,
  text          text not null,
  kind          text not null default 'unknown',  -- signal | update | ignored | unknown
  parsed        jsonb,
  parser        text,                              -- regex | ai
  status        text not null default 'received',  -- received | executed | partial | skipped | error | ignored
  reason        text,
  edited        boolean not null default false,
  created_at    timestamptz not null default now(),
  unique (channel_id, message_id)
);
create index if not exists signals_created_idx on signals (created_at desc);

-- ---------- ORDINI / POSIZIONI ----------
create table if not exists trades (
  id            bigserial primary key,
  signal_id     bigint references signals(id) on delete set null,
  channel_id    bigint,
  channel_title text,
  ticket        bigint not null unique,
  symbol        text not null,
  side          text not null,                 -- BUY | SELL
  order_kind    text not null default 'market',-- market | limit | stop
  volume        numeric not null,
  open_price    numeric,
  sl            numeric,
  tp            numeric,
  tp_index      int,
  status        text not null default 'open',  -- pending | open | closed | cancelled
  close_price   numeric,
  profit        numeric,
  opened_at     timestamptz not null default now(),
  closed_at     timestamptz
);
create index if not exists trades_status_idx on trades (status);

-- ---------- STATO MOTORE (una riga, id = 1) ----------
create table if not exists status (
  id             int primary key default 1 check (id = 1),
  engine_online  boolean not null default false,
  mt5_connected  boolean not null default false,
  tg_connected   boolean not null default false,
  account_login  bigint,
  account_server text,
  account_name   text,
  account_demo   boolean,
  currency       text,
  balance        numeric,
  equity         numeric,
  margin_free    numeric,
  day_start_balance numeric,
  positions      jsonb not null default '[]',
  message        text,
  version        text,
  last_seen      timestamptz
);
insert into status (id) values (1) on conflict do nothing;

-- ---------- COMANDI DALL'APP AL MOTORE ----------
create table if not exists commands (
  id          bigserial primary key,
  type        text not null,        -- close_ticket | close_all | refresh_channels | parse_test
  payload     jsonb not null default '{}',
  status      text not null default 'pending', -- pending | done | error
  result      jsonb,
  created_at  timestamptz not null default now(),
  done_at     timestamptz
);

-- ---------- SICUREZZA: solo utenti loggati ----------
alter table settings enable row level security;
alter table channels enable row level security;
alter table signals  enable row level security;
alter table trades   enable row level security;
alter table status   enable row level security;
alter table commands enable row level security;

do $$
declare t text;
begin
  foreach t in array array['settings','channels','signals','trades','status','commands'] loop
    execute format('drop policy if exists "auth_all" on %I', t);
    execute format('create policy "auth_all" on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

-- ---------- REALTIME ----------
do $$
declare t text;
begin
  foreach t in array array['settings','channels','signals','trades','status','commands'] loop
    begin
      execute format('alter publication supabase_realtime add table %I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;

-- ---------- PULIZIA AUTOMATICA (tiene 30 giorni di segnali ignorati) ----------
create or replace function cleanup_old() returns void language sql as $$
  delete from signals  where status = 'ignored' and created_at < now() - interval '30 days';
  delete from commands where created_at < now() - interval '7 days';
$$;
