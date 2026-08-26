#!/usr/bin/env python3
"""BusinessScraper'in Apify Google Maps tabanli yerine gecen surumu.

Eski scraper/maps_scraper.py ile AYNI arayuzu sunar (start_browser /
search_businesses / close_browser) - dashboard.py'de yalniz import satiri degisir.

Farklar:
  - Places Text Search'un sorgu basina 60 sonuc tavani YOK
  - Sehir tek sorguyla degil ILCE ILCE taranir (merkeze yigilma olmaz)
  - Ilce listesi OpenStreetMap'ten alinir (uydurma yok), diske onbelleklenir
  - Butce TUM yelpaze icin kumulatif; hesabin gercek harcamasi okunarak durulur
  - Web sitesi olmayan isletme ATILMAZ (telefon + sosyal hesapla doner)
"""
import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

ACTOR = "lukaskrivka~google-maps-with-contact-details"
API = "https://api.apify.com/v2"
OVERPASS = "https://overpass-api.de/api/interpreter"

_DIZIN = os.path.dirname(os.path.abspath(__file__))
ILCE_ONBELLEK = os.path.join(_DIZIN, "_ilceler.json")
AGIRLIK_DOSYASI = os.path.join(_DIZIN, "_ilce_agirlik.json")

# Ayni sektorde farkli sonuc kumesi getiren terim kaliplari
TERIM_KALIPLARI = ["{s}", "{s} {c}"]

ILCE_ALT = 8      # bir ilceye verilecek en az kayit
ILCE_UST = 60     # bir ilceye verilecek en fazla kayit


def _token():
    from config import APIFY_TOKEN, APIFY_TOKEN_FILE
    if APIFY_TOKEN:
        return APIFY_TOKEN
    with open(APIFY_TOKEN_FILE) as f:
        return json.load(f)["api_token"]


def _json_oku(yol, varsayilan):
    try:
        with open(yol) as f:
            return json.load(f)
    except Exception:
        return varsayilan


def _json_yaz(yol, veri):
    try:
        with open(yol, "w") as f:
            json.dump(veri, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"{yol} yazilamadi: {e}")


def ilceler_getir(sehir: str) -> list:
    """Ilin ilcelerini OpenStreetMap'ten al (admin_level=6), diske onbellekle."""
    onbellek = _json_oku(ILCE_ONBELLEK, {})
    if sehir in onbellek:
        return onbellek[sehir]

    sorgu = (
        '[out:json][timeout:180];'
        f'area["name"="{sehir}"]["admin_level"=4]->.il;'
        'rel["admin_level"=6](area.il);out tags;'
    )
    try:
        istek = urllib.request.Request(
            OVERPASS,
            data=urllib.parse.urlencode({"data": sorgu}).encode(),
            headers={"User-Agent": "scanner-ilce/1.0"},
        )
        with urllib.request.urlopen(istek, timeout=200) as r:
            d = json.load(r)
        ilceler = sorted({
            e["tags"]["name"] for e in d.get("elements", [])
            if e.get("tags", {}).get("name")
        })
    except Exception as e:
        logger.warning(f"Ilce listesi alinamadi ({sehir}): {e}")
        ilceler = []

    if ilceler:
        onbellek[sehir] = ilceler
        _json_yaz(ILCE_ONBELLEK, onbellek)
    return ilceler


class BusinessScraper:
    """Google Maps isletme kesfi (Apify), ilce yelpazeli."""

    def __init__(self, butce_usd: float = None):
        varsayilan = float(os.getenv("APIFY_BUTCE_USD", "2.0"))
        self.butce_usd = float(butce_usd) if butce_usd is not None else varsayilan
        self.token = None
        self._baslangic_harcama = None

    # --- arayuz uyumlulugu ---
    def start_browser(self):
        self.token = _token()
        self._baslangic_harcama = self.harcanan_usd()
        logger.info("Apify Google Maps kesif motoru hazir.")

    def close_browser(self):
        pass

    # --- hesap ---
    def _get(self, path):
        url = f"{API}/{path}{'&' if '?' in path else '?'}token={self.token}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)

    def harcanan_usd(self) -> float:
        """Fatura donemindeki gercek harcama (hesaptan okunur)."""
        try:
            d = self._get("users/me/usage/monthly")["data"]
            return float(d.get("totalUsageCreditsUsdAfterVolumeDiscount") or 0)
        except Exception:
            return 0.0

    def kalan_butce(self) -> float:
        if self._baslangic_harcama is None:
            return self.butce_usd
        return max(0.0, self.butce_usd - (self.harcanan_usd() - self._baslangic_harcama))

    # --- kesif ---
    def search_businesses(self, sector: str, city: str, min_results: int = 20,
                          ilceler: list = None) -> list:
        """Sektor + sehir icin isletmeleri bul.

        ilceler verilmezse ilin ilceleri OSM'den alinir ve yelpaze acilir.
        Butce TUM yelpaze icin gecerlidir; dolunca tarama durur.
        """
        if not self.token:
            self.start_browser()

        if ilceler is None:
            ilceler = ilceler_getir(city)

        if not ilceler:
            logger.info(f"{city} icin ilce listesi yok, sehir geneli taranacak.")
            konumlar = [f"{city}, Turkey"]
        else:
            agirliklar = _json_oku(AGIRLIK_DOSYASI, {}).get(city, {})
            # Once yogun ilceler: bilinmeyene orta deger verilir ki denensin
            ilceler = sorted(ilceler, key=lambda i: -agirliklar.get(i, 20))
            konumlar = [f"{i}, {city}, Turkey" for i in ilceler]

        terimler = [k.format(s=sector, c=city) for k in TERIM_KALIPLARI]
        gorulen, sonuc = set(), []
        yeni_agirlik = {}

        for sira, konum in enumerate(konumlar):
            if len(sonuc) >= min_results:
                break
            kalan_butce = self.kalan_butce()
            if kalan_butce <= 0.02:
                logger.warning(f"Butce doldu ({self.butce_usd} USD), tarama durduruldu.")
                break

            kalan_kayit = min_results - len(sonuc)
            kalan_konum = max(1, len(konumlar) - sira)
            adet = int(min(ILCE_UST, max(ILCE_ALT, math.ceil(kalan_kayit / kalan_konum))))

            kayitlar = self._kosu(terimler, konum, adet, kalan_butce)
            ilce_adi = konum.split(",")[0].strip()
            yeni_agirlik[ilce_adi] = len(kayitlar)

            eklenen = 0
            for k in kayitlar:
                pid = k.get("placeId")
                if pid and pid in gorulen:
                    continue
                gorulen.add(pid)
                sonuc.append(self._donustur(k, ilce_adi))
                eklenen += 1
            logger.info(f"{ilce_adi}: {len(kayitlar)} kayit ({eklenen} yeni) | toplam {len(sonuc)}")

        if yeni_agirlik:
            tum = _json_oku(AGIRLIK_DOSYASI, {})
            tum.setdefault(city, {}).update(yeni_agirlik)
            _json_yaz(AGIRLIK_DOSYASI, tum)

        return sonuc

    def _kosu(self, terimler, konum, adet, kalan_butce):
        girdi = {
            "searchStringsArray": terimler,
            "locationQuery": konum,
            "maxCrawledPlacesPerSearch": adet,
            "language": "tr",
            "skipClosedPlaces": True,
        }
        tavan = round(min(kalan_butce, 1.0), 4)
        istek = urllib.request.Request(
            f"{API}/acts/{ACTOR}/runs?token={self.token}&maxTotalChargeUsd={tavan}",
            data=json.dumps(girdi).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(istek, timeout=60) as r:
                run = json.load(r)["data"]
        except Exception as e:
            logger.error(f"Apify kosu baslatilamadi ({konum}): {e}")
            return []

        while True:
            time.sleep(10)
            try:
                d = self._get(f"actor-runs/{run['id']}")["data"]
            except Exception:
                continue
            if d["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        if d["status"] != "SUCCEEDED":
            logger.warning(f"{konum} kosu durumu: {d['status']}")
        try:
            return self._get(f"datasets/{run['defaultDatasetId']}/items?format=json")
        except Exception:
            return []

    @staticmethod
    def _donustur(k: dict, ilce: str) -> dict:
        ilk = lambda a: (k.get(a) or [""])[0]
        return {
            "maps_name": k.get("title", ""),
            "website": k.get("website") or "",
            "phone": k.get("phoneUnformatted") or k.get("phone") or "",
            "ilce": ilce,
            "kategori": k.get("categoryName", ""),
            "adres": k.get("address", ""),
            "puan": k.get("totalScore", ""),
            "yorum": k.get("reviewsCount", ""),
            "harita": k.get("url", ""),
            "instagram": ilk("instagrams"),
            "facebook": ilk("facebooks"),
            "linkedin": ilk("linkedIns"),
            "emails": k.get("emails") or [],
            "place_id": k.get("placeId", ""),
        }
