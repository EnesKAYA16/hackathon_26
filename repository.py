"""
VERİ ERİŞİM KATMANI (Repository)
================================

Tek veri kapısı. CSV'leri diskten BİR KEZ yükler ve bellekte cache'ler
(@lru_cache). Web backend'de her istekte 15MB'lık dosyaları yeniden okumamak
için kritik. Tarih/encoding/boolean dönüşümleri de burada tek seferde yapılır.

ÖNEMLİ: Bu fonksiyonlar PAYLAŞILAN (cache'li) DataFrame döndürür.
Çağıranlar bu kareleri MUTASYONA UĞRATMAMALI; yalnızca filtreleyip
(yeni kare üretip) kullanmalı. Sütun eklemek gerekiyorsa önce .copy() alın.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from config import settings

# Veri klasörü .env / config'ten gelir (tek kaynak).
DATA_DIR = settings.data_dir

UNIT_CSV = DATA_DIR / "trex_mes_unit.csv"
OEE_CSV = DATA_DIR / "trex_mes_oee_summary.csv"
STOPPAGE_CSV = DATA_DIR / "trex_mes_stoppage_slice.csv"
READING_DEF_CSV = DATA_DIR / "trex_mes_reading_def.csv"
ALERT_CSV = DATA_DIR / "trex_mes_alert.csv"
WORKORDER_CSV = DATA_DIR / "trex_mes_workorder.csv"
COUNTER_CSV = DATA_DIR / "trex_mes_counter_slice.csv"
NW_UNIT_CSV = DATA_DIR / "trex_nightwatch_unit.csv"
NW_READING_DEF_CSV = DATA_DIR / "trex_nightwatch_reading_def.csv"

# Bu CSV'ler UTF-8 DEĞİL; Türkçe karakterler için Latin-5.
READING_DEF_ENCODING = "iso-8859-9"


@lru_cache(maxsize=1)
def units() -> pd.DataFrame:
    """Makine ana verisi (uid <-> name)."""
    return pd.read_csv(UNIT_CSV, usecols=["uid", "name", "is_enabled"])


@lru_cache(maxsize=1)
def oee_summary() -> pd.DataFrame:
    """OEE özet tablosu; trans_date UTC datetime'a çevrilmiş."""
    df = pd.read_csv(OEE_CSV)
    df["trans_date"] = pd.to_datetime(df["trans_date"], utc=True)
    return df


@lru_cache(maxsize=1)
def stoppage_slices() -> pd.DataFrame:
    """
    Duruş eventleri; started_on datetime'a, boolean kolonlar bool'a çevrilmiş.
    started_on karışık formatta (bazısı mikrosaniyeli) -> ISO8601.
    """
    cols = [
        "unit_uid", "reading_def_uid", "started_on", "ended_on",
        "is_planned", "duration_milliseconds", "is_test_prod", "exclude_from_oee",
    ]
    s = pd.read_csv(STOPPAGE_CSV, usecols=cols)
    s["started_on"] = pd.to_datetime(s["started_on"], utc=True, format="ISO8601")
    s["ended_on"] = pd.to_datetime(s["ended_on"], utc=True, format="ISO8601")
    for col in ("is_planned", "is_test_prod", "exclude_from_oee"):
        s[col] = s[col].map({"t": True, "f": False}).astype("boolean")
    return s


@lru_cache(maxsize=1)
def reading_def_lookup() -> pd.DataFrame:
    """
    reading_def_uid -> isim/kategori sözlüğü (uid index'li).
    Aynı uid birden çok makinede tanımlı olabilir; isim/kategori tutarlı,
    bu yüzden uid'e göre dedup'lanır.
    """
    rd = pd.read_csv(
        READING_DEF_CSV,
        encoding=READING_DEF_ENCODING,
        usecols=["uid", "name", "display_text", "signal_category"],
    )
    return rd.drop_duplicates(subset="uid").set_index("uid")


@lru_cache(maxsize=1)
def alerts() -> pd.DataFrame:
    """
    CNC alarm eventleri (RCA giriş noktası). started_on datetime'a çevrilmiş,
    alarm metni (value) boşlukları kırpılmış. Türkçe -> Latin-5 encoding.
    """
    al = pd.read_csv(ALERT_CSV, encoding=READING_DEF_ENCODING)
    al["started_on"] = pd.to_datetime(al["started_on"], utc=True, format="ISO8601")
    if "ended_on" in al.columns:
        al["ended_on"] = pd.to_datetime(al["ended_on"], utc=True, format="ISO8601")
    # Alarm metnini temizle (baştaki/sondaki boşluk ve '\n').
    al["message"] = al["value"].astype(str).str.replace(r"\\n", "", regex=True).str.strip()
    return al


@lru_cache(maxsize=1)
def nightwatch_units() -> pd.DataFrame:
    """Nightwatch makine ana verisi (integer id <-> unit_uid eşlemesi)."""
    return pd.read_csv(NW_UNIT_CSV, usecols=["id", "unit_uid", "name"])


@lru_cache(maxsize=1)
def nightwatch_reading_def() -> pd.DataFrame:
    """
    Nightwatch sinyal tanımları. unit_id (integer) -> readingdef_uid eşlemesi
    telemetriyi makineye bağlamak için gerekli. Türkçe -> Latin-5.
    """
    return pd.read_csv(
        NW_READING_DEF_CSV,
        encoding=READING_DEF_ENCODING,
        usecols=["unit_id", "readingdef_uid", "readingdef_name", "display_name",
                 "external_signal_type"],
    )


@lru_cache(maxsize=1)
def counter_slices() -> pd.DataFrame:
    """Üretim sayacı dilimleri; value = parça artışı (delta). slice_on datetime."""
    cols = ["unit_uid", "reading_def_uid", "signal_type", "value", "slice_on", "exclude_from_oee"]
    c = pd.read_csv(COUNTER_CSV, usecols=cols)
    c["slice_on"] = pd.to_datetime(c["slice_on"], utc=True, format="ISO8601")
    c["exclude_from_oee"] = c["exclude_from_oee"].map({"t": True, "f": False}).astype("boolean")
    return c


@lru_cache(maxsize=1)
def workorders() -> pd.DataFrame:
    """İş emirleri / stok çalışmaları; tarihler datetime'a çevrilmiş."""
    cols = ["unit_uid", "order_no", "is_work_order", "is_stock",
            "started_on", "ended_on", "duration_milliseconds",
            "stock_cycle", "planned_quantity", "exclude_from_oee"]
    wo = pd.read_csv(WORKORDER_CSV, usecols=cols)
    wo["started_on"] = pd.to_datetime(wo["started_on"], utc=True, format="ISO8601")
    wo["ended_on"] = pd.to_datetime(wo["ended_on"], utc=True, format="ISO8601")
    return wo


def warm_cache() -> None:
    """Tüm tabloları önceden belleğe yükler (API başlangıcında çağrılır)."""
    units()
    oee_summary()
    stoppage_slices()
    reading_def_lookup()
    alerts()
    nightwatch_units()
    nightwatch_reading_def()
    workorders()
    counter_slices()
