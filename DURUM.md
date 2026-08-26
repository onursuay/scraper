# Google Map Scanner — Durum (26.08.2026)

## Panel adresi

**https://scanner.onursuay.com** (ve `www.scanner.onursuay.com`)

Sertifika Let's Encrypt, 24 Kasım 2026'ya kadar geçerli, otomatik yenilenir.

🔑 **Giriş:** sistemde kayıtlı kullanıcı **yoktu**, ilk hesabı Owner "Kayıt Ol" ile
kendisi oluşturuyor (`onursuay@hotmail.com` + en az 8 karakter şifre). Şifreler
bcrypt ile hashlenir; mevcut bir şifre okunamaz, yalnız sıfırlanabilir.

## Nerede çalışıyor

| | |
|---|---|
| Sunucu | Hostinger VPS `72.62.146.159` (Ubuntu 24.04, 2 vCPU / 8 GB) |
| Dizin | `/opt/scanner` (sanal ortam: `/opt/scanner/.venv`) |
| Servis | `systemctl status scanner` · günlük: `/var/log/scanner.log` |
| Bağlanma | yalnız `127.0.0.1:5050`, önünde Caddy + TLS |
| Tablo | "Müşteri Datası" → **Scanner** sayfası |
| Kimlikler | `/opt/scanner/credentials/` (`sheets_sa.json`, `apify_token.json`, izin 600) |

Yeniden başlatmada servis kendiliğinden ayağa kalkar (`systemctl enable` yapıldı).

## Onarılan arızalar

| Arıza | Ham kanıt | Durum |
|---|---|---|
| Places API anahtarı ölü | `API_KEY_INVALID` | Apify Maps motoruyla değiştirildi ✅ |
| Sheets servis hesabı ölü | `Project #35027133269 has been deleted.` | `lead-crm-bot` anahtarına geçildi ✅ |
| Site yayında değil | `x-railway-fallback: true` | VPS'e taşındı ✅ |
| Panel şifresiz portla açıktı | `0.0.0.0:5050` dinliyordu | `127.0.0.1` + Caddy TLS ✅ |
| **Kayıt herkese açıktı** | `/register` kısıtsızdı | `KAYIT_IZINLI` izin listesi ✅ |

🔴 **Kayıt açığı:** panel internete açıldığı an adresi bulan herkes hesap açıp
taramaları çalıştırabilir, Apify kredisini harcayabilir ve lead veritabanını
görebilirdi. `.env` içindeki `KAYIT_IZINLI` listesinde olmayan e-posta artık **403**
alır. Test: yabancı adres 403, `onursuay@hotmail.com` geçti.

## Alan adı — nasıl bağlandı

cPanel'de alt alan adı açmak kaydı otomatik olarak **paylaşımlı hostinge**
(`94.199.206.125`, LiteSpeed) yönlendiriyor, VPS'e değil. `scanner` ve `www.scanner`
A kayıtları cPanel API ile `72.62.146.159`'a çevrildi, TTL 300'e düşürüldü.
Diğer kayıtlara ve ana siteye dokunulmadı.

⚠️ Eski kayıt 4 saatlik TTL ile yayıldığı için bazı çözümleyiciler bir süre eski
adresi verdi. Belirti: panel yerine **"Index of /"** ve altında
*"Proudly Served by LiteSpeed"*. Çözüm: DNS'i `1.1.1.1` yapmak ya da beklemek.
Sunucu tarafında yapılacak bir şey yok — `--resolve` ile VPS'e zorlandığında
panel `HTTP 200` ve doğru başlıkla geliyordu.

## "Az firma buluyor" sorununun kökü

Anahtar değil mimariydi:

1. Places Text Search **sorgu başına 60 sonuç** döndürür; kod 3 sorguyla tüm şehri tarıyordu.
2. `min_results` varsayılanı 20'ydi.
3. **Web sitesi olmayan işletme tamamen siliniyordu** — Ankara'da firmaların **%64'ü** bu grupta.
4. E-postada sahiplik denetimi yoktu → web tasarımcısının adresi lead sanılıyordu
   (`beniarayiniz@akinkaplan.com`, `info@naon.com`, `donate@opencart.com`).

Ayrıca sessiz bir hata: mükerrer kontrolü Domain'i **sabit F sütunundan** okuyordu;
yeni şemada Domain L sütununa kaydı. Artık sütun `SHEET_COLUMNS`'tan hesaplanıyor.

## Yeni akış

```
kesif/maps_apify.py           Apify Google Maps keşfi — ilçe yelpazeli, kümülatif bütçeli
kesif/_ilceler.json           il -> ilçe listesi önbelleği (OpenStreetMap admin_level=6)
kesif/_ilce_agirlik.json      ilçe başına ölçülen firma yoğunluğu (tarama sırasını belirler)
kesif/islem.py                işletme -> lead satırı (sahiplik denetimli e-posta seçimi)
kesif/eposta_zenginlestir.py  sahiplik kuralı + e-posta temizleme
kesif/eposta_dogrula.py       SMTP ile adres doğrulama (posta GÖNDERMEZ, RCPT sorgusu)
kesif/dogrulama_kosusu.py     doğrulamayı tabloya yazar
kesif/dogrulama_tekrar.py     zaman aşımına uğrayanları 35 sn + yedek MX ile yeniden dener
kesif/facebook_katmani.py     sitesiz firmalar için Facebook e-posta katmanı
kesif/facebook_kosusu.py      Facebook katmanını tabloya bağlar
kesif/temizlik.py             toplayıcı kaynaklı hatalı kayıtları onarır
kesif/tara_ankara.py          ilçe × anahtar kelime yelpazesi, bütçe muhafızlı
kesif/masaustu_cikti.py       Excel + CSV (tablodan üretir)
kesif/sema_tasi.py            tabloyu birleşik şemaya taşır
```

**Sahiplik kuralı:** bir adres yalnız (a) firmanın kendi alan adındaysa, (b) marka-komşu
alan adındaysa (`rabiaince.com` sitesi + `info@rabiaincebeauty.com`), ya da (c) ücretsiz
sağlayıcıysa lead sayılır. Diğerleri elenir ama `Elenen (üçüncü taraf)` sütununda kalır.

## Ölçülen rakamlar (Ankara güzellik sektörü)

- Kayıt başına maliyet: **0,0078 USD**
- Taranan: **545 işletme** (tamamı Apify ücretsiz kredisinden)
- Web sitesi olan: 195 (%36) · telefonu olan: 503
- Doğrulanmış e-posta: 63 · tahmin: 21 · yok: 461
  (94 tahminin 73'ü `info@instagram.com` tuzağıydı, temizlendi)

### SMTP doğrulaması

| Durum | Adet |
|---|---|
| ✅ geçerli — gönderilebilir | **36** |
| ❌ geçersiz — bounce ederdi | 14 |
| ⚠️ belirsiz — sunucu yanıt vermedi/kısıtladı | 34 |

İlk koşuda 84 adresin 78'i "bağlantı kurulamadı" verdi; sebep ağ değil koddu
(STARTTLS oturumu bozuyor, dıştaki `except` yutuyordu; ayrıca "MX yok → geçersiz"
sınıflandırması hatalıydı — RFC 5321 örtük MX gereği A kaydı da posta alabilir).
Düzeltilince geçerli 0 → 36.

## Panel geniş tarama yapabilir mi — evet

Panel ilk bağlandığında tek "Ankara" sorgusu atıyordu, sonuçlar merkeze yığılıyordu.
Artık ilin ilçeleri OSM'den alınıp tek tek taranıyor, sıra ölçülmüş yoğunluğa göre.

🔴 Bu değişiklikle bir para riski kapatıldı: `maxTotalChargeUsd` koşu başınaydı,
25 ilçelik yelpazede bütçe 25 katına çıkabilirdi. Artık hesabın gerçek harcaması
her ilçeden önce okunuyor, kalan bütçe bitince tarama duruyor.

Doğrulama (0,15 USD tavan): Çankaya 16 + Yenimahalle 5 = 21 kayıt, harcanan
0,1486 USD, tavanda durdu. Tarama bütçesi `.env` → `APIFY_BUTCE_USD=2.0`.

## Sitesiz firmalara ulaşma — kaynak karşılaştırması

| Kaynak | Sonuç | Kanıt |
|---|---|---|
| Instagram profil verisi | ❌ **e-posta alanı yok** | dönen alanlar yalnız `biography`, `businessCategoryName`… |
| Instagram biyografi metni | ⚠️ 6'da 1 (%17), o da İK adresiydi | ölçüldü |
| Instagram isimle hesap arama | ❌ güvenilmez | "Epiunic Lazer Epilasyon" → `eiunicorn_her`, `Nicu Piu` |
| **Facebook sayfası** | ✅ **8'de 7 gerçek e-posta (%88)** | ölçüldü |

**Facebook katmanı kuruldu**, iki aşamalı: arama ile sayfayı bul → sayfa tarayıcısıyla
e-postayı al. Üç güvenlik kilidi var:

1. **Eşleşme önce telefonla.** Aynı numara = kesin aynı işletme. İsim ikincil.
2. **İsim eşleşmesi sert.** İki tuzak ölçüldü: `Noa` ≈ `Nova`, ve daha sinsisi
   `Tunalı Güzellik` ≈ `Tunalı Lazer` — ortak olan tek şey **semt adı**. Artık
   ilçe/semt adları marka sayılmıyor; ayırt edici parça kısaysa isim tek başına
   kanıt kabul edilmiyor. Dolu e-posta asla ezilmiyor.
3. **Sektör süzgeci.** Facebook kategori araması hedefi tutturamıyor: "güzellik salonu
   Ankara" sorgusu emlakçı, anaokulu, oto aksesuar ve yayınevi döndürdü. Sayfanın kendi
   kategorisi süzülüyor (`Nail Salon`, `Health/beauty` geçer; `Real Estate Agent`,
   `Day Care` elenir). Test: 10/10 doğru.

⏳ Katman **henüz tabloya yazmadı** — kuru çalıştırma sırasında oturum kapandı, süreç
öldü. Harcanan 0,194 USD'lik veri Apify'da duruyor ve incelendi; sektör süzgeci de bu
veriden çıktı. Kredi yenilenince gerçek koşu yapılacak.

## Bekleyenler

| Konu | Kimde |
|---|---|
| **İlk hesabın açılması** — panelde "Kayıt Ol" | Owner |
| Story77 **MERSİS + ticaret unvanı** — Owner "eklemeyeceğiz" dedi, karar teyidi bekliyor (md.8/2 zorunlu; 2026 cezası ihlal başına 2.859–14.309 TL, toplu gönderimde on katına kadar) | Owner |
| Apify kredisi — 5 USD'nin 4,86'sı kullanıldı, **23 Eylül**'de yenilenir | Owner kararı |
| Facebook katmanının gerçek koşusu | kredi bekliyor |

## Hukuki çerçeve (özet)

- **6563 / Yönetmelik md.6/3:** tacir ve esnafa önceden onay gerekmiyor. Ayrım posta
  sağlayıcısına göre değil, **alıcının sıfatına** göre.
- **md.8/2:** iletide gönderenin **MERSİS numarası + ticaret unvanı** bulunmalı (Story77),
  marka adı (DijiMagic) ek olarak yazılabilir.
- **KVKK — asıl risk:** Kurul kararı **2022/861**, web'den toplanan iş e-postasına onaysız
  pazarlama için **150.000 TL** ceza. Belirleyici olan adresin bir **gerçek kişiyi
  belirlenebilir kılıp kılmadığı**. Düşük riskli: tüzel kişinin genel adresi
  (`info@firma.com.tr`) — 46 kayıt. Yüksek riskli: kişi adı taşıyan veya ücretsiz
  sağlayıcı adresi — 17 kayıt.
- Abonelikten çıkma bağlantısı ve aydınlatma metni zorunlu.

## Kullanım

```bash
ssh root@72.62.146.159
cd /opt/scanner
systemctl restart scanner                       # paneli yeniden başlat
.venv/bin/python kesif/tara_ankara.py           # toplu ilçe taraması
.venv/bin/python kesif/dogrulama_kosusu.py      # e-posta doğrulama
.venv/bin/python kesif/dogrulama_tekrar.py      # zaman aşımına uğrayanları yeniden dene
.venv/bin/python kesif/facebook_kosusu.py --kuru  # Facebook katmanı (önce kuru dene)
.venv/bin/python kesif/masaustu_cikti.py        # Excel + CSV
```
