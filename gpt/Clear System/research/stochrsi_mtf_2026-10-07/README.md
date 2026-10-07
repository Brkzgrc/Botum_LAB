# StochRSI MTF v3 — bağımsız inceleme

Kaynak: kullanıcının 7 Ekim 2026'da yüklediği stochrsi_mtf(3).py. Orijinal kopya source/stochrsi_mtf.py altında; canlı dosya değiştirilmedi. Bu çalışma önceki RETRIGGER/D6 araştırmasından ayrı tutulur.

## Kapsam ve yürütme

Asıl hesapla() fonksiyonu, dip ve trend girişleri, piyasa genişliği ve BTC 4H RSI filtresi çalıştırılır. Başlangıç orijinal SIM_BASLA, değerlendirme sonu 2026-10-07 16:00 UTC = 19:00 Türkiye. Altı örnek: BTC, ETH, SOL, AVAX, SUI, ZEC. Tam evren performansı veya OOS değildir. Portföy/Telegram çağrıları engellenmiştir; emir/bildirim üretilmez. evren_kurallari.py yüklenmediği için import yerine boş araştırma shim'i vardır; evren() çağrılmaz ve üretim evreninin dışlama kuralları doğrulanmış sayılmaz.

Yerel çalışma bütçesi 420 saniye; request timeout 12 saniye; piyasa genişliği sekiz, strateji altı veri işçisi. GitHub Actions açılmadı. Veri boşlukları/tekrarlar/geçersiz OHLC reddedilir ve atlamalar summary.json içinde belirtilir. Veri ağ hatası olursa kör tekrar yoktur.

## Kanıtlanmış kod bulguları

1. Stop ve gösterge çıkışı aynı saatlik mumdaysa _cikis() stop denetimini atlıyor: `t1[j] >= cik[0]` durumunda break. Sentetik örnekte giriş 100, low 94, gösterge satışı 101; sonuç +%0,80. Muhafazakâr stop-first halinde -%5,19 olur. Gerçek mum içi sıra 1M/işlem verisiyle doğrulanmalıdır. _cikis_trend() aynı eşit-zaman davranışına sahiptir.
2. t5 (+%5 koruma aktivasyonu) stop kararı verilmeden önce gelecekteki yol üzerinde bulunur. Stop sonradan daha erkene çekilse bile t5 temizlenmez. Sentetik örnekte 02:00 stop ve 03:00 koruma aktivasyonu birlikte döner. _bildir() bu geçersiz aktivasyonu bildirebilir.
3. _canli() kapalı 1H mumlarını birleştirerek henüz kapanmamış 4H/1D mumunu oluşturur; MACD filtreleri bu kısmi mumdan hesaplanır. Bu, o anda bilinen geçmişle oluşturulduğundan tek başına geleceğe bakma değildir; ancak tamamen kapanmış çoklu-zaman-dilimi protokolüne uymaz ve tam mum kapanışına dek değişebilir.
4. Aynı anda tek pozisyon coin başınadır. Tüm portföy için tek pozisyon sınırı yoktur. Toplam işlem yüzdeleri portföy getirisi sayılamaz.
5. Dakika stoplarının kapanışları gonderildi durumuna yazılıyor; fakat sonraki saatlik turun deterministik hesapla() replay'i bu dakika kapanışlarını alım/çıkış geçmişine katmıyor. ACIK yeniden kurulurken zaten dakika-kapanmış pozisyon tekrar açık listesine girebilir; yeniden giriş zamanları/panel durumu ayrışabilir. Bu bulgu kod akışı incelemesidir, canlı ortamda reproduksiyon yapılmadı.
6. Kod veri setinde hacmi tutmuyor; girişte hacim/taker hareket onayı yok. StochRSI kesişimleri, MACD/RSI zayıflaması ve günlük kırılım gibi hareket öğeleri mevcut fakat çok sayıda statik eşik de var. Özellikle mutlak MACD histogram <0.05 farklı fiyat ölçeklerinde farklı anlama gelir; normalleştirilmiş teyitle karşılaştırma adaydır, henüz sonuç yok.
7. Alım POST başarısız olsa da Telegram gönderiliyor; kapanış POST 404 başarılı sayılıyor. Bunun doğru olup olmadığı panel API sözleşmesine bağlıdır. evren_kurallari.py ve panel kodu olmadan entegrasyon doğrulaması tamamlanamaz.
8. Başa baş çıkış komisyonla yaklaşık -%0,1998'dir. Dip stop yaklaşık -%5,1898; trend stop yaklaşık -%10,1798'dir. Sabit stop fiyatında dolum varsayılır; gap/slippage modellenmez.

## Karar

Önce teknik çıkış sırası, t5 zamanının gerçek pozisyon ömrüyle uyumu ve dakika/saatlik state parity düzeltilip test edilmeden performans canlıya birebir taşınmış sayılmaz. Kullanıcının çalışan dosyası değiştirilmez. Sonraki adım evren_kurallari.py ve panel kapanış sözleşmesini alarak tam akış doğrulaması; ardından orijinal ve nedensel düzeltilmiş replay karşılaştırmasıdır.

## Kullanıcının netleştirdiği hedef ve ekran kanıtı

7 Ekim: Amaç çalışan StochRSI MTF sisteminin çıkışını düzeltmek; +%5 sonrası alış fiyatına geri verme ve maliyet nedeniyle zarar kapanışı azaltılacak. Görselde yaklaşık +%7,64 ve +%11,70 peak sonrası -%0,20 başa-baş kapanış örnekleri görülüyor. Peak sütununun gerçek çıkış sonrası güncellenip güncellenmediği panel kodu/JSON olmadan kanıtlanamaz; mum yoluyla ayrıca doğrulanmalı.

Önceden seçilmiş tanısal karşılaştırma: orijinal koruma+stop-first, sabit brüt TP5, +%5 sonrası net +%0,10 maliyet tabanı, net +%2 kilit, +%5/7/10 sonrası net +%2/4/6 kademe, +%5 sonrası tepeye göre %3 trailing ve net +%2 taban. Aynı orijinal dip girişleri kullanılır; alternatif çıkışlar yeni giriş üretmez. Bu bir portföy simülasyonu veya OOS değildir. Bir mumun yüksek fiyatından türetilen yeni stop yalnız sonraki mumda aktif; stop-first ve gap açılışında daha kötü fiyat kullanılır. Hiç +%5 görmeyen kayıplar ayrıca korunmasız kayıp sayılır. Saatlik test olumlu olursa sonraki adım 1M/5M gerçek yol ve portföy snapshot JSON ile aynı kayıtları doğrulamak, dakika/saatlik state tutarlılığını düzeltmektir.

## 7 Ekim 2026 — yeni görev: çıkış stratejisi

StochRSI MTF girişleri sabit tutulacak. Amaç komisyon dahil kayıp sayısı/büyüklüğünü azaltırken toplam net getiriyi korumak veya artırmak. Başa başa taşıma nihai çözüm sayılmayacak; sabit hedef, maliyet dahil kâr kilidi, kademeli çıkış, ATR, momentum/osilatör ve hareket bozulması aileleri karşılaştırılacak. Üretim/portföy sistemine değişiklik veya emir/bildirim gönderilmedi.

Genişletilmiş tanısal örnek: BTC, ETH, SOL, AVAX, SUI, ZEC, MIRA, LUMIA, TST; 2026-01-01–2026-10-07 16:00 UTC. 74 coinlik piyasa genişliği verisi tamamlandı. Dip girişleri: 60, kapanan: 59, açık: 1. Orijinal dip kapanışlarının aritmetik toplamı +296,72 yüzde puan, 31 kayıp, PF 3,905. Bu toplam portföy getirisi değildir ve birkaç büyük kazananın etkisi yüksektir.

| Çıkış | Net toplam, yüzde puan | Kayıp | PF |
|---|---:|---:|---:|
| Orijinal, stop-first | 296,72 | 31 | 3,905 |
| Sabit brüt TP %5 | 49,51 | 22 | 1,493 |
| +%5 sonrası net +%0,10 taban | 292,03 | 22 | 3,910 |
| Net +%2 kilit | 218,50 | 22 | 3,177 |
| %5/7/10 kademesi | 232,55 | 22 | 3,318 |
| %3 trailing + net %2 taban | 83,12 | 22 | 1,828 |
| ATR2 + maliyet tabanı | 67,87 | 22 | 1,676 |
| ATR3 + maliyet tabanı | 73,06 | 22 | 1,728 |
| İki saat momentum bozulması | 64,28 | 22 | 1,641 |
| %5'te yarısını çıkar | 170,77 | 22 | 2,702 |

İlk altı politika ilk altı coin sonucundan önce seçildi; son dört aile sonuçlar görüldükten sonra eklendi. Hiçbiri untouched OOS değildir. Aynı orijinal girişler kullanıldı; alternatif çıkışların yaratacağı yeniden girişler modellenmedi. Yeni stop sonraki saatlik mumda aktif; stop-first ve gap açılışı dikkate alındı. Saatlik veri mum içi sıralamayı kanıtlamaz. %0,10 maliyet tabanı 9 kaybı kaldırırken toplamdan 4,69 yüzde puan azaltıyor; bu yalnız aday kanıttır. Sıkı kilit/trailing/ATR bu örnekte büyük kazananları kesiyor. Hiç %5 görmeyen 22 kayıp ayrı araştırılmalı.

Özgün kaynak audit'i 88 toplam sinyal, 83 kapanış, 5 açık, 56 aktif gün, yaklaşık 0,315 sinyal/gün buldu. Dip ve trend ayrıdır; trendde +%5 koruması yoktur. Kaynak audit'indeki geçersiz t5 sonrası-çıkış kaydı 10'dur. Veriler ve ayrıntılar summary.json/exit_comparison.json içindedir. Canlı panel verisi olmadan ekrandaki diğer stratejiler bu sonuçlarla birleştirilemez.

5M odak testi requests ReadTimeout nedeniyle tamamlanmadı; sonuç uydurulmadı ve tam tarama yeniden başlatılmadı. focus_5m.py şimdilik yalnız ilk altı politikayı uygulayabilir. Sonraki somut adım: 3 ekran örneğinin sınırlı 5M yolunu önbellek/timeout ile doğrula; t5 zamanı, stop-first ve dakika-saatlik kalıcı durum testlerini kur; ardından girişleri sabit tutarak önceden dondurulmuş çıkış ailelerini bağımsız dönem ve tam portföy replay'inde sınayıp yeniden giriş etkisini ölç. Kod ve veri erişimi yoksa durumu açıkça belirt. GitHub Actions başlatılmadı; bu çalışma yereldir. Yeni araştırma görev metni mevcut duraklatılmış göreve uygulanacak; saat/durum korunacak.


# Clear System — güncel StochRSI MTF çıkış araştırması

## 7 Ekim 2026 — StochRSI MTF çıkış araştırması (local-20261007-state-structure)

**Güncel amaç önceki r2/OR giriş araştırmasının yerini alır:** Kullanıcının yüklediği StochRSI MTF v3 girişlerini koruyarak kayıpları azaltan ve toplam maliyet-sonrası kazancı koruyan yeni çıkış stratejisi geliştirmek. Ayrıntılar ve birebir kaynak kopyası `research/stochrsi_mtf_2026-10-07/` altındadır. Önceki r2 ve RETRIGGER sonuçları tarihçe olarak korunur; bunların dönem/terfi kuralları bu yeni dosyanın sonuçlarına uygulanmış sayılmaz. `Clear System.py` ve canlı sistem değiştirilmedi.

Gerçek kaynak kontrolü: Son Clear System run **36340098433** preflight `completed/success`; son pahalı araştırma **36339721807** D6 `completed/success`, bilimsel olarak elenmiş. GitHub Actions in_progress ve queued listeleri bu turda boştu. Yeni workflow başlatılmadı, yeni runner maliyeti **0 dakika**. Yeni araştırma yalnız yerel/önbellekli çalıştı.

Veri: **2026-01-01–2026-10-07 16:00 UTC**, dokuz sabit Spot USDT örneği (BTC, ETH, SOL, AVAX, SUI, ZEC, MIRA, LUMIA, TST); stable/fiat/leveraged base yok. Tam tarihsel evren değildir; üretim evren_kurallari.py bağımlılığı elde değil. Piyasa genişliği 74 sembolün önceki önbelleğinden birebir korunuyor. Bu görülen 2026 örnekleri artık **exploratory**; OOS olarak sunulamaz. Yeni adayların geleceğe dönük dokunulmamış doğrulaması en erken **8 Ekim 2026** başlangıçlı, sonuç görülmeden dondurulmuş protokolle yapılmalıdır.

Referans dip: 60 giriş / 59 kapanış / 1 açık; **0,2145 sinyal/gün**, aktif gün **38/279,667 = %13,59**. Net toplam **+296,72 yüzde puan**, expectancy **+%5,029**, PF **3,905**; 28 pozitif / 31 negatif, negatif toplam **-102,143 yüzde puan**, en kötü **-%5,190**. Bu aritmetik toplam portföy getirisi değildir. Trend ayrı: 28 giriş, 24 kapanış / 4 açık, 19 negatif; net **-29,510 yüzde puan**, expectancy **-%1,230**, PF **0,773**. Trend exit araştırması henüz yapılmadı.

Maliyet her bacak %0,10; net formül `exit*0.999/(entry*1.001)-1`, yaklaşık %0,20 round-trip. Gap açılışında daha kötü dolum kullanıldı; spread/slippage yok. 1H stop-first muhafazakâr varsayımdır; intrabar gerçek sıra kanıtlanmadı.

Yeni tanı, çıkış saatinin ekstremumlarını 'kesin çıkış-öncesi' saymadan hesaplandı:

| Kayıp kolu | Adet | Negatif toplam (yüzde puan) | Çıkış mumundan önce ortalama MFE alt sınırı |
|---|---:|---:|---:|
| +%5 sonrası alış fiyatına geri veren | 9 | -1,798 | +%16,070 |
| +%5 koruması oluşmayan | 22 | -100,345 | +%1,197 |

**Kayıp büyüklüğünün %98,24'ü ikinci kolda.** Bu 22 kaybın 16'sında çıkıştan önce pozitif saatlik kapanış, 13'ünde her iki komisyonu karşılayan saatlik kapanış var. Yalnız +%5 korumasını değiştirmek kayıp sayısını düzeltebilir, esas zarar büyüklüğünü çözmez. Üç büyük kazanan pozitif toplamın **%66,80**'ini oluşturuyor; agresif çıkışları değerlendirirken bu yoğunlaşma gözetilmeli. MAE/MFE işlem bazında `state_and_loss_audit.json` içindedir; stop mumunun gerçek intrabar MAE'si 1H veriden kesinlenemez.

Gerçek kaynak üzerinde, ağ/portföy/Telegram ve disk durum yazımı stub'lanmış test **dakika-saatlik state ayrışmasını reproduksiyonla doğruladı**: `dakika_kontrol()` bir pozisyonu kapatıp kalıcı `satis=True` yapıyor, `tur()` aynı anahtarı tekrar ACIK'e alıyor. Bu kontrollü testtir; canlıda oluşmuş bir olay diye sunulmaz. Aynı-mum stop/gösterge önceliği ve çıkıştan sonra kalan t5 sentetik kaynak testleri de duruyor; 59 dip kayıtta 10 geçersiz gelecekte t5 var. Bunlar P&L'i güvenilir ölçmek için araştırma motoru/kalıcı kapanış günlüğü düzeyinde giderilmelidir.

Bağımsız yapısal çıkış ailesi bir kez kilitlendi: maliyeti karşılayan toparlanıştan sonra yalnız üç kapanmış 1H mumla doğrulanan dip desteği; bu desteğin altında iki ardışık kapanış oluşursa ikinci kapanışta çıkış. Stop önce uygulanır, +%5 koruma sonraki mumda aktif olur. Eşik taraması yok; yalnız 'yapı' ve 'yapı + maliyet tabanı' ablation'ı var. İlk üç kontrol: Python derleme, sentetik/numpy-JSON self-test, AST/ağ-yasağı/kapalı-mum sıra denetimi; ardından gerçek önbellekli dokuz coin replay'i. Ön kayıt JSON'u sonuç hesaplanmadan yazıldı fakat aile önceki tanıdan sonra seçildiği için bu **OOS değildir**.

| Varyant | Net toplam (yüzde puan) | Expectancy | PF | Kayıp | Negatif toplam |
|---|---:|---:|---:|---:|---:|
| Yalnız yapısal çıkış | +71,494 | +%1,212 | 1,987 | 33 | -72,449 |
| Yapı + maliyet tabanı | +72,993 | +%1,237 | 2,022 | 28 | -71,450 |

Her iki varyantta 59 kapanış / 1 açık, 28 yapı çıkışı; en kötü yaklaşık -%5,190. Negatif tutar azalırken toplam kazanç ağır bozuldu; kayıp sayısı kabul kapısını geçmedi. Karar **REJECT_FIXED_COHORT_SCREEN_NO_RESCAN**. Aynı yapı/eşik ailesi yeniden adlandırılıp taranmayacak; bağımsız doğrulamaya veya final dosyaya aktarılmadı. Target-first/stop-first kesin intrabar oranı **N/A**; mevcut dip hedefi sabit hedef değildir. Yeni OOS **N/A**.

5M odak kontrolü: üç kaynak yolundan üçü de `data-api.binance.vision` bağlantısında **ReadTimeout** verdi. Compile + dört self-test + statik bütçe/nedensellik kontrolü geçti, fakat gerçek-veri smoke geçmedi: **INCOMPLETE_DO_NOT_PROMOTE**, eksik yol **3/3**, kapsama doğrulanamadı. 180 sn genel / 195 sn komut tavanı, path başına en çok üç istek; bu turda yalnız üç istek ve 5,012 sn çalışma oldu. Aynı koşuyu kör yeniden çalıştırma yok. Hata artifact'ları `focus_checked.json/.log` altında korunuyor. Yapı replay'inde çıkan numpy.int64 JSON hatası özel serializer + dört self-test ile düzeltildi, ilk hata logu da korundu; yeni piyasa isteği gerektirmeyen önbellek replay'i yaklaşık 0,932 sn hesapla tamamlandı.

**Sonraki somut adım:** kapanmış pozisyonların fiyat/zaman/nedenini taşıyan kalıcı günlük ile dakika/saatlik/state replay eşitliğini araştırma kopyasında kur; aynı-mum stop-first ve t5 sırasını düzeltip mevcut dokuz coin referansını yeniden üret. Tek başına ACIK filtresi yeniden giriş eşitliğini kanıtlamaz. Ardından +%5 görmeyen kol için farklı bir hareket/katılım çıkışı gerekçelendir; elenen iki saatlik momentum veya destek-kırılması eşiklerini yeni adla tekrarlama. Veri bağlantısı gerçek küçük smoke ile çalışmadan tam 5M/evren taraması başlatma. Başarılı aday dondurulduğunda bağımsız coin/dönem ve gerçek yeniden giriş/eşzamanlı portföy replay'i zorunludur.


---

