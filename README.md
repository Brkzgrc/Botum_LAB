# Botum_LAB

Arastirma laboratuvari. **Her calisan kendi klasorunde durur, kok dizin ortaktir.**

```
claude/     Claude'un calismalari
  2026-09-15_dip-tarama/
  2026-09-15_hareket-tespiti/
  2026-09-16_tukenme/          (aktif)
  veri/                        Claude'un veri onbellegi
  tahminler/
```

Her calisma klasorunun kendi notlari icindedir.

## Kurallar

- **Kendi klasorunun disina yazma.** Workflow'lar da dahil:
  `git add -A kendi_klasorun/` seklinde sinirli olmali, `git add -A` degil.
- **Workflow dosyalari `.github/workflows/` altinda ayri isimle.**
  Isim, klasor adiyla baslasin (ornek: `claude-tukenme.yml`).
- **Ayni anda birden fazla is main'e push eder.** Her workflow'un push
  adiminda `git pull --rebase --autostash` ile birkac kez tekrar denemesi
  gerekir, yoksa digeri kazanir ve is cope gider.
- **`concurrency` grubu ve cron dakikasi her is icin farkli olsun** ki
  isler birbirini sıraya sokmasin ve ayni anda push etmeye calismasin.

## Onemli

Buradaki hicbir sey canli sisteme otomatik baglanmaz. Canli sistem ayri
ve **private** depodadir. Bu depo **public** — hicbir token, anahtar veya
kimlik bilgisi buraya girmez.
