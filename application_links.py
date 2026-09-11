"""Resmî bilgi sayfasından gerçek başvuru adımını güvenle bulur.

Tek bir URL'yi hem "koşulları oku" hem "başvur" için kullanmak kartları
yanıltıcı yapıyordu. Bu modül en fazla iki bağlantı adımı izler ve yalnız
kanıtlanmış form/portal/e-posta/belge hedefini başvuru URL'i olarak döndürür.
"""

from __future__ import annotations

import html as html_lib
import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


AGGREGATOR_HOSTS = {
    "youthop.com", "www.youthop.com", "nasilgitmis.com", "www.nasilgitmis.com",
}
JUNK_HOST_PARTS = (
    "facebook.", "instagram.", "linkedin.", "twitter.", "youtube.",
    "youtu.be", "tiktok.", "t.me", "wa.me", "whatsapp.",
)
FORM_HOSTS = {
    "forms.gle", "form.jotform.com", "jotform.com", "www.jotform.com",
    "typeform.com", "www.typeform.com", "form.typeform.com",
    "airtable.com", "www.airtable.com",
    "forms.office.com", "forms.cloud.microsoft",
    "tally.so", "www.tally.so", "surveymonkey.com", "www.surveymonkey.com",
}
DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".odt"}
TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid", "yclid",
    "twclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "_gl",
}

_STRONG_ACTION_RE = re.compile(
    r"\b(?:apply(?:\s+(?:now|here|online))?|start\s+(?:your\s+)?application|"
    r"submit\s+(?:your\s+)?application|online\s+application|application\s+form|"
    r"hemen\s+başvur|başvurusu|başvuru(?:\s+(?:formu|yap|yapın|sayfası))?|başvur|"
    r"online\s+başvuru|kayıt\s+formu|tıkla(?:yınız|yın|mak)?|"
    r"tikla(?:yiniz|yin|mak)?|buradan|bewerben|bewerbung|candidature)\b",
    re.IGNORECASE,
)
_INSTRUCTIONS_RE = re.compile(
    r"\b(?:how\s+to\s+apply|application\s+(?:requirements?|procedure|guide|"
    r"instructions?)|başvuru\s+(?:koşulları|şartları|rehberi|süreci)|"
    r"who\s+can\s+apply)\b",
    re.IGNORECASE,
)
_DETAIL_RE = re.compile(
    r"\b(?:official\s+(?:website|site|page|link)|resm[iî]\s+(?:site|sayfa|web)|"
    r"programme?\s+(?:details?|website)|more\s+(?:information|details)|detaylar)\b",
    re.IGNORECASE,
)
_ACTION_PATH_RE = re.compile(
    r"/(?:apply-now|apply-online|application-form|applications/start|"
    r"bewerbung|candidature|submit)(?:/|$)|/(?:apply|application)/?$",
    re.IGNORECASE,
)
_GENERIC_AUTH_RE = re.compile(r"/(?:login|log-in|sign-in|signin|register|signup|sign-up)/?$", re.I)
_SEARCH_PATH_RE = re.compile(r"/(?:search|find|programme?-search|scholarship-database)/?$", re.I)
_SOFT_404_RE = re.compile(r"\b(?:404|page\s+not\s+found|seite\s+nicht\s+gefunden)\b", re.I)
_ACTION_FRAGMENT_RE = re.compile(
    r"^(?:apply|application|application-form|apply-now|form|basvuru|başvuru)(?:[-_].*)?$",
    re.I,
)


@dataclass(frozen=True)
class FetchResult:
    status: int | None
    final_url: str
    body: str
    content_type: str = ""
    error: str | None = None


@dataclass(frozen=True)
class Candidate:
    url: str
    label: str
    method: str
    score: int
    kind: str = "action"


@dataclass(frozen=True)
class ApplicationRoute:
    application_url: str | None
    details_url: str
    application_method: str | None
    verified: bool
    status_code: int | None
    final_url: str | None
    evidence: str | None
    reason: str

    def submission_fields(self) -> dict:
        """Yeni submission için DB kolonlarına uygun alanları döndürür."""
        return {
            "url": self.application_url or self.details_url,
            "details_url": self.details_url,
            "application_route_status": "verified" if self.verified else "unverified",
            "application_method": self.application_method,
            "application_url_check_status": self.status_code,
            "application_url_final": self.final_url,
            "application_url_evidence": self.evidence,
        }


Fetcher = Callable[[str], FetchResult]


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _clean_url(url: str, *, keep_fragment: bool = False) -> str:
    url = html_lib.unescape(url.strip())
    parts = urlsplit(url)
    if parts.path.rstrip("/").endswith("/link") and "u=" in parts.query:
        wrapped = unquote(parse_qs(parts.query).get("u", [""])[0])
        if wrapped.startswith(("http://", "https://")):
            url = wrapped
            parts = urlsplit(url)
    fragment = parts.fragment if keep_fragment else ""
    if not parts.query:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", fragment))
    query = "&".join(
        item for item in parts.query.split("&")
        if item.split("=", 1)[0].lower() not in TRACKING_KEYS
        and not item.split("=", 1)[0].lower().startswith("utm_")
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))


def _public_http_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    if parts.username or parts.password or parts.hostname.lower() == "localhost":
        return False
    try:
        addresses = {row[4][0] for row in socket.getaddrinfo(parts.hostname, parts.port or 443)}
    except OSError:
        return False
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_reserved,
                ip.is_multicast, ip.is_unspecified)):
            return False
    return True


def fetch_url(url: str) -> FetchResult:
    """Sınırlı, SSRF-korumalı GET; her yönlendirme hedefi yeniden süzülür."""
    current = url
    try:
        for _ in range(6):
            if not _public_http_url(current):
                return FetchResult(None, current, "", error="public HTTP(S) adresi değil")
            response = requests.get(
                current,
                headers={"User-Agent": "Mozilla/5.0 (compatible; FirsatEsitligiLinkVerifier/1.0)"},
                timeout=20,
                allow_redirects=False,
                stream=True,
            )
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                response.close()
                if not location:
                    return FetchResult(response.status_code, current, "", error="yönlendirme hedefi yok")
                current = urljoin(current, location)
                continue

            content_type = response.headers.get("content-type", "").lower()
            if "text/" in content_type or "html" in content_type or not content_type:
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2_000_000:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
            else:
                body = ""
            final_url = current
            response.close()
            return FetchResult(response.status_code, final_url, body, content_type)
        return FetchResult(None, current, "", error="çok fazla yönlendirme")
    except requests.RequestException as exc:
        return FetchResult(None, current, "", error=str(exc)[:200])


def _method_for(url: str) -> str:
    if url.lower().startswith("mailto:"):
        return "email"
    path = urlsplit(url).path.lower()
    if PurePosixPath(path).suffix in DOCUMENT_SUFFIXES:
        return "document"
    if _is_form_provider(url):
        return "online_form"
    return "portal"


def _is_form_provider(url: str) -> bool:
    host = _host(url)
    return (
        host in FORM_HOSTS
        or host.endswith(".typeform.com")
        or host.endswith(".jotform.com")
        or (host == "docs.google.com" and "/forms/" in urlsplit(url).path.lower())
    )


def _is_junk(url: str) -> bool:
    host = _host(url)
    return not host or any(part in host for part in JUNK_HOST_PARTS)


def _has_real_form(soup: BeautifulSoup) -> bool:
    for form in soup.find_all("form"):
        marker = " ".join([
            form.get("id", ""), " ".join(form.get("class", [])),
            form.get("action", ""), form.get_text(" ", strip=True)[:300],
        ]).casefold()
        if any(word in marker for word in ("search", "newsletter", "login", "sign in", "subscribe")):
            continue
        fields = form.find_all(["input", "select", "textarea"])
        useful = [f for f in fields if (f.get("type") or "").lower() not in ("hidden", "search")]
        # Sıradan iletişim/geri bildirim POST formları başvuru formu değildir.
        # Formun kendi id/class/action/metninde açık başvuru sinyali zorunlu.
        if (len(useful) >= 2 and _STRONG_ACTION_RE.search(marker)
                and not _INSTRUCTIONS_RE.search(marker)):
            return True
    return False


def extract_candidates(page_html: str, page_url: str) -> tuple[list[Candidate], bool]:
    """HTML'den sıralanmış aksiyon ve resmî detay hedeflerini çıkarır."""
    soup = BeautifulSoup(page_html or "", "html.parser")
    real_form = _has_real_form(soup)
    candidates: dict[tuple[str, str], Candidate] = {}

    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).split())[:240]
        href = anchor.get("href", "").strip()
        if href.lower().startswith("mailto:"):
            target = href
        else:
            target = _clean_url(urljoin(page_url, href), keep_fragment=True)
            if _is_junk(target) or urlsplit(target).scheme not in ("http", "https"):
                continue
        path = urlsplit(target).path
        method = _method_for(target)
        strong = bool(_STRONG_ACTION_RE.search(label)) and not bool(_INSTRUCTIONS_RE.search(label))
        action_path = bool(_ACTION_PATH_RE.search(path)) and not bool(_GENERIC_AUTH_RE.search(path))

        candidate = None
        if strong or action_path:
            trusted_target = method in ("email", "document", "online_form")
            score = 70 + (25 if strong else 0) + (15 if action_path else 0) + (15 if trusted_target else 0)
            if _GENERIC_AUTH_RE.search(path) or _SEARCH_PATH_RE.search(path):
                score -= 60
            candidate = Candidate(target, label or target, method, score)
        elif _DETAIL_RE.search(label):
            candidate = Candidate(target, label, "portal", 45, "details")

        if candidate:
            key = (candidate.url, candidate.kind)
            if key not in candidates or candidates[key].score < candidate.score:
                candidates[key] = candidate

    ordered = sorted(candidates.values(), key=lambda c: c.score, reverse=True)
    return ordered, real_form


def _healthy_target(result: FetchResult) -> bool:
    if result.status is None or not 200 <= result.status < 400:
        return False
    if result.body:
        soup = BeautifulSoup(result.body, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if _SOFT_404_RE.search(title[:160]):
            return False
    return True


def resolve_application_route(
    start_url: str,
    source_html: str | None = None,
    *,
    max_hops: int = 2,
    fetcher: Fetcher = fetch_url,
) -> ApplicationRoute:
    """En fazla ``max_hops`` bilgi sayfası izleyerek gerçek aksiyonu bulur."""
    start_url = _clean_url(start_url)
    first = FetchResult(200, start_url, source_html) if source_html is not None else fetcher(start_url)
    if not first.body:
        return ApplicationRoute(None, start_url, None, False, first.status, first.final_url,
                                None, first.error or "başlangıç sayfası okunamadı")

    initial_host = _host(start_url)
    details_url = start_url
    queue: list[tuple[str, str, int]] = [(first.final_url or start_url, first.body, 0)]
    visited = set()
    best_unverified: tuple[Candidate, FetchResult] | None = None

    while queue:
        page_url, page_html, depth = queue.pop(0)
        normalized = _clean_url(page_url)
        if normalized in visited:
            continue
        visited.add(normalized)
        candidates, real_form = extract_candidates(page_html, page_url)
        if _is_form_provider(page_url):
            return ApplicationRoute(page_url, details_url, "online_form", True, 200,
                                    page_url, "Bilinen form sağlayıcısı URL'i",
                                    "sayfanın kendisi doğrulanmış form sağlayıcısı")
        if real_form:
            return ApplicationRoute(page_url, details_url, "online_form", True, 200,
                                    page_url, "Sayfada başvuru formu doğrulandı",
                                    "sayfanın kendisi başvuru formu")
        page_path = urlsplit(page_url).path
        if (_host(page_url) not in AGGREGATOR_HOSTS
                and _ACTION_PATH_RE.search(page_path)
                and not _GENERIC_AUTH_RE.search(page_path)
                and not _SEARCH_PATH_RE.search(page_path)):
            return ApplicationRoute(page_url, details_url, "portal", True, 200,
                                    page_url, "URL doğrudan başvuru yolu içeriyor",
                                    "sayfanın kendisi başvuru portalı")

        for candidate in candidates:
            if candidate.kind == "details":
                if initial_host in AGGREGATOR_HOSTS and _host(candidate.url) not in AGGREGATOR_HOSTS:
                    details_url = candidate.url
                if depth < max_hops:
                    target = fetcher(candidate.url)
                    if _healthy_target(target) and target.body:
                        queue.append((target.final_url, target.body, depth + 1))
                continue

            evidence = f'“{candidate.label}” bağlantısı'
            candidate_parts = urlsplit(candidate.url)
            same_document = _clean_url(candidate.url) == _clean_url(page_url)
            if (same_document and candidate_parts.fragment
                    and _ACTION_FRAGMENT_RE.fullmatch(candidate_parts.fragment)):
                return ApplicationRoute(
                    candidate.url, details_url, "online_form", True, 200,
                    candidate.url, evidence,
                    "sayfa içi başvuru bölümüne doğrudan bağlantı doğrulandı",
                )
            if candidate.method == "email":
                return ApplicationRoute(candidate.url, details_url, "email", True, None,
                                        candidate.url, evidence, "e-posta başvurusu doğrulandı")
            if candidate.method == "online_form" and _is_form_provider(candidate.url):
                target = fetcher(candidate.url)
                if _healthy_target(target):
                    return ApplicationRoute(
                        target.final_url, details_url, "online_form", True,
                        target.status, target.final_url, evidence,
                        "form sağlayıcısı anonim erişimle açıldı",
                    )
                if best_unverified is None or candidate.score > best_unverified[0].score:
                    best_unverified = (candidate, target)
                continue

            target = fetcher(candidate.url)
            if _healthy_target(target):
                if candidate.method == "document":
                    return ApplicationRoute(target.final_url, details_url, "document", True,
                                            target.status, target.final_url, evidence,
                                            "başvuru belgesi açıldı")
                target_candidates, target_form = extract_candidates(target.body, target.final_url)
                direct_path = bool(_ACTION_PATH_RE.search(urlsplit(target.final_url).path))
                if target_form or direct_path:
                    method = "online_form" if target_form else candidate.method
                    return ApplicationRoute(target.final_url, details_url, method, True,
                                            target.status, target.final_url, evidence,
                                            "başvuru hedefi açıldı ve doğrulandı")
                if depth < max_hops:
                    queue.append((target.final_url, target.body, depth + 1))
            if best_unverified is None or candidate.score > best_unverified[0].score:
                best_unverified = (candidate, target)

    if best_unverified:
        candidate, target = best_unverified
        return ApplicationRoute(None, details_url, candidate.method, False, target.status,
                                target.final_url, f'“{candidate.label}” bağlantısı',
                                "aday başvuru hedefi teknik olarak doğrulanamadı")
    return ApplicationRoute(None, details_url, None, False, first.status, first.final_url,
                            None, "doğrudan başvuru adımı bulunamadı")
