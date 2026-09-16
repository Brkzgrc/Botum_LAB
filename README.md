# Botum_LAB

Arastirma laboratuvari. **Her calisan kendi klasorunde durur, kok dizin ortaktir.**

```
claude/                          Claude'un alani
  spot-sinyal-arastirmasi/       PROJE
    2026-09-15_dip-tarama/         calisma
    2026-09-15_hareket-tespiti/    calisma
    2026-09-16_tukenme/            calisma (aktif)
    veri/  tahminler/
    README.md
```

Duzen: `claude/<proje>/<calisma>/`. Yeni proje gelirse `claude/` altinda
yeni bir proje klasoru acilir. Her calisma klasorunun kendi notlari icindedir.

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
