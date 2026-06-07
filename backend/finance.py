"""
FİNANSAL ROI KATMANI (Faz 2)
============================

What-If'in teknik çıktısını (geri kazanılan saat) İŞ DEĞERİNE çevirir:
geri kazanılan saat -> ekstra parça -> katkı marjı (+ duruş maliyeti tasarrufu)
-> net fayda, geri ödeme süresi (payback), ROI.

ÖNEMLİ — Bu katman VARSAYIMLARLA çalışır:
    Veri setinde satış fiyatı, marj, işçilik/enerji maliyeti YOK
    (docs/02 Bölüm 6). Bu yüzden finansal girdiler kullanıcı tarafından
    tanımlanan, AÇIKÇA ETİKETLENMİŞ varsayımlardır. Varsayılan değerler
    dataset dokümanındaki örnek finance dict ile aynıdır (jüri aşinalığı).

ÇİFT SAYIM UYARISI:
    GrossBenefit (kaçırılan marj) ile DowntimeSaving (saatlik duruş maliyeti)
    docs/02'ye göre TOPLANIR. Eğer ekibiniz duruş maliyetini "kaçırılan marj"
    olarak tanımlıyorsa çift sayım olmasın diye downtime_cost_per_hour=0 verin.

Formüller (docs/02 Bölüm 6):
    AverageGoodPiecesPerHour = ProductSum / RunningHours
    ExtraPieces   = RecoveredHours × PiecesPerHour
    GrossBenefit  = ExtraPieces × ContributionMarginPerPiece
    DowntimeSaving= RecoveredHours × DowntimeCostPerHour
    DailyBenefit  = GrossBenefit + DowntimeSaving        (tekrar eden günlük fayda)
    PaybackDays   = InterventionCost / DailyBenefit
    NetBenefit(H) = DailyBenefit × HorizonDays − InterventionCost
    ROI(H)        = NetBenefit(H) / InterventionCost
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class FinanceAssumptions:
    """Finansal varsayımlar (hepsi kullanıcı tanımlı; varsayılanlar docs/02'den)."""
    contribution_margin_per_piece: float = 12.0   # parça başı katkı marjı
    machine_hour_cost: float = 45.0               # makine-saat maliyeti (referans)
    downtime_cost_per_hour: float = 80.0          # plansız duruşun saatlik direkt maliyeti
    scrap_cost_per_piece: float = 18.0            # hurda maliyeti (kalite senaryosu için)
    intervention_cost: float = 300.0              # düzeltmenin tek seferlik maliyeti
    pieces_per_hour_override: float | None = None # None ise baz günden tahmin edilir
    horizon_days: int = 30                        # ROI ufku (gün)
    currency: str = "₺"


def estimate_pieces_per_hour(product_sum: float, running_hours: float,
                             override: float | None) -> float:
    """
    Çalışan saat başına iyi parça oranı.
    override verilmişse onu kullanır; yoksa baz günden tahmin eder.
    (Not: makinenin az ürettiği bir günde tahmin düşük çıkabilir; gerçekçi bir
     senaryo için override ile temsili plant oranını vermek önerilir.)
    """
    if override is not None:
        return float(override)
    return product_sum / running_hours if running_hours > 0 else 0.0


def compute_financial_impact(recovered_hours: float,
                             product_sum: float,
                             running_hours: float,
                             a: FinanceAssumptions,
                             extra_pieces_perf: float = 0.0) -> dict:
    """
    What-If'in teknik etkisini finansal etkiye çevirir.

    Args:
        recovered_hours: A kaldıracının geri kazandırdığı plansız duruş saati.
        product_sum: Baz gündeki üretilen iyi parça (pieces/hour tahmini için).
        running_hours: Baz gündeki çalışma saati (RunTime).
        a: FinanceAssumptions.
        extra_pieces_perf: P (performans) iyileştirmesinden gelen ek parça.
    """
    pieces_per_hour = estimate_pieces_per_hour(product_sum, running_hours,
                                               a.pieces_per_hour_override)
    extra_pieces = recovered_hours * pieces_per_hour + extra_pieces_perf
    gross_benefit = extra_pieces * a.contribution_margin_per_piece
    downtime_saving = recovered_hours * a.downtime_cost_per_hour
    daily_benefit = gross_benefit + downtime_saving

    payback_days = (a.intervention_cost / daily_benefit) if daily_benefit > 0 else None
    horizon_net = daily_benefit * a.horizon_days - a.intervention_cost
    roi = (horizon_net / a.intervention_cost) if a.intervention_cost > 0 else None

    return {
        "currency": a.currency,
        "is_assumption": True,  # finansal sayılar varsayıma dayanır
        "pieces_per_hour": pieces_per_hour,
        "pieces_per_hour_is_estimated": a.pieces_per_hour_override is None,
        "recovered_hours": recovered_hours,
        "extra_pieces": extra_pieces,
        "gross_benefit": gross_benefit,
        "downtime_saving": downtime_saving,
        "daily_benefit": daily_benefit,
        "intervention_cost": a.intervention_cost,
        "net_benefit_first_day": daily_benefit - a.intervention_cost,
        "payback_days": payback_days,
        "horizon_days": a.horizon_days,
        "horizon_net_benefit": horizon_net,
        "roi": roi,
        "assumptions": asdict(a),
    }


# ---------------------------------------------------------------------------
# CLI sunum (jüri için)
# ---------------------------------------------------------------------------

def print_finance(fin: dict) -> None:
    cur = fin["currency"]
    print("\n[ FİNANSAL ETKİ (varsayımsal) ]")
    pph_note = "tahmin" if fin["pieces_per_hour_is_estimated"] else "override"
    print(f"  Parça/saat ({pph_note})     : {fin['pieces_per_hour']:.2f}")
    print(f"  Geri kazanılan saat       : {fin['recovered_hours']:.2f} sa")
    print(f"  Ekstra parça              : {fin['extra_pieces']:.1f} adet")
    print(f"  Brüt fayda (marj)         : {cur}{fin['gross_benefit']:,.0f}")
    print(f"  Duruş maliyeti tasarrufu  : {cur}{fin['downtime_saving']:,.0f}")
    print(f"  Günlük fayda (toplam)     : {cur}{fin['daily_benefit']:,.0f}")
    print(f"  Müdahale maliyeti (1 kez) : {cur}{fin['intervention_cost']:,.0f}")
    payback = fin["payback_days"]
    print(f"  Geri ödeme süresi         : {payback:.2f} gün" if payback is not None
          else "  Geri ödeme süresi         : - (fayda yok)")
    roi = fin["roi"]
    print(f"  {fin['horizon_days']} günlük net fayda      : {cur}{fin['horizon_net_benefit']:,.0f}")
    print(f"  ROI ({fin['horizon_days']} gün)             : %{roi * 100:,.0f}" if roi is not None
          else "  ROI                       : -")
