#!/usr/bin/env python3
"""Scanner sayfasindaki e-postalari SMTP ile dogrular ve sonucu tabloya yazar.

Yeni sutun: "E-posta Doğrulama" (gecerli | gecersiz | belirsiz + gerekce).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import SHEET_COLUMNS, SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_URL, SHEET_NAME
from eposta_dogrula import dogrula_toplu

SID = GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]
SUTUN = "E-posta Doğrulama"


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

    ei = baslik.index("E-posta")
    if SUTUN in baslik:
        di = baslik.index(SUTUN)
    else:
        di = len(baslik)
        baslik.append(SUTUN)
        s.spreadsheets().values().update(
            spreadsheetId=SID, range=f"'{SHEET_NAME}'!{_harf(di + 1)}1",
            valueInputOption="RAW", body={"values": [[SUTUN]]},
        ).execute()
        print(f"'{SUTUN}' sütunu eklendi ({_harf(di + 1)}).")

    g = lambda r, i: r[i].strip() if i < len(r) else ""
    adresler = sorted({g(r, ei).lower() for r in satirlar if g(r, ei)})
    print(f"doğrulanacak benzersiz adres: {len(adresler)}")

    sonuc = dogrula_toplu(adresler)

    sutun = []
    for r in satirlar:
        e = g(r, ei).lower()
        if not e:
            sutun.append([""])
            continue
        d, neden = sonuc.get(e, ("belirsiz", "sorgulanmadı"))
        sutun.append([f"{d} ({neden})"])

    s.spreadsheets().values().update(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!{_harf(di + 1)}2",
        valueInputOption="RAW", body={"values": sutun},
    ).execute()

    # --- geri okuyarak dogrula ---
    geri = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!{_harf(di + 1)}1:{_harf(di + 1)}{len(satirlar) + 1}"
    ).execute().get("values", [])
    yazilan = sum(1 for r in geri[1:] if r and r[0].strip())

    say = {}
    for d, _ in sonuc.values():
        say[d] = say.get(d, 0) + 1
    print("\n--- SONUÇ (benzersiz adres) ---")
    for k in ("gecerli", "gecersiz", "belirsiz"):
        print(f"  {k}: {say.get(k, 0)}")
    print(f"\ntabloya yazılan hücre: {yazilan} (e-postalı satır sayısı kadar olmalı)")

    # tip kirilimi
    ti = baslik.index("Tip")
    kirilim = {}
    for r in satirlar:
        e = g(r, ei).lower()
        if not e:
            continue
        tip = g(r, ti) or "?"
        d = sonuc.get(e, ("belirsiz", ""))[0]
        kirilim.setdefault(tip, {}).setdefault(d, 0)
        kirilim[tip][d] += 1
    print("\n--- TİPE GÖRE ---")
    for tip, v2 in sorted(kirilim.items()):
        print(f"  {tip:10s} -> " + ", ".join(f"{k}:{n}" for k, n in sorted(v2.items())))


if __name__ == "__main__":
    main()
