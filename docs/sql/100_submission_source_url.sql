-- ============================================================
-- 100 · Kaynak kanıt sayfası ile doğrudan başvuru URL'ini ayır
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================

alter table public.submissions
  add column if not exists source_url text;

comment on column public.submissions.source_url is
  'Scraper bilgisinin alındığı kanıt sayfası; url ise doğrudan başvuru/resmî fırsat hedefidir.';
