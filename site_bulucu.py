"""
Fırsat Sayfası Bulucu
=====================
Groq (ücretsiz) + DuckDuckGo kullanarak Türk gençlerin
başvurabileceği uluslararası fırsatların bulunduğu web
sayfalarını bulur. Sonucu siteler.txt dosyasına yazar.

Kurulum:
  pip3 install groq requests beautifulsoup4 python-dotenv

Kullanım:
  python3 site_bulucu.py
  python3 site_bulucu.py --rounds 5
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
import requests
from dotenv import load_dotenv

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    print("pip3 install ddgs")

try:
    from groq import Groq
except ImportError:
    print("pip3 install groq")
    sys.exit(1)

load_dotenv()

GROQ_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL  = "meta-llama/llama-4-scout-17b-16e-instruct"  # ucretsiz, hizli

MAX_ROUNDS        = 3
MAX_RESULTS_PER_Q = 8
OUTPUT_FILE       = "siteler.txt"

visited    = set()
found_urls = []   # [(url, sayi)]

# ─── Groq ─────────────────────────────────────────────────────────────────────

_client = None

def ask(prompt):
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_KEY)
    try:
        resp = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        print("  Groq hatasi: {}".format(e))
        time.sleep(5)
        return ""

# ─── Sayfa çekici ─────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code != 200:
            return None
        content_type = r.headers.get("Content-Type", "")
        if "text" not in content_type and "html" not in content_type:
            return None  # PDF, binary vb. atla
        return r.text
    except Exception:
        return None

def to_text(html, max_chars=4000):
    if HAS_BS4:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for t in soup(["script", "style", "nav", "footer", "header"]):
                t.decompose()
            return soup.get_text(separator="\n", strip=True)[:max_chars]
        except Exception:
            pass
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html, flags=re.DOTALL))[:max_chars]

def uid(url):
    return hashlib.md5(url.encode()).hexdigest()

# ─── DuckDuckGo ───────────────────────────────────────────────────────────────

def ddg_search(query, n=8):
    try:
        results = DDGS().text(query, max_results=n)
        urls = [r["href"] for r in results if r.get("href", "").startswith("http")]
        return list(dict.fromkeys(urls))
    except Exception as e:
        print("  DDG hatasi: {}".format(e))
        return []

# ─── Sorgular üret ────────────────────────────────────────────────────────────

def generate_queries(round_num, prev):
    prev_str = "\n".join("- {}".format(q) for q in prev) if prev else "None"
    out = ask(
        "You are a researcher finding international opportunities for Turkish youth.\n"
        "Generate 5 NEW English DuckDuckGo search queries to find pages with scholarships, "
        "internships, volunteering, summer schools, exchange programs, or grants that "
        "Turkish students can apply to.\n\n"
        "Round: {}\n"
        "Previously used queries:\n{}\n\n"
        "Rules:\n"
        "- Must be different from previous queries\n"
        "- Use keywords like: apply, deadline, eligibility, Turkey, students, international\n"
        "- Target different categories each time\n\n"
        "Return ONLY a JSON list, nothing else:\n"
        '["query 1", "query 2", "query 3", "query 4", "query 5"]'.format(round_num, prev_str)
    )
    cleaned = re.sub(r"```json\s*|\s*```", "", out).strip()
    try:
        return [str(q) for q in json.loads(cleaned) if q][:6]
    except Exception:
        return re.findall(r'"([^"]{10,})"', cleaned)[:6]

# ─── Fırsat kontrolü ──────────────────────────────────────────────────────────

def count_opportunities(text, url):
    """Sayfadaki firsat sayisini dondurur. 0 = firsat yok."""
    out = ask(
        "How many real, apply-able international opportunities "
        "(scholarships, internships, volunteering, summer schools, exchange programs, grants, fellowships) "
        "that students from Turkey (or all countries) can apply to are listed on this page?\n\n"
        "Page: {}\n\nContent:\n---\n{}\n---\n\n"
        "Reply with ONLY a single integer number (0 if none). Nothing else.".format(url, text)
    )
    try:
        return int(re.search(r"\d+", out.strip()).group())
    except Exception:
        # Sayi bulamazsa evet/hayir kontrolu yap
        return 1 if any(w in out.upper() for w in ["YES", "EVET"]) else 0

# ─── Kaydet ───────────────────────────────────────────────────────────────────

def save():
    total_opps = sum(c for _, c in found_urls)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Turk gencler icin firsat iceren sayfalar\n")
        f.write("# Sayfa: {} | Tahmini firsat: {}\n\n".format(len(found_urls), total_opps))
        # Firsat sayisina gore sirala (coktan aza)
        for url, count in sorted(found_urls, key=lambda x: x[1], reverse=True):
            f.write("{} firsat -- {}\n".format(count, url))

# ─── Ana akış ─────────────────────────────────────────────────────────────────

def run(rounds):
    print("\nFirsat Sayfasi Bulucu basladi")
    print("   Model  : {} (ucretsiz)".format(GROQ_MODEL))
    print("   Turlar : {}".format(rounds))
    print("   Cikti  : {}\n".format(OUTPUT_FILE))

    all_queries = []
    checked = 0

    for round_num in range(1, rounds + 1):
        print("=" * 55)
        print("TUR {}/{} - Sorgular uretiliyor...\n".format(round_num, rounds))

        queries = generate_queries(round_num, all_queries)
        all_queries.extend(queries)

        for q in queries:
            print("   * {}".format(q))
        print()

        urls_this_round = []
        for query in queries:
            print("  Aranıyor: {}".format(query))
            results = ddg_search(query, MAX_RESULTS_PER_Q)
            new = [u for u in results if uid(u) not in visited]
            urls_this_round.extend(new)
            print("     -> {} yeni URL".format(len(new)))
            time.sleep(1.5)

        # Tekrarlari kaldir
        seen = set()
        unique = []
        for u in urls_this_round:
            if uid(u) not in seen:
                seen.add(uid(u))
                unique.append(u)

        print("\n  {} URL kontrol edilecek...\n".format(len(unique)))

        for url in unique:
            if uid(url) in visited:
                continue
            visited.add(uid(url))
            checked += 1

            print("  [{}] {}".format(checked, url[:70]))
            html = fetch(url)
            if not html:
                print("       Acilamadi")
                continue

            text = to_text(html)
            count = count_opportunities(text, url)
            if count > 0:
                found_urls.append((url, count))
                print("       {} FIRSAT -> kaydedildi ({})".format(count, len(found_urls)))
            else:
                print("       firsat yok")

            time.sleep(1)

        save()
        print()

    print("=" * 55)
    total_opps = sum(c for _, c in found_urls)
    print("Bulunan  : {} sayfa".format(len(found_urls)))
    print("Firsat   : ~{} tahmini".format(total_opps))
    print("Kontrol  : {} URL".format(checked))
    print("Dosya    : {}".format(OUTPUT_FILE))
    print("=" * 55 + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()

    if not GROQ_KEY:
        print("GROQ_API_KEY eksik (.env)")
        sys.exit(1)

    run(args.rounds)


if __name__ == "__main__":
    main()
