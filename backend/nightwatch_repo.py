"""
NIGHTWATCH TELEMETRİ ERİŞİMİ (DuckDB)
=====================================

6M+ satırlık Nightwatch telemetrisini belleğe YÜKLEMEDEN, DuckDB ile
doğrudan CSV'ler üzerinde (glob + zaman filtresi) sorgular. RCA için
yalnızca dar zaman pencereleri çekilir.

Makine eşlemesi (nightwatch_data'da unit_uid kolonu YOKTUR):
    nightwatch_data.readingdef_uid
      -> nightwatch_reading_def.readingdef_uid (unit_id ile)
      -> nightwatch_unit.id == unit_id  -> unit_uid (MES ile aynı)

Jenerik '00000000-...' sinyaller tüm makinelerde ortaktır (telemetride
makineyi ayırt edemez) -> makineye-özel telemetride DIŞLANIR.
"""

from __future__ import annotations

from functools import lru_cache

import duckdb
import pandas as pd

import repository
from config import settings

# Sadece numeric telemetri ('data_0*' string dosyalarını kapsamaz).
NUMERIC_GLOB = str(settings.data_dir / "trex_nightwatch_data_0*.csv")


@lru_cache(maxsize=1)
def _con() -> duckdb.DuckDBPyConnection:
    """Tek, yeniden kullanılan DuckDB bağlantısı."""
    return duckdb.connect()


def _naive_utc(ts) -> pd.Timestamp:
    """tz-aware/naive girdiyi naive-UTC Timestamp'a çevirir (DuckDB TIMESTAMP ile karşılaştırmak için)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t


def signal_map(unit_uid: str) -> pd.DataFrame:
    """
    Bir makineye-ÖZEL Nightwatch sinyalleri (jenerik 00000000 uid'ler hariç).
    Sütunlar: readingdef_uid, readingdef_name, display_name, external_signal_type
    """
    nu = repository.nightwatch_units()
    match = nu.loc[nu["unit_uid"] == unit_uid]
    if match.empty:
        raise ValueError(f"Nightwatch'ta unit_uid bulunamadı: {unit_uid}")
    unit_id = int(match.iloc[0]["id"])

    rd = repository.nightwatch_reading_def()
    sigs = rd.loc[
        (rd["unit_id"] == unit_id)
        & (~rd["readingdef_uid"].astype(str).str.startswith("00000000"))
    ]
    return sigs[["readingdef_uid", "readingdef_name", "display_name",
                 "external_signal_type"]].copy()


def telemetry_window(unit_uid: str, start, end,
                     signal_names: list[str] | None = None) -> pd.DataFrame:
    """
    [start, end] aralığında, makineye-özel numeric telemetriyi döndürür.

    Args:
        signal_names: readingdef_name listesi (örn. ["STATINFO_RUN"]). None=hepsi.

    Dönen sütunlar: time, signal (readingdef_name), readingdef_uid, value (str)
    """
    sigs = signal_map(unit_uid)
    if signal_names:
        sigs = sigs[sigs["readingdef_name"].isin(signal_names)]
    if sigs.empty:
        return pd.DataFrame(columns=["time", "signal", "readingdef_uid", "value"])

    uid_to_name = dict(zip(sigs["readingdef_uid"], sigs["readingdef_name"]))
    uid_list = ", ".join(f"'{u}'" for u in uid_to_name)

    sql = f"""
        SELECT time, readingdef_uid, value
        FROM read_csv_auto('{NUMERIC_GLOB}', union_by_name=true,
                           types={{'time': 'TIMESTAMP', 'value': 'VARCHAR'}})
        WHERE readingdef_uid IN ({uid_list})
          AND time BETWEEN ? AND ?
        ORDER BY time
    """
    df = _con().execute(sql, [_naive_utc(start), _naive_utc(end)]).df()
    # DuckDB TIMESTAMP naive döner; diğer katmanlarla tutarlı olsun diye UTC'ye localize et.
    if not df.empty:
        df["time"] = df["time"].dt.tz_localize("UTC")
    df["signal"] = df["readingdef_uid"].map(uid_to_name)
    return df[["time", "signal", "readingdef_uid", "value"]]


def transitions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Telemetriyi sıkıştırır: her sinyal için yalnızca DEĞER DEĞİŞİMLERİNİ tutar.
    (Örn. STATINFO_RUN 1->0 geçişi gibi anlamlı olayları öne çıkarır; payload küçülür.)
    """
    if df.empty:
        return df
    out = []
    for sig, g in df.sort_values("time").groupby("signal"):
        prev = object()
        for _, row in g.iterrows():
            if row["value"] != prev:
                out.append(row)
                prev = row["value"]
    return pd.DataFrame(out)[["time", "signal", "readingdef_uid", "value"]] if out else df.iloc[0:0]
