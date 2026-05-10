"""
Sorunlu URL'leri tespit edip aday URL'lerle değiştirir.
Her kayıt için aday listesini sırayla dener, ilk 200 (veya redirect ile 200) bulursa update eder.
Hiçbir aday çalışmazsa is_active=false yapar.
"""

import os, time, requests
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SB = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

# Browser-like UA — bazı siteler basit UA'yı 403'lüyor
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
HDR = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
       "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"}

# Her kayıt için aday URL'ler — en olasıdan en az olasıya
CANDIDATES = {
    "a09adede-289c-4cc9-8b7b-bd7efed9dac3": [  # Schuman
        "https://www.europarl.europa.eu/contracts-and-grants/en/traineeships/schuman-traineeships",
        "https://www.europarl.europa.eu/contracts-and-grants/en/traineeships",
        "https://traineeships.secure.europarl.europa.eu/traineeships/",
    ],
    "da4d33a4-7b19-4c9d-b367-90704c94cd5c": [  # BM Staj
        "https://careers.un.org/internships",
        "https://careers.un.org/jobs?ds=internship",
        "https://www.un.org/en/about-us/un-internships",
    ],
    "62a57f96-8d57-4ef7-a19c-1aa59a83784f": [  # Chevening (timeout idi)
        "https://www.chevening.org/scholarships/",
        "https://www.chevening.org/scholarship/",
        "https://www.chevening.org/",
    ],
    "f3660ac7-32d6-4e23-8846-76cf28e88c30": [  # Erasmus+ KA1
        "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/teach-or-train-abroad",
        "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals",
        "https://erasmus-plus.ec.europa.eu/opportunities",
    ],
    "d57d66d8-6654-4269-9280-504c4596019d": [  # ETH Zürich Excellence
        "https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html",
        "https://ethz.ch/en/studies/financial/scholarships/excellencescholarship.html",
        "https://ethz.ch/en/studies/non-eth-bachelor-students/financial-aid/excellence-scholarship.html",
    ],
    "1faf9d29-342d-49b6-91b9-96236a9cd793": [  # BGF Fransa
        "https://www.campusfrance.org/en/french-government-scholarship",
        "https://www.campusfrance.org/en/french-government-scholarships",
        "https://www.campusfrance.org/en/page/funding",
    ],
    "19ede3a1-08a7-480c-a6e0-88dee7885672": [  # FU Berlin Summer
        "https://www.fu-berlin.de/en/sites/fubest/",
        "https://www.fubis.org/",
        "https://www.fu-berlin.de/en/international/student-mobility/incoming/programs/summer-university/",
    ],
    "2fae9a40-d71e-4c49-a84f-6fe5e5296077": [  # Heinrich Böll
        "https://www.boell.de/en/scholarships",
        "https://www.boell.de/en/foundation/scholarships",
        "https://www.boell.de/en/study-grants",
    ],
    "e0ea9441-54ad-451e-a8b4-80d082997d48": [  # Holland Scholarship
        "https://www.studyinnl.org/finances/holland-scholarship",
        "https://www.studyinnl.org/scholarships/holland-scholarship",
        "https://www.studyinnl.org/",
    ],
    "9d978c23-f54b-4f7d-b228-fd497861ff7a": [  # SI Sweden
        "https://si.se/en/apply/scholarships/",
        "https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/",
        "https://si.se/en/",
    ],
    "c77c3eb4-e1b8-4485-9bb4-ce76860d2494": [  # Konrad Adenauer (403 bot olabilir)
        "https://www.kas.de/en/web/begabtenfoerderung-und-kultur/scholarships",
        "https://www.kas.de/en/scholarships",
        "https://www.kas.de/en/web/begabtenfoerderung-und-kultur",
    ],
    "e17cbc30-8345-4b02-aad5-b4aeb9e1ff86": [  # GKS Korea
        "https://www.studyinkorea.go.kr/en/sub/gks/gks_intro.do",
        "https://www.studyinkorea.go.kr/en/main.do",
        "https://www.studyinkorea.go.kr/en/",
    ],
    "5989ccc5-01ac-41cd-83df-66c87edb4b58": [  # MEXT Japan
        "https://www.studyinjapan.go.jp/en/planning/scholarship/types/scholarship-type-mext-scholarship.html",
        "https://www.studyinjapan.go.jp/en/planning/scholarship/",
        "https://www.studyinjapan.go.jp/en/",
    ],
}

def test_url(url):
    """URL'yi test et — 200/300 döndüğünde (status, final_url, error) döner."""
    try:
        r = requests.get(url, headers=HDR, timeout=20, allow_redirects=True)
        return r.status_code, r.url if r.url != url else None, None
    except requests.exceptions.SSLError as e:
        return None, None, f"SSL: {str(e)[:80]}"
    except requests.exceptions.Timeout:
        return None, None, "Timeout"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {str(e)[:80]}"

def find_alive(opp_id):
    """Adaylar arasından ilk 200 dönen URL'yi bul."""
    for url in CANDIDATES.get(opp_id, []):
        st, final, err = test_url(url)
        if st and 200 <= st < 400:
            return url, st, final
        time.sleep(0.5)
    return None, None, None

def update_record(opp_id, new_url, http_status, final_url, deactivate=False):
    payload = {
        "last_url_check_at": datetime.now(timezone.utc).isoformat(),
        "last_url_check_status": http_status,
        "last_url_check_error": None if not deactivate else "Tüm adaylar başarısız — pasifleştirildi",
        "last_url_check_final_url": final_url,
    }
    if new_url:
        payload["official_url"] = new_url
    if deactivate:
        payload["is_active"] = False
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={**SB, "Prefer": "return=minimal"},
        params={"id": f"eq.{opp_id}"}, json=payload)
    return r.status_code in (200, 204)

# Mevcut sorunlu kayıtları al
sorunlu = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities", headers=SB,
    params={"select":"id,title,official_url",
            "is_active":"eq.true",
            "or":"(last_url_check_error.not.is.null,and(last_url_check_status.gte.400,last_url_check_status.lt.600))",
            "order":"title.asc"}).json()

print(f"🔧 {len(sorunlu)} sorunlu kayıt onarılıyor")
print()

fixed = deactivated = 0
for x in sorunlu:
    title = x['title'][:55]
    new_url, status, final = find_alive(x['id'])
    if new_url:
        update_record(x['id'], new_url, status, final)
        marker = "🔁" if new_url != x['official_url'] else "✅"
        print(f"  {marker} {title}")
        print(f"     OLD: {x['official_url']}")
        print(f"     NEW: {new_url} (HTTP {status}{' → '+final if final else ''})")
        fixed += 1
    else:
        update_record(x['id'], None, None, None, deactivate=True)
        print(f"  ⛔ {title} — tüm adaylar başarısız, pasifleştirildi")
        deactivated += 1
    print()

print("─" * 60)
print(f"🔁 URL düzeltildi : {fixed}")
print(f"⛔ Pasifleştirildi : {deactivated}")
print("─" * 60)
