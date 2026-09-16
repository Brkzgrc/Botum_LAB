# Ofset uygulanirken stop ve TP1 de kaymali mi?

**Kullanicinin itirazi hakli cikti, dort donemde de.**

Canliya konan tasarim girisi %3 asagi cekiyor ama stop ve TP1'i SABIT
birakiyordu. Sonuc: stop mesafesi eriyor (bir islemde %0.11), TP1 ise
girise gore uzakliyor. "R:R 1.15 -> 4.51 iyilesti" olcumu bu yuzden
sahteydi: pay sisiyor, payda eriyor, ikisi de ofsetin yan etkisi.

## Olcum (dip_tarama sinyalleri, ATRx0.6 cikis, tek islem, 200 sira ortancasi)

| donem | ofsetsiz | giris-3 / stop sabit / tp1 sabit | giris-3 / stop-3 / tp1-3 |
|---|---|---|---|
| 2019-2020 | 11.254$ WR %50 | 12.280$ **WR %32** | 11.010$ WR %52 |
| 2021-2022 | 11.191$ WR %42 | 21.796$ **WR %31** | **25.377$ WR %53** |
| 2023-2024 | 3.827$ WR %48 | 16.509$ **WR %27** | **23.539$ WR %50** |
| 2025-2026 | 9.070$ WR %55 | 11.134$ **WR %21** | **19.856$ WR %50** |

Ayrica "stop da kayar ama tp1 sabit" ara tasarim da olculdu:
+%0.12 / +%1.26 / +%5.30 / +%1.58 — tutarsiz, ikisinin arasinda kaliyor.

## Okunacak sey KAZANMA ORANI

- stop+tp1 sabit : %32 -> %31 -> %27 -> %21   (donemden donme cokuyor)
- hepsi kayar    : %52 -> %53 -> %50 -> %50   (sabit)

Geometri bozulmayinca sistem bozulmuyor. Para tarafinda "hepsi kayar"
dortte ucunde acik ara onde, birinde basabas.

Dolan islem sayisi da farkli: sabit tasarimda 37/196/216/142,
hepsi-kayar tasarimda 62/266/333/222 — cunku giris stop'un altina
dustugu icin elenen sinyaller artik elenmiyor.

## Canliya TASINMADI

Bu olcum dip_tarama sinyalleriyle yapildi. `ORTUSME.md`'de olculdugu gibi
dip_tarama ile canli scanner SIFIR ortusuyor (458 sinyalde 0 cakisma),
dolayisiyla sonuc dogrudan canliya genellenemez.

Canlida ofset **0'a geri alindi** (Botum commit 6a76db6). Ileride ofset
tekrar denenirse dogru tasarimin hangisi oldugu artik biliniyor.

Arac: `araclar/ofset_tasarim.py`
