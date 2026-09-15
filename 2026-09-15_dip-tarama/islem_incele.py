import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ============================================================
# AYARLAR
# ============================================================

SYMBOL = "LSKUSDT"

QUANTITY = 100.0

ENTRY_PRICE = 0.1159
STOP_PRICE = 0.1003275
TP1_PRICE = 0.1199565

TRAILING_PERCENT = 2.5

# Türkiye saati
ENTRY_DATE = "10/09/2026"
ENTRY_TIME = "00:12"

ISTANBUL = ZoneInfo("Europe/Istanbul")


# ============================================================
# ZAMAN HESAPLAMA
# ============================================================

entry_dt = datetime.strptime(
    ENTRY_DATE + " " + ENTRY_TIME,
    "%d/%m/%Y %H:%M"
).replace(tzinfo=ISTANBUL)

entry_utc = entry_dt.astimezone(timezone.utc)

start_ms = int(entry_utc.timestamp() * 1000)
end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)


# ============================================================
# BINANCE'TEN 1 DAKIKALIK VERI CEK
# ============================================================

def get_binance_klines(symbol, start_time, end_time):

    url = "https://api.binance.com/api/v3/klines"

    all_klines = []
    current_start = start_time

    print()
    print("Binance 1 dakikalik veriler cekiliyor...")

    while current_start < end_time:

        params = {
            "symbol": symbol,
            "interval": "1m",
            "startTime": current_start,
            "endTime": end_time,
            "limit": 1000
        }

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            break

        all_klines.extend(data)

        last_open_time = data[-1][0]

        current_start = last_open_time + 60000

        print(
            "Cekilen mum:",
            len(all_klines)
        )

        if len(data) < 1000:
            break

    return all_klines


# ============================================================
# ISLEMI SIMULE ET
# ============================================================

def simulate_trade(klines):

    if not klines:
        print("Veri bulunamadi.")
        return

    trailing_active = False

    highest_price = None
    trailing_stop = None

    exit_price = None
    exit_time = None
    exit_reason = None

    tp1_time = None

    first_candle = klines[0]

    first_open = float(first_candle[1])
    first_high = float(first_candle[2])
    first_low = float(first_candle[3])
    first_close = float(first_candle[4])

    print()
    print("=" * 65)
    print("ISLEM BASLANGICI")
    print("=" * 65)

    print(
        "Coin           :",
        SYMBOL
    )

    print(
        "Alim zamani    :",
        entry_dt.strftime("%d/%m/%Y %H:%M")
    )

    print(
        "Alim fiyati    :",
        format(ENTRY_PRICE, ".8f"),
        "USDT"
    )

    print(
        "Miktar         :",
        QUANTITY,
        "LSK"
    )

    print(
        "Pozisyon       :",
        format(ENTRY_PRICE * QUANTITY, ".4f"),
        "USDT"
    )

    print()
    print("00:12 BINANCE MUMU")
    print("-" * 65)

    print(
        "Open           :",
        format(first_open, ".8f")
    )

    print(
        "High           :",
        format(first_high, ".8f")
    )

    print(
        "Low            :",
        format(first_low, ".8f")
    )

    print(
        "Close          :",
        format(first_close, ".8f")
    )

    if first_low <= ENTRY_PRICE <= first_high:
        print("Giris kontrolu : 0.1159 bu mumda GERCEKLESEBILIR.")
    else:
        print("Giris kontrolu : DIKKAT - 0.1159 bu mumun araliginda degil.")

    print()
    print("Stop           :", format(STOP_PRICE, ".8f"))
    print("TP1            :", format(TP1_PRICE, ".8f"))
    print("Trailing       :", str(TRAILING_PERCENT) + "%")

    print("=" * 65)

    # --------------------------------------------------------
    # HER 1 DAKIKALIK MUMU KONTROL ET
    # --------------------------------------------------------

    for candle in klines:

        open_time_ms = candle[0]

        candle_open = float(candle[1])
        candle_high = float(candle[2])
        candle_low = float(candle[3])
        candle_close = float(candle[4])

        candle_time = datetime.fromtimestamp(
            open_time_ms / 1000,
            tz=timezone.utc
        ).astimezone(ISTANBUL)

        # ====================================================
        # TP1 ONCESI
        # ====================================================

        if not trailing_active:

            # Ana stop
            if candle_low <= STOP_PRICE:

                exit_price = STOP_PRICE
                exit_time = candle_time
                exit_reason = "STOP"

                break

            # TP1 goruldu
            if candle_high >= TP1_PRICE:

                trailing_active = True
                tp1_time = candle_time

                highest_price = candle_high

                trailing_stop = highest_price * (
                    1 - TRAILING_PERCENT / 100
                )

                print()
                print(">>> TP1 GORULDU")

                print(
                    "TP1 zamani     :",
                    tp1_time.strftime("%d/%m/%Y %H:%M")
                )

                print(
                    "TP1 seviyesi   :",
                    format(TP1_PRICE, ".8f")
                )

                print(
                    "Mum High       :",
                    format(candle_high, ".8f")
                )

                print(
                    "Trailing stop  :",
                    format(trailing_stop, ".8f")
                )

                # TP1'in vuruldugu 1M mumda high-low sirasi
                # bilinmedigi icin trailing cikisi sonraki
                # mumdan itibaren kontrol edilir.
                continue

        # ====================================================
        # TP1 SONRASI TRAILING
        # ====================================================

        else:

            # Once mevcut trailing stop kontrol edilir
            if candle_low <= trailing_stop:

                exit_price = trailing_stop
                exit_time = candle_time
                exit_reason = "TRAILING STOP"

                break

            # Yeni tepe varsa trailing yukari tasinir
            if candle_high > highest_price:

                highest_price = candle_high

                trailing_stop = highest_price * (
                    1 - TRAILING_PERCENT / 100
                )

    # ========================================================
    # SONUC
    # ========================================================

    print()
    print()
    print("=" * 65)
    print("ISLEM SONUCU")
    print("=" * 65)

    investment = ENTRY_PRICE * QUANTITY

    print(
        "ALIM SAATI     :",
        entry_dt.strftime("%d/%m/%Y %H:%M")
    )

    print(
        "ALIM FIYATI    :",
        format(ENTRY_PRICE, ".8f"),
        "USDT"
    )

    print(
        "MIKTAR         :",
        QUANTITY,
        "LSK"
    )

    print(
        "YATIRIM        :",
        format(investment, ".4f"),
        "USDT"
    )

    print("-" * 65)

    if exit_price is not None:

        exit_value = exit_price * QUANTITY

        pnl_usd = (
            exit_price - ENTRY_PRICE
        ) * QUANTITY

        pnl_percent = (
            (exit_price / ENTRY_PRICE) - 1
        ) * 100

        print(
            "CIKIS SAATI    :",
            exit_time.strftime("%d/%m/%Y %H:%M")
        )

        print(
            "CIKIS FIYATI   :",
            format(exit_price, ".8f"),
            "USDT"
        )

        print(
            "CIKIS NEDENI   :",
            exit_reason
        )

        if tp1_time is not None:

            print("-" * 65)

            print(
                "TP1 SAATI      :",
                tp1_time.strftime("%d/%m/%Y %H:%M")
            )

            print(
                "TP1 FIYATI     :",
                format(TP1_PRICE, ".8f"),
                "USDT"
            )

            print(
                "EN YUKSEK      :",
                format(highest_price, ".8f"),
                "USDT"
            )

            print(
                "SON TRAILING   :",
                format(trailing_stop, ".8f"),
                "USDT"
            )

        print("-" * 65)

        print(
            "CIKIS DEGERI   :",
            format(exit_value, ".4f"),
            "USDT"
        )

        print(
            "KAR / ZARAR    :",
            format(pnl_usd, "+.4f"),
            "USDT"
        )

        print(
            "GETIRI         :",
            format(pnl_percent, "+.2f") + "%"
        )

    else:

        last_candle = klines[-1]

        last_close = float(last_candle[4])

        last_time = datetime.fromtimestamp(
            last_candle[0] / 1000,
            tz=timezone.utc
        ).astimezone(ISTANBUL)

        pnl_usd = (
            last_close - ENTRY_PRICE
        ) * QUANTITY

        pnl_percent = (
            (last_close / ENTRY_PRICE) - 1
        ) * 100

        print("POZISYON       : HALA ACIK")

        print(
            "SON VERI       :",
            last_time.strftime("%d/%m/%Y %H:%M")
        )

        print(
            "SON FIYAT      :",
            format(last_close, ".8f"),
            "USDT"
        )

        print(
            "ANLIK PNL      :",
            format(pnl_usd, "+.4f"),
            "USDT"
        )

        print(
            "ANLIK GETIRI   :",
            format(pnl_percent, "+.2f") + "%"
        )

        if trailing_active:

            print(
                "EN YUKSEK      :",
                format(highest_price, ".8f"),
                "USDT"
            )

            print(
                "TRAILING STOP  :",
                format(trailing_stop, ".8f"),
                "USDT"
            )

        else:

            print("TP1            : HENUZ GORULMEDI")

    print("=" * 65)


# ============================================================
# CALISTIR
# ============================================================

try:

    klines = get_binance_klines(
        SYMBOL,
        start_ms,
        end_ms
    )

    print()
    print(
        "Toplam",
        len(klines),
        "adet 1 dakikalik mum alindi."
    )

    simulate_trade(klines)

except requests.exceptions.HTTPError as error:

    print()
    print("BINANCE API HATASI")
    print(error)

except requests.exceptions.RequestException as error:

    print()
    print("BAGLANTI HATASI")
    print(error)

except Exception as error:

    print()
    print("HATA")
    print(error)
