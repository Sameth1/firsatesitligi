/**
 * Ülke verisi — ISO 3166-1 alpha-2 kodu ⇄ Türkçe ülke adı.
 *
 * Neden burada: veritabanındaki fırsat kayıtları (`host_country`, `citizenship`)
 * herhangi bir iki harfli ülke kodu taşıyabiliyor; sonuç ekranı da form ekranı da
 * kullanıcıya Türkçe adı göstermek zorunda. Eşleme tek yerde dursun ki
 * bir ülkenin adı ya da bayrağı değiştiğinde tek dosya güncellensin.
 *
 * Bayrak emojisi (🇩🇪) KULLANMIYORUZ: Windows'ta bayrak emojileri render
 * olmuyor ve kullanıcı "DE" gibi iki harf görüyor. Onun yerine
 * `public/flags/<kod>.svg` altındaki yerel SVG'ler `<Flag />` ile basılıyor.
 *
 * Kurallar:
 * - Kodlar her yerde BÜYÜK HARF tutulur (DB böyle çalışıyor).
 * - Dosya yolu üretilirken küçültülür (`flagSrc`).
 * - `countryNameTr` bilinmeyen kodda ASLA boş/undefined dönmez; kodu aynen döndürür.
 */

export type Country = {
  /** ISO 3166-1 alpha-2, büyük harf. Örn: 'DE' */
  code: string
  /** Türkçe ülke adı. Örn: 'Almanya' */
  nameTr: string
}

/**
 * Kod → Türkçe ad ham eşlemesi.
 * ISO 3166-1 alpha-2'nin tamamına yakını + istisnai olarak ayrılmış `EU`
 * (Erasmus+ gibi Avrupa geneli programlar için) ve yaygın kullanımdaki `XK` (Kosova).
 */
export const COUNTRY_NAMES_TR: Readonly<Record<string, string>> = {
  AD: 'Andorra',
  AE: 'Birleşik Arap Emirlikleri',
  AF: 'Afganistan',
  AG: 'Antigua ve Barbuda',
  AI: 'Anguilla',
  AL: 'Arnavutluk',
  AM: 'Ermenistan',
  AO: 'Angola',
  AQ: 'Antarktika',
  AR: 'Arjantin',
  AS: 'Amerikan Samoası',
  AT: 'Avusturya',
  AU: 'Avustralya',
  AW: 'Aruba',
  AX: 'Åland Adaları',
  AZ: 'Azerbaycan',
  BA: 'Bosna-Hersek',
  BB: 'Barbados',
  BD: 'Bangladeş',
  BE: 'Belçika',
  BF: 'Burkina Faso',
  BG: 'Bulgaristan',
  BH: 'Bahreyn',
  BI: 'Burundi',
  BJ: 'Benin',
  BL: 'Saint Barthélemy',
  BM: 'Bermuda',
  BN: 'Brunei',
  BO: 'Bolivya',
  BQ: 'Karayip Hollandası',
  BR: 'Brezilya',
  BS: 'Bahamalar',
  BT: 'Butan',
  BV: 'Bouvet Adası',
  BW: 'Botsvana',
  BY: 'Belarus',
  BZ: 'Belize',
  CA: 'Kanada',
  CC: 'Cocos Adaları',
  CD: 'Kongo Demokratik Cumhuriyeti',
  CF: 'Orta Afrika Cumhuriyeti',
  CG: 'Kongo Cumhuriyeti',
  CH: 'İsviçre',
  CI: 'Fildişi Sahili',
  CK: 'Cook Adaları',
  CL: 'Şili',
  CM: 'Kamerun',
  CN: 'Çin',
  CO: 'Kolombiya',
  CR: 'Kosta Rika',
  CU: 'Küba',
  CV: 'Cabo Verde',
  CW: 'Curaçao',
  CX: 'Christmas Adası',
  CY: 'Kıbrıs',
  CZ: 'Çekya',
  DE: 'Almanya',
  DJ: 'Cibuti',
  DK: 'Danimarka',
  DM: 'Dominika',
  DO: 'Dominik Cumhuriyeti',
  DZ: 'Cezayir',
  EC: 'Ekvador',
  EE: 'Estonya',
  EG: 'Mısır',
  EH: 'Batı Sahra',
  ER: 'Eritre',
  ES: 'İspanya',
  ET: 'Etiyopya',
  EU: 'Avrupa Birliği',
  FI: 'Finlandiya',
  FJ: 'Fiji',
  FK: 'Falkland Adaları',
  FM: 'Mikronezya',
  FO: 'Faroe Adaları',
  FR: 'Fransa',
  GA: 'Gabon',
  GB: 'Birleşik Krallık',
  GD: 'Grenada',
  GE: 'Gürcistan',
  GF: 'Fransız Guyanası',
  GG: 'Guernsey',
  GH: 'Gana',
  GI: 'Cebelitarık',
  GL: 'Grönland',
  GM: 'Gambiya',
  GN: 'Gine',
  GP: 'Guadeloupe',
  GQ: 'Ekvator Ginesi',
  GR: 'Yunanistan',
  GS: 'Güney Georgia ve Güney Sandwich Adaları',
  GT: 'Guatemala',
  GU: 'Guam',
  GW: 'Gine-Bissau',
  GY: 'Guyana',
  HK: 'Hong Kong',
  HM: 'Heard Adası ve McDonald Adaları',
  HN: 'Honduras',
  HR: 'Hırvatistan',
  HT: 'Haiti',
  HU: 'Macaristan',
  ID: 'Endonezya',
  IE: 'İrlanda',
  IL: 'İsrail',
  IM: 'Man Adası',
  IN: 'Hindistan',
  IO: 'Britanya Hint Okyanusu Toprakları',
  IQ: 'Irak',
  IR: 'İran',
  IS: 'İzlanda',
  IT: 'İtalya',
  JE: 'Jersey',
  JM: 'Jamaika',
  JO: 'Ürdün',
  JP: 'Japonya',
  KE: 'Kenya',
  KG: 'Kırgızistan',
  KH: 'Kamboçya',
  KI: 'Kiribati',
  KM: 'Komorlar',
  KN: 'Saint Kitts ve Nevis',
  KP: 'Kuzey Kore',
  KR: 'Güney Kore',
  KW: 'Kuveyt',
  KY: 'Cayman Adaları',
  KZ: 'Kazakistan',
  LA: 'Laos',
  LB: 'Lübnan',
  LC: 'Saint Lucia',
  LI: 'Liechtenstein',
  LK: 'Sri Lanka',
  LR: 'Liberya',
  LS: 'Lesotho',
  LT: 'Litvanya',
  LU: 'Lüksemburg',
  LV: 'Letonya',
  LY: 'Libya',
  MA: 'Fas',
  MC: 'Monako',
  MD: 'Moldova',
  ME: 'Karadağ',
  MF: 'Saint Martin',
  MG: 'Madagaskar',
  MH: 'Marshall Adaları',
  MK: 'Kuzey Makedonya',
  ML: 'Mali',
  MM: 'Myanmar',
  MN: 'Moğolistan',
  MO: 'Makao',
  MP: 'Kuzey Mariana Adaları',
  MQ: 'Martinik',
  MR: 'Moritanya',
  MS: 'Montserrat',
  MT: 'Malta',
  MU: 'Mauritius',
  MV: 'Maldivler',
  MW: 'Malavi',
  MX: 'Meksika',
  MY: 'Malezya',
  MZ: 'Mozambik',
  NA: 'Namibya',
  NC: 'Yeni Kaledonya',
  NE: 'Nijer',
  NF: 'Norfolk Adası',
  NG: 'Nijerya',
  NI: 'Nikaragua',
  NL: 'Hollanda',
  NO: 'Norveç',
  NP: 'Nepal',
  NR: 'Nauru',
  NU: 'Niue',
  NZ: 'Yeni Zelanda',
  OM: 'Umman',
  PA: 'Panama',
  PE: 'Peru',
  PF: 'Fransız Polinezyası',
  PG: 'Papua Yeni Gine',
  PH: 'Filipinler',
  PK: 'Pakistan',
  PL: 'Polonya',
  PM: 'Saint Pierre ve Miquelon',
  PN: 'Pitcairn Adaları',
  PR: 'Porto Riko',
  PS: 'Filistin',
  PT: 'Portekiz',
  PW: 'Palau',
  PY: 'Paraguay',
  QA: 'Katar',
  RE: 'Réunion',
  RO: 'Romanya',
  RS: 'Sırbistan',
  RU: 'Rusya',
  RW: 'Ruanda',
  SA: 'Suudi Arabistan',
  SB: 'Solomon Adaları',
  SC: 'Seyşeller',
  SD: 'Sudan',
  SE: 'İsveç',
  SG: 'Singapur',
  SH: 'Saint Helena',
  SI: 'Slovenya',
  SJ: 'Svalbard ve Jan Mayen',
  SK: 'Slovakya',
  SL: 'Sierra Leone',
  SM: 'San Marino',
  SN: 'Senegal',
  SO: 'Somali',
  SR: 'Surinam',
  SS: 'Güney Sudan',
  ST: 'São Tomé ve Príncipe',
  SV: 'El Salvador',
  SX: 'Sint Maarten',
  SY: 'Suriye',
  SZ: 'Esvatini',
  TC: 'Turks ve Caicos Adaları',
  TD: 'Çad',
  TF: 'Fransız Güney Toprakları',
  TG: 'Togo',
  TH: 'Tayland',
  TJ: 'Tacikistan',
  TK: 'Tokelau',
  TL: 'Doğu Timor',
  TM: 'Türkmenistan',
  TN: 'Tunus',
  TO: 'Tonga',
  TR: 'Türkiye',
  TT: 'Trinidad ve Tobago',
  TV: 'Tuvalu',
  TW: 'Tayvan',
  TZ: 'Tanzanya',
  UA: 'Ukrayna',
  UG: 'Uganda',
  UM: 'ABD Küçük Dış Adaları',
  US: 'ABD',
  UY: 'Uruguay',
  UZ: 'Özbekistan',
  VA: 'Vatikan',
  VC: 'Saint Vincent ve Grenadinler',
  VE: 'Venezuela',
  VG: 'Britanya Virjin Adaları',
  VI: 'ABD Virjin Adaları',
  VN: 'Vietnam',
  VU: 'Vanuatu',
  WF: 'Wallis ve Futuna',
  WS: 'Samoa',
  XK: 'Kosova',
  YE: 'Yemen',
  YT: 'Mayotte',
  ZA: 'Güney Afrika',
  ZM: 'Zambiya',
  ZW: 'Zimbabve',
}

/**
 * Türkçe alfabetik sıraya göre karşılaştırıcı.
 * `localeCompare(…, 'tr')` şart: Türkçede I harfi İ'den önce gelir
 * ("Irak" → "İran" → "İspanya"), varsayılan sıralama bunu yanlış yapar.
 */
export function compareCountriesTr(a: Country, b: Country): number {
  return a.nameTr.localeCompare(b.nameTr, 'tr')
}

/** Tüm ülkeler, Türkçe ada göre alfabetik. */
export const COUNTRIES: readonly Country[] = Object.entries(COUNTRY_NAMES_TR)
  .map(([code, nameTr]) => ({ code, nameTr }))
  .sort(compareCountriesTr)

/**
 * `COUNTRIES` için takma ad.
 * `page.tsx` içinde yerel bir `COUNTRIES` sabiti zaten var; oradan import ederken
 * ad çakışması yaşamamak için bunu kullanabilirsin.
 */
export const ALL_COUNTRIES = COUNTRIES

/** Toplam ülke sayısı — testlerde ve "N ülke" tipi metinlerde işe yarar. */
export const COUNTRY_COUNT = COUNTRIES.length

/** Gelen kodu normalize eder: boşlukları atar, büyük harfe çevirir. */
export function normalizeCountryCode(code: string | null | undefined): string {
  return (code ?? '').trim().toUpperCase()
}

/** Kod tanıdık bir ülkeye mi ait? (Bayrak dosyası da bu küme için garanti var.) */
export function isKnownCountry(code: string | null | undefined): boolean {
  return normalizeCountryCode(code) in COUNTRY_NAMES_TR
}

/**
 * Kodun Türkçe adı.
 * Bilinmeyen kod gelirse kodun kendisini döndürür (büyük harfe çevrilmiş);
 * kod da boşsa boş string döner. Asla `undefined` dönmez — sonuç ekranı
 * bu değeri doğrudan basıyor.
 */
export function countryNameTr(code: string | null | undefined): string {
  const key = normalizeCountryCode(code)
  return COUNTRY_NAMES_TR[key] ?? key
}

/**
 * Yerel bayrak SVG'sinin yolu — örn. `flagSrc('DE') === '/flags/de.svg'`.
 * Dış CDN'e runtime bağımlılığı yok; dosyalar `public/flags/` altında.
 *
 * İki harfli olmayan/bozuk girdide boş string döner; `<Flag />` bu durumda
 * görsel yerine kod rozetini basar.
 */
export function flagSrc(code: string | null | undefined): string {
  const key = normalizeCountryCode(code)
  if (!/^[A-Z]{2}$/.test(key)) return ''
  return `/flags/${key.toLowerCase()}.svg`
}

/**
 * Vatandaşlık seçicisinde listenin başında gösterilecek öne çıkan ülkeler:
 * Türkiye + yakın çevre + gençlerin en sık gittiği hedef ülkeler.
 * TR bilinçli olarak ilk sırada; kalanı Türkçe alfabetik.
 */
export const POPULAR_CITIZENSHIPS: readonly Country[] = (() => {
  const codes = [
    'AT', 'AZ', 'BE', 'BG', 'CA', 'CH', 'DE', 'FR', 'GB', 'GE',
    'GR', 'IQ', 'IR', 'KZ', 'MK', 'NL', 'RU', 'SE', 'SY', 'UA',
    'US', 'XK',
  ]
  const rest = codes
    .map(code => ({ code, nameTr: COUNTRY_NAMES_TR[code] }))
    .sort(compareCountriesTr)
  return [{ code: 'TR', nameTr: COUNTRY_NAMES_TR.TR }, ...rest]
})()

/** Öne çıkan ülke kodları kümesi — "bu kod popüler mi" kontrolü için. */
export const POPULAR_CITIZENSHIP_CODES: readonly string[] =
  POPULAR_CITIZENSHIPS.map(c => c.code)
