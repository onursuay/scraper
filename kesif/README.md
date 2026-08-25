# Keşif Motoru (yeni) — müşteri bulma tarafının yeniden kurulumu

Mevcut `scraper/maps_scraper.py` (Google Places API) motorunun yerine geçer.
Eskisi silinmedi; bu klasör bağımsız çalışır.

## Neden değişti — ölçülen arızalar

| # | Arıza | Kanıt |
|---|---|---|
| 1 | Places API anahtarı ölü | `REQUEST_DENIED · "The provided API key is invalid."` (eski uç) ve `API_KEY_INVALID` (places.googleapis.com) — 25.08.2026 |
| 2 | Text Search sorgu başına **60 sonuç** döndürür | `maps_scraper.py` 3 sorgu varyantı kullanıyor → tüm şehir için tavan ~60 işletme |
| 3 | `min_results` varsayılanı 20 | Tarama 20'de duruyor |
| 4 | Web sitesi olmayan işletme **tamamen siliniyor** | `main.py`: `if not website: continue` — güzellik sektöründe firmaların ~%50'si yalnız Instagram kullanıyor (ölçüldü: 20 firmanın 10'u) |
| 5 | E-postada **sahiplik denetimi yok** | Sitedeki ilk kurumsal adres alınıyor → web tasarımcısının adresi lead sanılıyor (ölçüldü: `beniarayiniz@akinkaplan.com`, `info@naon.com`) |

## Yeni mimari

1. **`apify_maps.py` — keşif.** Apify Google Maps aktörü (`lukaskrivka~google-maps-with-contact-details`).
   60 sonuç tavanı yok. İlçe × anahtar kelime yelpazesiyle çağrılır.
   Bütçe her koşuda `maxTotalChargeUsd` ile donanımsal olarak sınırlanır.
2. **`tara_ankara.py` — yelpaze.** İlçe listesi + ticari yoğunluğa göre kota.
   Her koşudan önce hesabın **gerçek** harcamasını okur, tavanı aşarsa durur.
3. **`eposta_zenginlestir.py` — sahiplik denetimli e-posta.**
   Bir adres yalnız şu iki durumda lead sayılır:
   - alan adı işletmenin **kendi** sitesinin alan adıyla aynı → `kurumsal`
   - ücretsiz sağlayıcı (gmail/hotmail/yandex…) → `kişisel` (bu sektörde yaygın ve geçerli)
   Diğer her adres **üçüncü taraf** sayılıp elenir, ama `elenen_ucuncu_taraf`
   sütununda görünür kalır (denetlenebilirlik).
4. **`disa_aktar.py` — çıktı.** Excel + CSV. Web sitesi olmayan işletmeler
   **silinmez**; telefon ve Instagram bilgisiyle listede kalır.

## Ölçülen birim maliyet

Kayıt başına **0,0078 USD** (pilot 20 kayıt = 0,155 USD; Çankaya 90 kayıt = 0,706 USD).
Apify hesabı FREE planda ve aylık 5 USD kredi ücretsiz geliyor → dönem başına ~600 kayıt bedelsiz.

## Kullanım

```bash
python3 kesif/tara_ankara.py     # keşif (arka planda çalıştırın, ilçe başına 1-3 dk)
python3 kesif/disa_aktar.py      # zenginleştirme + Excel/CSV
```
