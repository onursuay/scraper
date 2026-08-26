#!/usr/bin/env python3
"""Cozumlenmemis ('belirsiz') adresleri daha toleransli ayarlarla yeniden dener.

Ilk kosuda 53 satir TimeoutError verdi: Turk paylasimli hosting posta sunuculari
12 saniyede yanit vermiyor. Bu gecis 35 saniye bekler, yedek MX sunucularini da
dener ve adresleri tek tek sorar (toplu sorgu bazi sunucularda kesiliyor).
"""
import os
import smtplib
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import SHEET_COLUMNS, SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_URL, SHEET_NAME
from eposta_dogrula import mx_sunuculari, HELO

SID = GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]
ZAMAN_ASIMI = 35
YENIDEN_DENENECEK = ("TimeoutError", "SMTPServerDisconnected", "bağlantı kurulamadı")


def _harf(n):
    s = ""
    while n:
        n, k = divmod(n - 1, 26)
        s = chr(65 + k) + s
    return s


def tek_sor(sunucu: str, adres: str):
    """Tek adres icin tek oturum. POSTA GONDERMEZ."""
    try:
        s = smtplib.SMTP(timeout=ZAMAN_ASIMI)
        s.connect(sunucu, 25)
        s.ehlo(HELO)
        s.docmd("MAIL", "FROM:<>")
        kod, _ = s.docmd("RCPT", f"TO:<{adres}>")
        try:
            s.docmd("RSET")
            s.quit()
        except Exception:
            pass
        return kod, ""
    except (socket.error, smtplib.SMTPException, OSError) as e:
        return 0, type(e).__name__


def dogrula(adres: str):
    alan = adres.split("@", 1)[1]
    mx = mx_sunuculari(alan)
    if not mx:
        return "belirsiz", "posta sunucusu bulunamadı"
    son_hata = "bağlantı kurulamadı"
    for sunucu in mx[:3]:
        kod, hata = tek_sor(sunucu, adres)
        if 200 <= kod < 300:
            return "gecerli", f"SMTP {kod}"
        if 500 <= kod < 600:
            return "gecersiz", f"SMTP {kod}"
        if kod:
            son_hata = f"SMTP {kod}"
        elif hata:
            son_hata = hata
        time.sleep(1)
    return "belirsiz", son_hata


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
    ei, di = baslik.index("E-posta"), baslik.index("E-posta Doğrulama")
    g = lambda r, i: r[i].strip() if i < len(r) else ""

    hedef = sorted({
        g(r, ei).lower() for r in satirlar
        if g(r, ei) and any(h in g(r, di) for h in YENIDEN_DENENECEK)
    })
    print(f"yeniden denenecek adres: {len(hedef)}", flush=True)

    yeni = {}
    for i, a in enumerate(hedef, 1):
        d, neden = dogrula(a)
        yeni[a] = (d, neden)
        print(f"  [{i}/{len(hedef)}] {a:42s} -> {d} ({neden})", flush=True)
        time.sleep(1)

    sutun = []
    for r in satirlar:
        e = g(r, ei).lower()
        mevcut = g(r, di)
        if e in yeni:
            d, neden = yeni[e]
            sutun.append([f"{d} ({neden})"])
        else:
            sutun.append([mevcut])

    s.spreadsheets().values().update(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!{_harf(di + 1)}2",
        valueInputOption="RAW", body={"values": sutun},
    ).execute()

    geri = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!{_harf(di + 1)}2:{_harf(di + 1)}{len(satirlar) + 1}"
    ).execute().get("values", [])
    from collections import Counter
    say = Counter(r[0].split(" (")[0] for r in geri if r and r[0].strip())
    print("\n--- TABLODAN GERİ OKUNAN DURUM ---")
    for k, n in say.most_common():
        print(f"  {k}: {n}")


if __name__ == "__main__":
    main()
