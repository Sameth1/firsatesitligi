-- ============================================================
-- 113 · RPC yüzeyinin daraltılması + search_path sabitleme
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- NEDEN: Supabase güvenlik denetçisi (database linter) 14 SECURITY DEFINER
--   fonksiyonun `anon` rolüyle, yani GİRİŞ YAPMADAN çağrılabildiğini bildiriyor.
--   Tek tek incelendi:
--
--   • Çoğunun gövdesinde admin kontrolü VAR (`admins` tablosuna bakıp
--     exception atıyor) — yani veri sızmıyor. Yine de anon'un bunları
--     çağırabilmesi gereksiz bir yüzey: gövdedeki tek bir hata doğrudan
--     internete açılır. EXECUTE yetkisi anon'dan alınıyor, admin paneli
--     `authenticated` rolüyle çalıştığı için etkilenmiyor.
--
--   • get_submission_stats: HİÇBİR kontrolü yok, anon çağırabiliyor ve
--     öneri sayılarını döndürüyor. Küçük ama gereksiz bir bilgi sızıntısı.
--
--   • submit_revision / get_revision_submission: e-posta + token'lı eski
--     revize akışına ait. Bu akış HİÇ çalışmadı (mail gönderen kod yok,
--     submission_revision_tokens'ta 0 satır) ve 108 ile yerine ajan akışı
--     geldi. Yani bunlar ölü kod ama anon'a açık YAZMA yolu. Yetki alınıyor.
--     Fonksiyonlar silinmiyor: /revise/[token] sayfası hâlâ repoda duruyor,
--     önce o temizlenmeli.
--
--   • record_submission_review_event / remember_human_rejection: bunlar
--     TRIGGER fonksiyonu. RPC olarak çağrılınca NEW kaydı olmadığı için
--     zaten hata verirler, ama API yüzeyinde durmalarının anlamı yok.
--
-- AYRICA: 4 fonksiyonun search_path'i sabit değil (linter uyarısı). Sabit
--   olmayan search_path, yetkili bir rol şemasını değiştirebiliyorsa
--   fonksiyonun yanlış tabloyu kullanmasına yol açabilir. Gövdeye
--   dokunmadan `alter function ... set search_path` ile sabitleniyor.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet — `grant execute on function
--   ... to anon;` ile eski hâline döner.
-- ============================================================

begin;

-- ─── 1) Yalnız admin için olan RPC'ler anon'a kapatılıyor ───────
-- DİKKAT: PostgreSQL fonksiyonlara varsayılan olarak PUBLIC'e de EXECUTE
-- verir. Yalnız `from anon` demek yetmiyor — ölçüldü: revoke sonrası anon
-- fonksiyonu çağırmaya devam edebiliyordu (gövdedeki admin kontrolü
-- durdurdu). Doğrusu PUBLIC'ten almak, sonra gereken role AÇIKÇA vermek.

-- Admin panelinin (authenticated) kullandıkları
revoke execute on function public.approve_submission(uuid) from public, anon;
grant  execute on function public.approve_submission(uuid) to authenticated;

revoke execute on function public.reject_submission(uuid, text) from public, anon;
grant  execute on function public.reject_submission(uuid, text) to authenticated;

revoke execute on function public.get_admin_stats() from public, anon;
grant  execute on function public.get_admin_stats() to authenticated;

revoke execute on function public.get_submission_stats() from public, anon;
grant  execute on function public.get_submission_stats() to authenticated;

revoke execute on function public.get_opportunity_link_audit() from public, anon;
grant  execute on function public.get_opportunity_link_audit() to authenticated;

revoke execute on function public.get_opportunity_review_queue() from public, anon;
grant  execute on function public.get_opportunity_review_queue() to authenticated;

revoke execute on function public.resolve_opportunity_review(uuid) from public, anon;
grant  execute on function public.resolve_opportunity_review(uuid) to authenticated;

-- Bağlantı denetimi: hem admin paneli hem service key'li script kullanıyor
revoke execute on function public.mark_opportunity_verified(uuid) from public, anon;
grant  execute on function public.mark_opportunity_verified(uuid) to authenticated, service_role;

revoke execute on function public.pick_opportunities_for_url_check(integer) from public, anon;
grant  execute on function public.pick_opportunities_for_url_check(integer) to authenticated, service_role;

revoke execute on function public.record_opportunity_url_check(uuid, integer, text, text) from public, anon;
grant  execute on function public.record_opportunity_url_check(uuid, integer, text, text) to authenticated, service_role;

-- ─── 2) Ölü token akışı: kimseye açık değil ─────────────────────
revoke execute on function public.get_revision_submission(text) from public, anon, authenticated;
revoke execute on function public.submit_revision(
  text, text, text, text, text[], text, text, text, text, text
) from public, anon, authenticated;

-- ─── 3) Trigger fonksiyonları API yüzeyinden çıkıyor ────────────
revoke execute on function public.record_submission_review_event() from public, anon, authenticated;
revoke execute on function public.remember_human_rejection() from public, anon, authenticated;

-- ─── 5) search_path sabitleme (gövdeye dokunmadan) ──────────────
alter function public.set_updated_at() set search_path to 'public';
alter function public.check_submission_rate_limit() set search_path to 'public';
alter function public.get_filter_options() set search_path to 'public';
alter function public.match_opportunities(text, text, text, integer, text, text, text, text)
  set search_path to 'public';

commit;
