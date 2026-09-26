# PRESSURE / RETRIGGER / TSI-BB — hareket onayı araştırması

## Kaynak ve sınır

Canlı tarayıcıdan ve kağıt portföyden alınan kaynaklar `../../sources/botum_2026-09-26/` altında SHA ile arşivlidir. Botum deposuna yazılmaz. Bu klasördeki araştırma, üretim `Clear System.py` dosyasını değiştirmez.

## Soru

PRESSURE yükseliş devamını koruyarak, RETRIGGER ve TSI_BB_FROZEN kurulumlarındaki kayıp yollarını kapanmış 15M→1H fiyat/tepki/hacim hareketiyle erken ayırabilir miyiz? Daha erken ama ancak doğrulanmış geri çekilme/reclaim girişleri net expectancy ve toplam fırsatı artırıyor mu?

## Aşama 0: gerçek kağıt kayıtlarının gözlemsel denetimi

`paper_cohort_audit.py`, arşivlenen `portfolio_snapshot.json` üzerinde 0,20% kaydedilmiş ücret, benzersiz işlem kimliği, gross/net tutarlılığı ve expired sınıfının tek kez sayılması kontrollerini yapar. Sonuç: `paper_cohort_summary.json`. Bu alt kümeler **aynı beş günün sonucuna bakılarak** tanımlanmıştır; kazanma tahmini veya gerçek portföy getirisi değildir. Kalan günlük kota, frozen katmanın ayrı kotası ve görünmeyen adaylar yüzünden çıkarılan sinyallerin yerine hangisinin geleceği bilinmez. Tüm kaybedenlerin MFE/MAE değerleri ileri gözlemdir; giriş filtresine alınamaz.

Çalıştırma: `python 'gpt/Clear System/research/pressure_confirmation/paper_cohort_audit.py' --self-test` ardından `python 'gpt/Clear System/research/pressure_confirmation/paper_cohort_audit.py' --snapshot 'gpt/Clear System/sources/botum_2026-09-26/portfolio_snapshot.json' --output 'gpt/Clear System/research/pressure_confirmation/paper_cohort_summary.json'`.

## Çıkış yolları da eşit öncelikli

Adaylar yalnız giriş filtresinden ibaret değil: sabit tam TP, kademeli kâr alma, stop sonrası yeniden giriş değil; kapanmış 15M/1H hareket sönmesiyle erken çıkış, 24/48 saat süre, volatilite/ATR ve mevcut trailing politikası aynı adaylarla karşılaştırılacak. İşlem öncesi stop genişliği ile üst direnç alanı risk bağlamı olarak kullanılabilir. Her çıkış için 5M veya daha küçük güvenilir mumda **hedef mi stop mu önce** sorusu, yeni fill ve maliyet, elenen büyük kazananlar ve toplam portföy fırsatı ayrı ölçülecek. Aynı gün farklı çıkışların sermayeyi ne zaman serbest bıraktığı da kota ve eşzamanlı pozisyonlara uygulanacak.

Kağıt kaydında tüm beş negatif işlem daha sonra en az +%0,26 tepe görmüş; %0,25 brüt sabit TP kâğıt üzerinde hepsini pozitif yapabilecek kadar düşük görünür. Fakat %0,20 maliyetten sonra işlem başına yalnız +%0,05 kalır ve 23 işlemde iyimser toplam **+%1,15 puan**, mevcut +%28,35 puanın çok altında. %0,80 brüt TP tepe kayıtlarında beş kaybın üçünü kapsar ama iyimser toplam +%8,87 puandır. Bu yalnız **tepeye erişilebilirlik üst sınırı**, çıkış backtest'i değildir; sıralama, spread ve fill henüz doğrulanmadı. Tek bir sabit TP ile kaybı sıfırlamanın toplam kazancı yok edebilmesi, kademeli ve hareket-temelli çıkışları test etme gerekçesidir.

## Aşama 1: tarihsel yeniden oynatma planı

1. Kaynağın `_prefilter`, `evaluate`, `discover` ve `scan_cycle` sırasını, ilk taramada sinyal vermeme kuralını, 15M bar kimliğini, 18 saatlik watch TTL ve ayrı günlük 3 legacy / 6 frozen kontenjanını yeniden üret. Sadece geçmişte o anda kapanmış OHLCV kullan; seçilen coin evrenini tarihsel günlerde kur. Mevcut günün 24 saatlik hacmine göre geriye dönük coin seçimi yapma.
2. Önce 6–12 farklı likidite ve volatilite profilinden coin üzerinde kısa gerçek veri smoke denetimi: 1D/4H/1H/15M zaman hizası, aday yoğunluğu, aynı mumdaki iki kurulumun önceliği, fill/stop/TP hesapları. Başarılı smoke olmadan 64 shard veya tam piyasa taraması açma.
3. Ayrı giriş **ve çıkış** politika karşılaştırması: mevcut üç katman; PRESSURE; PRESSURE + yalnız GREEN RETRIGGER; PRESSURE + hareketle onaylı geri çekilme; erken watch→reclaim→15M devam; tam/kademeli TP; hareket sönmesi ve süreli çıkış. Filtreyi ve eşikleri 2023–2025 Discovery/Calibration üzerinde seç; dönemi/coin kümelerini ayır. Giriş gecikirse yeni fiyat, işlem maliyeti, kayıp kazanan ve boşalan kota ile tüm portföyü yeniden hesapla.
4. 2026-09-22–26 kağıt örneği **hipotezi seçtirdiği için** bu aralık temiz OOS sayılamaz. 2026'nın önceki bölümleri yalnız retrospektif tanı niteliğinde kullanılabilir. Prospektif, kural dondurulduktan sonraki yeni tarihli forward shadow kayıtları şarttır. Frozen r2 ile OR birleşiminde frekans artışı ve net kalite ayrı raporlanır.
5. Metrikler: maliyet sonrası işlem beklentisi ve toplam fırsat, aktif gün oranı, win rate, PF, target-first/stop-first, MFE/MAE, en kötü kuyruk, coin/ay dağılımı, eşzamanlı pozisyonlar ve elenen kazanan/kaybeden. İlk görülen 7/7 PRESSURE veya 10/10 alt küme tek başına terfi gerekçesi değildir.

## Önceki deneylerden sınır

Ayrı r2 çalışmalarında genel loss-veto kuralı bazı kayıpları azaltırken kazananları da sildi; farklı aday havuzundaki veto eşiklerini PRESSURE'a kopyalama. Frozen r2 için 0,5%/2 saat dip girişinde 2026 denetiminde dolum 16/36 oldu ve fırsat ayarlı ortalama orijinal sinyal başına %4,30 ile %5,81 temel düzeyin altında kaldı. Bu bulgu PRESSURE için sonuç değildir; yalnız dip bekleme testinde kaçan fırsatın ölçülmesi gerektiğini gösterir.

## Çalışma bütçesi ve güvenlik kapısı

Aşama 0 yerel, yaklaşık saniyeler. Tarihsel 6 coin smoke bütçesi: 2025-01-01–08-29 arasında yaklaşık 138.000 adet 15M mum ve yaklaşık 140 sayfalı HTTP isteği; önceki 360.000 mumluk veri denetimi 4 dk 37 sn olduğundan kurulumla birlikte tahmini **8–12 runner-dk**, 20 dk açık job sınırı ve 10 dk gerçek-veri komut sınırı. 20 dakika sınırı aşılırsa işlem hata verip kapanır; tam taramaya geçilmez. Workflow derleme, SHA self-test, statik nedensellik, gerçek veri smoke, tek shard/altı sembol eksiksizlik kontrolü ve hata halinde artifact koruması içerir. Push yalnız workflow dosyasının oluşturulmasıyla tetiklenir; kod/snapshot değişikliği tekrar tetiklemez. Tam pazar taraması ancak smoke süresi ve olay yoğunluğundan yeniden bütçelenir. Şu anda böyle bir pahalı çalışma başlamadı.

## 2026-09-26 durum ve sonraki adım

Kaynak beş dosya birebir alındı; gözlemsel audit derleme, self-test ve gerçek 23 kayıtta geçti. Sonraki somut adım: tarihsel zaman sıralı yeniden oynatma kodunu küçük gerçek-veri smoke üzerinde doğrulayıp, tam çalışma için süre tahmini çıkarmak. Üretim sisteme kural eklenmedi.
