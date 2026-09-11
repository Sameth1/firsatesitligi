-- 116 · PostgREST'in hangi match_opportunities overload'unu çağıracağını
-- seçememesine neden olan eski 9 parametreli imzayı temizler.

begin;

drop function if exists public.match_opportunities(
  text, text, text, integer, text, text, text, text, text
);

notify pgrst, 'reload schema';

commit;
