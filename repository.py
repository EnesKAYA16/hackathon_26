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
from pathlib import Path

import pandas as pd

# hackathon_26/ -> kardeş klasör uludag_hackathon_dataset/
DATA_DIR = Path(__file__).resolve().parent.parent / "uludag_hackathon_dataset"

UNIT_CSV = DATA_DIR / "trex_mes_unit.csv"
OEE_CSV = DATA_DIR / "trex_mes_oee_summary.csv"
STOPPAGE_CSV = DATA_DIR / "trex_mes_stoppage_slice.csv"
READING_DEF_CSV = DATA_DIR / "trex_mes_reading_def.csv"

# reading_def UTF-8 DEĞİL; Türkçe karakterler için Latin-5.
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


def warm_cache() -> None:
    """Tüm tabloları önceden belleğe yükler (API başlangıcında çağrılır)."""
    units()
    oee_summary()
    stoppage_slices()
    reading_def_lookup()
