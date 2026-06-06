"""
KÖK NEDEN ANALİZİ (RCA) — Faz 3
================================

Üretim anomalilerini (alarmlar, duruşlar, performans düşüşleri) telemetri ve
olay korelasyonu ile açıklar. Üç katmanı birleştirir:
    RCA (NEDEN) -> What-If (DÜZELTİRSEK) -> Finans (ROI).

Veri kaynakları:
    - trex_mes_alert      : ayrıştırılmış CNC alarm metinleri (giriş noktası)
    - trex_mes_stoppage_slice : duruş eventleri (ne zaman durdu)
    - trex_nightwatch_data_*  : numeric telemetri (run durumu vb. — KANIT)

Fonksiyonlar:
    get_alerts        : bir makinenin alarmları (opsiyonel gün filtresi)
    alert_pareto      : en sık tekrarlayan alarmlar (recurrence)
    build_timeline    : bir an etrafında alarm + duruş + telemetri (±dakika)
    root_cause_card   : kanıtlı kök neden kartı + öneri
"""

from __future__ import annotations

import pandas as pd

import nightwatch_repo as nw
import repository
from config import settings
from oee_baseline import fmt_hms, ms_to_hours
from oee_whatif import get_unplanned_by_reason, reason_name

# Alarm metnine göre önerilen aksiyon (substring eşleşmesi, normalize edilmiş).
RECOMMENDATIONS = {
    "AIR PRESSURE FAILED": "Pnömatik hat basıncını, kompresör ve regülatör bakımını kontrol edin; vardiya başı basınç teyit prosedürü ekleyin.",
    "Z AXIS NEED": "Vardiya başı eksen referanslama (homing) prosedürünü standartlaştırın; Z ekseni enkoder/limit switch kontrolü yapın.",
    "EMERGENCY STOP": "Acil-stop tetikleyicilerini, kapı ve emniyet devrelerini inceleyin; operatör eğitimini gözden geçirin.",
    "MOTOR OVERLOAD": "Motor yükünü, soğutmayı ve mekanik sıkışma/yatak durumunu kontrol edin.",
    "DOOR INTERLOCK": "Kapı kilidi sensörü ve kablajını kontrol edin; gevşek bağlantı/temassızlık arayın.",
    "CHUCK UNCLAMP": "Ayna (chuck) kavrama basıncını ve kavrama sensörünü kontrol edin.",
    "OVERTRAVEL": "Eksen soft-limit ayarlarını ve iş parçası konumlandırmasını gözden geçirin.",
    "LUBE OIL": "Yağlama yağı seviyesini ve pompasını kontrol edin; periyodik dolum planı oluşturun.",
}


def recommend(message: str) -> str:
    """Alarm metnine göre önerilen aksiyonu döndürür."""
    norm = str(message).upper()
    for key, action in RECOMMENDATIONS.items():
        if key in norm:
            return action
    return "Alarm tekrar paternini inceleyin ve ilgili alt sistemde (bakım) kök neden araştırması yapın."


# ---------------------------------------------------------------------------
# ALARMLAR
# ---------------------------------------------------------------------------

def get_alerts(unit_uid: str, date: str | None = None) -> pd.DataFrame:
    """
    Bir makinenin alarmları (started_on'a göre sıralı).
    date verilirse o takvim gününe (UTC) filtreler.
    Sütunlar: started_on, message, reading_def_uid
    """
    al = repository.alerts()
    m = al.loc[al["unit_uid"] == unit_uid].copy()
    if date is not None:
        target = pd.Timestamp(date).date()
        m = m[m["started_on"].dt.date == target]
    return m.sort_values("started_on")[["started_on", "message", "reading_def_uid"]]


def alert_pareto(unit_uid: str | None = None, top_n: int = 10) -> pd.DataFrame:
    """
    En sık tekrarlayan alarm metinleri (recurrence). unit_uid None ise tesis geneli.
    Sütunlar: message, count, first_seen, last_seen
    """
    al = repository.alerts()
    if unit_uid is not None:
        al = al.loc[al["unit_uid"] == unit_uid]
    g = (al.groupby("message")
           .agg(count=("message", "size"),
                first_seen=("started_on", "min"),
                last_seen=("started_on", "max"))
           .reset_index()
           .sort_values("count", ascending=False))
    return g.head(top_n)


# ---------------------------------------------------------------------------
# OLAY ZAMAN ÇİZELGESİ (alarm + duruş + telemetri)
# ---------------------------------------------------------------------------

def _stoppages_overlapping(unit_uid: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Pencereyle örtüşen duruş dilimleri (isimleriyle)."""
    s = repository.stoppage_slices()
    mask = (
        (s["unit_uid"] == unit_uid)
        & (s["started_on"] < end)
        & (s["ended_on"] > start)
    )
    ov = s.loc[mask].copy()
    rd = repository.reading_def_lookup()
    ov["reason"] = ov["reading_def_uid"].map(lambda u: reason_name(rd, u))
    return ov.sort_values("started_on")


def build_timeline(unit_uid: str, center, window_min: int | None = None) -> dict:
    """
    Bir an (center) etrafında ±window_min dakikalık olay çizelgesi:
    alarmlar + duruşlar + telemetri geçişleri (run durumu vb.).
    """
    window_min = window_min or settings.rca_window_minutes
    center = pd.Timestamp(center)
    if center.tzinfo is None:
        center = center.tz_localize("UTC")
    start = center - pd.Timedelta(minutes=window_min)
    end = center + pd.Timedelta(minutes=window_min)

    # Alarmlar
    al = repository.alerts()
    am = al[(al["unit_uid"] == unit_uid) & (al["started_on"] >= start) & (al["started_on"] <= end)]
    alerts = [{"time": t, "message": m} for t, m in zip(am["started_on"], am["message"])]

    # Duruşlar
    stp = _stoppages_overlapping(unit_uid, start, end)
    stoppages = [{
        "started_on": r.started_on, "ended_on": r.ended_on, "reason": r.reason,
        "is_planned": bool(r.is_planned), "duration_ms": int(r.duration_milliseconds),
    } for r in stp.itertuples(index=False)]

    # Telemetri (run durumu + execution) geçişleri — KANIT
    tel = nw.telemetry_window(unit_uid, start, end,
                              signal_names=["STATINFO_RUN", "EXECUTION"])
    tel_t = nw.transitions(tel)
    telemetry = [{"time": r.time, "signal": r.signal, "value": r.value}
                 for r in tel_t.itertuples(index=False)]

    return {
        "center": center, "window_min": window_min,
        "window_start": start, "window_end": end,
        "alerts": alerts, "stoppages": stoppages, "telemetry": telemetry,
    }


# ---------------------------------------------------------------------------
# KÖK NEDEN KARTI
# ---------------------------------------------------------------------------

def _shift_date_of(ts: pd.Timestamp) -> str:
    """Bir an'ın ait olduğu vardiya gününü (21:00 UTC sınırı) döndürür (YYYY-MM-DD)."""
    return (ts - pd.Timedelta(hours=21)).date().isoformat()


def root_cause_card(unit_uid: str, date: str, window_min: int | None = None) -> dict:
    """
    Bir makine/gün için kanıtlı kök neden kartı:
      - günün alarmları + her birinin TÜM GEÇMİŞTEKİ tekrar sayısı (recurrence)
      - birincil alarm etrafında olay çizelgesi (telemetri kanıtı dahil)
      - run-durumu kanıtı (alarm anında makine durdu mu?)
      - önerilen aksiyon
      - o vardiya günündeki plansız duruş bağlamı (What-If/ROI köprüsü)
    """
    window_min = window_min or settings.rca_window_minutes
    alerts_today = get_alerts(unit_uid, date)

    if alerts_today.empty:
        return {
            "unit_uid": unit_uid, "date": date, "has_alarm": False,
            "summary": f"{date} gününde bu makine için kayıtlı alarm yok.",
            "alarms": [], "timeline": None, "downtime_context": None,
        }

    # Birincil olay = günün ilk alarmı
    primary_time = alerts_today["started_on"].min()

    # Günün alarmları + tüm geçmişteki tekrar sayısı
    pareto = alert_pareto(unit_uid, top_n=1000).set_index("message")
    alarms = []
    for msg in alerts_today["message"].unique():
        rec = int(pareto.loc[msg, "count"]) if msg in pareto.index else 1
        alarms.append({
            "message": msg,
            "recurrence_total": rec,
            "first_seen": pareto.loc[msg, "first_seen"] if msg in pareto.index else primary_time,
            "last_seen": pareto.loc[msg, "last_seen"] if msg in pareto.index else primary_time,
            "recommendation": recommend(msg),
        })
    alarms.sort(key=lambda a: a["recurrence_total"], reverse=True)

    # Olay çizelgesi (telemetri kanıtı)
    timeline = build_timeline(unit_uid, primary_time, window_min)

    # Run-durumu kanıtı: alarm anında YÜRÜRLÜKTEKİ STATINFO_RUN değeri (alarmdan
    # önceki son geçiş; numune alarmdan birkaç yüz ms önce/sonra olabilir).
    run_trans = sorted([t for t in timeline["telemetry"] if t["signal"] == "STATINFO_RUN"],
                       key=lambda x: x["time"])
    effective_run = None
    for t in run_trans:
        if t["time"] <= primary_time:
            effective_run = str(t["value"]).strip()
        else:
            break
    if effective_run is None and run_trans:  # alarm penceredeki ilk numuneden önceyse
        effective_run = str(run_trans[0]["value"]).strip()
    stopped = effective_run in ("0", "0.0")
    evidence = (
        f"Alarm anında ({primary_time:%H:%M:%S}) run-durumu (STATINFO_RUN) = 0 "
        f"-> makine duruyordu; telemetri alarmı doğruluyor."
        if stopped else
        f"Alarm anında run-durumu (STATINFO_RUN) = {effective_run}; net duruş kanıtı yok."
    )

    # Plansız duruş bağlamı (vardiya günü) — What-If/ROI köprüsü
    downtime_context = None
    try:
        shift_date = _shift_date_of(primary_time)
        agg = get_unplanned_by_reason(unit_uid, shift_date)
        total_ms = float(agg["total_ms"].sum())
        downtime_context = {
            "shift_date": shift_date,
            "total_unplanned_ms": total_ms,
            "total_unplanned_h": ms_to_hours(total_ms),
            "top_reasons": [
                {"reason": r.reason, "hours": ms_to_hours(r.total_ms)}
                for r in agg.head(3).itertuples(index=False)
            ],
            "note": "Tekrarlayan alarmı kalıcı çözmek bu plansız duruşu azaltır -> What-If/ROI ile parasal etki hesaplanabilir.",
        }
    except Exception:
        downtime_context = None

    primary = alarms[0]
    summary = (
        f"{date}: '{primary['message']}' (toplam {primary['recurrence_total']} kez tekrarlamış). "
        f"{evidence}"
    )

    return {
        "unit_uid": unit_uid, "date": date, "has_alarm": True,
        "primary_time": primary_time, "summary": summary,
        "evidence": evidence, "run_stopped_at_alarm": stopped,
        "alarms": alarms, "timeline": timeline, "downtime_context": downtime_context,
    }
