#!/usr/bin/env python3
"""Toplayici (instagram/facebook vb.) adreslerinden turemis hatali kayitlari temizler.

Sorun: Google Maps'te "web sitesi" alani Instagram adresi olan isletmelerde alan adi
instagram.com sanildi ve tahmin katmani info@instagram.com uretti (71 kayit).

Duzeltme: bu satirlarda E-posta/Tip/Domain bosaltilir, adres kendi sutununa
(Instagram/Facebook) tasinir, Web Sitesi bosaltilir. Satir SILINMEZ - isletme
telefonuyla listede kalir.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import SHEET_COLUMNS, SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_URL, SHEET_NAME
from utils.filters import is_aggregator_website, extract_domain_from_url

SID = GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]


def _harf(n):
    s = ""
    while n:
        n, k = divmod(n - 1, 26)
        s = chr(65 + k) + s
    return s


def main():
    c = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    s = build("sheets", "v4", credentials=c, cache_discovery=False)

    son = _harf(len(SHEET_COLUMNS) + 2)
    v = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1:{son}"
    ).execute().get("values", [])
    baslik, satirlar = v[0], v[1:]
    idx = {b: i for i, b in enumerate(baslik)}
    genislik = len(baslik)

    def al(r, ad):
        i = idx.get(ad, -1)
        return r[i].strip() if 0 <= i < len(r) else ""

    def yaz(r, ad, deger):
        i = idx[ad]
        while len(r) <= i:
            r.append("")
        r[i] = deger

    eposta_temiz = site_temiz = 0
    for r in satirlar:
        while len(r) < genislik:
            r.append("")

        e = al(r, "E-posta")
        if e and "@" in e and is_aggregator_website(e.split("@", 1)[1]):
            yaz(r, "E-posta", "")
            yaz(r, "Tip", "")
            yaz(r, "Tüm E-postalar", "")
            eposta_temiz += 1

        site = al(r, "Web Sitesi")
        if site and is_aggregator_website(site):
            d = extract_domain_from_url(site).lower()
            if "instagram" in d and not al(r, "Instagram"):
                yaz(r, "Instagram", site)
            elif ("facebook" in d or d == "fb.com") and not al(r, "Facebook"):
                yaz(r, "Facebook", site)
            yaz(r, "Web Sitesi", "")
            yaz(r, "Domain", "")
            site_temiz += 1

    print(f"temizlenen e-posta: {eposta_temiz} | doğru sütuna taşınan adres: {site_temiz}")

    s.spreadsheets().values().update(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A2",
        valueInputOption="RAW", body={"values": satirlar},
    ).execute()

    # --- geri okuyarak dogrula ---
    geri = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1:{son}"
    ).execute().get("values", [])
    gs = geri[1:]
    kalan = [r for r in gs if 0 <= idx["E-posta"] < len(r)
             and "@" in r[idx["E-posta"]]
             and is_aggregator_website(r[idx["E-posta"]].split("@", 1)[1])]
    epostali = sum(1 for r in gs if 0 <= idx["E-posta"] < len(r) and r[idx["E-posta"]].strip())
    igli = sum(1 for r in gs if 0 <= idx["Instagram"] < len(r) and r[idx["Instagram"]].strip())

    print(f"\nGERİ OKUMA: {len(gs)} satır")
    print(f"  kalan toplayıcı e-postası: {len(kalan)} (0 olmalı)")
    print(f"  e-postalı satır: {epostali}")
    print(f"  Instagram'ı olan satır: {igli}")
    assert not kalan, "TEMİZLİK EKSİK"
    print("\n✅ TEMİZLENDİ VE DOĞRULANDI")


if __name__ == "__main__":
    main()
