#!/usr/bin/env python3
"""İlan veren firmalar → iletişim bilgisi → Scanner tablosu. 25.11.2026.

Owner: "Ben firmaların adlarını toplayıp sana veririm, sen iletişim bilgilerini alıp kayda geç,
Scanner datasına al." Firma adlarını Owner iş ilanı sitelerinden (elle) toplar; bu betik yalnız
firma adından firmanın KENDİ sitesine ve oradan kurumsal genel e-postaya gider.

GİRDİ: metin dosyası, satır başına  `Firma adı ; Grup ; Şehir(isteğe bağlı)`
       Grup: Sosyal Medya | Web | Reklam | ... (Owner'ın seçtiği pozisyon grubu, tabloda "İlan: <Grup>")

KURALLAR (tara_places ile aynı)
- Firma → site: Places Text Search (1 istek/firma, AYLIK_TAVAN defteri paylaşılır; Places içeriği saklanmaz).
- Eşleşme güvenliği: girdi adının anlamlı sözcüklerinin ≥ %60'ı Places adında ya da alan adında geçmezse
  YANLIŞ FİRMA sayılır, kayıt yazılmaz, rapora "eşleşmedi" düşer.
- E-posta: yalnız kurumsal alan adlı GENEL adres (KVKK); kişi adlı / ücretsiz sağlayıcı adresi alınmaz.
- Tekrar yok: tablo E sütunu, DijiMagic kişileri, gönderilmişler, aynı alan adı.
- YALNIZ Scanner tablosuna yazar. DijiMagic'e AKTARMAZ, kuyruğa ALMAZ, _places_adaylar.jsonl'e yazmaz
  (aktar_dijimagic bu satırları otomatik seriye sokmasın; seri ve metin Owner kararıdır).
- --kuru: tabloya yazmaz (Places isteği yine yapılır ve kotadan sayılır).
"""
import json, os, re, sys, unicodedata

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import tara_places as tp
import aktar_dijimagic as ad
import firma_adi

KAYIT = os.path.join(BURASI, "_ilan_firmalari_kayit.jsonl")
ESIK = 0.6
# Eşleşmede sayılmayacak kurumsal ek sözcükler
EK = {"as", "a", "s", "ltd", "sti", "sirketi", "limited", "anonim", "sanayi", "ticaret", "tic", "san", "ve",
      "ic", "dis", "pazarlama", "turizm", "insaat", "grup", "holding", "gida", "dan", "danismanlik", "hizmetleri",
      "hizmetler", "sistemleri", "teknoloji", "yazilim", "uretim", "dagitim", "otomotiv", "tekstil", "ith", "ihr",
      "the", "and", "co", "inc", "turkiye", "turk", "tr"}


def sade(s):
    s = unicodedata.normalize("NFKC", s or "").translate(firma_adi._TR).lower()
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


def anlamli(ad_):
    return [t for t in sade(ad_) if t not in EK and len(t) > 1]


def eslesme(girdi_adi, places_adi, domain):
    g = anlamli(girdi_adi)
    if not g:
        return 0.0
    hedef = " ".join(sade(places_adi)) + " " + " ".join(sade(domain or ""))
    bitisik = re.sub(r"[^a-z0-9]", "", hedef)
    bulunan = sum(1 for t in g if t in hedef.split() or t in bitisik)
    oran = bulunan / len(g)
    # Marka adının ilk sözcüğü (≥4 harf) alan adının kökündeyse aynı firma sayılır ("Mavi Giyim" → mavi.com)
    kok = re.sub(r"[^a-z0-9]", "", sade(domain.split(".")[0] if domain else "")[0] if domain and sade(domain.split(".")[0]) else "")
    if len(g[0]) >= 4 and kok and (g[0] == kok or kok.startswith(g[0]) or g[0].startswith(kok) and len(kok) >= 4):
        oran = max(oran, 1.0)
    return oran


def oku(yol):
    kayitlar = []
    for satir in open(yol, encoding="utf-8"):
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;\t]", satir)]
        kayitlar.append({"girdi": p[0], "grup": (p[1] if len(p) > 1 and p[1] else "Genel"),
                         "sehir": (p[2] if len(p) > 2 else "")})
    return kayitlar


def site_bul(d, k):
    """Firma adından Places ile web sitesi. Yalnız eşleşen sonuç alınır."""
    sorgu = k["girdi"] + (" " + k["sehir"] if k["sehir"] else "")
    try:
        j = tp.ara(d, sorgu)
    except tp.KotaBitti as e:
        return None, f"kota: {e}"
    for p in j.get("places", [])[:5]:
        site = p.get("websiteUri", "")
        if not site or tp.is_aggregator_website(site):
            continue
        dom = tp.extract_domain_from_url(site)
        ad_ = p.get("displayName", {}).get("text", "")
        oran = eslesme(k["girdi"], ad_, dom)
        if oran >= ESIK:
            return {"site": site, "_ad": ad_}, ""
    return None, "eşleşmedi (Places'ta bu adla web sitesi olan firma yok)"


def main():
    yol = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if not yol:
        sys.exit("kullanım: ilan_firmalari.py <girdi.txt> [--kuru]")
    kuru = "--kuru" in sys.argv
    girdiler = oku(yol)
    d = tp.defter_oku()

    v = ad.sheets()
    tablo = v.get(spreadsheetId=ad.SID, range="Scanner!E2:F8000").execute().get("values", [])
    gorulen_e = {r[0].strip().lower() for r in tablo if r}
    gorulen_dom = {r[1].strip().lower() for r in tablo if len(r) > 1}
    c = ad.baglan(); kur = c.cursor()
    kur.execute("select lower(email) from email_contacts where user_id=%s", (ad.UID,))
    db = {r[0] for r in kur.fetchall()}
    kur.execute("select lower(email) from email_sends where user_id=%s", (ad.UID,))
    db |= {r[0] for r in kur.fetchall()}
    gorulen_e |= db
    gorulen_dom |= {e.split("@")[1] for e in db if "@" in e}

    satirlar, rapor = [], []
    for k in girdiler:
        bulundu, neden = site_bul(d, k)
        if not bulundu:
            rapor.append((k, "SİTE YOK", neden))
            if neden.startswith("kota"):
                break
            continue
        bulundu["sektor"] = f"İlan: {k['grup']}"
        bulundu["ilce"] = ""
        s = tp.site_isle(bulundu)
        if not s:
            rapor.append((k, "E-POSTA YOK", bulundu["site"] + " (kurumsal genel adres bulunamadı)"))
            continue
        if s["eposta"].lower() in gorulen_e or s["domain"].lower() in gorulen_dom:
            rapor.append((k, "ZATEN VAR", s["domain"]))
            continue
        gorulen_e.add(s["eposta"].lower()); gorulen_dom.add(s["domain"].lower())
        satirlar.append([s["tarih"], s["sektor"], s["firma"], s.get("telefon", ""), s["eposta"].lower(),
                         s["domain"].lower(), s["site"], s.get("instagram", ""), s.get("facebook", ""),
                         s.get("linkedin", ""), s["tip"], "", k["sehir"], ""])
        rapor.append((k, "EKLENİRDİ" if kuru else "EKLENDİ", f"{s['firma'] or '(ad yok)'} | {s['eposta']} | {s['tip']}"))

    print(f"girdi {len(girdiler)} | eklenecek {len(satirlar)} | bu ay Places isteği {d['aylik'].get(tp.ay(), 0)}/{tp.AYLIK_TAVAN}")
    for k, durum, ayrinti in rapor:
        print(f"  {durum:12} {k['girdi'][:42]:42} [{k['grup']}] {ayrinti}")
    if kuru or not satirlar:
        return
    v.append(spreadsheetId=ad.SID, range="Scanner!A1:N1", valueInputOption="RAW", insertDataOption="INSERT_ROWS",
             body={"values": satirlar}).execute()
    geri = v.get(spreadsheetId=ad.SID, range="Scanner!E2:E8000").execute().get("values", [])
    var = {r[0].strip().lower() for r in geri if r}
    print(f"GERİ OKUNAN: {sum(1 for s in satirlar if s[4] in var)}/{len(satirlar)} satır Scanner'da")
    with open(KAYIT, "a", encoding="utf-8") as f:
        for s in satirlar:
            f.write(json.dumps({"tarih": s[0], "sektor": s[1], "domain": s[5], "eposta": s[4]}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
