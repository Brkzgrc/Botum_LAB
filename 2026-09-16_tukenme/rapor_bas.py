# -*- coding: utf-8 -*-
"""Birikimi okuyup raporu basar. Her an calistirilabilir."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analiz import rapor
KOK = os.path.dirname(os.path.abspath(__file__))
b = json.load(open(os.path.join(KOK, "birikim.json")))
d = json.load(open(os.path.join(KOK, "durum.json")))
print(f"islenen coin-donem: {len(d['bitti'])}   toplam yukselis bolumu: {d['bolum']}")
rapor(b, ust=int(sys.argv[1]) if len(sys.argv) > 1 else 40)
