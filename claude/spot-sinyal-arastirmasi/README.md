# Spot Sinyal Arastirmasi

**Amac:** Botum canli sisteminin sinyallerini karli hale getirmek.
10.000$ sermaye, ayni anda TEK islem.

Buradaki hicbir sey canliya otomatik baglanmaz. Canli sistem ayri ve
private depodadir (`Brkzgrc/Botum`).

## Calismalar

| klasor | konu | durum |
|---|---|---|
| `2026-09-15_dip-tarama/` | kullanicinin kendi dip alim yontemi; giris ofseti, ATR carpani, para akisi, ortusme | bitti |
| `2026-09-15_hareket-tespiti/` | yakinsama bazli hareket olcumu | bitti |
| `2026-09-16_tukenme/` | yukselis imzasi: ortak payda ne, hangi asamada okunabiliyor | **aktif** |
| `2026-09-22_kademe-hareket/` | 4h->1h->15m kademe hipotezi; 77 olcu, iki aday REDDEDILDI | bitti |
| `2026-10-01_gunluk-stochrsi-kesisim/` | kullanicinin 1 GUNLUK StochRSI kesisim kurulumu; 593 parite, 789k gunluk bar | bitti |

`veri/` ve `tahminler/` bu projeye ait.

## Ozet bulgular

- **Dip tarama ile canli scanner SIFIR ortusuyor** (458 sinyalde 0 cakisma).
  Ayri sistemler, ayri firsat kumeleri. `2026-09-15_dip-tarama/ORTUSME.md`
- **Ofset uygulanacaksa yapinin TAMAMI kaymali** (giris+stop+TP1). Sadece
  girisi kaydirmak kazanma oranini cokertiyor. `OFSET_TASARIMI.md`
- **Sonuk hacimde dipten alim yapilmamali** — dort donemin dordunde de
  dusuk hacim yarisi sifir ya da altinda. Ama tam dogrulanamadi
  (dokunulmamis donemde yeterli islem yok). `HACIM_SONUC.md`
- **Ayni anda cok sayida sinyal gelebiliyor** (bir anda 25 coin). Tek islem
  kuralinda hangisinin secilecegi belirsiz ve denenen uc secim kurali da
  rastgeleden iyi degil. `OFSET_DOGRULAMA.md`
- **1 GUNLUKTE StochRSI kesisimi bir "gec kaldik" isaretidir.** Yukselis
  baslangiclarinin sadece %2.1'inde kesisim var (taban %11.6 — yani
  baslangiclarda DAHA SEYREK). Kullanicinin kurali bu yuzden reddedildi; ayni
  kurulum kesisim sarti atilip RSI>40 TERS cevrilince (RSI<=40) iki dogrulama
  doneminde de tabani geciyor. `2026-10-01_gunluk-stochrsi-kesisim/BULGULAR.md`
- **DUZELTILEN HATA:** `2026-09-15_dip-tarama/araclar/gosterge.py` icindeki
  `nan_to_num`'lu SMA, StochRSI'de her sembolun ilk ~26 barinda SAHTE
  "StochRSI<15" uretiyor. Duzeltilmis surum:
  `2026-10-01_gunluk-stochrsi-kesisim/araclar/gosterge1g.py`. Eski calismalarin
  bu hatadan etkilenip etkilenmedigi GOZDEN GECIRILMELI (ayri is).
