# Live Portfolio OI/Funding Audit — DEVAM DOSYASI

> **YENİ SESSION İÇİN TALİMAT:** Bu klasörde çalışmaya başlamadan önce bu README'nin TAMAMINI oku. Sonra `SOURCE_AUDIT.md` ve `WORKSPACE_LOCK.md` dosyalarını oku. Kullanıcıdan geçmişi tekrar anlatmasını isteme. Aşağıdaki **GÜNCEL DURUM / SONRAKİ ADIM** bölümünden devam et.

## Amaç
Canlı Portfolio'ya sinyal yansıtan iki bağımsız sinyal ailesinde BTC Open Interest ve Funding bilgisinin zararları azaltan **nedensel veto** olarak işe yarayıp yaramadığını ölçmek. Başarılı/robust sonuç çıkarsa geliştirmek; başarısızsa yeni veto tanımları/özellikleri test ederek araştırmayı sürdürmek. Canlı sisteme kanıtsız değişiklik yapılmaz.

## Çalışma alanı kilidi
Bu araştırmanın bütün yeni kodu, raporu, cache tanımı, sonuç özeti ve deney kaydı yalnız:
`gpt/Live-Portfolio-OI-Funding-Audit/`

Başka GPT araştırma klasörlerine dosya yazma. Dış klasörleri yalnız kaynak olarak oku. Production dosyalarını araştırma sırasında değiştirme.

## Canlı referans / iki bağımsız üretici
1. **Legacy v11** — RETRIGGER / PRESSURE. BTC RED hard veto değil, kalite puanından 5 düşürür. Günlük legacy kotası 3.
2. **TSI_BB_FROZEN r1** — Legacy'den bağımsız sinyal ailesi. Kendi BTC TSI/BB + motion gate'i, coin 4H/15M koşulları, cooldown/pending ve bir tam 15M gecikmeli eligibility mantığı var. Günlük frozen kotası 6.
3. Portfolio tracker / position monitor sinyal üretmez; takip/pozisyon yönetimidir.
4. v12 orchestrator Frozen'ı önce yollar ve aynı taramada aynı sembol legacy ise çakışmayı bastırır. Bu, iki üreticinin bağımsız sinyal mantığını değiştirmez.

## Değiştirilmeyecek araştırma kuralları
- Önce production-parity baseline üret.
- OI/Funding baseline sinyal üretimini değiştirmez; yalnız sonradan causal veto olarak test edilir.
- OI/Funding yalnız sinyal zamanında veya öncesinde bilinen veriyle backward join edilir.
- Gelecek funding settlement kullanma.
- OI raw nominal yerine özellikle değişim, z-score ve trailing percentile ile incelenir.
- Development / validation / final holdout korunur. Final holdout eşik seçmek için kullanılmaz.
- RETRIGGER, PRESSURE, TSI_BB_FROZEN ve COMBINED_PORTFOLIO ayrı raporlanır.
- Yalnız win rate'e bakma: net P&L, expectancy, PF, max DD, sinyal/gün, blocked loss/win ve kaybedilen büyük winner'ları da ölç.

## Production-parity kritik ayrıntılar
- Legacy no-first-scan/watch state birebir korunmalı.
- Historical scan 15 dakikada bir ve yalnız kapanmış mumlarla yapılmalı.
- Legacy prefilter/top-N global sıralaması korunmalı.
- Frozen raw setup leadlag'de başarısız olsa bile cooldown tüketir.
- Frozen pending, BTC gate eligibility anında kapanmış olsa dahi geçerliliğini korur.
- Frozen kararından sonra bir tam 15M bar gecikmesi korunmalı.
- Frozen ve legacy günlük kotaları ayrıdır.
- Aynı-symbol/same-scan collision canlı v12 ile aynı uygulanmalı.
- Tarihsel 24h quote-volume mümkünse tarihsel mumlardan türetilmeli; bugünkü ticker ile geçmiş evren yaratmak limitation'dır.
- Çıkış simülasyonu eski sabit %2.5 trailing'e dönmemeli. Canlı payload kontratı ATR trailing `mult=0.6`, floor=entry, expiry=24h. Portfolio/position-monitor ayrıntıları mümkün olan en yakın production davranışıyla kilitlenmeli.
- Round-trip maliyetini production doğrulanmadan uydurma. Araştırma r2'deki %0.20 production Portfolio için otomatik varsayım değildir.

## Repo içindeki kaynaklar
- `SOURCE_AUDIT.md`: kaynak/fark denetimi.
- `WORKSPACE_LOCK.md`: klasör sınırı.
- `legacy_live_replay.py`: Legacy baseline replay üzerinde çalışılan dosya.
- `oi_funding_audit.py`: baseline sonuçlarına BTC OI/Funding'i causal backward-join edip veto ailelerini development/validation/final-holdout üzerinde ölçer.\n- `signal_system_champion.py`: araştırmada o ana kadar **kanıtlanmış en iyi sinyal/veto sistemi**. Production değildir. Başlangıçta baseline/no-veto olarak tutulur; yalnız validation + untouched final holdout ile robust iyileşme kanıtlanan değişiklikler buraya promote edilir.
- Eski `gpt/retrigger_high_guard_2026/retrigger_high_guard_2026.py` yalnız altyapı referansıdır. Canlı baseline değildir; RETRIGGER guard ve eski %2.5 trailing içeriyordu.
- Eski/iddia edilen `backtest_standalone_v5.py` dosyasına bağımlı olma.

## Ölçümler
Her veto için baseline n, blocked LOSS, blocked WIN, expired, net P&L delta, expectancy, PF, WR, max DD, signals/day, büyük winner kaybı ve setup-family kırılımı.

## GÜNCEL DURUM — HER SESSION BURAYI ESAS ALSIN
**Son güncelleme: 2026-09-21**

Tamamlanan somut işler:
- Çalışma klasörü oluşturuldu ve workspace kilidi yazıldı.
- Kaynak audit'i yazıldı.
- `oi_funding_audit.py` oluşturuldu.
- `legacy_live_replay.py` oluşturuldu. High-guard iskeletindeki RETRIGGER `near_high20_pct <= 1.0` ek kısıtı kaldırıldı ve ATR×0.6 trailing yönüne çevrildi.
- GitHub Actions workflow oluşturuldu: `.github/workflows/live_portfolio_oi_funding_audit.yml`.
- Legacy baseline run **gerçekten başlatıldı**.
- GitHub Actions run ID: **35623193985**
- Başlatıldığı anda durum: **in_progress**
- Test dönemi: **2026-01-01 → 2026-09-21**
- Bu run henüz sonuçlanmış kabul edilmez; yeni session önce run durumunu kontrol etmelidir.

## SONRAKİ ADIM — SIRAYI BOZMA
1. İlk iş run **35623193985** durumunu kontrol et.
2. Başarısızsa job logunu oku, hatayı düzelt ve aynı baseline'ı tekrar çalıştır. Hata çözülmeden performans yorumu yapma.
3. Başarılıysa artifact `live-legacy-baseline` içindeki `legacy_baseline.json` sonucunu incele; signal/trade sayıları ve diagnostikleri kaydet.
4. Legacy baseline doğrulanınca **Frozen r1 historical replay** motorunu aynı klasörde tamamla ve çalıştır. r2'yi production baseline sanma.
5. İki bağımsız akışı v12 orchestration/collision ve ayrı günlük kotalarla birleştir; COMBINED_PORTFOLIO baseline üret.
6. Baseline güvenilir hale geldikten sonra `oi_funding_audit.py` ile OI/Funding coverage kontrolü yap. Binance OI history retention dönemi yetmiyorsa sonucu zorlamadan archive/public alternatif kaynağa geç.
7. Veto taraması → validation → untouched final holdout. Robust iyileşme yoksa yeni causal özellik/kombinasyon dene; tek iyi in-sample sonucu başarı diye raporlama.
8. Her deneyden sonra README'yi güncelle. Sonuç KEEP ise kanıtlanmış değişikliği `signal_system_champion.py` dosyasına uygula ve version/reason bilgisini güncelle. REJECT ise champion PY'ı değiştirme; README deney günlüğüne reddedilen kuralı yaz.\n9. Kullanıcıya yalnız **somut sonuç, hata/engel veya karar gerektiren durum** olduğunda yaz.

## README GÜNCELLEME PROTOKOLÜ — ZORUNLU
Bu README statik belge değildir; araştırmanın **session handoff/state dosyasıdır**.

Her anlamlı işlemden sonra, session bitmeden veya kullanıcıya sonuç vermeden önce:
1. **GÜNCEL DURUM** bölümünü gerçek durumla güncelle.
2. Çalışan/sonlanan workflow run ID, status, artifact ve önemli commitleri yaz.
3. Elde edilen sayısal sonucu ve güvenilirlik/limitation'ı ekle.
4. Başarısız denemeyi silme; kısa biçimde **DENENDİ / SONUÇ / NEDEN RED** olarak kaydet ki sonraki session tekrar etmesin.
5. **SONRAKİ ADIM** bölümündeki ilk madde her zaman yeni session'ın yapacağı kesin ilk iş olsun.
6. Dosya adları veya mimari değişirse ilgili kaynak listesini güncelle.
7. Varsayımı gerçekmiş gibi yazma. Çalışmayan workflow'a “çalışıyor”, tamamlanmayan teste “sonuçlandı” deme.
8. README'yi başka klasöre kopyalama; tek authoritative handoff bu dosyadır.\n9. `signal_system_champion.py` yalnız daha iyi sonuç görüldüğü için güncellenmez; improvement validation + untouched final holdout'ta robust olmalı. Her promotion README'de eski/yeni metriklerle ve commit/run ile kayıtlı olmalı.\n10. Başarısız deneylerde de README güncellenir; fakat champion PY geriye gitmemesi için değiştirilmez.

## Araştırma günlüğü formatı
Yeni sonuç çıktığında aşağıya ekle; eski kayıtları silme:

### YYYY-MM-DD — <deney adı>
- Commit/run:
- Dönem/evren:
- Baseline:
- Değişiklik:
- Sonuç:
- Validation:
- Final holdout:
- Karar: KEEP / REJECT / INVESTIGATE
- Neden:
- Sonraki iş:

## Deney günlüğü
Henüz tamamlanmış performans deneyi yok.\n\n### 2026-09-21 — Champion dosyası başlatıldı\n- Commit: `e19811c6b0d8015a56899f54a8618f3b9aa2fabc`\n- Durum: BASELINE_NO_OI_FUNDING_VETO\n- Karar: INVESTIGATE\n- Neden: Henüz validation + final holdout ile kanıtlanmış OI/Funding iyileştirmesi yok; bu yüzden champion mevcut production-baseline sinyallerini veto etmeden geçiriyor.\n- Sonraki iş: aktif Legacy baseline run sonucunu al, ardından Frozen r1 ve combined baseline; sonra OI/Funding veto validation.