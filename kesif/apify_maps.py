#!/usr/bin/env python3
"""Apify Google Maps tabanli isletme kesfi.

Mevcut Places API motorunun iki yapisal sinirini kaldirir:
  1. Text Search'un sorgu basina 60 sonuc tavani -> ilce x anahtar kelime yelpazesi
  2. Web sitesi olmayan isletmelerin silinmesi -> telefon/Instagram ile korunur
"""
import json, os, time, urllib.request, urllib.parse

TOKEN_FILE = "/Users/onursuay/Desktop/Agency Wizard/Dökümanlar/google-api-setup/apify_token.json"
ACTOR = "lukaskrivka~google-maps-with-contact-details"
API = "https://api.apify.com/v2"


def _token():
    return json.load(open(TOKEN_FILE))["api_token"]


def _get(path):
    with urllib.request.urlopen(f"{API}/{path}{'&' if '?' in path else '?'}token={_token()}", timeout=60) as r:
        return json.load(r)


def harcanan_usd():
    """Bu fatura doneminde harcanan tutar (gercek hesap verisi)."""
    d = _get("users/me/usage/monthly")["data"]
    return float(d.get("totalUsageCreditsUsdAfterVolumeDiscount") or 0)


def calistir(anahtar_kelimeler, konum, adet, dil="tr", butce_usd=1.0):
    """Tek bir kesif kosusu baslatir ve biter bitmez kayitlari dondurur."""
    girdi = {
        "searchStringsArray": anahtar_kelimeler,
        "locationQuery": konum,
        "maxCrawledPlacesPerSearch": adet,
        "language": dil,
        "skipClosedPlaces": True,
    }
    req = urllib.request.Request(
        f"{API}/acts/{ACTOR}/runs?token={_token()}&maxTotalChargeUsd={butce_usd}",
        data=json.dumps(girdi).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        run = json.load(r)["data"]

    run_id, ds_id = run["id"], run["defaultDatasetId"]
    while True:
        time.sleep(10)
        d = _get(f"actor-runs/{run_id}")["data"]
        if d["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    maliyet = float(d.get("usageTotalUsd") or 0)
    kayitlar = _get(f"datasets/{ds_id}/items?format=json")
    return kayitlar, maliyet, d["status"]
