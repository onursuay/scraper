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

## Güncel durum (24.11.2026 akşamı)

| Kalem | Değer |
|---|---|
| Kasım ayı Places isteği | 137 / 990 |
| Görülen place | 1.686 · biten sorgu 47 |
| Aday kaydı | 364 (kurumsal 188 · inceleme 7 · eski biçim 169) |
| DijiMagic'e aktarılan | 262 · kişi listesi 304 |
| Gönderilen | kuyruktan 24 (son 24.11 10:00) |
| **Gönderim** | 🔴 **DURDURULDU** (Owner 24.11: "mail gönderimini durdur, metinler değişmeli") |

**Durdurma nasıl yapıldı:** iki otomasyon (`DijiMagic Tanıtım Serisi`, `DijiMagic Sağlık Kuruluşları`)
`enabled = false`; ancak drip cron `enabled` alanına bakmadığı için bekleyen **296** kuyruk satırının
`scheduled_at` değeri `2099-01-01`e alındı. Asıl saatler `_gonderim_durdurma_yedegi_2026-11-24.json`
dosyasında (kuyruk kimliği → eski saat). Yeniden başlatma: yeni metinler onaylanır → otomasyon adımları
güncellenir → kuyruk yedekten geri yazılır ya da yeniden planlanır → iki otomasyon açılır → geri okunur.

**Bozuk ad onarımı (24.11):** `onar` eklenmeden önceki taramadan kalan 11 bozuk ad aday dosyasında,
6'sı DijiMagic kişilerinde, 5'i Scanner sekmesinde düzeltildi; üçünde de geri okumada kalan 0.

## Açık işler

- Places taraması her gün TR 11:00'den sonra 30.11'e kadar, ardından `aktar_dijimagic.py`.
- **1 Aralık:** Cloud konsolunda `SearchTextRequest` günlük kotası yeniden **32**'ye alınır.
- `site_telefon` bazı sitelerde yanlış numara seçiyor (dentoran → 0244, drtolgakodaz → 0214).
- Mail metinleri değişmeden gönderim açılmaz.

## Kullanım

```bash
python3 kesif/tara_places.py                 # keşif (günlük kota bitince kendisi durur)
python3 kesif/aktar_dijimagic.py --kuru      # planı göster, hiçbir yere yazma
python3 kesif/aktar_dijimagic.py             # tabloya yaz + DijiMagic'e aktar + kuyruğa planla
```
