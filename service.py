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

import ai
import finance as fin
import oee_baseline as core
import oee_whatif as whatif
import rca
import repository
from config import settings


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


def _jsonify(obj):
    """Dict/list/skaler'i özyinelemeli olarak JSON-güvenli native tiplere çevirir."""
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    return _native(obj)


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

def _overlapping_stops(unit_uid: str, start, end):
    """Pencereyle örtüşen, OEE'ye dahil duruş dilimleri."""
    s = repository.stoppage_slices()
    return s[(s["unit_uid"] == unit_uid) & (s["started_on"] < end) & (s["ended_on"] > start)
             & (~s["exclude_from_oee"]) & (~s["is_test_prod"])].copy()


def _hour_clip_ms(sub, hb, he):
    """Dilimlerin [hb, he) saat aralığına KIRPILMIŞ sürelerini ms olarak ekler."""
    cs = sub["started_on"].clip(lower=hb)
    ce = sub["ended_on"].clip(upper=he)
    return ((ce - cs).dt.total_seconds() * 1000).clip(lower=0)


def stoppage_trend(machine: str, date: str) -> dict:
    """
    Vardiya günü boyunca SAATLİK planlı/plansız duruş — DAKİKA cinsinden,
    her saat aralığına KIRPILMIŞ (saat başına en çok 60 dk).
    """
    unit_uid = _resolve(machine)
    start, end = _shift_window(date)
    ov = _overlapping_stops(unit_uid, start, end)
    base = start.floor("h")

    buckets = []
    for i in range(24):
        hb = base + pd.Timedelta(hours=i)
        he = hb + pd.Timedelta(hours=1)
        sub = ov[(ov["started_on"] < he) & (ov["ended_on"] > hb)].copy()
        if not sub.empty:
            sub["clip_ms"] = _hour_clip_ms(sub, hb, he)
            planned = float(sub.loc[sub["is_planned"] == True, "clip_ms"].sum())    # noqa: E712
            unplanned = float(sub.loc[sub["is_planned"] == False, "clip_ms"].sum())  # noqa: E712
        else:
            planned = unplanned = 0.0
        buckets.append({"hour": hb.strftime("%H:%M"),
                        "planned_min": round(planned / 60_000, 2),
                        "unplanned_min": round(unplanned / 60_000, 2)})
    return {"machine": machine, "unit_uid": unit_uid, "date": date, "buckets": buckets}


def stoppage_kpis(machine: str, date: str) -> dict:
    """Duruşlar sayfası için 4 özet KPI: toplam duruş, plansız oran, MTBF, MTTR."""
    unit_uid = _resolve(machine)
    b = get_baseline(machine, date)
    work = b["availability"]["work_total_ms"]
    planned = b["availability"]["planned_stop_ms"]
    unplanned = b["availability"]["unplanned_stop_ms"]
    run = b["availability"]["run_time_ms"]
    total_stop = planned + unplanned

    start, end = _shift_window(date)
    s = repository.stoppage_slices()
    ev = s[(s["unit_uid"] == unit_uid) & (s["started_on"] >= start) & (s["started_on"] < end)
           & (~s["is_planned"]) & (~s["exclude_from_oee"]) & (~s["is_test_prod"])]
    n = int(len(ev))

    return {
        "machine": machine, "unit_uid": unit_uid, "date": date,
        "total_stop_ms": total_stop,
        "total_stop_h": total_stop / 3_600_000,
        "unplanned_ratio_pct": (unplanned / total_stop * 100) if total_stop else 0.0,
        "unplanned_events": n,
        "mtbf_ms": (run / n) if n else 0.0,        # iki arıza arası ortalama çalışma
        "mttr_ms": (unplanned / n) if n else 0.0,  # ortalama tamir/duruş süresi
    }


def oee_hourly_trend(machine: str, date: str) -> dict:
    """
    Tek bir gün için SAATLİK OEE trendi. Saatlik Availability duruşlardan
    (kırpılmış) hesaplanır; P ve Q gün-seviyesi sabit alınır (saatlik P yoktur).
    """
    unit_uid = _resolve(machine)
    try:
        b = get_baseline(machine, date)
        P = b["performance"]["P"]
        Q = b["quality"]["Q"]
    except ValueError:
        P, Q = 0.0, 1.0  # o gün OEE baz verisi yok -> saatlik A yine duruşlardan gelir
    start, end = _shift_window(date)
    ov = _overlapping_stops(unit_uid, start, end)
    base = start.floor("h")
    HOUR_MS = 3_600_000

    points = []
    for i in range(24):
        hb = base + pd.Timedelta(hours=i)
        he = hb + pd.Timedelta(hours=1)
        sub = ov[(ov["started_on"] < he) & (ov["ended_on"] > hb)].copy()
        planned = unplanned = 0.0
        if not sub.empty:
            sub["clip_ms"] = _hour_clip_ms(sub, hb, he)
            planned = float(sub.loc[sub["is_planned"] == True, "clip_ms"].sum())    # noqa: E712
            unplanned = float(sub.loc[sub["is_planned"] == False, "clip_ms"].sum())  # noqa: E712
        scheduled = HOUR_MS - planned
        run = max(scheduled - unplanned, 0.0)
        A = (run / scheduled) if scheduled > 0 else 0.0
        oee = A * P * Q
        points.append({"hour": hb.strftime("%H:%M"),
                       "availability": A * 100, "performance": P * 100, "oee": oee * 100})
    return {"machine": machine, "unit_uid": unit_uid, "date": date, "points": points}


def counter_trend(machine: str, date: str) -> dict:
    """Vardiya günü boyunca saatlik üretilen parça (COUNT sayaç artışları, slayt 'Counters')."""
    unit_uid = _resolve(machine)
    c = repository.counter_slices()
    start, end = _calendar_window(date)  # takvim günü (off-by-one düzeltmesi)
    m = c[(c["unit_uid"] == unit_uid) & (c["slice_on"] >= start) & (c["slice_on"] < end)
          & (c["signal_type"] == "COUNT") & (~c["exclude_from_oee"])].copy()
    m["bucket"] = m["slice_on"].dt.floor("h")

    base = start.floor("h")
    buckets = []
    for i in range(24):
        b = base + pd.Timedelta(hours=i)
        pieces = float(m.loc[m["bucket"] == b, "value"].sum())
        buckets.append({"hour": b.strftime("%H:%M"), "pieces": pieces})
    total = float(m["value"].sum())
    return {"machine": machine, "unit_uid": unit_uid, "date": date,
            "total_pieces": total, "buckets": buckets}


def oee_trend(machine: str, days: int = 30,
              start: str | None = None, end: str | None = None) -> dict:
    """
    Bir makinenin OEE/A/P trendi. start+end verilirse o tarih aralığı,
    yoksa son N gün (baseline karşılaştırma, slayt 'Shift Comparison').
    """
    unit_uid = _resolve(machine)
    o = repository.oee_summary()
    m = o[(o["level"] == 1) & (o["unit_uid"] == unit_uid)].sort_values("trans_date")
    if start and end:
        s, e = pd.Timestamp(start).date(), pd.Timestamp(end).date()
        m = m[(m["trans_date"].dt.date >= s) & (m["trans_date"].dt.date <= e)]
    else:
        m = m.tail(days)
    points = []
    for r in m.itertuples(index=False):
        a = core.safe_json(r.availability)
        p = core.safe_json(r.performance)
        points.append({
            "date": r.trans_date.date().isoformat(),
            "oee": float(r.oee) * 100,
            "availability": float(a.get("A", 0)) * 100,
            "performance": float(p.get("P", 0)) * 100,
        })
    return {"machine": machine, "unit_uid": unit_uid, "count": len(points), "points": points}


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


def run_whatif(machine: str, date: str, durus_nedeni: str | None = None,
               azaltma_yuzdesi: float = 0.0, finance_inputs: dict | None = None,
               reclassify: bool = False, cycle_improvement_pct: float = 0.0,
               scrap_rate: float = 0.0) -> dict:
    """
    OEE'nin A/P/Q kaldıraçlarında What-If + FİNANSAL etki (JSON-güvenli).
    finance_inputs verilmezse varsayılan (docs/02) varsayımlar kullanılır.
    """
    unit_uid = _resolve(machine)
    sim = whatif.simulate_whatif(unit_uid, date, durus_nedeni, azaltma_yuzdesi,
                                 reclassify=reclassify,
                                 cycle_improvement_pct=cycle_improvement_pct,
                                 scrap_rate=scrap_rate)

    oee_base = float(sim["OEE_base"])
    rel = (sim["dOEE"] / oee_base * 100) if oee_base else 0.0

    # --- Finansal katman (A geri kazanımı + P ekstra parça) ---
    assumptions = fin.FinanceAssumptions(**(finance_inputs or {}))
    financial = fin.compute_financial_impact(
        recovered_hours=sim["recovered_hours"],
        product_sum=sim["product_sum"],
        running_hours=sim["running_hours"],
        a=assumptions,
        extra_pieces_perf=sim["extra_pieces_perf"],
    )

    return {
        "machine": machine, "unit_uid": unit_uid, "date": date,
        "durus_nedeni": _native(sim["durus_nedeni"]),
        "azaltma_yuzdesi": _native(sim["azaltma_yuzdesi"]),
        "reclassify": bool(sim["reclassify"]),
        "cycle_improvement_pct": _native(sim["cycle_improvement_pct"]),
        "scrap_rate": _native(sim["scrap_rate"]),
        "share": _native(sim["share"]),
        "reason_official_ms": _native(sim["reason_official_ms"]),
        "reduced_ms": _native(sim["reduced_ms"]),
        "recovered_hours": _native(sim["recovered_hours"]),
        "before": {
            "unplanned_stop_ms": _native(sim["official_unplanned"]),
            "availability": _native(sim["A_base"]),
            "performance": _native(sim["P_base"]),
            "quality": _native(sim["Q_base"]),
            "oee": _native(sim["OEE_base"]),
        },
        "after": {
            "unplanned_stop_ms": _native(sim["new_unplanned"]),
            "availability": _native(sim["A_new"]),
            "performance": _native(sim["P_new"]),
            "quality": _native(sim["Q_new"]),
            "oee": _native(sim["OEE_new"]),
        },
        "delta": {
            "availability_pp": _native(sim["dA"] * 100),
            "performance_pp": _native(sim["dP"] * 100),
            "quality_pp": _native(sim["dQ"] * 100),
            "oee_pp": _native(sim["dOEE"] * 100),
            "oee_relative_pct": _native(rel),
        },
        "waterfall": {
            "a": _native(sim["waterfall"]["a"] * 100),
            "p": _native(sim["waterfall"]["p"] * 100),
            "q": _native(sim["waterfall"]["q"] * 100),
        },
        "financial": _coerce_finance(financial),
    }


# ---------------------------------------------------------------------------
# RCA (Kök Neden Analizi) — Faz 3
# ---------------------------------------------------------------------------

def list_alerts(machine: str, date: str | None = None) -> dict:
    """Bir makinenin alarmları (opsiyonel gün filtresi)."""
    unit_uid = _resolve(machine)
    df = rca.get_alerts(unit_uid, date)
    return {
        "machine": machine, "unit_uid": unit_uid, "date": date,
        "count": int(len(df)),
        "alerts": [{"started_on": _native(r.started_on), "message": _native(r.message)}
                   for r in df.itertuples(index=False)],
    }


def get_alert_pareto(machine: str | None = None, top_n: int = 10) -> dict:
    """En sık tekrarlayan alarmlar (makine veya tesis geneli)."""
    unit_uid = _resolve(machine) if machine else None
    df = rca.alert_pareto(unit_uid, top_n)
    return {
        "machine": machine, "unit_uid": unit_uid,
        "items": [{"message": _native(r.message), "count": _native(r.count),
                   "first_seen": _native(r.first_seen), "last_seen": _native(r.last_seen)}
                  for r in df.itertuples(index=False)],
    }


def get_timeline(machine: str, center: str, window_min: int | None = None) -> dict:
    """Bir an etrafında alarm + duruş + telemetri çizelgesi."""
    unit_uid = _resolve(machine)
    tl = rca.build_timeline(unit_uid, center, window_min)
    return _jsonify({"machine": machine, "unit_uid": unit_uid, **tl})


def get_root_cause(machine: str, date: str, window_min: int | None = None) -> dict:
    """Kanıtlı kök neden kartı."""
    unit_uid = _resolve(machine)
    card = rca.root_cause_card(unit_uid, date, window_min)
    return _jsonify({"machine": machine, **card})


# ---------------------------------------------------------------------------
# AI Kök Neden Analizi (Gemini)
# ---------------------------------------------------------------------------

def _build_rca_prompt(machine: str, date: str, card: dict, dev: dict | None) -> str:
    """Kök neden kartı + sapma + olay çizelgesinden Gemini için Türkçe prompt kurar."""
    a0 = card["alarms"][0]
    lines = [
        f"Makine: {machine} | Gün: {date}",
        f"Birincil alarm: {a0['message']} (tüm geçmişte {a0['recurrence_total']} kez tekrarlamış)",
        "Günün alarmları: " + "; ".join(f"{a['message']} (x{a['recurrence_total']})" for a in card["alarms"]),
        f"Telemetri kanıtı: {card['evidence']}",
    ]
    if dev and dev.get("available"):
        lines.append(f"İstatistiksel sapma: {dev['summary']}")
    if card.get("downtime_context"):
        dc = card["downtime_context"]
        lines.append(f"Vardiya {dc['shift_date']} toplam plansız duruş: {dc['total_unplanned_h']:.1f} saat")
    tl = card.get("timeline") or {}
    ev = []
    for x in tl.get("alerts", []):
        ev.append(f"{x['time']} ALARM: {x['message']}")
    for x in tl.get("telemetry", []):
        ev.append(f"{x['time']} TELEMETRİ {x['signal']}={x['value']}")
    for x in tl.get("stoppages", []):
        ev.append(f"{x['started_on']} DURUŞ: {x['reason']} ({'planlı' if x['is_planned'] else 'plansız'})")
    if ev:
        lines.append("Olay çizelgesi:\n" + "\n".join(ev[:25]))

    data_block = "\n".join(lines)
    return (
        "Sen kıdemli bir bakım/güvenilirlik (reliability) mühendisisin. Aşağıdaki CNC "
        "makinesine ait kök-neden verisini analiz et.\n\n"
        f"{data_block}\n\n"
        "Türkçe, kısa ve teknik bir rapor yaz. Şu başlıkları kullan (markdown):\n"
        "## Özet Teşhis\n## En Olası Kök Neden\n## Destekleyen Kanıtlar\n"
        "## Önerilen Aksiyonlar (önceliklendirilmiş)\n## Önleyici Bakım Notu\n"
        "Veride olmayan çıkarımları 'varsayım' diye etiketle. Kısa madde işaretleri kullan."
    )


def _local_rca_summary(card: dict, dev: dict | None) -> str:
    """Gemini yoksa kart verisinden yerel (markdown) özet üretir."""
    rank = {"Yüksek": 3, "Orta": 2, "Düşük": 1}
    top = max(card.get("hypotheses", []), key=lambda h: rank.get(h["likelihood"], 0), default=None)
    out = ["## Özet Teşhis", card.get("summary", ""), "", "## En Olası Kök Neden"]
    out.append(f"- {top['hypothesis']} (ihtimal: {top['likelihood']})" if top else "- Yeterli kanıt yok.")
    out += ["", "## Destekleyen Kanıtlar", f"- {card.get('evidence', '')}"]
    if dev and dev.get("available"):
        out.append(f"- {dev['summary']}")
    if card.get("downtime_context"):
        dc = card["downtime_context"]
        out.append(f"- Vardiya {dc['shift_date']}: {dc['total_unplanned_h']:.1f} saat plansız duruş")
    out += ["", "## Önerilen Aksiyonlar"]
    for al in card["alarms"]:
        out.append(f"- **{al['message']}**: {al['recommendation']}")
    return "\n".join(out)


def analyze_root_cause(machine: str, date: str, window_min: int | None = None) -> dict:
    """
    Kök neden verisini Gemini'ye gönderip detaylı analiz alır.
    Anahtar yoksa veya hata olursa kart verisinden YEREL özet döner (sayfa hep çalışır).
    """
    card = get_root_cause(machine, date, window_min)  # JSON-güvenli (string zamanlar)
    if not card.get("has_alarm"):
        return {"machine": machine, "date": date, "has_alarm": False,
                "source": "none", "analysis": card.get("summary", "")}

    unit_uid = _resolve(machine)
    try:
        dev = _jsonify(rca.deviation_analysis(unit_uid, card["primary_time"]))
    except Exception:  # noqa: BLE001
        dev = None
    prompt = _build_rca_prompt(machine, date, card, dev)

    if ai.is_configured():
        try:
            text = ai.call_gemini(prompt)
            return {"machine": machine, "date": date, "has_alarm": True,
                    "source": "gemini", "model": settings.gemini_model, "analysis": text}
        except Exception as exc:  # noqa: BLE001 — Gemini hatasında yerele düş
            return {"machine": machine, "date": date, "has_alarm": True, "source": "local",
                    "note": f"Gemini kullanılamadı: {exc}", "analysis": _local_rca_summary(card, dev)}
    return {"machine": machine, "date": date, "has_alarm": True, "source": "local",
            "analysis": _local_rca_summary(card, dev)}


# ---------------------------------------------------------------------------
# İŞ EMİRLERİ & STOK
# ---------------------------------------------------------------------------

def _shift_window(date: str):
    """Vardiya penceresi [gün 21:00 UTC, +24s) — OEE/duruş (oee_summary ile uyumlu)."""
    start = pd.Timestamp(date, tz="UTC") + pd.Timedelta(hours=21)
    return start, start + pd.Timedelta(hours=24)


def _calendar_window(date: str):
    """Takvim günü [gün 00:00 UTC, +24s) — iş emri/stok/sayaç (kullanıcı beklentisi)."""
    start = pd.Timestamp(date, tz="UTC")
    return start, start + pd.Timedelta(hours=24)


def list_workorders(machine: str, date: str) -> dict:
    """Bir makinenin vardiya günündeki iş emri çalışmaları."""
    unit_uid = _resolve(machine)
    wo = repository.workorders()
    start, end = _calendar_window(date)  # takvim günü (off-by-one düzeltmesi)
    m = wo[(wo["unit_uid"] == unit_uid) & (wo["started_on"] >= start) & (wo["started_on"] < end)]
    m = m.sort_values("started_on")
    orders = []
    for r in m.itertuples(index=False):
        dur = r.duration_milliseconds
        # Çevrim, çalışma süresini AŞAMAZ -> süreye clamp (mantıksal tutarlılık).
        cyc = None if pd.isna(r.stock_cycle) else min(float(r.stock_cycle), float(dur))
        orders.append({
            "order_no": _native(r.order_no),
            "is_stock": bool(r.is_stock == "t") if isinstance(r.is_stock, str) else bool(r.is_stock),
            "started_on": _native(r.started_on),
            "ended_on": _native(r.ended_on),
            "duration_ms": _native(dur),
            "stock_cycle_ms": _native(cyc),
            "planned_quantity": _native(r.planned_quantity),
        })
    return {"machine": machine, "unit_uid": unit_uid, "date": date,
            "count": len(orders), "orders": orders}


def stock_summary(machine: str, start: str, end: str | None = None) -> dict:
    """
    Stok / Program Özeti — TAMAMEN GERÇEK dataset verisi (uydurma yok).

    Kaynak: trex_mes_workorder (program/runs/süre/çevrim) + trex_mes_counter_slice
    (üretilen adet, COUNT artışları). Tarih aralığı TAKVİM penceresi.

    Sütunlar:
      - Çalışma Sayısı = o programın iş emri kaydı sayısı (gerçek)
      - Toplam Süre = duration_milliseconds toplamı (gerçek)
      - Ort. Çevrim = stock_cycle ortalaması, süreye clamp'li (gerçek alan)
      - Üretilen Adet = iş emri zaman pencerelerindeki sayaç artışları (gerçek)
    Not: planned_quantity dataset'te hep 0, fire/hedef veri setinde yok -> gösterilmez.
    """
    unit_uid = _resolve(machine)
    end = end or start
    cstart = pd.Timestamp(start, tz="UTC")
    cend = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)

    wo = repository.workorders()
    m = wo[(wo["unit_uid"] == unit_uid) & (wo["started_on"] >= cstart) & (wo["started_on"] < cend)]

    # Sayaç (COUNT) dilimleri — üretilen adet için
    c = repository.counter_slices()
    cw = c[(c["unit_uid"] == unit_uid) & (c["signal_type"] == "COUNT")
           & (~c["exclude_from_oee"]) & (c["slice_on"] >= cstart) & (c["slice_on"] < cend)][["slice_on", "value"]]

    agg = {}  # order_no -> toplamlar
    for r in m.itertuples(index=False):
        o = str(r.order_no)
        a = agg.setdefault(o, {"runs": 0, "dur": 0.0, "produced": 0.0, "cyc": []})
        a["runs"] += 1
        a["dur"] += float(r.duration_milliseconds)
        # bu iş emri penceresindeki sayaç artışları = üretilen parça (gerçek)
        a["produced"] += float(cw.loc[(cw["slice_on"] >= r.started_on)
                                      & (cw["slice_on"] <= r.ended_on), "value"].sum())
        if pd.notna(r.stock_cycle):
            a["cyc"].append(min(float(r.stock_cycle), float(r.duration_milliseconds)))  # çevrim<=süre

    items = [{
        "order_no": o,
        "runs": a["runs"],
        "total_duration_ms": a["dur"],
        "avg_cycle_ms": (sum(a["cyc"]) / len(a["cyc"])) if a["cyc"] else None,
        "produced": int(round(a["produced"])),
    } for o, a in agg.items()]
    items.sort(key=lambda x: x["total_duration_ms"], reverse=True)

    return {
        "machine": machine, "unit_uid": unit_uid, "start": start, "end": end,
        "count": len(items),
        "total_runs": sum(i["runs"] for i in items),
        "total_duration_ms": sum(i["total_duration_ms"] for i in items),
        "total_produced": sum(i["produced"] for i in items),
        "items": items,
    }


# ---------------------------------------------------------------------------
# RCA — Referans Sapması (Teknik 3)
# ---------------------------------------------------------------------------

def get_deviation(machine: str, center: str, signal: str = "CYCLE_TIME_MS",
                  window_min: int | None = None) -> dict:
    """Bir telemetri sinyalinin olay anındaki istatistiksel sapması."""
    unit_uid = _resolve(machine)
    dev = rca.deviation_analysis(unit_uid, center, signal_name=signal, window_min=window_min)
    return _jsonify({"machine": machine, "unit_uid": unit_uid, "center": center, **dev})


# ---------------------------------------------------------------------------
# FİLO (çapraz-makine, Platinum)
# ---------------------------------------------------------------------------

def fleet_overview(date: str) -> dict:
    """Tüm etkin makinelerin o gündeki OEE/A/plansız özetini OEE'ye göre sıralar."""
    rows = []
    for m in list_machines():
        if not m["is_enabled"]:
            continue
        try:
            b = get_baseline(m["name"], date)
        except ValueError:
            continue  # o gün veri yok
        rows.append({
            "machine": m["name"], "unit_uid": m["unit_uid"],
            "oee": b["oee"], "availability": b["availability"]["A"],
            "performance": b["performance"]["P"], "quality": b["quality"]["Q"],
            "unplanned_stop_ms": b["availability"]["unplanned_stop_ms"],
            "unplanned_stop_h": b["availability"]["unplanned_stop_h"],
        })
    rows.sort(key=lambda r: r["oee"])  # en kötü OEE üstte (öncelik)
    return {"date": date, "count": len(rows), "machines": rows}


def fleet_alarm_patterns(min_machines: int = 2, top_n: int = 15) -> dict:
    """Birden fazla makinede görülen ortak alarm örüntüleri (filo geneli)."""
    al = repository.alerts()
    units = core.load_units().set_index("uid")["name"].to_dict()
    g = al.groupby("message").agg(
        total=("message", "size"),
        machines=("unit_uid", lambda s: sorted(set(s))),
    ).reset_index()
    g["machine_count"] = g["machines"].apply(len)
    g = g[g["machine_count"] >= min_machines].sort_values(
        ["machine_count", "total"], ascending=False).head(top_n)
    items = [{
        "message": _native(r.message),
        "total": _native(r.total),
        "machine_count": _native(r.machine_count),
        "machines": [units.get(u, u) for u in r.machines],
    } for r in g.itertuples(index=False)]
    return {"count": len(items), "items": items}
