# Causal Spot Long

Bu klasör, Binance Spot USDT evreninde **LONG** sistem araştırmasının bana ayrılmış tek çalışma alanıdır. Yeni araştırma, kod ve kanıt dosyaları yalnız burada oluşturulur. Eski `gpt/Multi-Timeframe-Independent-Evidence/` alanı geçmiş kanıt ve halen sonuçlanmakta olan eski workflow için korunur; silinmez ve yeni çalışma için değiştirilmez.

## Amaç ve değişmez sınırlar

- Mevcut yüksek kaliteli `tsi_bb_frozen_candidate_spot_audited_r2` korunur; kanıt olmadan değiştirilmez.
- Amaç r2'yi gevşetmek değil, **bağımsız fiyat-yolu ailelerini OR olarak** ekleyerek yaklaşık 2--3 gerçek sinyal/gün seviyesini araştırmaktır.
- Round-trip maliyet %0.20'dir.
- Başarı yalnız win rate değildir: sinyal/gün, aktif gün oranı, +3/+4/+5 target-first, -2/-2.5/-3 stop-first, expectancy, PF, MFE/MAE, yıl/coin dağılımı ve OOS birlikte geçmelidir.
- Holdout sonucuna bakarak kural seçilmez. Emir açılmaz; araştırma ve tarama yalnız sinyal üretir.

## Bu klasördeki kanonik dosyalar

| Konum | Rol |
| --- | --- |
| `baseline/r2_candidate_scanner.py` | R2 tarayıcısının salt-okunur referans kopyası. Araştırma kanıtı olmadan değiştirilmez. |
| `research/impulse_origin_retest.py` | Güncel, bağımsız neden-sonuç/impuls kökeni retest çalışması. |
| `research/independent_price_families_v2.py` | Price-path aile altyapısı. |
| `research/movement_family_discovery.py` | Hareket ailesi altyapısı. |
| `research/coin_mtf_causal_validation.py` | Ortak çoklu-zaman dilimi/doğrulama altyapısı. |
| `evidence/*.json` | Tamamlanmış önceki taramaların taşınmış özet kanıtları. |
| `output/` | Bu klasörde çalıştırılan workflow'ların kalıcı çıktı ve özetleri. |

## Devralınan kanıt

- Frozen r2, 2026 ALL'de yaklaşık 110 sinyal; mean24 +%3.98, win %92.7, PF 12.07, +3-before--2 %80: kalite referansıdır, frekans referansı değildir.
- `independent_price_families_v2_summary.json`: 62 kural, 695.463 event, 466 sembol; `NO_STABLE_INDEPENDENT_PRICE_FAMILIES`.
- `independent_relative_path_families_summary.json`: 60 kural, 552.597 event, 466 sembol; `NO_STABLE_RELATIVE_PATH_FAMILY`.
- Önceki movement expansion, clustering ve signature aile çalışmalarının hiçbiri r2 kalitesinde stabil 2--3/gün set üretmedi.

## Güncel durum — 2026-09-21 UTC

Taşınma sırasında eski çalışma alanında tamamlanan **`Causal Impulse Origin Retest`** GitHub Actions run **`35619941624`**, gerçek olarak `completed / success` durumundadır. Özet çıktı buraya `output/impulse_origin_retest/summary.json` olarak aktarıldı. Sonuç: 18 nedensel impuls-kökeni kuralı, 43.920 event ve 455 sembol taranmasına rağmen champion veya birleşik stabil set yoktur: `NO_STABLE_CAUSAL_IMPULSE_ORIGIN_RETEST`. Dolayısıyla r2'ye ekleme yapılmayacak.

Yeni workflow `.github/workflows/gpt-causal-spot-long-impulse-origin-retest.yml` yalnız `workflow_dispatch` ile tutulur. Bu, taşınma yüzünden aynı 64-shard taramayı iki kez çalıştırmamak içindir. Eski run tamamlandıktan sonra sonraki anlamlı değişiklik için bu yeni workflow üzerinden preflight → gerçek-veri smoke → full scan sırası izlenir.

Yeni aktif hipotez: **Causal Recovery Leadership**. Mekanizma, kapanmış BTC şoku sırasında BTC'ye göre daha az zayıflayan/önden güçlenen coinlerin, BTC düşüşü uzatmayı bıraktığında kendi 15M mikro-yapı kırılımını yapmasıdır. Bu, tek-coin breakout/pullback değil, coin--BTC tepki sırasını test eder; eski Price Families v2 eventleri çakışma koruması ile dışlanır. Workflow dosyası: `.github/workflows/gpt-causal-spot-long-recovery-leadership.yml`.

Bu çalışma GitHub Actions run **`35627163220`** ile gerçek olarak `completed / success` bitti. Preflight ve gerçek-veri smoke geçti; 18 kural, 7.131 event ve 440 sembol tarandı. Discovery + Calibration'da stabil champion bulunmadı: `NO_STABLE_CAUSAL_RECOVERY_LEADERSHIP`. R2'ye ekleme yapılmaz.

Yeni aktif hipotez: **Sell Climax Reclaim**. Kapanmış 1H yüksek-hacimli satış doruğundan sonra coin önce o mumun dibini korur, sonra 15M'de doruk mumun tepesini geri alır. Bu tek-coin akut satış emilimi yoludur; mevcut price-family eventleri çakışma koruması ile dışlanır.

Bu çalışma GitHub Actions run **`35635834726`** ile gerçek olarak `completed / success` bitti. Preflight ve gerçek-veri smoke geçti; 18 kural, 52.943 event ve 459 sembol tarandı. Discovery + Calibration'da stabil champion bulunmadı: `NO_STABLE_SELL_CLIMAX_RECLAIM`. R2'ye ekleme yapılmaz.

Yeni aktif hipotez: **Structural Acceptance Transition**. Kapanmış 1H yukarı displacement sonrası fiyat, impuls aralığının belirli üst bölümünü korur ve 15M'de yeni yapı kırılımıyla devamı teyit eder. Önceki Price Families v2 eventleri çakışma koruması ile dışlanır.

## Sıfır oturumdan devam protokolü (zorunlu)

1. Önce bu `README.md` dosyasını tamamen oku.
2. Bu bölümdeki aktif run kimliğinin **gerçek** durumunu GitHub Actions'tan sorgula; tahmin etme.
3. Run bittiyse belirtilen `summary.json` dosyasını oku. Başarısızsa job ve loglardan gerçek nedeni bul; aynı çalışmayı kurtar, sıfırdan ilgisiz araştırma başlatma.
4. Sonucu bu README'ye, `output/` altına ve gerekirse `evidence/` altına kaydetmeden yeni hipoteze geçme.
5. Yeni hipotez outcome-first ve gerçek fiyat yolu üzerinden türetilmeli; r2 koşullarını gevşeterek frekans artırma kabul edilmez.
6. Yeni uzun workflow'dan önce compile/path/dependency, artifact/schema/cohort, gerçek-veri smoke ve çıktı-boyutu kontrollerini çalıştır.
7. Bir aile ancak frekans + kalite + OOS birlikte geçerse adaydır. Ancak o zaman r2 ile OR eklemesine ve tarayıcı/GUI revizyonuna bakılır.
8. Her anlamlı durum değişiminde bu README'nin **Güncel durum** ve **Oturum günlüğü** bölümlerini güncelle. Bu dosya yaşayan teslim kaydıdır.

## Oturum günlüğü

| Tarih (UTC) | Durum | Yapılan | Sonraki somut adım |
| --- | --- | --- | --- |
| 2026-09-21 | Taşındı | Gerekli araştırma kaynakları ve iki önceki özet kanıt bu klasöre kopyalandı; yeni dispatch-only workflow eklendi. | Tamamlanan impuls retest çıktısını içeri aktar ve değerlendirme kaydını ekle. |
| 2026-09-21 | Elendi | Run `35619941624` gerçek olarak `completed/success`; 18 kural, 43.920 event, 455 sembol; stabil champion/birleşik set bulunmadı. | Yeni bağımsız outcome-first hipotezini, önceki ailelerle çakışma koruması altında tasarla. |
| 2026-09-21 | Başlatılıyor | Causal Recovery Leadership kodu derleme ve sentetik self-test geçti; gerçek-veri smoke GitHub preflight'ında zorunlu. | Preflight gerçek-veri smoke geçerse 64 shard tam tarama; değilse logla aynı çalışmayı düzelt. |
| 2026-09-21 | Elendi | Run `35627163220` completed/success; 18 kural, 7.131 event, 440 sembol; stabil champion yok. | Farklı bir bağımsız mekanizma tasarla; r2 ve önceki fiyat-yolu aileleriyle çakışma koruması zorunlu. |
| 2026-09-21 | Başlatılıyor | Sell Climax Reclaim: 1H satış doruğu → dip korunumu → 15M tepe geri alımı. | Derleme/self-test, gerçek-veri smoke, ardından 64-shard tarama. |
| 2026-09-21 | Elendi | Run `35635834726` completed/success; 18 kural, 52.943 event, 459 sembol; stabil champion yok. | Yeni mekanizma tek-coin dönüşü değil, arz-talep geçişi/çoklu-zaman yapısına dayandırılmalı. |
| 2026-09-21 | Başlatılıyor | Structural Acceptance Transition: 1H displacement → aralık kabulü → 15M devam kırılımı. | Preflight, gerçek-veri smoke, ardından 64-shard tarama. |

## Her güncellemede eklenecek kayıt şablonu

`Tarih (UTC) | Run/çalışma | Gerçek durum | Kullanılan cohort ve maliyet | Ana metrikler (frekans, kalite, OOS) | Karar | Bir sonraki adım`

Kayıt, "çalışıyor" veya "başarılı" gibi tahmin içermemeli: run kimliği, çıktı dosyası ya da log kanıtı belirtilmelidir.
