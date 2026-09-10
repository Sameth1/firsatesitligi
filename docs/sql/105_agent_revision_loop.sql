-- ============================================================
-- 105 · Revize akışı: admin revize verince kayıt AGENT'a gitsin
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- MEVCUT DURUM (ölçüldü, bugüne dek hiç çalışmamış):
--   request_revision yalnızca status='needs_revision' yazıyor ve BİR TOKEN
--   ÜRETMİYOR. Projede mail gönderen hiçbir kod da yok. Yani öneri sahibine
--   ne link gidiyor ne bildirim; /revise/[token] sayfasına ulaşmak imkânsız.
--   Kanıt: submission_revision_tokens tablosunda 0 satır, needs_revision'da
--   0 kayıt. Akış ilk adımda çıkmaza giriyordu.
--
-- YENİ AKIŞ:
--   admin "Revize" + not  →  review_stage='agent_revision'  →  agent kaynağı
--   yeniden çeker, admin notunu dikkate alarak değerlendirir, BOŞ alanları
--   doldurur, verdiğini nota yazar  →  kayıt human_review'e döner, yayına
--   alma tek tık.
--
--   Agent bu kayıtları ONAYLAMAZ. 099'daki koruma (agent_approve_submission
--   yalnız submission_origin='agent' kayıtları onaylar) olduğu gibi duruyor;
--   insan gönderisi insan onayı olmadan yayına giremez.
--
-- NE DEĞİŞİYOR:
--   1) review_stage kısıtına 'agent_revision' eklenir.
--   2) sync_submission_review_stage trigger'ı DÜZELTİLİR. Trigger INSERT ve
--      UPDATE'te çalışıyor ve "status='pending' + origin='human'" gördüğünde
--      review_stage'i human_review'e EZİYOR. Bu düzeltilmeden request_revision
--      ne yazarsa yazsın anında geri alınır ve kayıt agenta hiç ulaşmaz.
--   3) request_revision yeniden yazılır:
--      • artık submitter_email şartı YOK (mail yolu zaten yok; e-postasız
--        gönderiler de revize edilebilmeli)
--      • status='pending' + review_stage='agent_revision'
--      • admin notu agentın okuyabileceği biçimde yazılır
--
-- GERİ ALINABİLİR Mİ: evet — 097'deki trigger ve request_revision tanımları
--   yeniden çalıştırılırsa eski davranış geri gelir.
-- IDEMPOTENT: evet.
-- ============================================================

begin;

-- ─── 1) Yeni aşama değeri ────────────────────────────────────────
alter table public.submissions drop constraint if exists submissions_review_stage_check;
alter table public.submissions add constraint submissions_review_stage_check
  check (review_stage in ('human_review', 'agent_queue', 'agent_uncertain',
                          'agent_revision', 'awaiting_revision', 'decided'));

-- ─── 2) Trigger artık agent aşamalarını ezmiyor ──────────────────
create or replace function public.sync_submission_review_stage()
returns trigger
language plpgsql
set search_path to 'public'
as $function$
begin
  if new.status in ('approved', 'rejected') then
    new.review_stage := 'decided';
  elsif new.status = 'needs_revision' then
    new.review_stage := 'awaiting_revision';
  elsif new.status = 'pending' and new.submission_origin = 'human'
        -- AÇIKÇA bir agent aşaması yazıldıysa dokunma. Bu koşul olmadan
        -- request_revision'ın yazdığı 'agent_revision' aynı ifadede
        -- human_review'e eziliyor ve kayıt agenta hiç ulaşmıyordu.
        and new.review_stage not in ('agent_revision', 'agent_queue', 'agent_uncertain') then
    new.review_stage := 'human_review';
  end if;
  return new;
end;
$function$;

-- ─── 3) request_revision: artık agenta yönlendiriyor ─────────────
create or replace function public.request_revision(p_id uuid, p_note text)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_note text := btrim(p_note);
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;
  if nullif(v_note, '') is null then
    raise exception 'Revize notu zorunludur';
  end if;

  update public.submissions set
    status       = 'pending',            -- agent yalnız pending kayıtları çeker
    review_stage = 'agent_revision',
    -- Not agentın okuyacağı biçimde: hangi düzeltmenin istendiği prompt'a girer.
    admin_note   = '[insan] REVİZE İSTENDİ: ' || v_note,
    reviewed_at  = now(),
    reviewed_by  = auth.uid()
  where id = p_id
    and submission_origin = 'human'
    and status in ('pending', 'needs_revision');

  if not found then
    raise exception 'Revize edilebilecek bir kullanıcı gönderisi bulunamadı';
  end if;

  return json_build_object('success', true, 'review_stage', 'agent_revision');
end;
$function$;

commit;
