# Frozen r2 Scanner GUI

Bu arayüz mevcut `r2_candidate_scanner.py` dosyasını değiştirmeden kullanır.
Binance veri alma, coin evreni, indikatörler, cooldown ve sinyal koşulları aynı
tarayıcı fonksiyonlarından çalışır. Uygulama emir açmaz.

## Windows'ta çalıştırma

1. Python 3.11 veya daha yeni bir sürümün kurulu olduğundan emin olun.
2. Terminali bu klasörde açın.
3. İlk kullanımda gereksinimleri kurun:

   ```powershell
   pip install numpy pandas requests
   ```

4. `start_r2_gui.bat` dosyasına çift tıklayın.

Alternatif olarak terminalden:

```powershell
python r2_candidate_gui.py
```

## Kullanım akışı

1. **Taramayı Başlat** ile Binance Spot/USDT evrenini tarayın.
2. Sinyal oluşursa tablodan satırı seçip **Takibe Al** düğmesine basın.
3. **Takip Sistemi** sekmesinde **Fiyatları Güncelle** düğmesine basın.
4. Güncel değişim, görülen maksimum/minimum fiyat ve maksimum yükseliş/düşüş
   değerlerini takip edin.

Takip kayıtları `gui_data/tracked_signals.json` dosyasında saklanır. Tarama
çıktıları ve hata/warmup CSV dosyaları da aynı `gui_data` klasörüne yazılır.

## Notlar

- Varsayılan worker sayısı tarayıcıdaki mevcut değer olan `6`'dır.
- **Durdur** düğmesi yeni işleri iptal eder; o anda çalışan Binance isteklerinin
  tamamlanması birkaç saniye sürebilir.
- Aynı symbol ve aynı sinyal zamanı takip listesine ikinci kez eklenmez.
