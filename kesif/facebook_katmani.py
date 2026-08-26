#!/usr/bin/env python3
"""Facebook katmani - web sitesi olmayan isletmelerin e-postasini bulur.

Neden: taranan isletmelerin %64'unun web sitesi yok. Instagram profil verisinde
e-posta ALANI YOK (olculdu); Facebook sayfalari ise e-postayi herkese acik
gosteriyor (olculdu: 4 sayfanin 3'u gercek e-posta verdi).

Iki asama:
  A. arama  (apify/facebook-search-scraper) - kategori + konum -> sayfa adresleri
  B. sayfa  (apify/facebook-pages-scraper)  - sayfa adresi -> e-posta, telefon, site

Eslestirme guvenligi: mevcut bir satirin e-postasi ancak isim benzerligi YUKSEK
ise yazilir. Zayif eslesme mevcut satira DOKUNMAZ; sayfa yeni satir olarak eklenir.
Boylece yanlis firmaya yanlis e-posta yazilmaz.
"""
import difflib
import json
import logging
import os
import re
import sys
import time
import urllib.request

_DIZIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_DIZIN))
sys.path.insert(0, _DIZIN)

from eposta_zenginlestir import sahiplik, temizle, JENERIK, _sadelestir

logger = logging.getLogger(__name__)

API = "https://api.apify.com/v2"
ARAMA_ACTOR = "apify~facebook-search-scraper"
SAYFA_ACTOR = "apify~facebook-pages-scraper"

ESIK = 0.90          # isim benzerligi esigi (altinda mevcut satira dokunulmaz)
EN_KISA_AYIRT = 8    # containment'in gecerli sayilmasi icin en kisa anahtar
# Semt/ilce adlari marka DEGILDIR: "Tunali Guzellik" ile "Tunali Lazer" ayri isletmedir
YER_ADLARI = set()
SAYFA_TOPLU = 20     # tek kosuda kac sayfa taranir

# Facebook kategori aramasi hedefi tutturamiyor: "guzellik salonu Ankara" sorgusu
# emlakci, anaokulu, oto aksesuar da donduruyor (olculdu 26.08). Sayfanin KENDI
# kategorisiyle suzuyoruz - sektor disi kayit listeye girmesin.
SEKTOR_KATEGORILERI = (
    "beauty", "salon", "spa", "hair", "nail", "barber", "cosmetic",
    "skin care", "massage", "waxing", "make-up", "makeup", "hairdresser",
    "guzellik", "kuafor", "epilasyon", "estetik",
)


def sektor_uygun(kategoriler, ad: str = "") -> bool:
    """Sayfa hedef sektorde mi? Kategori yoksa isimden bakilir."""
    metin = " ".join(kategoriler or []).lower()
    if metin and any(k in metin for k in SEKTOR_KATEGORILERI):
        return True
    if metin:
        return False
    return any(k in _sadelestir(ad) for k in ("guzellik", "kuafor", "epilasyon", "estetik", "beauty"))


def _token():
    from config import APIFY_TOKEN, APIFY_TOKEN_FILE
    if APIFY_TOKEN:
        return APIFY_TOKEN
    with open(APIFY_TOKEN_FILE) as f:
        return json.load(f)["api_token"]


def yer_adlari_yukle(sehir: str = "Ankara"):
    """Ilce adlarini jenerik sayilacak yer adlari kumesine ekle."""
    try:
        from maps_apify import ilceler_getir
        for i in ilceler_getir(sehir):
            YER_ADLARI.add(_sadelestir(i))
    except Exception:
        pass


def telefon_anahtari(t: str) -> str:
    """Telefonu karsilastirilabilir hale getir: sadece rakam, son 10 hane."""
    r = re.sub(r"\D", "", t or "")
    return r[-10:] if len(r) >= 10 else ""


def _ad_anahtari(ad: str) -> str:
    """Isim benzerligi icin sadelestirilmis anahtar (jenerik kelimeler atilir)."""
    parcalar = [
        _sadelestir(k) for k in re.split(r"[^\wğüşıöçĞÜŞİÖÇ]+", ad or "")
    ]
    anlamli = [p for p in parcalar
               if len(p) >= 3 and p not in JENERIK and p not in YER_ADLARI]
    return "".join(anlamli) or _sadelestir(ad)


def benzerlik(a: str, b: str) -> float:
    x, y = _ad_anahtari(a), _ad_anahtari(b)
    if not x or not y:
        return 0.0
    oran = difflib.SequenceMatcher(None, x, y).ratio()
    if x in y or y in x:
        oran = 1.0
    # Ayirt edici parca cok kisaysa isim TEK BASINA kanit degildir.
    # ("Tunali Guzellik" ile "Tunali Lazer" ayni semtte iki ayri isletme)
    if min(len(x), len(y)) < EN_KISA_AYIRT:
        return min(oran, ESIK - 0.05)
    return oran


class FacebookKatmani:
    def __init__(self, butce_usd: float = 1.0):
        self.token = _token()
        self.butce_usd = float(butce_usd)
        self._baslangic = self.harcanan_usd()

    # --- hesap ---
    def _get(self, path):
        url = f"{API}/{path}{'&' if '?' in path else '?'}token={self.token}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)

    def harcanan_usd(self) -> float:
        try:
            d = self._get("users/me/usage/monthly")["data"]
            return float(d.get("totalUsageCreditsUsdAfterVolumeDiscount") or 0)
        except Exception:
            return 0.0

    def kalan_butce(self) -> float:
        return max(0.0, self.butce_usd - (self.harcanan_usd() - self._baslangic))

    def _kosu(self, actor: str, girdi: dict) -> list:
        tavan = round(min(self.kalan_butce(), 1.0), 4)
        if tavan <= 0.01:
            logger.warning("Butce doldu.")
            return []
        istek = urllib.request.Request(
            f"{API}/acts/{actor}/runs?token={self.token}&maxTotalChargeUsd={tavan}",
            data=json.dumps(girdi).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(istek, timeout=60) as r:
                run = json.load(r)["data"]
        except Exception as e:
            logger.error(f"{actor} baslatilamadi: {e}")
            return []
        while True:
            time.sleep(8)
            try:
                d = self._get(f"actor-runs/{run['id']}")["data"]
            except Exception:
                continue
            if d["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        try:
            return self._get(f"datasets/{run['defaultDatasetId']}/items?format=json")
        except Exception:
            return []

    # --- A: sayfa adreslerini bul ---
    def sayfa_bul(self, terimler: list, konumlar: list, limit: int = 20) -> list:
        bulunan, gorulen = [], set()
        for konum in konumlar:
            if self.kalan_butce() <= 0.02:
                logger.warning("Butce doldu, arama durduruldu.")
                break
            kayitlar = self._kosu(ARAMA_ACTOR, {
                "search": terimler[0],
                "searchType": "place",
                "searchLimit": limit,
                "locations": [konum],
                "categories": terimler,
            })
            yeni = 0
            for k in kayitlar:
                if k.get("error"):
                    continue
                url = k.get("pageUrl") or k.get("facebookUrl")
                pid = k.get("pageId") or url
                if not url or pid in gorulen:
                    continue
                gorulen.add(pid)
                bulunan.append({
                    "url": url,
                    "title": k.get("title", ""),
                    "adres": k.get("address", ""),
                    "ilce": konum.split(",")[0].strip(),
                })
                yeni += 1
            logger.info(f"{konum}: {yeni} sayfa bulundu (toplam {len(bulunan)})")
        return bulunan

    # --- B: sayfalardan e-posta cek ---
    def sayfa_detay(self, sayfalar: list) -> list:
        sonuc = []
        for i in range(0, len(sayfalar), SAYFA_TOPLU):
            dilim = sayfalar[i:i + SAYFA_TOPLU]
            if self.kalan_butce() <= 0.02:
                logger.warning("Butce doldu, sayfa tarama durduruldu.")
                break
            kayitlar = self._kosu(SAYFA_ACTOR, {
                "startUrls": [{"url": s["url"]} for s in dilim]
            })
            harita = {s["url"]: s for s in dilim}
            for k in kayitlar:
                if k.get("error"):
                    continue
                kaynak = harita.get(k.get("pageUrl") or k.get("facebookUrl"), {})
                ad = k.get("title") or kaynak.get("title", "")
                kats = k.get("categories") or ([k["category"]] if k.get("category") else [])
                if not sektor_uygun(kats, ad):
                    logger.info(f"  sektör dışı elendi: {ad[:30]} ({', '.join(kats[-1:]) or '?'})")
                    continue
                eposta = temizle(k.get("email") or "")
                site = k.get("website") or ""
                if eposta and sahiplik(eposta, site, ad) == "ucuncu_taraf":
                    logger.info(f"  üçüncü taraf elendi: {ad[:26]} -> {eposta}")
                    eposta = ""
                sonuc.append({
                    "ad": ad,
                    "eposta": eposta,
                    "tip": sahiplik(eposta, site, ad).replace("kisisel", "kişisel") if eposta else "",
                    "telefon": k.get("phone") or "",
                    "web": site,
                    "facebook": k.get("pageUrl") or k.get("facebookUrl", ""),
                    "adres": k.get("address") or kaynak.get("adres", ""),
                    "kategori": (k.get("categories") or [""])[0] if k.get("categories") else "",
                    "ilce": kaynak.get("ilce", ""),
                })
            logger.info(f"  {i + len(dilim)}/{len(sayfalar)} sayfa tarandi, "
                        f"e-postali: {sum(1 for x in sonuc if x['eposta'])}")
        return sonuc


def eslestir(fb_kayitlari: list, mevcut: list, ad_alan: str, tel_alan: str) -> tuple:
    """Facebook kayitlarini mevcut satirlarla eslestir.

    Oncelik TELEFON: ayni numara = kesin ayni isletme. Isim benzerligi ikincil
    ve serttir; semt adlari marka sayilmaz.

    Returns: (guncellemeler, yeniler)
      guncellemeler: [(satir_index, fb_kayit, gerekce)]
      yeniler:       [fb_kayit]
    """
    tel_haritasi = {}
    for i, m in enumerate(mevcut):
        t = telefon_anahtari(m.get(tel_alan, ""))
        if t:
            tel_haritasi.setdefault(t, i)

    guncelleme, yeni = [], []
    for fb in fb_kayitlari:
        if not fb["eposta"]:
            continue
        t = telefon_anahtari(fb.get("telefon", ""))
        if t and t in tel_haritasi:
            guncelleme.append((tel_haritasi[t], fb, "telefon"))
            continue
        en_iyi, en_skor = None, 0.0
        for i, m in enumerate(mevcut):
            sk = benzerlik(fb["ad"], m[ad_alan])
            if sk > en_skor:
                en_iyi, en_skor = i, sk
        if en_iyi is not None and en_skor >= ESIK:
            guncelleme.append((en_iyi, fb, f"isim {en_skor:.2f}"))
        else:
            yeni.append(fb)
    return guncelleme, yeni
