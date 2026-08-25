#!/usr/bin/env python3
"""Tek isletmeyi lead satirina cevirir - sahiplik denetimli, sitesizi ATMADAN."""
import os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.filters import extract_domain_from_url, is_aggregator_website
from utils.domain_parser import domain_to_business_name
from eposta_zenginlestir import sahiplik, temizle


def _ad(biz, extractor, website):
    ad = (biz.get("maps_name") or "").strip()
    if ad:
        for ayrac in (" | ", " - ", " – "):
            if ayrac in ad:
                ad = ad.split(ayrac)[0].strip()
                break
        if len(ad) > 50:
            ad = ad[:50].rsplit(" ", 1)[0]
    if ad:
        return ad
    if website:
        return extractor.extract_site_title(website) or domain_to_business_name(website)
    return biz.get("maps_name", "")


def isle(biz: dict, extractor, sektor: str) -> dict:
    """Isletmeyi birlesik sema satirina cevirir. E-posta yoksa da satir doner."""
    website = biz.get("website") or ""
    if website and is_aggregator_website(website):
        website = ""
    domain = extract_domain_from_url(website) if website else ""
    ad = _ad(biz, extractor, website)

    adaylar = {temizle(e) for e in (biz.get("emails") or []) if e}
    tahmin = ""
    if website:
        try:
            c = extractor.extract_contact_email(website)
            if c["type"] == "tahmin":
                tahmin = c["email"]
            else:
                adaylar |= {temizle(e) for e in c["all"]}
        except Exception:
            pass
    adaylar = {e for e in adaylar if e and "@" in e}

    kurumsal = sorted(e for e in adaylar if sahiplik(e, domain, ad) == "kurumsal")
    kisisel = sorted(e for e in adaylar if sahiplik(e, domain, ad) == "kisisel")
    elenen = sorted(e for e in adaylar if sahiplik(e, domain, ad) == "ucuncu_taraf")

    if kurumsal:
        eposta, tip = kurumsal[0], "kurumsal"
    elif kisisel:
        eposta, tip = kisisel[0], "kişisel"
    elif tahmin:
        eposta, tip = tahmin, "tahmin"
    else:
        eposta, tip = "", ""

    sosyal = {"instagram": biz.get("instagram", ""), "facebook": biz.get("facebook", ""),
              "linkedin": biz.get("linkedin", "")}
    if website and not sosyal["instagram"]:
        try:
            sosyal.update({k: v for k, v in extractor.extract_social_links(website).items() if v})
        except Exception:
            pass

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sector": sektor,
        "name": ad,
        "ilce": biz.get("ilce", ""),
        "kategori": biz.get("kategori", ""),
        "adres": biz.get("adres", ""),
        "phone": biz.get("phone", ""),
        "email": eposta,
        "type": tip,
        "tum_epostalar": ", ".join(kurumsal + kisisel),
        "elenen": ", ".join(elenen),
        "domain": domain,
        "website": website,
        "instagram": sosyal["instagram"],
        "facebook": sosyal["facebook"],
        "linkedin": sosyal["linkedin"],
        "puan": biz.get("puan", ""),
        "yorum": biz.get("yorum", ""),
        "harita": biz.get("harita", ""),
        "anahtar": (domain or biz.get("phone") or biz.get("place_id") or ad).lower().strip(),
    }
