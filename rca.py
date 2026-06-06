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
from oee_baseline import ms_to_hours
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


# Makine tipine göre RCA sinyalleri (Slayt 7 matrisi). Mevcut sinyallerden ilk eşleşeni seçer.
# Run/durum sinyali öncelik sırası (Fanuc -> Mitsubishi):
_RUN_KEYS = ["STATINFO_RUN", "RUN_STATUS_START", "RUN_STATUS", "ISNOTRUNNING", "EXECUTION"]
# Sapma (sürekli numerik) sinyali. "CYCLE_TIME" hem Fanuc (CYCLE_TIME_MS) hem
# Mitsubishi (CYCLE_TIME_M800) ile eşleşir; sonra güç/sıcaklık/yük.
_DEV_KEYS = ["CYCLE_TIME", "POWER_CONSUMPTION", "SERVO_MOTOR_TEMPERATURE",
             "TEMPERATURE", "PATH_LOAD", "LOAD"]


def pick_signals(unit_uid: str) -> dict:
    """Makinenin GERÇEK mevcut sinyallerinden run ve sapma sinyalini seçer (tip-agnostik)."""
    try:
        names = nw.signal_map(unit_uid)["readingdef_name"].astype(str).tolist()
    except Exception:  # noqa: BLE001
        names = []
    upper = [(n, n.upper()) for n in names]

    def find(keys):
        for k in keys:
            for orig, up in upper:
                if k in up:
                    return orig
        return None

    return {"run": find(_RUN_KEYS), "dev": find(_DEV_KEYS)}


def build_timeline(unit_uid: str, center, window_min: int | None = None,
                   post_min: int | None = None) -> dict:
    """
    Bir an (center) etrafında [-window_min, +post_min] dk olay çizelgesi (Slayt: -15/+5):
    alarmlar + duruşlar + telemetri geçişleri (makineye göre seçilen run sinyali).
    """
    window_min = window_min or settings.rca_window_minutes
    post_min = post_min if post_min is not None else settings.rca_post_minutes
    center = pd.Timestamp(center)
    if center.tzinfo is None:
        center = center.tz_localize("UTC")
    start = center - pd.Timedelta(minutes=window_min)
    end = center + pd.Timedelta(minutes=post_min)

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

    # Telemetri (makineye göre seçilen run sinyali) geçişleri — KANIT
    run_sig = pick_signals(unit_uid)["run"]
    telemetry = []
    if run_sig:
        tel = nw.telemetry_window(unit_uid, start, end, signal_names=[run_sig])
        tel_t = nw.transitions(tel)
        telemetry = [{"time": r.time, "signal": r.signal, "value": r.value}
                     for r in tel_t.itertuples(index=False)]

    return {
        "center": center, "window_min": window_min, "post_min": post_min,
        "window_start": start, "window_end": end, "run_signal": run_sig,
        "alerts": alerts, "stoppages": stoppages, "telemetry": telemetry,
    }


# ---------------------------------------------------------------------------
# TEKNİK 3: REFERANS SAPMASI (istatistiksel anomali)
# ---------------------------------------------------------------------------

def deviation_analysis(unit_uid: str, center, signal_name: str = "CYCLE_TIME_MS",
                       window_min: int | None = None,
                       baseline_window_min: int = 360, z_threshold: float = 2.0) -> dict:
    """
    Bir telemetri sinyalinin (vars. CYCLE_TIME_MS) baz ortalamadan istatistiksel
    sapmasını bulur (Gold kriteri). Geniş bir pencerede ortalama/std hesaplar,
    odak penceresindeki noktaların z-skorunu çıkarır, |z|>eşik olanları işaretler.
    """
    window_min = window_min or settings.rca_window_minutes
    center = pd.Timestamp(center)
    if center.tzinfo is None:
        center = center.tz_localize("UTC")
    wide_start = center - pd.Timedelta(minutes=baseline_window_min)
    wide_end = center + pd.Timedelta(minutes=baseline_window_min)

    tel = nw.telemetry_window(unit_uid, wide_start, wide_end, signal_names=[signal_name])
    if tel.empty:
        return {"signal": signal_name, "available": False,
                "summary": f"{signal_name} için bu pencerede telemetri yok."}

    tel = tel.copy()
    tel["num"] = pd.to_numeric(tel["value"], errors="coerce")
    tel = tel.dropna(subset=["num"])
    mean = float(tel["num"].mean())
    std = float(tel["num"].std()) or 0.0

    foc_start = center - pd.Timedelta(minutes=window_min)
    foc_end = center + pd.Timedelta(minutes=window_min)
    focus = tel[(tel["time"] >= foc_start) & (tel["time"] <= foc_end)].copy()
    focus["z"] = (focus["num"] - mean) / std if std > 0 else 0.0

    anomalies = focus[focus["z"].abs() > z_threshold]
    points = [{"time": t, "value": float(v), "z": float(z)}
              for t, v, z in zip(focus["time"], focus["num"], focus["z"])]
    max_z = float(focus["z"].abs().max()) if not focus.empty else 0.0

    summary = (
        f"{signal_name}: baz ortalama {mean:,.0f} ± {std:,.0f}. "
        + (f"Olay penceresinde {len(anomalies)} anomali (|z|>{z_threshold}, en yüksek |z|={max_z:.1f}) "
           f"-> istatistiksel sapma kök neden kanıtını destekliyor."
           if len(anomalies) else
           f"Olay penceresinde belirgin sapma yok (en yüksek |z|={max_z:.1f}).")
    )
    return {
        "signal": signal_name, "available": True,
        "baseline_mean": mean, "baseline_std": std,
        "z_threshold": z_threshold, "anomaly_count": int(len(anomalies)),
        "max_abs_z": max_z, "points": points, "summary": summary,
    }


# ---------------------------------------------------------------------------
# KÖK NEDEN KARTI
# ---------------------------------------------------------------------------

def _build_hypotheses(primary_msg: str, recurrence: int, run_stopped: bool,
                      downtime_context: dict | None) -> list[dict]:
    """
    Birincil alarm için hipotez–kanıt–sonuç–ihtimal matrisi üretir (kural tabanlı).
    """
    hyps = []
    # H1: Tekrar eden donanım/sistem arızası
    hyps.append({
        "hypothesis": "Tekrar eden donanım/sistem arızası (kalıcı kök neden).",
        "expected": "Aynı alarm geçmişte çok sayıda tekrarlamış olmalı.",
        "data_result": f"{recurrence} kez tekrarlamış.",
        "likelihood": "Yüksek" if recurrence >= 5 else ("Orta" if recurrence >= 2 else "Düşük"),
    })
    # H2: Alarm üretimi durdurdu (anlık etki)
    hyps.append({
        "hypothesis": "Alarm makineyi anında durdurdu (üretim kaybı).",
        "expected": "Alarm anında run-durumu sinyali 0 olmalı.",
        "data_result": "Run-durumu 0 (durdu)." if run_stopped else "Net duruş kanıtı yok.",
        "likelihood": "Yüksek" if run_stopped else "Düşük",
    })
    # H3: Operatör/sınıflandırma kaynaklı (tanımsız duruş ağırlığı)
    top = (downtime_context or {}).get("top_reasons", [])
    undefined_heavy = any("Undefined" in r["reason"] or "Tanımsız" in r["reason"] for r in top)
    hyps.append({
        "hypothesis": "Operatör/sınıflandırma kaynaklı (mekanik arıza değil).",
        "expected": "Tanımsız (Undefined) duruşların payı yüksek olmalı.",
        "data_result": "Tanımsız duruş baskın." if undefined_heavy else "Tanımsız duruş baskın değil.",
        "likelihood": "Orta" if undefined_heavy else "Düşük",
    })
    return hyps

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

    # Run-durumu kanıtı: alarm anında YÜRÜRLÜKTEKİ run sinyali değeri (makineye göre
    # seçilen sinyal; alarmdan önceki son geçiş). build_timeline yalnız run sinyalini çeker.
    run_sig = timeline.get("run_signal")
    run_trans = sorted(timeline["telemetry"], key=lambda x: x["time"])
    effective_run = None
    for t in run_trans:
        if t["time"] <= primary_time:
            effective_run = str(t["value"]).strip()
        else:
            break
    if effective_run is None and run_trans:  # alarm penceredeki ilk numuneden önceyse
        effective_run = str(run_trans[0]["value"]).strip()
    stopped = effective_run in ("0", "0.0")
    sig_label = run_sig or "run-durumu"
    if effective_run is None:
        evidence = "Bu makine için run-durumu telemetrisi bulunamadı (sinyal yok)."
    elif stopped:
        evidence = (f"Alarm anında ({primary_time:%H:%M:%S}) {sig_label} = 0 "
                    f"-> makine duruyordu; telemetri alarmı doğruluyor.")
    else:
        evidence = f"Alarm anında {sig_label} = {effective_run}; net duruş kanıtı yok."

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
    hypotheses = _build_hypotheses(primary["message"], primary["recurrence_total"],
                                   stopped, downtime_context)

    return {
        "unit_uid": unit_uid, "date": date, "has_alarm": True,
        "primary_time": primary_time, "summary": summary,
        "evidence": evidence, "run_stopped_at_alarm": stopped,
        "alarms": alarms, "timeline": timeline, "downtime_context": downtime_context,
        "hypotheses": hypotheses,
    }
