"""
Mevcut siteler.txt'deki her URL'ye gidip
kac firsat oldugunu sayar ve siteler_sayili.txt'e yazar.

Kullanim:
  python3 say_firsatlari.py
"""

import os
import re
import time
import requests
from dotenv import load_dotenv

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from groq import Groq
except ImportError:
    print("pip3 install groq")
    exit(1)

load_dotenv()

GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
INPUT_FILE  = "siteler.txt"
OUTPUT_FILE = "siteler_sayili.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
}

client = Groq(api_key=GROQ_KEY)

def ask(prompt):
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        print("  Groq hatasi: {}".format(e))
        time.sleep(5)
        return "0"

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code != 200:
            return None
        ct = r.headers.get("Content-Type", "")
        if "text" not in ct and "html" not in ct:
            return None
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
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:max_chars]

def count_opps(text, url):
    out = ask(
        "How many real, apply-able international opportunities "
        "(scholarships, internships, volunteering, summer schools, exchange programs, grants) "
        "that students from Turkey or all countries can apply to are listed on this page?\n\n"
        "Page: {}\nContent:\n---\n{}\n---\n\n"
        "Reply with ONLY a single integer. Nothing else.".format(url, text)
    )
    try:
        return int(re.search(r"\d+", out.strip()).group())
    except Exception:
        return 1

# --- Ana akis ---

urls = []
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("http"):
            urls.append(line)

print("\n{} site bulundu, sayiliyor...\n".format(len(urls)))

results = []
for i, url in enumerate(urls, 1):
    print("[{}/{}] {}".format(i, len(urls), url[:70]))
    html = fetch(url)
    if not html:
        print("       Acilamadi")
        results.append((url, 0))
        continue
    text = to_text(html)
    count = count_opps(text, url)
    results.append((url, count))
    print("       {} firsat".format(count))
    time.sleep(1)

# Sirala ve kaydet
results.sort(key=lambda x: x[1], reverse=True)
total = sum(c for _, c in results if c > 0)
found = [(u, c) for u, c in results if c > 0]

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("# Firsat iceren sayfalar (coktan aza sirali)\n")
    f.write("# Sayfa: {} | Tahmini toplam firsat: {}\n\n".format(len(found), total))
    for url, count in found:
        f.write("{} firsat -- {}\n".format(count, url))

print("\n" + "="*50)
print("Sonuc         : {} sayfa".format(len(found)))
print("Tahmini firsat: {}".format(total))
print("Dosya         : {}".format(OUTPUT_FILE))
print("="*50 + "\n")
