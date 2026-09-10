# Bayraklar

Buradaki SVG'ler [lipis/flag-icons](https://github.com/lipis/flag-icons) projesinin
`flags/4x3` setinden alınmıştır (MIT lisansı); hepsi 4:3 en-boy oranındadır ve
dosya adı ISO 3166-1 alpha-2 kodunun küçük harfli hâlidir (`de.svg`, `gb.svg`).
Emoji bayraklar Windows'ta render olmadığı için siteyi kendi dosyalarımızla
sunuyoruz — çalışma anında hiçbir dış CDN'e bağımlılık yok.

Güncellemek veya yeni ülke eklemek için dosyayı
`https://raw.githubusercontent.com/lipis/flag-icons/main/flags/4x3/<kod>.svg`
adresinden indirip bu klasöre koy ve ülkeyi `src/lib/countries.ts` içindeki
`COUNTRY_NAMES_TR` eşlemesine ekle; bileşen tarafında yapılacak bir şey yok
(`src/components/Flag.tsx` yolu koddan üretiyor).
