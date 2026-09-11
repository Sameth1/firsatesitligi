/**
 * Kategori görselleri — Higgsfield ile üretilmiş cam/iridesan 3B ikonlar.
 *
 * Dosyalar `public/icons/*.webp` altında, siyah zemin alfaya çevrilmiş olarak
 * duruyor; bu yüzden hem koyu hem açık yüzeylerde halesiyle birlikte çalışıyor.
 * Hem form ekranındaki seçim kartları hem sonuç kartları buradan okur ki
 * ikon–kategori eşlemesi tek yerde kalsın.
 */

export const CATEGORY_ICON_SRC: Record<string, string> = {
  scholarship:   '/icons/scholarship.webp',
  volunteering:  '/icons/volunteering.webp',
  youth_project: '/icons/youth_project.webp',
  internship:    '/icons/internship.webp',
  summer_school: '/icons/summer_school.webp',
  exchange:      '/icons/exchange.webp',
}

/** Kartların vurgu rengi — sahneye gönderilen darbe de bu rengi kullanır. */
export const CATEGORY_ACCENT: Record<string, string> = {
  scholarship:   '#7C5CFF',
  volunteering:  '#FF5FA2',
  youth_project: '#9B6BFF',
  internship:    '#5C9EFF',
  summer_school: '#FFB547',
  exchange:      '#2BE0C8',
}
