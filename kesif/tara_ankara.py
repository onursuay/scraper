#!/usr/bin/env python3
"""Ankara guzellik sektoru kesfi - ilce x anahtar kelime yelpazesi."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apify_maps as am

CIKTI = "/private/tmp/claude-501/-Users-onursuay-Desktop-Agency-Wizard/43525271-34a1-4a87-9594-e34cdccb80eb/scratchpad/ankara_ham.json"
BUTCE_TAVANI = 4.40  # ucretsiz kredi icinde kal

KELIMELER = ["güzellik merkezi", "lazer epilasyon"]

# (ilce, arama terimi basina kayit adedi) - ticari yogunluga gore
ILCELER = [
    ("Çankaya", 45), ("Yenimahalle", 35), ("Keçiören", 35), ("Etimesgut", 25),
    ("Mamak", 22), ("Altındağ", 22), ("Sincan", 22), ("Gölbaşı", 15),
    ("Pursaklar", 12), ("Polatlı", 12), ("Çubuk", 8), ("Kahramankazan", 8),
    ("Akyurt", 6), ("Beypazarı", 6), ("Elmadağ", 5),
]

tum = json.load(open(CIKTI)) if os.path.exists(CIKTI) else {}
print(f"başlangıç: {len(tum)} kayıt | harcanan {am.harcanan_usd():.4f} USD", flush=True)

for ilce, adet in ILCELER:
    harcanan = am.harcanan_usd()
    if harcanan >= BUTCE_TAVANI:
        print(f"!! bütçe tavanı ({BUTCE_TAVANI} USD) doldu, {ilce} atlandı", flush=True)
        break
    print(f"\n>> {ilce} ({adet}/terim) | harcanan {harcanan:.4f} USD", flush=True)
    try:
        kayitlar, maliyet, durum = am.calistir(
            KELIMELER, f"{ilce}, Ankara, Turkey", adet,
            butce_usd=min(1.0, BUTCE_TAVANI - harcanan),
        )
    except Exception as e:
        print(f"   HATA: {e}", flush=True)
        continue
    yeni = 0
    for k in kayitlar:
        pid = k.get("placeId")
        if pid and pid not in tum:
            k["_ilce"] = ilce
            tum[pid] = k
            yeni += 1
    json.dump(tum, open(CIKTI, "w"), ensure_ascii=False)
    print(f"   {durum} | {len(kayitlar)} kayıt ({yeni} yeni) | {maliyet:.4f} USD | toplam benzersiz: {len(tum)}", flush=True)

print(f"\nBİTTİ: {len(tum)} benzersiz işletme | toplam harcanan {am.harcanan_usd():.4f} USD", flush=True)
