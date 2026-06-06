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
    durus_nedeni: str = Field(examples=["System Offline"])
    azaltma_yuzdesi: float = Field(ge=0.0, le=1.0, examples=[0.20])
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
    oee_pp: float
    oee_relative_pct: float


class WhatIfOut(BaseModel):
    machine: str
    unit_uid: str
    date: str
    durus_nedeni: str
    azaltma_yuzdesi: float
    share: float
    reason_official_ms: float
    reduced_ms: float
    recovered_hours: float
    before: StateOut
    after: StateOut
    delta: DeltaOut
    financial: FinancialOut


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

# Frontend farklı origin'den çağıracağı için CORS açık (hackathon ayarı).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
                          "/oee/baseline", "/oee/pareto", "/oee/whatif"]}


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


@app.post("/oee/whatif", response_model=WhatIfOut, tags=["oee"])
def whatif(req: WhatIfRequest):
    """Bir duruş nedenini X% azaltmanın OEE + finansal (ROI) etkisini simüle eder."""
    finance_inputs = req.finance.model_dump() if req.finance else None
    return _guard(lambda: service.run_whatif(
        req.machine, req.date, req.durus_nedeni, req.azaltma_yuzdesi, finance_inputs))
