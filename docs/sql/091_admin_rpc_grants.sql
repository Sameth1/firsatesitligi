-- ============================================================
-- 091 · Admin RPC’ler için authenticated GRANT’leri
-- Supabase SQL Editor’da çalıştır; 006/090 sonrası idempotent.
-- ============================================================
-- PostgREST üzerinden çağrılan güvenlik tanımlayıcı RPC’ler için
-- EXECUTE yetkisi; işlev içi admin kontrolü (public.admins) aynen kalır.
-- ============================================================

grant execute on function public.request_revision(uuid, text) to authenticated;
grant execute on function public.reject_submission(uuid, text) to authenticated;
grant execute on function public.get_submission_stats() to authenticated;

-- 090 ile aynı (tekrar vermek zararsız)
grant execute on function public.approve_submission(uuid) to authenticated;
grant execute on function public.get_admin_stats() to authenticated;
