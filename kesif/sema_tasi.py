#!/usr/bin/env python3
"""Scanner sayfasindaki kayitlari birlesik SHEET_COLUMNS semasina tasir.

Silme YAPMAZ: yeni sema (21 sutun) eski semanin (16 sutun) ustune yazilir,
satir sayisi ayni oldugu icin artik veri kalmaz. Yazim sonrasi geri okunup dogrulanir.
"""
import csv, os, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import SHEET_COLUMNS, SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_URL, SHEET_NAME
from utils.filters import extract_domain_from_url

CSV_YOL = os.path.expanduser(
    "~/Desktop/Ankara Güzellik Merkezleri - Lead Listesi/ankara_guzellik_merkezleri.csv"
)
SEKTOR = "güzellik merkezi"
SID = GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]


def satir(k):
    site = k["Web Sitesi"]
    d = {
        "Tarih": datetime.datetime.now().strftime("%Y-%m-%d"),
        "Sektör": SEKTOR,
        "Firma Adı": k["Firma Adı"],
        "İlçe": k["İlçe"],
        "Kategori": k["Kategori"],
        "Adres": k["Adres"],
        "Telefon": k["Telefon"],
        "E-posta": k["E-posta"],
        "Tip": k["E-posta Tipi"],
        "Tüm E-postalar": k["Tüm E-postalar"],
        "Elenen (üçüncü taraf)": k["Elenen (üçüncü taraf)"],
        "Domain": extract_domain_from_url(site) if site else "",
        "Web Sitesi": site,
        "Instagram": k["Instagram"],
        "Facebook": "",
        "LinkedIn": "",
        "Puan": k["Puan"],
        "Yorum Sayısı": k["Yorum Sayısı"],
        "Harita": k["Harita Bağlantısı"],
        "Süreç": "",
        "Görüşme Sonucu": "",
    }
    return [d.get(c, "") for c in SHEET_COLUMNS]


def main():
    kayitlar = list(csv.DictReader(open(CSV_YOL, encoding="utf-8-sig")))
    veri = [SHEET_COLUMNS] + [satir(k) for k in kayitlar]

    c = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    s = build("sheets", "v4", credentials=c, cache_discovery=False)

    onceki = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A:A"
    ).execute().get("values", [])
    print(f"mevcut satır: {len(onceki)} | yazılacak: {len(veri)}")
    if len(onceki) > len(veri):
        print("DUR: mevcut satır sayısı yazılacaktan fazla, artık veri kalır.")
        sys.exit(1)

    s.spreadsheets().values().update(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1",
        valueInputOption="RAW", body={"values": veri},
    ).execute()

    geri = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SHEET_NAME}'!A1:U{len(veri)}"
    ).execute().get("values", [])
    dolu = [r for r in geri if r and r[0].strip()]
    g = lambda r, i: r[i] if i < len(r) else ""
    di, ei, ti = (SHEET_COLUMNS.index(x) for x in ("Domain", "E-posta", "Telefon"))

    print("başlık:", geri[0][:8], "...")
    print(f"geri okunan dolu satır: {len(dolu)} (beklenen {len(veri)})")
    print("domain dolu :", sum(1 for r in geri[1:] if g(r, di)))
    print("e-posta dolu:", sum(1 for r in geri[1:] if g(r, ei)))
    print("telefon dolu:", sum(1 for r in geri[1:] if g(r, ti)))
    assert len(dolu) == len(veri), "UYUŞMAZLIK"
    print("\n✅ ŞEMA TAŞINDI VE GERİ OKUNARAK DOĞRULANDI")


if __name__ == "__main__":
    main()
