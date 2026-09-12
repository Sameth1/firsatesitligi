/**
 * Bölüm (alan) sözlüğü — TEK DOĞRULUK KAYNAĞI.
 *
 * Bu liste üç yerde birden kullanılıyordu ve kopyalar kaçınılmaz olarak
 * birbirinden ayrılıyordu:
 *   1. Arama formundaki seçim kutusu (src/app/page.tsx)
 *   2. Ajanın kabul ettiği slug kümesi (validate_submissions.py · VALID_FIELDS)
 *   3. Ajan promptundaki slug listesi (LLM'e "şunlardan seç" denen yer)
 *
 * Artık 2 ve 3 bu dosyayı okuyor (validate_submissions.py · load_field_slugs).
 * Sözlükte olmayan bir slug ajan tarafından sessizce düşürülür; formda da
 * görünmez. Yani buraya eklenmeyen bölüm sistemde YOK demektir.
 *
 * SLUG DEĞİŞTİRME: mevcut bir slug'ı yeniden adlandırmak, o slug'la
 * kaydedilmiş fırsatları kimsenin bulamaması demek. Yeniden adlandırma
 * yapılacaksa opportunities.target_fields için de bir migration şart.
 */
export type FieldOption = { value: string; label: string; group: string }

export const FIELDS: FieldOption[] = [
  // ─── Mühendislik ────────────────────────────────────────────────
  { value: 'computer_science',          label: 'Bilgisayar Mühendisliği',            group: 'Mühendislik' },
  { value: 'software_engineering',      label: 'Yazılım Mühendisliği',               group: 'Mühendislik' },
  { value: 'artificial_intelligence',   label: 'Yapay Zeka Mühendisliği',            group: 'Mühendislik' },
  { value: 'cybersecurity',             label: 'Siber Güvenlik',                     group: 'Mühendislik' },
  { value: 'information_systems',       label: 'Yönetim Bilişim Sistemleri',         group: 'Mühendislik' },
  { value: 'robotics',                  label: 'Robotik',                            group: 'Mühendislik' },
  { value: 'electrical_engineering',    label: 'Elektrik-Elektronik Mühendisliği',   group: 'Mühendislik' },
  { value: 'mechanical_engineering',    label: 'Makine Mühendisliği',                group: 'Mühendislik' },
  { value: 'mechatronics',              label: 'Mekatronik Mühendisliği',            group: 'Mühendislik' },
  { value: 'industrial_engineering',    label: 'Endüstri Mühendisliği',              group: 'Mühendislik' },
  { value: 'manufacturing_engineering', label: 'İmalat / Üretim Mühendisliği',       group: 'Mühendislik' },
  { value: 'civil_engineering',         label: 'İnşaat Mühendisliği',                group: 'Mühendislik' },
  { value: 'geomatics_engineering',     label: 'Harita / Geomatik Mühendisliği',     group: 'Mühendislik' },
  { value: 'geological_engineering',    label: 'Jeoloji Mühendisliği',               group: 'Mühendislik' },
  { value: 'mining_engineering',        label: 'Maden Mühendisliği',                 group: 'Mühendislik' },
  { value: 'petroleum_engineering',     label: 'Petrol ve Doğalgaz Mühendisliği',    group: 'Mühendislik' },
  { value: 'chemical_engineering',      label: 'Kimya Mühendisliği',                 group: 'Mühendislik' },
  { value: 'materials_engineering',     label: 'Malzeme / Metalurji Mühendisliği',   group: 'Mühendislik' },
  { value: 'environmental_engineering', label: 'Çevre Mühendisliği',                 group: 'Mühendislik' },
  { value: 'energy_engineering',        label: 'Enerji Sistemleri Mühendisliği',     group: 'Mühendislik' },
  { value: 'nuclear_engineering',       label: 'Nükleer Enerji Mühendisliği',        group: 'Mühendislik' },
  { value: 'aerospace_engineering',     label: 'Uzay / Havacılık Mühendisliği',      group: 'Mühendislik' },
  { value: 'automotive_engineering',    label: 'Otomotiv Mühendisliği',              group: 'Mühendislik' },
  { value: 'marine_engineering',        label: 'Gemi İnşaatı / Deniz Teknolojisi',   group: 'Mühendislik' },
  { value: 'food_engineering',          label: 'Gıda Mühendisliği',                  group: 'Mühendislik' },
  { value: 'textile_engineering',       label: 'Tekstil Mühendisliği',               group: 'Mühendislik' },
  { value: 'biomedical_engineering',    label: 'Biyomedikal Mühendislik',            group: 'Mühendislik' },
  { value: 'bioengineering',            label: 'Biyomühendislik',                    group: 'Mühendislik' },
  { value: 'biotechnology',             label: 'Biyoteknoloji',                      group: 'Mühendislik' },

  // ─── Sağlık ─────────────────────────────────────────────────────
  { value: 'medicine',            label: 'Tıp',                            group: 'Sağlık' },
  { value: 'dentistry',           label: 'Diş Hekimliği',                  group: 'Sağlık' },
  { value: 'pharmacy',            label: 'Eczacılık',                      group: 'Sağlık' },
  { value: 'nursing',             label: 'Hemşirelik',                     group: 'Sağlık' },
  { value: 'midwifery',           label: 'Ebelik',                         group: 'Sağlık' },
  { value: 'veterinary',          label: 'Veterinerlik',                   group: 'Sağlık' },
  { value: 'psychology',          label: 'Psikoloji',                      group: 'Sağlık' },
  { value: 'physiotherapy',       label: 'Fizyoterapi ve Rehabilitasyon',  group: 'Sağlık' },
  { value: 'occupational_therapy',label: 'Ergoterapi',                     group: 'Sağlık' },
  { value: 'speech_therapy',      label: 'Dil ve Konuşma Terapisi',        group: 'Sağlık' },
  { value: 'audiology',           label: 'Odyoloji',                       group: 'Sağlık' },
  { value: 'nutrition_dietetics', label: 'Beslenme ve Diyetetik',          group: 'Sağlık' },
  { value: 'public_health',       label: 'Halk Sağlığı',                   group: 'Sağlık' },
  { value: 'health_management',   label: 'Sağlık Yönetimi',                group: 'Sağlık' },
  { value: 'sports_science',      label: 'Spor Bilimleri',                 group: 'Sağlık' },
  { value: 'neuroscience',        label: 'Sinirbilim',                     group: 'Sağlık' },

  // ─── Temel Bilimler ─────────────────────────────────────────────
  { value: 'mathematics',       label: 'Matematik',                      group: 'Temel Bilimler' },
  { value: 'statistics',        label: 'İstatistik',                     group: 'Temel Bilimler' },
  { value: 'data_science',      label: 'Veri Bilimi',                    group: 'Temel Bilimler' },
  { value: 'physics',           label: 'Fizik',                          group: 'Temel Bilimler' },
  { value: 'astronomy',         label: 'Astronomi ve Uzay Bilimleri',    group: 'Temel Bilimler' },
  { value: 'chemistry',         label: 'Kimya',                          group: 'Temel Bilimler' },
  { value: 'biochemistry',      label: 'Biyokimya',                      group: 'Temel Bilimler' },
  { value: 'biology',           label: 'Biyoloji',                       group: 'Temel Bilimler' },
  { value: 'molecular_biology', label: 'Moleküler Biyoloji & Genetik',   group: 'Temel Bilimler' },
  { value: 'bioinformatics',    label: 'Biyoenformatik',                 group: 'Temel Bilimler' },
  { value: 'geology',           label: 'Jeoloji / Yer Bilimleri',        group: 'Temel Bilimler' },
  { value: 'meteorology',       label: 'Meteoroloji',                    group: 'Temel Bilimler' },
  { value: 'marine_science',    label: 'Deniz Bilimleri',                group: 'Temel Bilimler' },
  { value: 'nanotechnology',    label: 'Nanoteknoloji',                  group: 'Temel Bilimler' },

  // ─── Sosyal Bilimler & Hukuk ────────────────────────────────────
  { value: 'law',                     label: 'Hukuk',                          group: 'Sosyal Bilimler' },
  { value: 'criminology',             label: 'Kriminoloji',                    group: 'Sosyal Bilimler' },
  { value: 'international_relations', label: 'Uluslararası İlişkiler',         group: 'Sosyal Bilimler' },
  { value: 'political_science',       label: 'Siyaset Bilimi',                 group: 'Sosyal Bilimler' },
  { value: 'public_administration',   label: 'Kamu Yönetimi',                  group: 'Sosyal Bilimler' },
  { value: 'public_policy',           label: 'Kamu Politikası',                group: 'Sosyal Bilimler' },
  { value: 'sociology',               label: 'Sosyoloji',                      group: 'Sosyal Bilimler' },
  { value: 'social_work',             label: 'Sosyal Hizmet',                  group: 'Sosyal Bilimler' },
  { value: 'anthropology',            label: 'Antropoloji',                    group: 'Sosyal Bilimler' },
  { value: 'archaeology',             label: 'Arkeoloji',                      group: 'Sosyal Bilimler' },
  { value: 'history',                 label: 'Tarih',                          group: 'Sosyal Bilimler' },
  { value: 'art_history',             label: 'Sanat Tarihi',                   group: 'Sosyal Bilimler' },
  { value: 'philosophy',              label: 'Felsefe',                        group: 'Sosyal Bilimler' },
  { value: 'theology',                label: 'İlahiyat / Din Bilimleri',       group: 'Sosyal Bilimler' },
  { value: 'geography',               label: 'Coğrafya',                       group: 'Sosyal Bilimler' },
  { value: 'social_sciences',         label: 'Sosyal Bilimler (genel)',        group: 'Sosyal Bilimler' },
  { value: 'human_rights',            label: 'İnsan Hakları',                  group: 'Sosyal Bilimler' },
  { value: 'gender_studies',          label: 'Toplumsal Cinsiyet Çalışmaları', group: 'Sosyal Bilimler' },
  { value: 'migration_studies',       label: 'Göç Çalışmaları',                group: 'Sosyal Bilimler' },
  { value: 'peace_conflict_studies',  label: 'Barış ve Çatışma Çalışmaları',   group: 'Sosyal Bilimler' },
  { value: 'development_studies',     label: 'Kalkınma Çalışmaları',           group: 'Sosyal Bilimler' },
  { value: 'area_studies',            label: 'Bölge / Alan Çalışmaları',       group: 'Sosyal Bilimler' },
  { value: 'library_science',         label: 'Bilgi ve Belge Yönetimi',        group: 'Sosyal Bilimler' },

  // ─── İşletme & Ekonomi ──────────────────────────────────────────
  { value: 'business',             label: 'İşletme',                    group: 'İşletme & Ekonomi' },
  { value: 'management',           label: 'Yönetim',                    group: 'İşletme & Ekonomi' },
  { value: 'entrepreneurship',     label: 'Girişimcilik',               group: 'İşletme & Ekonomi' },
  { value: 'economics',            label: 'Ekonomi / İktisat',          group: 'İşletme & Ekonomi' },
  { value: 'finance',              label: 'Finans',                     group: 'İşletme & Ekonomi' },
  { value: 'accounting',           label: 'Muhasebe',                   group: 'İşletme & Ekonomi' },
  { value: 'banking_insurance',    label: 'Bankacılık ve Sigortacılık', group: 'İşletme & Ekonomi' },
  { value: 'actuarial_science',    label: 'Aktüerya',                   group: 'İşletme & Ekonomi' },
  { value: 'marketing',            label: 'Pazarlama',                  group: 'İşletme & Ekonomi' },
  { value: 'human_resources',      label: 'İnsan Kaynakları',           group: 'İşletme & Ekonomi' },
  { value: 'international_trade',  label: 'Uluslararası Ticaret',       group: 'İşletme & Ekonomi' },
  { value: 'logistics',            label: 'Lojistik / Tedarik Zinciri', group: 'İşletme & Ekonomi' },

  // ─── Eğitim & Dil ───────────────────────────────────────────────
  { value: 'education',           label: 'Eğitim Bilimleri',                 group: 'Eğitim & Dil' },
  { value: 'preschool_education', label: 'Okul Öncesi Öğretmenliği',         group: 'Eğitim & Dil' },
  { value: 'primary_education',   label: 'Sınıf Öğretmenliği',               group: 'Eğitim & Dil' },
  { value: 'special_education',   label: 'Özel Eğitim',                      group: 'Eğitim & Dil' },
  { value: 'guidance_counseling', label: 'Rehberlik ve Psikolojik Danışma',  group: 'Eğitim & Dil' },
  { value: 'english_teaching',    label: 'İngilizce Öğretmenliği',           group: 'Eğitim & Dil' },
  { value: 'linguistics',         label: 'Dilbilim',                         group: 'Eğitim & Dil' },
  { value: 'translation',         label: 'Mütercim-Tercümanlık',             group: 'Eğitim & Dil' },
  { value: 'literature',          label: 'Edebiyat',                         group: 'Eğitim & Dil' },

  // ─── Tasarım & Sanat ────────────────────────────────────────────
  { value: 'architecture',             label: 'Mimarlık',                          group: 'Tasarım & Sanat' },
  { value: 'interior_architecture',    label: 'İç Mimarlık',                       group: 'Tasarım & Sanat' },
  { value: 'landscape_architecture',   label: 'Peyzaj Mimarlığı',                  group: 'Tasarım & Sanat' },
  { value: 'urban_planning',           label: 'Şehir ve Bölge Planlama',           group: 'Tasarım & Sanat' },
  { value: 'conservation_restoration', label: 'Kültür Varlıklarını Koruma-Onarım', group: 'Tasarım & Sanat' },
  { value: 'industrial_design',        label: 'Endüstriyel Tasarım',               group: 'Tasarım & Sanat' },
  { value: 'graphic_design',           label: 'Grafik Tasarım',                    group: 'Tasarım & Sanat' },
  { value: 'fashion_design',           label: 'Moda ve Tekstil Tasarımı',          group: 'Tasarım & Sanat' },
  { value: 'game_design',              label: 'Oyun Tasarımı',                     group: 'Tasarım & Sanat' },
  { value: 'animation',                label: 'Animasyon',                         group: 'Tasarım & Sanat' },
  { value: 'photography',              label: 'Fotoğrafçılık',                     group: 'Tasarım & Sanat' },
  { value: 'fine_arts',                label: 'Güzel Sanatlar',                    group: 'Tasarım & Sanat' },
  { value: 'music',                    label: 'Müzik',                             group: 'Tasarım & Sanat' },
  { value: 'performing_arts',          label: 'Sahne Sanatları (tiyatro, dans)',   group: 'Tasarım & Sanat' },
  { value: 'cinema',                   label: 'Sinema & TV',                       group: 'Tasarım & Sanat' },

  // ─── Medya & İletişim ───────────────────────────────────────────
  { value: 'communication',    label: 'İletişim',                  group: 'Medya & İletişim' },
  { value: 'journalism',       label: 'Gazetecilik',               group: 'Medya & İletişim' },
  { value: 'new_media',        label: 'Yeni Medya / Dijital Medya',group: 'Medya & İletişim' },
  { value: 'public_relations', label: 'Halkla İlişkiler',          group: 'Medya & İletişim' },
  { value: 'advertising',      label: 'Reklamcılık',               group: 'Medya & İletişim' },

  // ─── Diğer ──────────────────────────────────────────────────────
  { value: 'agriculture',           label: 'Ziraat / Tarım',              group: 'Diğer' },
  { value: 'forestry',              label: 'Ormancılık',                  group: 'Diğer' },
  { value: 'fisheries',             label: 'Su Ürünleri / Balıkçılık',    group: 'Diğer' },
  { value: 'environmental_science', label: 'Çevre Bilimleri',             group: 'Diğer' },
  { value: 'climate_studies',       label: 'İklim ve Sürdürülebilirlik',  group: 'Diğer' },
  { value: 'disaster_management',   label: 'Afet ve Acil Durum Yönetimi', group: 'Diğer' },
  { value: 'aviation',              label: 'Havacılık Yönetimi / Pilotaj',group: 'Diğer' },
  { value: 'maritime',              label: 'Denizcilik',                  group: 'Diğer' },
  { value: 'tourism',               label: 'Turizm & Otelcilik',          group: 'Diğer' },
  { value: 'gastronomy',            label: 'Gastronomi',                  group: 'Diğer' },
  { value: 'ngo',                   label: 'STK / Sivil Toplum',          group: 'Diğer' },
  { value: 'youth_work',            label: 'Gençlik Çalışması',           group: 'Diğer' },
]

export const FIELD_LABELS: Record<string, string> = Object.fromEntries(
  FIELDS.map(f => [f.value, f.label])
)
