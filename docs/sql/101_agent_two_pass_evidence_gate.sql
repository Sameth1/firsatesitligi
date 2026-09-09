-- ============================================================
-- 101 · Agent onayında iki tur + birebir kanıt zorunluluğu
-- Önkoşul: 099
-- ============================================================

create or replace function public.enforce_agent_two_pass_evidence()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_key text;
  v_second jsonb;
begin
  -- İnsan admin onayına dokunma. Yalnızca service-role agent'ın
  -- pending -> approved geçişinde ek kanıt kapısı uygula.
  if new.status = 'approved'
     and old.status = 'pending'
     and new.submission_origin = 'agent'
     and new.reviewed_by is null then
    if new.agent_validation is null then
      raise exception 'Agent onayı engellendi: validation nesnesi yok';
    end if;

    v_second := new.agent_validation->'second_pass';
    if jsonb_typeof(v_second) is distinct from 'object'
       or v_second->>'durum' is distinct from 'acik'
       or v_second->>'guven' is distinct from 'yuksek'
       or v_second->'kategori_uygun' is distinct from 'true'::jsonb
       or v_second->'tek_firsat' is distinct from 'true'::jsonb
       or v_second->'dogrudan_firsat_sayfasi' is distinct from 'true'::jsonb
       or v_second->'son_tarih_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'finansman_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'ulke_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'uygunluk_dogrulandi' is distinct from 'true'::jsonb then
      raise exception 'Agent onayı engellendi: ikinci denetim olumlu değil';
    end if;

    foreach v_key in array array[
      'guncellik', 'son_tarih', 'kategori', 'finansman', 'ulke', 'uygunluk'
    ] loop
      if char_length(btrim(coalesce(
           new.agent_validation->'kanitlar'->>v_key, ''))) < 5 then
        raise exception 'Agent onayı engellendi: ilk tur % kanıtı yok', v_key;
      end if;
      if char_length(btrim(coalesce(
           v_second->'kanitlar'->>v_key, ''))) < 5 then
        raise exception 'Agent onayı engellendi: ikinci tur % kanıtı yok', v_key;
      end if;
    end loop;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_agent_two_pass_evidence on public.submissions;
create trigger trg_agent_two_pass_evidence
  before update of status, agent_validation on public.submissions
  for each row execute function public.enforce_agent_two_pass_evidence();

comment on function public.enforce_agent_two_pass_evidence() is
  'Agent auto-approval requires two positive reviews and evidence quotes.';
