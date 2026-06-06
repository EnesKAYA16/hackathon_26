"""
FASTAPI BACKEND — OEE What-If & RCA
===================================

Web frontend'in tüketeceği HTTP/JSON API. İnce bir katman: tüm iş servis
katmanında (service.py), o da çekirdeği (oee_baseline/oee_whatif) çağırır.

Çalıştırma (hackathon_26/ içinden):
    uvicorn api:app --reload --port 8000

Etkileşimli dokümantasyon (otomatik):
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import repository
import service
from config import settings


# ---------------------------------------------------------------------------
# Pydantic response/request modelleri (otomatik /docs şeması için)
# ---------------------------------------------------------------------------

class MachineOut(BaseModel):
    name: str
    unit_uid: str
    is_enabled: bool


class AvailabilityOut(BaseModel):
    A: float
    work_total_ms: float
    planned_stop_ms: float
    unplanned_stop_ms: float
    scheduled_time_ms: float
    run_time_ms: float
    unplanned_stop_h: float


class PerformanceOut(BaseModel):
    P: float
    working_time_ms: float
    planned_time_ms: float
    raw_ratio: float


class QualityOut(BaseModel):
    Q: float
    product_sum: float
    scrape_sum: float


class BaselineOut(BaseModel):
    machine: str
    unit_uid: str
    date: str
    trans_date: str | None
    availability: AvailabilityOut
    performance: PerformanceOut
    quality: QualityOut
    oee: float
    oee_recomputed: float
    validation_delta: float


class ParetoItemOut(BaseModel):
    rank: int
    reason: str
    category: str | None
    reading_def_uid: str
    events: int
    total_ms: float
    total_hours: float
    pct: float
    cumulative_pct: float


class ParetoOut(BaseModel):
    machine: str
    unit_uid: str
    date: str
    total_unplanned_ms: float
    total_unplanned_h: float
    items: list[ParetoItemOut]


class FinanceIn(BaseModel):
    """Finansal varsayımlar (opsiyonel; verilmezse docs/02 varsayılanları)."""
    contribution_margin_per_piece: float = 12.0
    machine_hour_cost: float = 45.0
    downtime_cost_per_hour: float = 80.0
    scrap_cost_per_piece: float = 18.0
    intervention_cost: float = 300.0
    pieces_per_hour_override: float | None = None
    horizon_days: int = 30
    currency: str = "₺"


class WhatIfRequest(BaseModel):
    machine: str = Field(examples=["Makine 1"])
    date: str = Field(examples=["2025-11-10"])
    durus_nedeni: str | None = Field(default=None, examples=["System Offline"])
    azaltma_yuzdesi: float = Field(default=0.0, ge=0.0, le=1.0, examples=[0.20])  # W1
    reclassify: bool = Field(default=False, description="W2: PLANSIZ->PLANLI")    # W2
    cycle_improvement_pct: float = Field(default=0.0, ge=0.0, lt=1.0, examples=[0.10])  # W3 (P)
    scrap_rate: float = Field(default=0.0, ge=0.0, lt=1.0, examples=[0.03])       # W4 (Q)
    finance: FinanceIn | None = Field(default=None,
                                      description="Opsiyonel finansal varsayımlar")


class FinancialOut(BaseModel):
    currency: str
    is_assumption: bool
    pieces_per_hour: float
    pieces_per_hour_is_estimated: bool
    recovered_hours: float
    extra_pieces: float
    gross_benefit: float
    downtime_saving: float
    daily_benefit: float
    intervention_cost: float
    net_benefit_first_day: float
    payback_days: float | None
    horizon_days: int
    horizon_net_benefit: float
    roi: float | None
    assumptions: dict


class StateOut(BaseModel):
    unplanned_stop_ms: float
    availability: float
    performance: float
    quality: float
    oee: float


class DeltaOut(BaseModel):
    availability_pp: float
    performance_pp: float
    quality_pp: float
    oee_pp: float
    oee_relative_pct: float


class WhatIfOut(BaseModel):
    machine: str
    unit_uid: str
    date: str
    durus_nedeni: str | None
    azaltma_yuzdesi: float
    reclassify: bool
    cycle_improvement_pct: float
    scrap_rate: float
    share: float
    reason_official_ms: float
    reduced_ms: float
    recovered_hours: float
    before: StateOut
    after: StateOut
    delta: DeltaOut
    waterfall: dict
    financial: FinancialOut


# --- RCA modelleri ---

class AlertItem(BaseModel):
    started_on: str
    message: str


class AlertsOut(BaseModel):
    machine: str
    unit_uid: str
    date: str | None
    count: int
    alerts: list[AlertItem]


class ParetoAlertItem(BaseModel):
    message: str
    count: int
    first_seen: str
    last_seen: str


class AlertParetoOut(BaseModel):
    machine: str | None
    unit_uid: str | None
    items: list[ParetoAlertItem]


# ---------------------------------------------------------------------------
# Uygulama kurulumu
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Başlangıçta CSV'leri belleğe ısıt -> ilk istek de hızlı olsun.
    repository.warm_cache()
    yield


app = FastAPI(
    title="OEE What-If & RCA API",
    description="Endüstriyel OEE baz hesabı, plansız duruş Pareto'su ve What-If simülasyonu.",
    version="1.0.0",
    lifespan=lifespan,
)

# Frontend farklı origin'den çağıracağı için CORS (origin listesi .env'den).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _guard(call):
    """Servis çağrılarını sarmalar: ValueError -> uygun HTTP hatası."""
    try:
        return call()
    except ValueError as exc:
        msg = str(exc)
        # 'bulunamadı' -> kaynak yok (404), aksi halde geçersiz girdi (400).
        status = 404 if "bulunamadı" in msg or "kaydı yok" in msg else 400
        raise HTTPException(status_code=status, detail=msg)


# ---------------------------------------------------------------------------
# Endpoint'ler
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root():
    return {"status": "ok", "docs": "/docs",
            "endpoints": ["/machines", "/machines/{machine}/dates",
                          "/oee/baseline", "/oee/pareto", "/oee/whatif",
                          "/oee/stoppage-trend", "/oee/trend", "/oee/counter-trend",
                          "/finance/assumptions",
                          "/rca/alerts", "/rca/alert-pareto",
                          "/rca/timeline", "/rca/root-cause", "/rca/deviation",
                          "/workorders", "/stock",
                          "/fleet/overview", "/fleet/alarm-patterns"]}


@app.get("/machines", response_model=list[MachineOut], tags=["catalog"])
def machines():
    """Tüm makineleri listeler (frontend dropdown'u için)."""
    return _guard(service.list_machines)


@app.get("/machines/{machine}/dates", response_model=list[str], tags=["catalog"])
def machine_dates(machine: str):
    """Bir makine için OEE kaydı olan vardiya günlerini listeler."""
    return _guard(lambda: service.list_dates(machine))


@app.get("/oee/baseline", response_model=BaselineOut, tags=["oee"])
def baseline(machine: str = Query(examples=["Makine 1"]),
             date: str = Query(examples=["2025-11-10"])):
    """Bir makine/gün için baz OEE (A x P x Q) ayrıştırması."""
    return _guard(lambda: service.get_baseline(machine, date))


@app.get("/oee/pareto", response_model=ParetoOut, tags=["oee"])
def pareto(machine: str = Query(examples=["Makine 1"]),
           date: str = Query(examples=["2025-11-10"]),
           top_n: int = Query(5, ge=1, le=50)):
    """En çok süre kaybettiren ilk N plansız duruş nedeni (Pareto)."""
    return _guard(lambda: service.get_pareto(machine, date, top_n))


@app.get("/finance/assumptions", tags=["finance"])
def finance_assumptions():
    """Varsayılan finansal varsayımlar (frontend formunu önceden doldurmak için)."""
    return _guard(service.default_finance_assumptions)


@app.get("/oee/stoppage-trend", tags=["oee"])
def stoppage_trend(machine: str = Query(examples=["Makine 1"]),
                   date: str = Query(examples=["2025-11-10"])):
    """Vardiya günü boyunca saatlik planlı/plansız duruş süresi (zaman serisi)."""
    return _guard(lambda: service.stoppage_trend(machine, date))


@app.get("/oee/trend", tags=["oee"])
def oee_trend(machine: str = Query(examples=["Makine 1"]),
              days: int = Query(30, ge=2, le=180),
              start: str | None = Query(default=None, examples=["2025-10-20"]),
              end: str | None = Query(default=None, examples=["2025-11-20"])):
    """Bir makinenin OEE/A/P trendi (start+end aralığı veya son N gün)."""
    return _guard(lambda: service.oee_trend(machine, days, start, end))


@app.get("/oee/counter-trend", tags=["oee"])
def counter_trend(machine: str = Query(examples=["Makine 1"]),
                  date: str = Query(examples=["2025-11-10"])):
    """Vardiya günü boyunca saatlik üretilen parça (sayaç)."""
    return _guard(lambda: service.counter_trend(machine, date))


@app.post("/oee/whatif", response_model=WhatIfOut, tags=["oee"])
def whatif(req: WhatIfRequest):
    """Bir duruş nedenini X% azaltmanın OEE + finansal (ROI) etkisini simüle eder."""
    finance_inputs = req.finance.model_dump() if req.finance else None
    return _guard(lambda: service.run_whatif(
        req.machine, req.date, req.durus_nedeni, req.azaltma_yuzdesi, finance_inputs,
        reclassify=req.reclassify, cycle_improvement_pct=req.cycle_improvement_pct,
        scrap_rate=req.scrap_rate))


# ---------------------------------------------------------------------------
# RCA endpoint'leri (Faz 3)
# ---------------------------------------------------------------------------

@app.get("/rca/alerts", response_model=AlertsOut, tags=["rca"])
def rca_alerts(machine: str = Query(examples=["Makine 1"]),
               date: str | None = Query(default=None, examples=["2026-01-12"])):
    """Bir makinenin CNC alarmları (opsiyonel gün filtresi)."""
    return _guard(lambda: service.list_alerts(machine, date))


@app.get("/rca/alert-pareto", response_model=AlertParetoOut, tags=["rca"])
def rca_alert_pareto(machine: str | None = Query(default=None, examples=["Makine 1"]),
                     top_n: int = Query(10, ge=1, le=100)):
    """En sık tekrarlayan alarmlar (makine veya tesis geneli)."""
    return _guard(lambda: service.get_alert_pareto(machine, top_n))


@app.get("/rca/timeline", tags=["rca"])
def rca_timeline(machine: str = Query(examples=["Makine 1"]),
                 center: str = Query(examples=["2026-01-12 04:47:11"]),
                 window_min: int | None = Query(default=None, ge=1, le=240)):
    """Bir an etrafında ±window_min dk: alarm + duruş + telemetri çizelgesi."""
    return _guard(lambda: service.get_timeline(machine, center, window_min))


@app.get("/rca/root-cause", tags=["rca"])
def rca_root_cause(machine: str = Query(examples=["Makine 1"]),
                   date: str = Query(examples=["2026-01-12"]),
                   window_min: int | None = Query(default=None, ge=1, le=240)):
    """Kanıtlı kök neden kartı (alarm + telemetri kanıtı + öneri + downtime köprüsü)."""
    return _guard(lambda: service.get_root_cause(machine, date, window_min))


# ---------------------------------------------------------------------------
# İş emirleri & Stok
# ---------------------------------------------------------------------------

@app.get("/workorders", tags=["workorder"])
def workorders(machine: str = Query(examples=["Makine 1"]),
               date: str = Query(examples=["2025-11-10"])):
    """Bir makinenin vardiya günündeki iş emri çalışmaları."""
    return _guard(lambda: service.list_workorders(machine, date))


@app.get("/stock", tags=["workorder"])
def stock(machine: str = Query(examples=["Makine 1"]),
          date: str = Query(examples=["2025-11-10"])):
    """Vardiya günündeki iş emirlerinin program (order_no) bazında stok özeti."""
    return _guard(lambda: service.stock_summary(machine, date))


@app.get("/rca/deviation", tags=["rca"])
def rca_deviation(machine: str = Query(examples=["Makine 1"]),
                  center: str = Query(examples=["2026-01-12 04:47:11"]),
                  signal: str = Query("CYCLE_TIME_MS"),
                  window_min: int | None = Query(default=None, ge=1, le=240)):
    """Telemetri sinyalinin olay anındaki istatistiksel sapması (Teknik 3)."""
    return _guard(lambda: service.get_deviation(machine, center, signal, window_min))


@app.get("/fleet/overview", tags=["fleet"])
def fleet_overview(date: str = Query(examples=["2025-11-10"])):
    """Tüm makinelerin o gündeki OEE/A özetini (en kötü üstte) sıralar."""
    return _guard(lambda: service.fleet_overview(date))


@app.get("/fleet/alarm-patterns", tags=["fleet"])
def fleet_alarm_patterns(min_machines: int = Query(2, ge=1, le=12),
                         top_n: int = Query(15, ge=1, le=100)):
    """Birden fazla makinede görülen ortak alarm örüntüleri."""
    return _guard(lambda: service.fleet_alarm_patterns(min_machines, top_n))
