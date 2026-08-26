# Google Map Scanner — Durum (26.08.2026)

## Nerede çalışıyor

| | |
|---|---|
| Sunucu | Hostinger VPS `72.62.146.159` (Ubuntu 24.04, 2 vCPU / 8 GB) |
| Dizin | `/opt/scanner` (sanal ortam: `/opt/scanner/.venv`) |
| Servis | `systemctl status scanner` · günlük: `/var/log/scanner.log` |
| Bağlanma | yalnız `127.0.0.1:5050`, önünde Caddy + Let's Encrypt |
| Tablo | "Müşteri Datası" → **Scanner** sayfası |
| Kimlikler | `/opt/scanner/credentials/` (`sheets_sa.json`, `apify_token.json`, izin 600) |

Yeniden başlatmada servis kendiliğinden ayağa kalkar (`systemctl enable` yapıldı).

## Onarılan arızalar

Üçü birbirinden bağımsız, ikisi sessizce ölmüştü:

| Arıza | Ham kanıt | Durum |
|---|---|---|
| Places API anahtarı ölü | `API_KEY_INVALID` | Apify Maps motoruyla değiştirildi ✅ |
| Sheets servis hesabı ölü | `Project #35027133269 has been deleted.` | `lead-crm-bot` anahtarına geçildi ✅ |
| Site yayında değil | `x-railway-fallback: true` | VPS'e taşındı ✅ |
| Panel şifresiz portla açıktı | `0.0.0.0:5050` dinliyordu | `127.0.0.1` + Caddy TLS ✅ |

## "Az firma buluyor" sorununun kökü

Anahtar değil mimariydi:

1. Places Text Search **sorgu başına 60 sonuç** döndürür; kod 3 sorguyla tüm şehri tarıyordu.
2. `min_results` varsayılanı 20'ydi.
3. **Web sitesi olmayan işletme tamamen siliniyordu** — Ankara taramasında firmaların **%64'ü** bu gruptaydı.
4. E-postada sahiplik denetimi yoktu → web tasarımcısının adresi lead sanılıyordu
   (ölçülen vakalar: `beniarayiniz@akinkaplan.com`, `info@naon.com`, `donate@opencart.com`).

Ayrıca sessiz bir hata: mükerrer kontrolü Domain'i **sabit F sütunundan** okuyordu; yeni şemada
Domain L sütununa kaydı. Artık sütun numarası `SHEET_COLUMNS`'tan hesaplanıyor, telefon da anahtar.

## Yeni akış

```
kesif/maps_apify.py           Apify Google Maps keşfi — ilçe yelpazeli, kümülatif bütçeli
kesif/_ilceler.json           il -> ilçe listesi önbelleği (OpenStreetMap admin_level=6)
kesif/_ilce_agirlik.json      ilçe başına ölçülen firma yoğunluğu (tarama sırasını belirler)
kesif/islem.py                işletme -> lead satırı (sahiplik denetimli e-posta seçimi)
kesif/eposta_zenginlestir.py  sahiplik kuralı + e-posta temizleme
kesif/eposta_dogrula.py       SMTP ile adres doğrulama (posta GÖNDERMEZ, RCPT sorgusu)
kesif/tara_ankara.py          ilçe × anahtar kelime yelpazesi, bütçe muhafızlı
kesif/disa_aktar.py           Excel + CSV çıktısı
kesif/sema_tasi.py            tabloyu birleşik şemaya taşır
```

**Sahiplik kuralı:** bir adres yalnız (a) firmanın kendi alan adındaysa, (b) marka-komşu alan
adındaysa (`rabiaince.com` sitesi + `info@rabiaincebeauty.com`), ya da (c) ücretsiz sağlayıcıysa
lead sayılır. Diğerleri elenir ama `Elenen (üçüncü taraf)` sütununda görünür kalır.

## Ölçülen rakamlar (Ankara güzellik sektörü)

- Kayıt başına maliyet: **0,0078 USD** (pilot ve Çankaya koşusunda birebir aynı)
- Taranan: **545 işletme** / 4,47 USD (tamamı Apify ücretsiz kredisinden)
- Web sitesi olan: 195 (%36) · telefonu olan: 503
- Doğrulanmış e-posta: 63 · tahmin: 21 · yok: 461
  (94 tahminin 73'ü `info@instagram.com` tuzağıydı, temizlendi)

### SMTP doğrulaması (adres gerçekten var mı)

| Durum | Adet |
|---|---|
| ✅ geçerli — gönderilebilir | **36** |
| ❌ geçersiz — bounce ederdi, çıkarılmalı | 14 |
| ⚠️ belirsiz — sunucu yanıt vermedi/kısıtladı | 34 |

## Kaynak karşılaştırması — sitesiz firmalara nasıl ulaşılır

Firmaların %64'ünün sitesi yok. Bu grup için e-posta kaynağı arandı:

| Kaynak | Sonuç | Kanıt |
|---|---|---|
| Instagram profil verisi | ❌ **e-posta alanı yok** | dönen alanlar yalnız `biography`, `businessCategoryName`, `isBusinessAccount`… |
| Instagram biyografi metni | ⚠️ 6'da 1 (%17), çıkan adres İK adresiydi | ölçüldü |
| Instagram isimle hesap arama | ❌ güvenilmez | "Epiunic Lazer Epilasyon" → `eiunicorn_her`, `Nicu Piu` |
| **Facebook sayfası** | ✅ **4'te 3 gerçek e-posta** | `bilgi@drderm.com.tr`, `destek@esmerlife.com.tr`, `info@showlazer.com` |
| **Facebook kategori+konum araması** | ✅ sayfaları gerçekten buluyor | 8 sonuç, 7'si erişilebilir |

**Sonuç:** sitesiz firmalar için doğru yol Instagram değil **Facebook**; iki aşamalı
(arama ile sayfayı bul → sayfa tarayıcısıyla e-postayı al). Henüz kurulmadı.

## Panel geniş tarama yapabilir mi — evet

Panel ilk bağlandığında tek "Ankara" sorgusu atıyordu; sonuçlar merkeze yığılıyordu.
Artık ilin ilçeleri OSM'den alınıp tek tek taranıyor, sıra ölçülmüş yoğunluğa göre.

🔴 Bu değişiklikle birlikte bir para riski kapatıldı: `maxTotalChargeUsd` koşu
başınaydı, 25 ilçelik yelpazede bütçe 25 katına çıkabilirdi. Artık hesabın gerçek
harcaması her ilçeden önce okunuyor, kalan bütçe bitince tarama duruyor.

Doğrulama koşusu (0,15 USD tavan): Çankaya 16 + Yenimahalle 5 = 21 kayıt,
harcanan 0,1486 USD, tavanda durdu.

Tarama bütçesi `.env` içinde `APIFY_BUTCE_USD=2.0` (yaklaşık 250 firma/tarama).

## Bekleyenler

| Konu | Kimde |
|---|---|
| **DNS kaydı** — `A  scanner  72.62.146.159` (dijimagic.com bölgesi, Turhost) | Owner |
| Story77 **MERSİS + ticaret unvanı** — Owner "eklemeyeceğiz" dedi, karar teyidi bekliyor (md.8/2 zorunlu; 2026 cezası ihlal başına 2.859–14.309 TL, toplu gönderimde on katına kadar) | Owner |
| Apify kredisi (5 USD'nin 4,47'si kullanıldı, **23 Eylül**'de yenilenir) | Owner kararı |
| Facebook katmanının kurulması | onay bekliyor |

⚠️ **Neden DNS gerekiyor:** sunucunun kendi adı `srv1622864.hstgr.cloud` Türkiye'den
erişilemiyor — istek `88.255.216.16/landpage` adresine, yani Türk Telekom'un engelleme
sayfasına düşüyor. Sunucu doğru çalışıyor (kendi üzerinden `HTTP 200`, geçerli sertifika),
kesilen şey erişim yolu.

## Hukuki çerçeve (özet)

- **6563 / Yönetmelik md.6/3:** tacir ve esnafa önceden onay gerekmiyor. Ayrım posta
  sağlayıcısına göre değil, **alıcının sıfatına** göre.
- **md.8/2:** iletide gönderenin **MERSİS numarası + ticaret unvanı** bulunmalı (Story77),
  marka adı (DijiMagic) ek olarak yazılabilir.
- **KVKK — asıl risk:** Kurul kararı **2022/861**, web'den toplanan iş e-postasına onaysız
  pazarlama için **150.000 TL** ceza. Belirleyici olan adresin bir **gerçek kişiyi
  belirlenebilir kılıp kılmadığı**. Düşük riskli grup: tüzel kişinin genel adresi
  (`info@firma.com.tr`) — listede 46 kayıt. Yüksek riskli: kişi adı taşıyan veya ücretsiz
  sağlayıcı adresi — 17 kayıt.
- Abonelikten çıkma bağlantısı ve aydınlatma metni zorunlu.

## Kullanım

```bash
ssh root@72.62.146.159
cd /opt/scanner
systemctl restart scanner                    # paneli yeniden başlat
.venv/bin/python kesif/tara_ankara.py        # toplu ilçe taraması
.venv/bin/python kesif/dogrulama_kosusu.py   # e-posta doğrulama
```
