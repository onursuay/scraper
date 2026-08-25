#!/usr/bin/env python3
"""Lead listesini 'Müşteri Datası' dosyasinin Scanner sayfasina yazar + geri okuyarak dogrular."""
import csv, sys, datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SID = "1lopLbx-37I2N4q31KH8_XVCP4rP6DDC23Kp82XgGC_Y"
SAYFA = "Scanner"
ANAHTAR = "/Users/onursuay/.claude/secrets/lead-crm-bot-key.json"
CSV_YOL = "/Users/onursuay/Desktop/Ankara Güzellik Merkezleri - Lead Listesi/ankara_guzellik_merkezleri.csv"

BASLIK = ["FİRMA ADI","İLÇE","KATEGORİ","ADRES","TELEFON","WEB SİTESİ","INSTAGRAM",
          "E-POSTA","E-POSTA TİPİ","TÜM E-POSTALAR","PUAN","YORUM SAYISI","HARİTA",
          "KAYIT TARİHİ","SÜREÇ","GÖRÜŞME SONUCU"]
# CSV sutun adi -> hedef sira (SÜREÇ/GÖRÜŞME SONUCU ekip doldurur, BOS birakilir)
ESLEME = ["Firma Adı","İlçe","Kategori","Adres","Telefon","Web Sitesi","Instagram",
          "E-posta","E-posta Tipi","Tüm E-postalar","Puan","Yorum Sayısı","Harita Bağlantısı"]


def servis():
    c = Credentials.from_service_account_file(ANAHTAR, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=c, cache_discovery=False)


def main():
    damga = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+03:00")
    with open(CSV_YOL, encoding="utf-8-sig") as f:
        satirlar = list(csv.DictReader(f))
    print(f"CSV'den {len(satirlar)} kayıt okundu.")

    veri = [BASLIK]
    for s in satirlar:
        veri.append([s.get(k, "") for k in ESLEME] + [damga, "", ""])

    s = servis()
    mevcut = s.spreadsheets().values().get(spreadsheetId=SID, range=f"'{SAYFA}'!A:A").execute().get("values", [])
    if mevcut:
        print(f"UYARI: Scanner boş değil ({len(mevcut)} satır) - alta ekleniyor.")
        veri = veri[1:]
        baslangic = len(mevcut) + 1
    else:
        baslangic = 1

    # Grid'i genislet (gerekirse)
    meta = s.spreadsheets().get(spreadsheetId=SID).execute()
    sp = next(sh["properties"] for sh in meta["sheets"] if sh["properties"]["title"] == SAYFA)
    gerekli = baslangic + len(veri) + 5
    if sp["gridProperties"]["rowCount"] < gerekli:
        s.spreadsheets().batchUpdate(spreadsheetId=SID, body={"requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": sp["sheetId"],
                               "gridProperties": {"rowCount": gerekli,
                                                  "columnCount": max(sp["gridProperties"]["columnCount"], len(BASLIK))}},
                "fields": "gridProperties.rowCount,gridProperties.columnCount"}}]}).execute()
        print(f"Grid {gerekli} satıra genişletildi.")

    s.spreadsheets().values().update(
        spreadsheetId=SID, range=f"'{SAYFA}'!A{baslangic}",
        valueInputOption="RAW", body={"values": veri}).execute()

    # --- GERI OKUYARAK DOGRULA ---
    geri = s.spreadsheets().values().get(
        spreadsheetId=SID, range=f"'{SAYFA}'!A1:P{baslangic + len(veri) - 1}").execute().get("values", [])
    dolu = [r for r in geri if r and r[0].strip()]
    print(f"\nGERİ OKUMA: {len(dolu)} dolu satır (başlık dahil)")
    print("başlık :", geri[0][:6] if geri else "-")
    print("ilk    :", geri[1][:5] if len(geri) > 1 else "-")
    print("son    :", geri[-1][:5] if geri else "-")

    beklenen = len(satirlar) + (1 if baslangic == 1 else 0)
    if len(dolu) == beklenen:
        print(f"\n✅ DOĞRULANDI: beklenen {beklenen} = okunan {len(dolu)}")
    else:
        print(f"\n❌ UYUŞMAZLIK: beklenen {beklenen}, okunan {len(dolu)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
