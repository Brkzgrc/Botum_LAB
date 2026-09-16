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
