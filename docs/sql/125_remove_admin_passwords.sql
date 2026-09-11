-- ============================================================
-- 115 · Admin hesaplarındaki kullanılmayan parolaların kaldırılması
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- NEDEN: Arayüz yalnız magic link (signInWithOtp) kullanıyor, ama projede
--   parola ile giriş AÇIK ve iki admin hesabının da parolası vardı. Yani
--   kimsenin kullanmadığı bir parola, sistemdeki en değerli hedefin (admin
--   paneli) önünde duruyordu: parola deneme / sızmış parola yolu açıktı.
--
--   Parola kaldırılınca grant_type=password bu hesaplar için çalışmaz;
--   giriş magic link'te kalır (auth.identities''teki email kaydı duruyor).
--
-- KAPSAM UYARISI: bu, parola girişini HESAP BAZINDA kapatır. Proje ayarında
--   parola girişi hâlâ açık; ileride parolayla yeni bir hesap açılır ve
--   admins''e eklenirse yol yeniden açılır. Kalıcı çözüm panelden
--   Authentication → Providers → Email → parola girişini kapatmaktır
--   (aynı ekranda "leaked password protection" da açılmalı).
--
-- GERİ ALINABİLİR Mİ: parola hash''i geri getirilemez — ama gerekirse
--   panelden (Authentication → Users → Reset password) ya da /auth/v1/recover
--   ile yeni parola belirlenebilir. İkisi de admin''in e-posta kutusuna erişim
--   gerektirir, yani magic link ile aynı güven düzeyinde.
-- ============================================================

update auth.users u
set encrypted_password = null
from public.admins a
where a.user_id = u.id
  and u.encrypted_password is not null;
