# Keşif Motoru — firma bulma → Scanner tablosu → DijiMagic Email Marketing

Güncel: **24.11.2026.** Keşif artık **Google Places API (New)** ile yapılıyor (Owner kararı).
Apify katmanı (`apify_maps.py`, `maps_apify.py`, `tara_ankara.py`, `facebook_*`) kullanılmıyor;
dosyalar tarihçe olarak duruyor.

## Akış

| # | Betik | Ne yapar |
|---|---|---|
| 1 | `tara_places.py` | Places Text Search (ilçe × sektör kelimesi, sorgu başına en çok 3 sayfa) → firmanın **kendi sitesinden** kurumsal genel e-posta, telefon, firma adı ve sosyal hesaplar → `_places_adaylar.jsonl` |
| 2 | `firma_adi.py` | Firma adını sitenin schema.org / og:site_name / title / logo alt metninden seçer; bozuk kodlamayı onarır (`onar`, "Ä°nce" → "İnce"). Güvenilir ad yoksa `""` döner, kayıt `inceleme` olur ve gönderime alınmaz |
| 3 | `aktar_dijimagic.py` | Yeni adayları Iron Mountain tablosunun **Scanner** sekmesine (gid 987142293) yazar, DijiMagic Email Marketing kişilerine ekler ve ilk maili kuyruğa planlar. `--kuru` hiçbir yere yazmaz |

## Kurallar

- **Ücret kilidi iki katman:** Google Cloud kotası `SearchTextRequest/gün` (aşılınca 429 → betik durur) +
  defterdeki aylık sayaç `AYLIK_TAVAN = 990` (Enterprise SKU ayda 1.000 istek ücretsiz).
  Aylık sayaç ABD Pasifik saatine göre sıfırlanır, günlük kota TR 11:00'de.
- **Google Maps şartı:** Places içeriği saklanmaz; defterde yalnız place ID tutulur. Ad, telefon,
  e-posta ve sosyal hesap firmanın kendi sitesinden okunur.
- **KVKK süzgeci:** yalnız kurumsal alan adlı **genel** adres (`info@`, `iletisim@`, `randevu@`…);
  kişi adı taşıyan ya da ücretsiz sağlayıcı adresi alınmaz. Hastane zincirleri, kamu ve rehber siteleri elenir.
- **Tekrar yok:** tablo E sütunu, DijiMagic kişileri, gönderilmişler ve aynı alan adı denetlenir.
- **Gönderim planı (spam'e düşmemek için):** günlük **toplam** tavan (ilk mail + takipler) ısınma rampasıyla
  25 → 40 (02.12) → 60 (09.12) → 80 (16.12) → 100 (23.12); yalnız hafta içi, 10:00-16:00 arasına eşit aralıkla.
  Takip mailleri öngörülerek yük haritasına eklenir; yeni ilk mail yalnız o günün boş kapasitesine konur.
- **Otomasyonlar kapalıyken** yeni kişi tabloya yazılır ama **kuyruğa alınmaz**.

## Güncel durum (25.11.2026 16:30, veritabanından geri okundu)

| Kalem | Değer |
|---|---|
| Kasım ayı Places isteği | 140 / 990 |
| DijiMagic kişi listesi | 305 |
| **Gönderim** | ✅ **AÇIK** (25.11 yeni metinlerle yeniden başladı; iki otomasyon açık) |
| Kuyruk | 286 bekleyen (son 09.12) · 34 gönderildi · zamanı geçmiş bekleyen 0 |
| Takip | açılma 3 · tıklama 0 · geri dönen 4 |

- Gönderim zamanlayıcısı **10 dakikada bir** çalışır (25.11'e kadar saatlikti); mail planlı saatten en çok 10 dk sonra gider.
- DijiMagic kişi listesi Mail Tarihi'ne göre **takvim sırasıyla** (eskiden yeniye) sıralanır.
- Telefon her kaynakta "0532 000 00 00" biçimine çevrilir (DijiMagic tarafında; `aktar_dijimagic.py` hâlâ ham yazar, veri şu an uyumlu).
- Elle/CSV/CRM eklenen kişi otomatik seriye girmez (Owner kararı); seriye almak DijiMagic'te "Seriye al" ile.
- Mailde tek bağlantı (dijimagic.com) + abonelikten çık; ek bağlantı eklenmez, açılma takibi açık (Owner 25.11: "şu haliyle kalsın").
- 24.11 durdurma yedeği (`_gonderim_durdurma_yedegi_2026-11-24.json`) tarihçedir, kuyruk 25.11'de yeniden planlandı.

## Açık işler

- Places taraması her gün TR 11:00'den sonra 30.11'e kadar, ardından `aktar_dijimagic.py`.
- **1 Aralık:** Cloud konsolunda `SearchTextRequest` günlük kotası yeniden **32**'ye alınır.
- `site_telefon` bazı sitelerde yanlış numara seçiyor (dentoran → 0244, drtolgakodaz → 0214).
- İlan veren firma listesi Owner'dan bekleniyor (`ilan_firmalari.py`).

## Kullanım

```bash
python3 kesif/tara_places.py                 # keşif (günlük kota bitince kendisi durur)
python3 kesif/aktar_dijimagic.py --kuru      # planı göster, hiçbir yere yazma
python3 kesif/aktar_dijimagic.py             # tabloya yaz + DijiMagic'e aktar + kuyruğa planla
```

## İlan veren firmalar (25.11.2026, Owner fikri)

Owner iş ilanı sitelerinden (Kariyer.net, İşin Olsun vb.) **elle** firma adı + pozisyon grubu toplar;
`ilan_firmalari.py` adı firmanın kendi sitesine ve kurumsal genel e-postaya çevirip **yalnız Scanner tablosuna** yazar.
Sektör sütunu `İlan: <Grup>` (Sosyal Medya / Web / Reklam). DijiMagic'e **aktarmaz, kuyruğa almaz**: seri ve metin Owner kararıdır.
İlan sitelerinden otomatik veri çekilmez (Kariyer.net bot korumalı, LinkedIn/Armut kullanım koşulları yasak).

```bash
# ilan_firmalari_girdi.txt: her satır  Firma adı ; Grup ; Şehir(isteğe bağlı)
python3 kesif/ilan_firmalari.py kesif/ilan_firmalari_girdi.txt --kuru   # tabloya yazmaz
python3 kesif/ilan_firmalari.py kesif/ilan_firmalari_girdi.txt          # Scanner'a yazar + geri okur
```

Güvenlikler: Places'ta bulunan firma adı girdiyle ≥%60 örtüşmezse yanlış firma sayılır (yazılmaz); her firma 1 Places isteği
(aylık sayaç tara_places ile ortak); tekrar denetimi tablo + DijiMagic kişileri + alan adı. Rapor durumları: EKLENDİ, ZATEN VAR, SİTE YOK, E-POSTA YOK.
Python 3.9 için `psycopg2-binary` kullanıcı düzeyinde kuruldu (25.11).
