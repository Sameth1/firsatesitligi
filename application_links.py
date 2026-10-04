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
# Kapanmış form bir başvuru hedefi değil, KAPANMIŞ fırsat kanıtıdır. Google
# Forms yanıt almayı durdurunca .../closedform adresine yönlendirip 200 dönüyor;
# Typeform ve Microsoft Forms da 200 ile "kapandı" sayfası gösteriyor. Eskiden
# bunlar "doğrulanmış başvuru" sayılıyordu (Ekim 2026: iki nasilgitmis ilanı).
_CLOSED_FORM_RE = re.compile(
    r"no\s+longer\s+accepting\s+responses|(?:is\s+not|isn't)\s+accepting\s+responses"
    r"|artık\s+yanıt\s+kabul\s+etmiyor|yanıt\s+kabul\s+etmiyor"
    r"|this\s+(?:typeform|form)\s+is\s+(?:now\s+)?closed|form\s+is\s+closed",
    re.I,
)
CLOSED_FORM_REASON = "başvuru formu kapanmış (artık yanıt kabul etmiyor)"
# Başvurunun portalın kendi butonu/sayfasıyla yapıldığı resmî kaynaklar. Ayrı
# bir form adresi olmayabilir: buton kullanıcıyı portal hesabına sokup o ilana
# başvurtuyor. Her kural sayfada başvuru adımının gerçekten bulunduğunu
# metinden doğrular; yalnız adres kalıbına güvenilmez.
@dataclass(frozen=True)
class KnownApplyPage:
    host: str
    path_re: re.Pattern
    evidence_re: re.Pattern
    label: str
    # Sayfa ilanın kendisi mi (koşullar burada) yoksa ayrı başvuru adımı mı?
    is_listing: bool
    # Başvuru harici siteye devrediliyorsa o bağlantının etiketi.
    external_label_re: re.Pattern | None = None


KNOWN_APPLY_PAGES = (
    # Avrupa Dayanışma Programı: ilan sayfasındaki "Apply" butonu "In order to
    # check if you can apply for this project, you must first Sign In or Join
    # the Corps." penceresini açar.
    KnownApplyPage(
        "youth.europa.eu",
        re.compile(r"^/solidarity/(?:placement|opportunity)/\d+(?:_[a-z]{2})?/?$"),
        re.compile(r"check\s+if\s+you\s+can\s+apply\s+for\s+this\s+project", re.I),
        "İlan sayfasındaki Apply butonu (Avrupa Dayanışma Programı hesabıyla başvuru)",
        is_listing=True,
    ),
    # SALTO Avrupa Eğitim Takvimi: eğitimin "Apply now!" butonu bu sayfaya
    # gelir. Ya SALTO'nun kendi formu (SALTO hesabıyla) ya da "Applications
    # for this training activity are handled on an external website" notuyla
    # düzenleyicinin formuna devir.
    KnownApplyPage(
        "www.salto-youth.net",
        re.compile(r"^/tools/european-training-calendar/application-procedure/\d+/?$"),
        re.compile(r"\bApply\s+online\b", re.I),
        "SALTO başvuru sayfası (SALTO hesabıyla başvuru)",
        is_listing=False,
        external_label_re=re.compile(r"proceed\s+to\s+the\s+external\s+online\s+application", re.I),
    ),
)
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
    details_status_code: int | None = None

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


def is_safe_guided_url(url: str) -> bool:
    """Doğrudan form yokken gösterilebilecek sade, resmî bilgi sayfası mı?"""
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    path = (parts.path or "/").rstrip("/") or "/"
    if (parts.scheme not in ("http", "https") or not host or _is_junk(url)
            or host in AGGREGATOR_HOSTS or _is_form_provider(url)):
        return False
    is_database_detail = (
        "scholarship-database" in path.casefold()
        and "detail" in parse_qs(parts.query)
    )
    if (path == "/" or _GENERIC_AUTH_RE.search(path)
            or (_SEARCH_PATH_RE.search(path) and not is_database_detail)):
        return False
    if path.casefold() in ("/careers", "/jobs", "/vacancies"):
        return False
    if "scholarship-database" in path.casefold() and not is_database_detail:
        return False
    return True


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


def known_apply_page(url: str, body: str | None) -> KnownApplyPage | None:
    """Sayfa, başvurunun kendi adımıyla yapıldığı bilinen bir portal sayfasıysa
    kuralı; değilse None."""
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    for rule in KNOWN_APPLY_PAGES:
        if (host == rule.host and rule.path_re.match(parts.path or "")
                and rule.evidence_re.search(body or "")):
            return rule
    return None


def _external_apply_link(rule: KnownApplyPage, page_html: str, page_url: str) -> str | None:
    if not rule.external_label_re:
        return None
    soup = BeautifulSoup(page_html or "", "html.parser")
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if rule.external_label_re.search(label):
            target = _clean_url(urljoin(page_url, anchor["href"].strip()))
            if urlsplit(target).scheme in ("http", "https"):
                return target
    return None


def _known_apply_route(rule, page_url, page_html, details_url, details_status_code, fetcher):
    """Bilinen portal sayfasından doğrudan başvuru hedefi.

    Öncelik: portalın devrettiği harici başvuru sitesi, sonra kurumun ilan
    metninde verdiği form ("ONLY way to apply: please fill in this form:
    forms.gle/…"), en son portalın kendi başvuru sayfası. Kapanmış form
    kapalı fırsat kanıtıdır."""
    conditions_url = page_url if rule.is_listing else details_url
    external = _external_apply_link(rule, page_html, page_url)
    targets = ([(external, "Portalın yönlendirdiği harici başvuru sitesi")] if external else [])
    targets += [(url, "İlan açıklamasında kurumun verdiği başvuru formu")
                for url in contextual_form_links(page_html, page_url)]
    for target_url, label in targets:
        target = fetcher(target_url)
        if is_closed_form(target.final_url or target_url, target.body):
            return ApplicationRoute(None, conditions_url, "online_form", False,
                                    target.status, target.final_url, None,
                                    CLOSED_FORM_REASON,
                                    details_status_code=details_status_code)
        if _healthy_target(target):
            if external and target_url == external and not _is_form_provider(target_url):
                # Devredilen adres bazen formun kendisi değil, düzenleyicinin
                # çağrı yazısı. İçinde form varsa doğrudan ona git.
                inner = resolve_application_route(target_url, target.body, max_hops=1,
                                                  fetcher=fetcher)
                if inner.verified and inner.application_url:
                    return ApplicationRoute(inner.application_url, conditions_url,
                                            inner.application_method, True,
                                            inner.status_code, inner.final_url,
                                            f"{label} → {inner.evidence}",
                                            "portalın devrettiği sitede başvuru adımı doğrulandı",
                                            details_status_code=details_status_code)
            return ApplicationRoute(target_url, conditions_url, _method_for(target_url), True,
                                    target.status, target.final_url, label,
                                    "portal başvuruyu bu adrese devrediyor",
                                    details_status_code=details_status_code)
        if label.startswith("Portalın"):
            # Portal başvuruyu yalnız bu siteye devrediyor; açılmıyorsa
            # portal sayfasını "doğrulanmış" saymak yanlış olur.
            return ApplicationRoute(None, conditions_url, "portal", False, target.status,
                                    target.final_url, None,
                                    "portalın yönlendirdiği harici başvuru sitesi açılmadı",
                                    details_status_code=details_status_code)
    # İlan sayfasıysa detay adresi başvuru adresiyle aynı: kartta ayrı
    # "Koşulları Gör" linki çıkmaz.
    return ApplicationRoute(page_url, conditions_url, "portal", True, 200, page_url,
                            rule.label, "portalın kendi başvuru sayfası",
                            details_status_code=details_status_code)


_APPLY_CONTEXT_RE = re.compile(r"\b(?:appl(?:y|ication)|register|registration|başvur)", re.I)


def contextual_form_links(page_html: str, page_url: str) -> list[str]:
    """Hemen önündeki metinde başvuru geçen form sağlayıcısı linkleri.

    Portal ilanlarında form linki çoğu zaman etiketi URL'in kendisi olan düz
    bir bağlantı: "To apply, fill in this form: https://forms.gle/…". Etiket
    zayıf olduğu için genel aday çıkarımı bunu görmüyor."""
    soup = BeautifulSoup(page_html or "", "html.parser")
    found = []
    for anchor in soup.find_all("a", href=True):
        target = _clean_url(urljoin(page_url, anchor["href"].strip()))
        if not _is_form_provider(target) or target in found:
            continue
        before = []
        for node in anchor.previous_elements:
            if isinstance(node, str):
                before.append(node)
                if sum(len(part) for part in before) >= 160:
                    break
        context = " ".join(reversed(before))[-160:]
        if _APPLY_CONTEXT_RE.search(context):
            found.append(target)
    return found


def is_closed_form(url: str, body: str | None = None) -> bool:
    """Form sağlayıcısının "artık yanıt kabul etmiyor" sayfası mı?"""
    path = (urlsplit(url or "").path or "").rstrip("/").casefold()
    if path.endswith("/closedform"):
        return True
    return bool(body) and _is_form_provider(url) and bool(_CLOSED_FORM_RE.search(body[:50000]))


def _healthy_target(result: FetchResult) -> bool:
    if result.status is None or not 200 <= result.status < 400:
        return False
    if is_closed_form(result.final_url, result.body):
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
                                None, first.error or "başlangıç sayfası okunamadı",
                                details_status_code=first.status)

    initial_host = _host(start_url)
    details_url = start_url
    details_status_code = first.status
    queue: list[tuple[str, str, int]] = [(first.final_url or start_url, first.body, 0)]
    visited = set()
    best_unverified: tuple[Candidate, FetchResult] | None = None
    closed_form_url: str | None = None

    while queue:
        page_url, page_html, depth = queue.pop(0)
        normalized = _clean_url(page_url)
        if normalized in visited:
            continue
        visited.add(normalized)
        candidates, real_form = extract_candidates(page_html, page_url)
        if is_closed_form(page_url, page_html):
            return ApplicationRoute(None, details_url, "online_form", False, 200, page_url,
                                    None, CLOSED_FORM_REASON,
                                    details_status_code=details_status_code)
        known = known_apply_page(page_url, page_html)
        if known:
            return _known_apply_route(known, page_url, page_html, details_url,
                                      details_status_code, fetcher)
        if _is_form_provider(page_url):
            return ApplicationRoute(page_url, details_url, "online_form", True, 200,
                                    page_url, "Bilinen form sağlayıcısı URL'i",
                                    "sayfanın kendisi doğrulanmış form sağlayıcısı",
                                    details_status_code=details_status_code)
        if real_form:
            return ApplicationRoute(page_url, details_url, "online_form", True, 200,
                                    page_url, "Sayfada başvuru formu doğrulandı",
                                    "sayfanın kendisi başvuru formu",
                                    details_status_code=details_status_code)
        page_path = urlsplit(page_url).path
        if (_host(page_url) not in AGGREGATOR_HOSTS
                and _ACTION_PATH_RE.search(page_path)
                and not _GENERIC_AUTH_RE.search(page_path)
                and not _SEARCH_PATH_RE.search(page_path)):
            return ApplicationRoute(page_url, details_url, "portal", True, 200,
                                    page_url, "URL doğrudan başvuru yolu içeriyor",
                                    "sayfanın kendisi başvuru portalı",
                                    details_status_code=details_status_code)

        for candidate in candidates:
            if candidate.kind == "details":
                if initial_host in AGGREGATOR_HOSTS and _host(candidate.url) not in AGGREGATOR_HOSTS:
                    details_url = candidate.url
                if depth < max_hops:
                    target = fetcher(candidate.url)
                    if candidate.url == details_url:
                        details_status_code = target.status
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
                    details_status_code=details_status_code,
                )
            if candidate.method == "email":
                return ApplicationRoute(candidate.url, details_url, "email", True, None,
                                        candidate.url, evidence, "e-posta başvurusu doğrulandı",
                                        details_status_code=details_status_code)
            if candidate.method == "online_form" and _is_form_provider(candidate.url):
                target = fetcher(candidate.url)
                if is_closed_form(target.final_url or candidate.url, target.body):
                    closed_form_url = target.final_url or candidate.url
                    continue
                if _healthy_target(target):
                    return ApplicationRoute(
                        target.final_url, details_url, "online_form", True,
                        target.status, target.final_url, evidence,
                        "form sağlayıcısı anonim erişimle açıldı",
                        details_status_code=details_status_code,
                    )
                if best_unverified is None or candidate.score > best_unverified[0].score:
                    best_unverified = (candidate, target)
                continue

            target = fetcher(candidate.url)
            if _healthy_target(target):
                if candidate.method == "document":
                    return ApplicationRoute(target.final_url, details_url, "document", True,
                                            target.status, target.final_url, evidence,
                                            "başvuru belgesi açıldı",
                                            details_status_code=details_status_code)
                target_candidates, target_form = extract_candidates(target.body, target.final_url)
                direct_path = bool(_ACTION_PATH_RE.search(urlsplit(target.final_url).path))
                if target_form or direct_path:
                    method = "online_form" if target_form else candidate.method
                    return ApplicationRoute(target.final_url, details_url, method, True,
                                            target.status, target.final_url, evidence,
                                            "başvuru hedefi açıldı ve doğrulandı",
                                            details_status_code=details_status_code)
                if depth < max_hops:
                    queue.append((target.final_url, target.body, depth + 1))
            if best_unverified is None or candidate.score > best_unverified[0].score:
                best_unverified = (candidate, target)

    if closed_form_url:
        return ApplicationRoute(None, details_url, "online_form", False, 200, closed_form_url,
                                None, CLOSED_FORM_REASON,
                                details_status_code=details_status_code)
    if best_unverified:
        candidate, target = best_unverified
        return ApplicationRoute(None, details_url, candidate.method, False, target.status,
                                target.final_url, f'“{candidate.label}” bağlantısı',
                                "aday başvuru hedefi teknik olarak doğrulanamadı",
                                details_status_code=details_status_code)
    return ApplicationRoute(None, details_url, None, False, first.status, first.final_url,
                            None, "doğrudan başvuru adımı bulunamadı",
                            details_status_code=details_status_code)
