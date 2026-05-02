<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

<!-- BEGIN:ux-principles -->
# UX Prensipleri (mentör kuralları)

Bu projede her UI değişikliği aşağıdaki kurallara uymak zorundadır:

1. **Buton beklenen yerinde.** Birincil aksiyon sağ üst (logo karşıtı) veya kart/modal'ın sağ altında. "Sepet/profil/ayarlar" tipi şeyler hep sağ üst. Sürpriz yerleşim yok.
2. **Az soru, az alan.** Bir input gerçekten eşleşmeyi/onayı/iletişimi etkilemiyorsa form'a koyma. Opsiyoneller varsayılan olarak `expand` içinde gizli.
3. **Engel koyma.** Katkı verecek kullanıcının önüne email/hesap/zorunlu alan zinciri çıkarma. Sadece **işlevsel olarak şart olanı** zorunlu yap; her ek zorunlu alanın "vazgeçirme bedeli" var. Email, telefon, isim gibi kişisel veriler **her zaman opsiyonel** — kullanıcı geri bildirim almak için verir.
4. **En az tıkla bitir.** Sonuç odaklı kullanıcı 1 ekranda işini bitirsin. Detay isteyen pop-up/sheet'te kaybolabilir; bu sonuç akışını bozmaz.
5. **Eldeki bilgiyi tekrar sorma.** searchSnapshot, email, ülke seçimi vb. bir kez alındıysa otomatik doldur.
6. **Tıklanabilir görünen tıklanabilir.** Link link, buton buton; karta tıklayınca sürpriz aksiyon olmaz.
7. **Yön ver, kaybolma.** Form → Sonuç gibi adımlar `StepPill` ile görünür; geri dönüş hep aynı yerde ("← Aramayı düzenle").
<!-- END:ux-principles -->
