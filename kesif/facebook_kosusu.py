#!/usr/bin/env python3
"""Facebook katmanini calistirip Scanner sayfasini zenginlestirir.

Kural: mevcut bir satirin E-postasi ancak BOSSA doldurulur; dolu adres asla
ezilmez. Eslesme once TELEFONLA, olmazsa sert isim benzerligiyle yapilir.
Eslesmeyen sayfalar YENI satir olarak eklenir (Maps'te olmayan isletmeler).
"""
import argparse
import datetime
import logging
import os
import sys

_DIZIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_DIZIN))
sys.path.insert(0, _DIZIN)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import SHEET_COLUMNS, SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_URL, SHEET_NAME
from facebook_katmani import FacebookKatmani, eslestir, yer_adlari_yukle
from maps_apify import ilceler_getir, _json_oku, AGIRLIK_DOSYASI

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("facebook")

SID = GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]


def _harf(n):
    s = ""
    while n:
        n, k = divmod(n - 1, 26)
        s = chr(65 + k) + s
    return s


def servis():
    c = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=c, cache_discovery=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sehir", default="Ankara")
    ap.add_argument("--sektor", default="güzellik salonu")
    ap.add_argument("--butce", type=float, default=float(os.getenv("APIFY_BUTCE_USD", "1.0")))
    ap.add_argument("--ilce-sayisi", type=int, default=4)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--kuru", action="store_true", help="tabloya yazma, yalnız raporla")
    a = ap.parse_args()

    yer_adlari_yukle(a.sehir)
    s = servis()
    son = _harf(len(SHEET_COLUMNS) + 2)
    v = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1:{son}"
    ).execute().get("values", [])
    baslik, satirlar = v[0], v[1:]
    gen = len(baslik)
    satirlar = [r + [""] * (gen - len(r)) for r in satirlar]
    idx = {b: i for i, b in enumerate(baslik)}

    mevcut = [{"ad": r[idx["Firma Adı"]], "tel": r[idx["Telefon"]]} for r in satirlar]

    # Yogun ilcelerden basla
    ag = _json_oku(AGIRLIK_DOSYASI, {}).get(a.sehir, {})
    ilceler = sorted(ilceler_getir(a.sehir), key=lambda i: -ag.get(i, 20))[:a.ilce_sayisi]
    konumlar = [f"{i}, {a.sehir}, Turkey" for i in ilceler]
    logger.info(f"taranacak ilçeler: {ilceler}")

    fk = FacebookKatmani(butce_usd=a.butce)
    logger.info(f"bütçe {a.butce} USD | kalan {fk.kalan_butce():.3f}")

    sayfalar = fk.sayfa_bul([a.sektor, f"{a.sektor} {a.sehir}"], konumlar, a.limit)
    logger.info(f"bulunan sayfa: {len(sayfalar)}")
    if not sayfalar:
        logger.warning("sayfa bulunamadı, çıkılıyor.")
        return

    detay = fk.sayfa_detay(sayfalar)
    epostali = [d for d in detay if d["eposta"]]
    logger.info(f"taranan sayfa: {len(detay)} | e-postalı: {len(epostali)}")
    for d in epostali:
        logger.info(f"   {d['ad'][:32]:34s} {d['eposta']:32s} [{d['tip']}]")

    guncelleme, yeni = eslestir(detay, mevcut, "ad", "tel")
    logger.info(f"\neşleşen (mevcut satır): {len(guncelleme)} | yeni işletme: {len(yeni)}")

    yazildi = eklendi = atlandi = 0
    for i, fb, gerekce in guncelleme:
        r = satirlar[i]
        if r[idx["E-posta"]].strip():
            atlandi += 1
            logger.info(f"   dolu, dokunulmadı: {r[idx['Firma Adı']][:30]}")
            continue
        r[idx["E-posta"]] = fb["eposta"]
        r[idx["Tip"]] = fb["tip"]
        if not r[idx["Facebook"]].strip():
            r[idx["Facebook"]] = fb["facebook"]
        if not r[idx["Telefon"]].strip() and fb["telefon"]:
            r[idx["Telefon"]] = fb["telefon"]
        yazildi += 1
        logger.info(f"   dolduruldu ({gerekce}): {r[idx['Firma Adı']][:28]} -> {fb['eposta']}")

    bugun = datetime.datetime.now().strftime("%Y-%m-%d")
    yeni_satirlar = []
    for fb in yeni:
        d = {
            "Tarih": bugun, "Sektör": a.sektor, "Firma Adı": fb["ad"],
            "İlçe": fb["ilce"], "Kategori": fb["kategori"], "Adres": fb["adres"],
            "Telefon": fb["telefon"], "E-posta": fb["eposta"], "Tip": fb["tip"],
            "Web Sitesi": fb["web"], "Facebook": fb["facebook"],
        }
        yeni_satirlar.append([d.get(c, "") for c in baslik])
        eklendi += 1

    logger.info(f"\ndolduruldu: {yazildi} | zaten doluydu: {atlandi} | yeni satır: {eklendi}")

    if a.kuru:
        logger.info("kuru çalışma - tabloya yazılmadı.")
        return

    if yazildi:
        s.spreadsheets().values().update(
            spreadsheetId=SID, range=f"'{SHEET_NAME}'!A2",
            valueInputOption="RAW", body={"values": satirlar},
        ).execute()
    if yeni_satirlar:
        s.spreadsheets().values().append(
            spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": yeni_satirlar},
        ).execute()

    # --- geri okuyarak dogrula ---
    geri = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1:{son}"
    ).execute().get("values", [])
    gs = [r for r in geri[1:] if r and r[0].strip()]
    g = lambda r, i: r[i].strip() if i < len(r) else ""
    print(f"\nGERİ OKUMA: {len(gs)} satır (önce {len(satirlar)})")
    print(f"  e-postalı satır : {sum(1 for r in gs if g(r, idx['E-posta']))}")
    print(f"  Facebook'lu satır: {sum(1 for r in gs if g(r, idx['Facebook']))}")
    print(f"  harcanan: {fk.harcanan_usd() - fk._baslangic:.4f} USD")
    assert len(gs) == len(satirlar) + eklendi, "SATIR SAYISI UYUŞMUYOR"
    print("\n✅ YAZILDI VE DOĞRULANDI")


if __name__ == "__main__":
    main()
