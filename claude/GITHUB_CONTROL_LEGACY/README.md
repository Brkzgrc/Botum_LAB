# GITHUB_CONTROL_LEGACY

Bu klasor, Botum ana repodaki "Hipotez A" / parmak izi arastirmasini yuruten
oturumun Lab tarafindaki calisma alanidir (2026-09-22'de acildi).

Kural: sadece bu klasore yazilir. Diger klasorler (gpt/, claude/spot-sinyal-arastirmasi/)
SADECE OKUNUR.

## Bu klasordeki is

Ilk gorev: `gpt/TSI_BB_Structural_Phase`'de bulunan bir tutarsizligi olcmek.
Arastirma net24'u "al, 24 saat sonra sat, stop yok" olarak olcuyor
(equal_2026_comparison.py satir 146-147). Ama Botum canli sisteminin cikis
kurali (destek stopu + TP1 + ATR trailing + expire) hic uygulanmamis. Ayni
dosyada `danger_dn2_first` alani pre-2026 donemde %56 cikiyor — yani
sinyallerin yarisindan fazlasi hedefe varmadan -%2 goruyor. Bu, gercek
canli cikisla olculmemis bir risk.

Ikinci not (kullanicidan, 2026-09-22): bilgi tabani (video 18, Model A-E)
sabit cikis degil HAREKET TAKIBI (trailing) oneriyor. Model A (sabit stop+hedef)
kontrol grubu olarak tanimlanmis; TSI+BB sinyalleri uzerinde hicbir modelin
kosulmadigi dogrulandi.

Plan: donmuş TSI+BB sinyallerini (~478 kayit, kesif/kalibrasyon/capraz-holdout/
2026-holdout etiketli) 1 dakikalik mumla, Model A-E ile yeniden olc — donem
donem, havuzlamadan. Sonuc bu klasore yazilacak.
