#!/usr/bin/env python3
"""BusinessScraper'in Apify Google Maps tabanli yerine gecen surumu.

Eski scraper/maps_scraper.py ile AYNI arayuzu sunar (start_browser /
search_businesses / close_browser) - dashboard.py'de yalniz import satiri degisir.

Farklar:
  - Places Text Search'un sorgu basina 60 sonuc tavani YOK (ilce/terim yelpazesi)
  - Web sitesi olmayan isletme ATILMAZ (telefon + Instagram ile doner)
  - Ilce, kategori, adres, puan, yorum sayisi ve harita bagi da doner
"""
import json, logging, os, time, urllib.request

logger = logging.getLogger(__name__)

ACTOR = "lukaskrivka~google-maps-with-contact-details"
API = "https://api.apify.com/v2"
# Ayni sektorde farkli sonuc kumesi getiren terim kaliplari
TERIM_KALIPLARI = ["{s}", "{s} {c}"]


def _token():
    from config import APIFY_TOKEN, APIFY_TOKEN_FILE
    if APIFY_TOKEN:
        return APIFY_TOKEN
    with open(APIFY_TOKEN_FILE) as f:
        return json.load(f)["api_token"]


class BusinessScraper:
    """Google Maps isletme kesfi (Apify)."""

    def __init__(self, butce_usd: float = 2.0):
        self.butce_usd = float(os.getenv("APIFY_BUTCE_USD", butce_usd))
        self.token = None

    def start_browser(self):
        self.token = _token()
        logger.info("Apify Google Maps kesif motoru hazir.")

    def close_browser(self):
        pass

    def _get(self, path):
        url = f"{API}/{path}{'&' if '?' in path else '?'}token={self.token}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)

    def search_businesses(self, sector: str, city: str, min_results: int = 20,
                          ilceler: list = None) -> list:
        """Sektor + sehir icin isletmeleri bul.

        ilceler verilirse her ilce ayri kosu olur (60 sonuc tavanini kirar).
        """
        if not self.token:
            self.start_browser()

        konumlar = [f"{i}, {city}, Turkey" for i in ilceler] if ilceler else [f"{city}, Turkey"]
        adet = max(1, int(min_results / max(1, len(konumlar))))
        terimler = [k.format(s=sector, c=city) for k in TERIM_KALIPLARI]

        gorulen, sonuc = set(), []
        for konum in konumlar:
            if len(sonuc) >= min_results:
                break
            kayitlar = self._kosu(terimler, konum, adet)
            for k in kayitlar:
                pid = k.get("placeId")
                if pid and pid in gorulen:
                    continue
                gorulen.add(pid)
                sonuc.append(self._donustur(k, konum))
            logger.info(f"{konum}: toplam {len(sonuc)} isletme")
        return sonuc

    def _kosu(self, terimler, konum, adet):
        girdi = {
            "searchStringsArray": terimler,
            "locationQuery": konum,
            "maxCrawledPlacesPerSearch": adet,
            "language": "tr",
            "skipClosedPlaces": True,
        }
        req = urllib.request.Request(
            f"{API}/acts/{ACTOR}/runs?token={self.token}&maxTotalChargeUsd={self.butce_usd}",
            data=json.dumps(girdi).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                run = json.load(r)["data"]
        except Exception as e:
            logger.error(f"Apify kosu baslatilamadi: {e}")
            return []

        while True:
            time.sleep(10)
            d = self._get(f"actor-runs/{run['id']}")["data"]
            if d["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        if d["status"] != "SUCCEEDED":
            logger.warning(f"Apify kosu durumu: {d['status']}")
        return self._get(f"datasets/{run['defaultDatasetId']}/items?format=json")

    @staticmethod
    def _donustur(k: dict, konum: str) -> dict:
        ig = (k.get("instagrams") or [""])[0]
        fb = (k.get("facebooks") or [""])[0]
        li = (k.get("linkedIns") or [""])[0]
        return {
            "maps_name": k.get("title", ""),
            "website": k.get("website") or "",
            "phone": k.get("phoneUnformatted") or k.get("phone") or "",
            "ilce": konum.split(",")[0].strip(),
            "kategori": k.get("categoryName", ""),
            "adres": k.get("address", ""),
            "puan": k.get("totalScore", ""),
            "yorum": k.get("reviewsCount", ""),
            "harita": k.get("url", ""),
            "instagram": ig, "facebook": fb, "linkedin": li,
            "emails": k.get("emails") or [],
            "place_id": k.get("placeId", ""),
        }
