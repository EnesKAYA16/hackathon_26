"""
SERVİS KATMANI (Orkestrasyon)
=============================

Çekirdek hesaplama fonksiyonları (oee_baseline / oee_whatif) ile API arasında
köprü. Tek işi: makine adı + tarih alıp, cache'li veriyi çekip, çekirdeği
çağırıp, sonucu JSON-GÜVENLİ (native Python tipli) dict'e çevirmektir.

Hem FastAPI (api.py) hem de CLI bu katmanı tüketebilir -> çekirdek tek,
sunum çok. numpy/pandas tipleri burada native int/float/str'e dönüştürülür.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import finance as fin
import oee_baseline as core
import oee_whatif as whatif


# ---------------------------------------------------------------------------
# JSON güvenliği: numpy/pandas tiplerini native Python'a çevir
# ---------------------------------------------------------------------------

def _native(v):
    """numpy/pandas skalerini JSON'a uygun native tipe çevirir (NaN -> None)."""
    if v is None:
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if pd.isna(v):
        return None
    return v


def _resolve(machine: str) -> str:
    """Makine adından (veya 'M1' kısaltmasından) unit_uid çözer."""
    return core.resolve_unit_uid(core.load_units(), machine)


# ---------------------------------------------------------------------------
# Makine listesi & uygun günler (frontend dropdown'ları için)
# ---------------------------------------------------------------------------

def list_machines() -> list[dict]:
    """Tüm makineler: name + unit_uid + is_enabled."""
    units = core.load_units()
    return [
        {"name": str(r["name"]).strip(),
         "unit_uid": str(r["uid"]),
         "is_enabled": str(r["is_enabled"]).strip().lower() == "t"}
        for _, r in units.iterrows()
    ]


def list_dates(machine: str) -> list[str]:
    """Bir makine için OEE kaydı olan tüm vardiya günleri (level=1)."""
    unit_uid = _resolve(machine)
    oee = core.load_oee_summary()
    mask = (oee["level"] == 1) & (oee["unit_uid"] == unit_uid)
    dates = oee.loc[mask, "trans_date"].dt.date.astype(str)
    return sorted(dates.unique().tolist())


# ---------------------------------------------------------------------------
# Baz OEE (A x P x Q)
# ---------------------------------------------------------------------------

def get_baseline(machine: str, date: str) -> dict:
    """Bir makine/gün için baz OEE ayrıştırması (JSON-güvenli)."""
    unit_uid = _resolve(machine)
    row = core.select_baseline_row(core.load_oee_summary(), unit_uid, date)
    bd = core.build_oee_breakdown(row)

    a, p, q = bd["availability"], bd["performance"], bd["quality"]
    return {
        "machine": machine,
        "unit_uid": unit_uid,
        "date": date,
        "trans_date": _native(bd["trans_date"]),
        "availability": {
            "A": _native(a["A"]),
            "work_total_ms": _native(a["WorkTotal_ms"]),
            "planned_stop_ms": _native(a["PlannedStop_ms"]),
            "unplanned_stop_ms": _native(a["UnPlannedStop_ms"]),
            "scheduled_time_ms": _native(a["ScheduledTime_ms"]),
            "run_time_ms": _native(a["RunTime_ms"]),
            "unplanned_stop_h": _native(core.ms_to_hours(a["UnPlannedStop_ms"])),
        },
        "performance": {
            "P": _native(p["P"]),
            "working_time_ms": _native(p["WorkingTime_ms"]),
            "planned_time_ms": _native(p["PlannedTime_ms"]),
            "raw_ratio": _native(p["P_raw_ratio"]),
        },
        "quality": {
            "Q": _native(q["Q"]),
            "product_sum": _native(q["ProductSum"]),
            "scrape_sum": _native(q["ScrapeSum"]),
        },
        "oee": _native(bd["stored"]["OEE"]),
        "oee_recomputed": _native(bd["OEE_recomputed"]),
        "validation_delta": _native(bd["OEE_recomputed"] - float(bd["stored"]["OEE"])),
    }


# ---------------------------------------------------------------------------
# Pareto (en çok süre kaybettiren plansız duruşlar)
# ---------------------------------------------------------------------------

def get_pareto(machine: str, date: str, top_n: int = 5) -> dict:
    """En çok süre kaybettiren ilk N plansız duruş nedeni (JSON-güvenli)."""
    unit_uid = _resolve(machine)
    pareto = whatif.pareto_unplanned(unit_uid, date, top_n=top_n)

    items = []
    for rank, r in enumerate(pareto.itertuples(index=False), start=1):
        items.append({
            "rank": rank,
            "reason": _native(r.reason),
            "category": _native(r.signal_category),
            "reading_def_uid": _native(r.reading_def_uid),
            "events": _native(r.events),
            "total_ms": _native(r.total_ms),
            "total_hours": _native(r.total_hours),
            "pct": _native(r.pct),
            "cumulative_pct": _native(r.cumulative_pct),
        })

    total_ms = float(pareto["total_ms"].sum()) if len(pareto) else 0.0
    return {
        "machine": machine,
        "unit_uid": unit_uid,
        "date": date,
        "total_unplanned_ms": total_ms,
        "total_unplanned_h": core.ms_to_hours(total_ms),
        "items": items,
    }


# ---------------------------------------------------------------------------
# What-If simülasyonu
# ---------------------------------------------------------------------------

def default_finance_assumptions() -> dict:
    """Varsayılan finansal varsayımlar (frontend formunu önceden doldurmak için)."""
    from dataclasses import asdict
    return asdict(fin.FinanceAssumptions())


def _coerce_finance(d: dict | None) -> dict:
    """dict'teki finansal alanları _native ile JSON-güvenli yapar."""
    if d is None:
        return d
    out = {}
    for k, v in d.items():
        out[k] = _coerce_finance(v) if isinstance(v, dict) else _native(v)
    return out


def run_whatif(machine: str, date: str, durus_nedeni: str, azaltma_yuzdesi: float,
               finance_inputs: dict | None = None) -> dict:
    """
    Spesifik bir duruş nedenini azaltmanın OEE + FİNANSAL etkisi (JSON-güvenli).
    finance_inputs verilmezse varsayılan (docs/02) varsayımlar kullanılır.
    """
    unit_uid = _resolve(machine)
    sim = whatif.simulate_whatif(unit_uid, date, durus_nedeni, azaltma_yuzdesi)

    oee_base = float(sim["OEE_base"])
    rel = (sim["dOEE"] / oee_base * 100) if oee_base else 0.0

    # --- Finansal katman ---
    assumptions = fin.FinanceAssumptions(**(finance_inputs or {}))
    financial = fin.compute_financial_impact(
        recovered_hours=sim["recovered_hours"],
        product_sum=sim["product_sum"],
        running_hours=sim["running_hours"],
        a=assumptions,
    )

    return {
        "machine": machine,
        "unit_uid": unit_uid,
        "date": date,
        "durus_nedeni": _native(sim["durus_nedeni"]),
        "azaltma_yuzdesi": _native(sim["azaltma_yuzdesi"]),
        "share": _native(sim["share"]),
        "reason_official_ms": _native(sim["reason_official_ms"]),
        "reduced_ms": _native(sim["reduced_ms"]),
        "recovered_hours": _native(sim["recovered_hours"]),
        "before": {
            "unplanned_stop_ms": _native(sim["official_unplanned"]),
            "availability": _native(sim["A_base"]),
            "performance": _native(sim["P"]),
            "quality": _native(sim["Q"]),
            "oee": _native(sim["OEE_base"]),
        },
        "after": {
            "unplanned_stop_ms": _native(sim["new_unplanned"]),
            "availability": _native(sim["A_new"]),
            "performance": _native(sim["P"]),
            "quality": _native(sim["Q"]),
            "oee": _native(sim["OEE_new"]),
        },
        "delta": {
            "availability_pp": _native(sim["dA"] * 100),
            "oee_pp": _native(sim["dOEE"] * 100),
            "oee_relative_pct": _native(rel),
        },
        "financial": _coerce_finance(financial),
    }
