-- ============================================================
-- 096 · İnsan reddinde gerekçe zorunluluğu
-- ============================================================
-- Admin paneli yapılandırılmış bir admin_note gönderir. Bu migration, panel
-- dışından reject_submission RPC'si çağrılsa bile boş/null gerekçeyle red
-- verilmesini engeller. Agent bu RPC'yi kullanmaz; kendi gerekçeli kararını
-- service-role ile yazar ve reviewed_by alanını NULL bırakır.

create or replace function public.reject_submission(p_id uuid, p_note text)
returns json
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  if nullif(btrim(p_note), '') is null then
    raise exception 'Red sebebi zorunludur';
  end if;

  update public.submissions set
    status = 'rejected',
    admin_note = btrim(p_note),
    reviewed_at = now(),
    reviewed_by = auth.uid()
  where id = p_id;

  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;

  return json_build_object('success', true);
end;
$$;

revoke all on function public.reject_submission(uuid, text) from public;
revoke all on function public.reject_submission(uuid, text) from anon;
grant execute on function public.reject_submission(uuid, text) to authenticated;
