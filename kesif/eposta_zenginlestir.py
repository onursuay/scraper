#!/usr/bin/env python3
"""E-posta zenginlestirme - SAHIPLIK denetimli.

Mevcut EmailExtractor sitedeki ilk kurumsal adresi aliyor; bu yuzden
web tasarimcisinin / tema saticisinin adresi lead listesine karisiyor
(olculdu: beniarayiniz@akinkaplan.com, info@naon.com).

Buradaki kural: bir e-posta ancak su ikisinden biriyse lead sayilir.
  1. Alan adi, isletmenin KENDI sitesinin alan adiyla ayni  -> kurumsal
  2. Ucretsiz saglayici (gmail/hotmail/yandex...)           -> kisisel (sektorde yaygin, gecerli)
Bunlarin disindaki her adres UCUNCU TARAF sayilir ve elenir.
"""
import re, sys, warnings, logging, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

from concurrent.futures import ThreadPoolExecutor
from scraper.email_extractor import EmailExtractor
from utils.filters import extract_domain_from_url
from config import BLOCKED_EMAIL_DOMAINS, BLOCKED_EMAIL_PREFIXES, BLOCKED_DOMAIN_SUFFIXES


# Sektorde herkeste gecen jenerik kelimeler - marka esleismesinde sayilmaz
JENERIK = {"guzellik","guzellilk","beauty","merkezi","merkez","salonu","salon","studio",
           "ankara","lazer","epilasyon","estetik","kuafor","center","clinic","klinik",
           "medikal","bakim","spa","cilt","saglik","hizmetleri","tasarim","akademi","life"}

_TR = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iisSgGuUoOcC")


def _sadelestir(m: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (m or "").translate(_TR).lower())


def _markalar(isim: str, site_domain: str) -> set:
    """Isletme adindan ve site alan adindan anlamli marka parcalari uret."""
    parca = set()
    if site_domain:
        parca.add(_sadelestir(extract_domain_from_url(site_domain).split(".")[0]))
    for k in re.split(r"[^\wğüşıöçĞÜŞİÖÇ]+", isim or ""):
        k = _sadelestir(k)
        if len(k) >= 4 and k not in JENERIK:
            parca.add(k)
    return {p for p in parca if p and p not in JENERIK and len(p) >= 4}


def temizle(email: str) -> str:
    """URL kodlamasi ve artik karakterleri temizle (skurtulmaz@yahoo.com%20 vakasi)."""
    from urllib.parse import unquote
    e = unquote((email or "").strip()).strip().lower()
    return re.sub(r"[^a-z0-9._%+@\-]+$", "", e).strip(".")


def sahiplik(email: str, site_domain: str, isim: str = "") -> str:
    """E-postanin kime ait oldugunu sinifla: kurumsal | kisisel | ucuncu_taraf."""
    email = temizle(email)
    if not email or "@" not in email:
        return "ucuncu_taraf"
    local, dom = email.split("@", 1)
    if any(local.startswith(p) for p in BLOCKED_EMAIL_PREFIXES):
        return "ucuncu_taraf"
    if any(dom.endswith(s) for s in BLOCKED_DOMAIN_SUFFIXES):
        return "ucuncu_taraf"
    if dom in BLOCKED_EMAIL_DOMAINS:
        return "kisisel"
    eposta_marka = _sadelestir(extract_domain_from_url(dom).split(".")[0])
    if site_domain and extract_domain_from_url(dom) == extract_domain_from_url(site_domain):
        return "kurumsal"
    # Marka-komsu alan adi: rabiaince.com sitesi + info@rabiaincebeauty.com
    for m in _markalar(isim, site_domain):
        if m in eposta_marka or eposta_marka in m:
            return "kurumsal"
    return "ucuncu_taraf"


def _instagram(kayit) -> str:
    ig = kayit.get("instagrams") or []
    return ig[0] if ig else ""


def zenginlestir(kayit: dict) -> dict:
    """Tek isletme icin e-posta + iletisim kanallarini cikar."""
    ad = kayit.get("title", "")
    site = kayit.get("website") or ""
    site_dom = extract_domain_from_url(site) if site else ""
    adaylar = set(temizle(e) for e in (kayit.get("emails") or []) if e)

    tahmin = ""
    if site:
        ex = EmailExtractor()
        try:
            c = ex.extract_contact_email(site)
            if c["type"] == "tahmin":
                tahmin = c["email"]
            else:
                adaylar |= set(e.lower() for e in c["all"])
        except Exception:
            pass
        finally:
            ex.close()

    kurumsal = sorted(e for e in adaylar if sahiplik(e, site_dom, ad) == "kurumsal")
    kisisel = sorted(e for e in adaylar if sahiplik(e, site_dom, ad) == "kisisel")
    elenen = sorted(e for e in adaylar if sahiplik(e, site_dom, ad) == "ucuncu_taraf")

    if kurumsal:
        eposta, tip = kurumsal[0], "kurumsal"
    elif kisisel:
        eposta, tip = kisisel[0], "kişisel"
    elif tahmin:
        eposta, tip = tahmin, "tahmin"
    else:
        eposta, tip = "", ""

    return {
        "ad": kayit.get("title", ""),
        "ilce": kayit.get("_ilce", "") or kayit.get("neighborhood", ""),
        "kategori": kayit.get("categoryName", ""),
        "adres": kayit.get("address", ""),
        "telefon": kayit.get("phoneUnformatted") or kayit.get("phone", ""),
        "web": site,
        "instagram": _instagram(kayit),
        "eposta": eposta,
        "eposta_tipi": tip,
        "tum_epostalar": ", ".join(kurumsal + kisisel),
        "elenen_ucuncu_taraf": ", ".join(elenen),
        "puan": kayit.get("totalScore", ""),
        "yorum_sayisi": kayit.get("reviewsCount", ""),
        "harita": kayit.get("url", ""),
    }


def toplu(kayitlar, isci=12):
    with ThreadPoolExecutor(max_workers=isci) as p:
        return list(p.map(zenginlestir, kayitlar))
