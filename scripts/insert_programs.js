const https = require("https");

const SUPABASE_URL =
  process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error(
    "Eksik ortam değişkeni: SUPABASE_URL (veya NEXT_PUBLIC_SUPABASE_URL) ve SUPABASE_SERVICE_ROLE_KEY gerekli.\n" +
      "Örnek: scripts/env.example — anahtar repoda tutulmaz.\n" +
      "Eski anahtar sızdıysa: Supabase Dashboard → Settings → API → service_role → Regenerate."
  );
  process.exit(1);
}

let restHost;
try {
  restHost = new URL(SUPABASE_URL).hostname;
} catch {
  console.error("Geçersiz SUPABASE_URL:", SUPABASE_URL);
  process.exit(1);
}

const PROGRAMS = [
  {
    title: "MEXT Bursu — Japonya",
    official_url: "https://www.studyinjapan.go.jp/en/smap-stopj-applications-scholarships.html",
    deadline: "2027-06-30",
    deadline_notes: "Türkiye Japonya Büyükelçiliği üzerinden Mayıs–Haziran aylarında başvurulur",
    host_countries: ["JP"], target_countries: ["TR"], eligible_citizenships: ["TR"],
    target_fields: ["all"], study_level: ["bachelor", "master", "phd"],
    age_min: 18, age_max: 35,
    language_requirement: "Japonca veya İngilizce",
    eligibility_notes: "Japonya Büyükelçiliği kanalıyla başvurulur. Lisans, yüksek lisans ve doktora programları için ayrı kategoriler mevcuttur.",
    funding_type: "full",
    funding_notes: "Uçak bileti + aylık ¥117.000–144.000 harcırah + öğrenim ücreti muafiyeti",
    category_id: "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "Kore Hükümeti Bursu (GKS) — Güney Kore",
    official_url: "https://www.studyinkorea.go.kr/en/sub/gks/allnew_korea.do",
    deadline: "2027-03-31",
    deadline_notes: "Büyükelçilik veya üniversite kanalıyla Şubat–Mart ayında başvurulur",
    host_countries: ["KR"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["all"], study_level: ["bachelor", "master", "phd"],
    age_min: 18, age_max: 34,
    language_requirement: "Korece (TOPIK) veya İngilizce",
    eligibility_notes: "147 ülkeden başvuru alınır. Büyükelçilik ya da doğrudan üniversite kanalıyla başvurulabilir. 1 yıllık hazırlık Korece kursu dahildir.",
    funding_type: "full",
    funding_notes: "Aylık ₩900.000–1.000.000 harcırah + öğrenim ücreti + uçak bileti + sağlık sigortası",
    category_id: "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "İsveç Enstitüsü Bursu (SI) — İsveç",
    official_url: "https://si.se/en/apply/scholarships/sweden-institute-scholarships-for-global-professionals/",
    deadline: "2027-02-10",
    deadline_notes: "Her yıl Şubat başında başvurular kapanır",
    host_countries: ["SE"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["all"], study_level: ["master"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce (IELTS 6.5+)",
    eligibility_notes: "En az 3.000 saat iş deneyimi gerektirir. Liderlik potansiyeli ve ülkeler arası köprü kurma hedefi önem taşır.",
    funding_type: "full",
    funding_notes: "Aylık 11.000 SEK + öğrenim ücreti + seyahat katkısı + sağlık sigortası",
    category_id: "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "Stipendium Hungaricum — Macaristan",
    official_url: "https://stipendiumhungaricum.hu",
    deadline: "2027-01-16",
    deadline_notes: "Her yıl Ocak ayı ortasında kapanır; YÖK üzerinden başvurulur",
    host_countries: ["HU"], target_countries: ["TR"], eligible_citizenships: ["TR"],
    target_fields: ["all"], study_level: ["bachelor", "master", "phd"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce veya Macarca",
    eligibility_notes: "Türkiye kota ülkeler arasındadır. Başvurular YÖK ve Macaristan Büyükelçiliği üzerinden yapılır. Geniş program ve üniversite seçeneği sunar.",
    funding_type: "full",
    funding_notes: "Öğrenim ücreti muafiyeti + aylık HUF 43.700–140.000 harcırah + yurt veya konut katkısı",
    category_id: "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    is_featured: true, is_active: true, is_verified: true,
  },
  {
    title: "Holland Scholarship — Hollanda",
    official_url: "https://www.studyinholland.nl/finances/grants-and-scholarships/holland-scholarship",
    deadline: "2027-02-01",
    deadline_notes: "Her yıl Ocak–Şubat arasında kapanır; ilgili Hollanda üniversitesi üzerinden başvurulur",
    host_countries: ["NL"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["all"], study_level: ["bachelor", "master"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce (IELTS/TOEFL)",
    eligibility_notes: "AB/AEA üyesi olmayan ülkelerden Hollanda üniversitelerine başvuran öğrenciler için. Başvuruyu ilgili üniversite üzerinden yaparsın.",
    funding_type: "partial",
    funding_notes: "€5.000 tek seferlik hibe (ilk yıl için)",
    category_id: "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "ETH Zürich Mükemmellik Bursu — İsviçre",
    official_url: "https://ethz.ch/en/the-eth-zurich/education/excellence-scholarship.html",
    deadline: "2026-12-15",
    deadline_notes: "Aralık ayı ortasında kapanır (sonraki akademik yıl için)",
    host_countries: ["CH"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["computer_science","electrical_engineering","mechanical_engineering","architecture","mathematics","physics","chemistry","data_science","environmental_science"],
    study_level: ["master"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce veya Almanca",
    eligibility_notes: "ETH Zürich Master programına kabul almış olmak gerekmektedir. Üstün akademik başarı ve araştırma deneyimi beklenir.",
    funding_type: "full",
    funding_notes: "Aylık CHF 12.000 + öğrenim ücreti muafiyeti",
    category_id: "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "CERN Yaz Öğrencisi Programı — İsviçre",
    official_url: "https://home.cern/students-educators/summer-student-programme",
    deadline: "2027-01-27",
    deadline_notes: "Başvurular her yıl Ocak ayı sonunda kapanır",
    host_countries: ["CH"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["physics","computer_science","electrical_engineering","mathematics","mechanical_engineering"],
    study_level: ["bachelor","master"],
    age_min: 18, age_max: 31,
    language_requirement: "İngilizce",
    eligibility_notes: "Fizik, bilgisayar veya mühendislikte en az 3 yıl lisans eğitimi tamamlanmış olmalıdır. 8–13 haftalık program; CERN üye ülke şartı aranmaz.",
    funding_type: "stipend",
    funding_notes: "Günlük 91 CHF harcırah + konaklama katkısı + gidiş-dönüş uçak bileti",
    category_id: "2db63ccc-3cf2-4659-90f6-f8b799559cfe",
    is_featured: true, is_active: true, is_verified: true,
  },
  {
    title: "Avrupa Parlamentosu Schuman Stajı — Brüksel/Lüksemburg",
    official_url: "https://www.europarl.europa.eu/at-your-service/en/be-part-of-it/traineeships",
    deadline: null,
    deadline_notes: "Şubat dönemi için Eylül, Ekim dönemi için Nisan başında başvurular kapanır",
    host_countries: ["BE","LU"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["law","international_relations","political_science","economics","communication","linguistics"],
    study_level: ["bachelor","master"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce, Fransızca veya Almanca",
    eligibility_notes: "Üniversite diploması veya en az 3 yıl yükseköğrenim tamamlanmış olmalıdır. 5 aylık ücretli staj; Şubat ve Ekim dönemleri mevcuttur.",
    funding_type: "stipend",
    funding_notes: "Aylık ~€1.400 harcırah",
    category_id: "2db63ccc-3cf2-4659-90f6-f8b799559cfe",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "IAESTE Uluslararası Teknik Staj",
    official_url: "https://iaeste.org/students/",
    deadline: null,
    deadline_notes: "Türkiye için başvurular genellikle Aralık–Şubat arasında yapılır",
    host_countries: ["*"], target_countries: ["TR"], eligible_citizenships: ["TR"],
    target_fields: ["computer_science","electrical_engineering","mechanical_engineering","chemistry","agriculture","architecture"],
    study_level: ["bachelor","master"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce veya ev sahibi ülke dili",
    eligibility_notes: "IAESTE Türkiye üzerinden başvurulur. 50'den fazla ülkede teknik alanda ücretli staj imkânı sunar.",
    funding_type: "stipend",
    funding_notes: "Konaklama + yerel ulaşım + haftalık harcırah (ülkeye göre değişir)",
    category_id: "2db63ccc-3cf2-4659-90f6-f8b799559cfe",
    is_featured: false, is_active: true, is_verified: true,
  },
  {
    title: "Birleşmiş Milletler Staj Programı",
    official_url: "https://www.un.org/en/about-us/internships",
    deadline: null,
    deadline_notes: "Sürekli açık; pozisyona göre 2–3 ay öncesinde başvurulur",
    host_countries: ["US","CH","AT","KE"], target_countries: ["all"], eligible_citizenships: ["all"],
    target_fields: ["international_relations","law","economics","public_health","communication","human_rights","environmental_science"],
    study_level: ["master","phd"],
    age_min: null, age_max: null,
    language_requirement: "İngilizce veya Fransızca",
    eligibility_notes: "Yüksek lisans öğrencisi veya son bir yıl içinde mezun olmuş olmak gerekmektedir. New York, Cenevre, Viyana ve Nairobi pozisyonları mevcuttur.",
    funding_type: "partial",
    funding_notes: "Çoğu pozisyon ücretsizdir; bazı programlarda günlük harcırah ödenir",
    category_id: "2db63ccc-3cf2-4659-90f6-f8b799559cfe",
    is_featured: false, is_active: true, is_verified: true,
  },
];

const body = JSON.stringify(PROGRAMS);
const options = {
  hostname: restHost,
  path: "/rest/v1/opportunities",
  method: "POST",
  headers: {
    apikey: SERVICE_KEY,
    Authorization: "Bearer " + SERVICE_KEY,
    "Content-Type": "application/json",
    Prefer: "return=minimal",
    "Content-Length": Buffer.byteLength(body),
  },
};

const req = https.request(options, (res) => {
  let data = "";
  res.on("data", (chunk) => (data += chunk));
  res.on("end", () => {
    if (res.statusCode === 201 || res.statusCode === 200) {
      console.log(`Basarili! ${PROGRAMS.length} program eklendi.`);
    } else {
      console.log(`Hata ${res.statusCode}: ${data}`);
    }
  });
});
req.on("error", (e) => console.error("Hata:", e));
req.write(body);
req.end();
