-- 117 · Kategorisiz kayıtlar kartlarda doğru sunulamaz ve kategori filtresini
-- bozar. Eski kategorisiz kayıtları yayından kaldır, yenilerinin aktif olmasını engelle.

begin;

update public.opportunities
set is_active = false
where is_active = true
  and category_id is null;

do $block$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.opportunities'::regclass
      and conname = 'opportunities_active_requires_category'
  ) then
    alter table public.opportunities
      add constraint opportunities_active_requires_category
      check (not is_active or category_id is not null);
  end if;
end
$block$;

commit;
