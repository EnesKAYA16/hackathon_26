"""
OEE İŞ DEĞERİ + KÖK NEDEN MODÜLÜ — Pareto & What-If Simülasyonu
================================================================

Bu modül, doğrulanmış baz hesabın (oee_baseline.py) üzerine iki katman ekler:

  GÖREV 1 — İnsan Okunur Duruşlar + Pareto
      stoppage_slice'taki plansız duruş eventlerini reading_def tablosundaki
      Türkçe isimlerle (display_text) birleştirir ve bir makine için
      "en çok süre kaybettiren ilk N plansız duruş nedenini" Pareto formatında
      (süre, %, kümülatif %) listeler.

  GÖREV 2 — Spesifik What-If Simülasyonu
      simulate_whatif(durus_nedeni, azaltma_yuzdesi):
        1) Seçilen nedenin toplam plansız duruş süresini bulur, % kadar azaltır.
        2) Kalan tüm plansız sürelerle toplayıp YENİ UnPlannedStop'u bulur.
        3) Yeni UnPlannedStop ile YENİ Availability'yi hesaplar.
        4) YENİ A x mevcut P x mevcut Q ile YENİ OEE'yi bulur, ΔOEE'yi gösterir.

TUTARLILIK YAKLAŞIMI (jüri notu):
    Baz OEE'yi trexCloud ile 0.000000 hata payıyla eşleştirdiğimiz için,
    What-If'i de RESMİ oee_summary tabanına oturtuyoruz:
      - WorkTotal, PlannedStop, UnPlannedStop (toplam), P ve Q -> oee_summary.
      - Nedenlerin PAYI -> gerçek event-log (stoppage_slice) Pareto oranları.
    Yani resmi toplam plansız duruş, event-log'daki nedenlere oranlarına göre
    dağıtılır. Böyle hem baz OEE (0.0312) korunur hem de neden bazlı azaltma
    yapılabilir. (Slice ham toplamı ~17s, resmi ~15.3s; fark vardiya sınırı /
    trexCloud aralık birleştirmesinden kaynaklanır — bu yüzden resmi toplamı
    "ground truth" alıp orantısal dağıtıyoruz.)

Çalıştırma:
    python3 oee_whatif.py
"""

from __future__ import annotations

import pandas as pd

import finance
import repository
# Doğrulanmış baz hesap modülünü yeniden kullan (DRY).
from oee_baseline import (
    TARGET_DATE,
    TARGET_MACHINE_NAME,
    build_oee_breakdown,
    compute_availability,
    fmt_hms,
    load_oee_summary,
    load_units,
    ms_to_hours,
    resolve_unit_uid,
    select_baseline_row,
)


# ---------------------------------------------------------------------------
# YARDIMCI: basit, hizalı tablo yazıcı (harici kütüphane yok)
# ---------------------------------------------------------------------------

def print_table(headers: list[str], rows: list[list], aligns: list[str] | None = None) -> None:
    """Sunumda okunabilir, kenarlıklı ASCII tablo basar."""
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    aligns = aligns or ["<"] * len(headers)

    def fmt_row(cells):
        return " | ".join(f"{str(c):{a}{w}}" for c, w, a in zip(cells, widths, aligns))

    sep = "-+-".join("-" * w for w in widths)
    print(fmt_row(headers))
    print(sep)
    for r in rows:
        print(fmt_row(r))


# ---------------------------------------------------------------------------
# LOOKUP: reading_def_uid -> (display_text, signal_category)
# ---------------------------------------------------------------------------

def load_reading_def_lookup() -> pd.DataFrame:
    """reading_def lookup'ı döndürür (cache'li, uid index'li)."""
    return repository.reading_def_lookup()


def reason_name(rd_lookup: pd.DataFrame, reading_def_uid: str) -> str:
    """uid'den okunabilir duruş adını döndürür (display_text > name > uid)."""
    if reading_def_uid in rd_lookup.index:
        row = rd_lookup.loc[reading_def_uid]
        for key in ("display_text", "name"):
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return f"{reading_def_uid} (bilinmiyor)"


# ---------------------------------------------------------------------------
# EVENT-REPLAY: bir makine/gün için plansız duruşları isimleriyle topla
# ---------------------------------------------------------------------------

def get_unplanned_by_reason(unit_uid: str, target_date: str) -> pd.DataFrame:
    """
    Vardiya penceresindeki [gün 21:00 UTC, +24s) PLANSIZ duruşları neden bazında
    toplar ve reading_def isimleriyle birleştirir.

    Filtreler: is_planned=False, exclude_from_oee=False, is_test_prod=False.

    Dönen sütunlar: reason, reading_def_uid, signal_category, events, total_ms
    """
    shift_start = pd.Timestamp(target_date, tz="UTC") + pd.Timedelta(hours=21)
    shift_end = shift_start + pd.Timedelta(hours=24)

    s = repository.stoppage_slices()  # cache'li, tarih/boolean parse edilmiş

    mask = (
        (s["unit_uid"] == unit_uid)
        & (s["started_on"] >= shift_start)
        & (s["started_on"] < shift_end)
        & (~s["is_planned"])
        & (~s["exclude_from_oee"])
        & (~s["is_test_prod"])
    )
    unplanned = s.loc[mask]

    agg = (
        unplanned.groupby("reading_def_uid")
        .agg(events=("duration_milliseconds", "size"),
             total_ms=("duration_milliseconds", "sum"))
        .reset_index()
    )

    rd_lookup = load_reading_def_lookup()
    agg["reason"] = agg["reading_def_uid"].map(lambda u: reason_name(rd_lookup, u))
    agg["signal_category"] = agg["reading_def_uid"].map(
        lambda u: rd_lookup.loc[u, "signal_category"] if u in rd_lookup.index else None
    )
    return agg.sort_values("total_ms", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# GÖREV 1: PARETO
# ---------------------------------------------------------------------------

def pareto_unplanned(unit_uid: str, target_date: str, top_n: int = 5) -> pd.DataFrame:
    """
    En çok süre kaybettiren ilk N plansız duruş nedenini Pareto formatında döndürür.
    Sütunlar: reason, events, total_ms, total_hours, pct, cumulative_pct
    """
    agg = get_unplanned_by_reason(unit_uid, target_date)
    grand_total = agg["total_ms"].sum()

    agg["total_hours"] = agg["total_ms"].apply(ms_to_hours)
    agg["pct"] = 100 * agg["total_ms"] / grand_total if grand_total else 0
    agg["cumulative_pct"] = agg["pct"].cumsum()

    return agg.head(top_n)


def print_pareto(machine: str, target_date: str, pareto: pd.DataFrame) -> None:
    print("=" * 72)
    print(" PARETO — En Çok Süre Kaybettiren Plansız Duruşlar")
    print(f" Makine: {machine}   |   Vardiya günü: {target_date}")
    print("=" * 72)

    rows = []
    for i, r in enumerate(pareto.itertuples(index=False), start=1):
        rows.append([
            i,
            r.reason,
            r.signal_category or "-",
            int(r.events),
            fmt_hms(r.total_ms),
            f"{r.pct:5.1f}%",
            f"{r.cumulative_pct:5.1f}%",
        ])
    print_table(
        ["#", "Duruş Nedeni", "Kategori", "Event", "Toplam Süre", "Pay", "Kümülatif"],
        rows,
        aligns=["<", "<", "<", ">", ">", ">", ">"],
    )
    print(f"\n  Toplam plansız duruş (event-log): {fmt_hms(pareto['total_ms'].sum() if len(pareto) else 0)} "
          f"(ilk {len(pareto)} neden)")
    print("=" * 72)


# ---------------------------------------------------------------------------
# GÖREV 2: WHAT-IF SİMÜLASYONU
# ---------------------------------------------------------------------------

def simulate_whatif(unit_uid: str, target_date: str,
                    durus_nedeni: str | None = None, azaltma_yuzdesi: float = 0.0,
                    reclassify: bool = False,
                    cycle_improvement_pct: float = 0.0,
                    scrap_rate: float = 0.0) -> dict:
    """
    OEE'nin ÜÇ kaldıracında (A, P, Q) What-If senaryolarını simüle eder.

    Kaldıraçlar (slayt 001 senaryoları W1–W4):
      W1 (A) durus_nedeni + azaltma_yuzdesi: plansız nedeni %X azalt.
      W2 (A) durus_nedeni + reclassify=True : nedeni PLANSIZ->PLANLI taşı
              (run-time değişmez, payda küçülür, A izole artar).
      W3 (P) cycle_improvement_pct: çevrim süresini %X iyileştir
              -> P_new = P / (1 - X) (1.0'da sınırlı).
      W4 (Q) scrap_rate: sentetik fire oranı -> Q_new = 1 - fire.

    Çıktı ayrıca ΔOEE'yi A/P/Q katkılarına ayrıştıran 'waterfall' içerir.
    """
    if not 0.0 <= azaltma_yuzdesi <= 1.0:
        raise ValueError("azaltma_yuzdesi 0.0 ile 1.0 arasında olmalı.")
    if not 0.0 <= cycle_improvement_pct < 1.0:
        raise ValueError("cycle_improvement_pct 0.0 ile 1.0 (hariç) arasında olmalı.")
    if not 0.0 <= scrap_rate < 1.0:
        raise ValueError("scrap_rate 0.0 ile 1.0 (hariç) arasında olmalı.")

    # --- Resmi baz (oee_summary) ---
    oee = load_oee_summary()
    bd = build_oee_breakdown(select_baseline_row(oee, unit_uid, target_date))
    work_total = bd["availability"]["WorkTotal_ms"]
    planned_stop = bd["availability"]["PlannedStop_ms"]
    official_unplanned = bd["availability"]["UnPlannedStop_ms"]
    A_base = bd["availability"]["A"]
    P_base = bd["performance"]["P"]
    Q_base = bd["quality"]["Q"]
    OEE_base = A_base * P_base * Q_base
    product_sum = bd["quality"]["ProductSum"]

    # --- A kaldıracı (W1 / W2) ---
    share = 0.0
    reason_official_ms = 0.0
    reduced_ms = 0.0
    new_unplanned = official_unplanned
    new_planned = planned_stop
    reason_label = None

    if durus_nedeni:
        # Gerçek duruş nedeni (event-log oransal payı).
        agg = get_unplanned_by_reason(unit_uid, target_date)
        slice_total = agg["total_ms"].sum()
        match = agg[agg["reason"].str.casefold() == durus_nedeni.casefold()]
        if match.empty:
            secenekler = ", ".join(f"'{r}'" for r in agg["reason"])
            raise ValueError(f"'{durus_nedeni}' bulunamadı. Geçerli nedenler: {secenekler}")
        reason_label = match["reason"].iloc[0]
        share = float(match["total_ms"].iloc[0]) / slice_total if slice_total else 0.0
        reason_official_ms = share * official_unplanned

        if reclassify:  # W2: tamamını PLANLI'ya taşı (run-time sabit, A artar)
            new_unplanned = official_unplanned - reason_official_ms
            new_planned = planned_stop + reason_official_ms
            reduced_ms = 0.0  # üretim zamanı geri kazanılmaz
        else:           # W1: %X azalt
            reduced_ms = reason_official_ms * azaltma_yuzdesi
            new_unplanned = official_unplanned - reduced_ms

    A_new = compute_availability(work_total, new_planned, new_unplanned)["A"]

    # --- P kaldıracı (W3) ---
    P_new = min(P_base / (1 - cycle_improvement_pct), 1.0) if cycle_improvement_pct > 0 else P_base

    # --- Q kaldıracı (W4) ---
    Q_new = 1.0 - scrap_rate if scrap_rate > 0 else Q_base

    OEE_new = A_new * P_new * Q_new

    # --- Etki Şelalesi: ΔOEE = ΔA katkı + ΔP katkı + ΔQ katkı ---
    a_contrib = (A_new - A_base) * P_base * Q_base
    p_contrib = A_new * (P_new - P_base) * Q_base
    q_contrib = A_new * P_new * (Q_new - Q_base)

    # W3 performans iyileştirmesinden gelen ekstra parça (finans için)
    extra_pieces_perf = product_sum * (P_new / P_base - 1) if P_base > 0 else 0.0

    return {
        "durus_nedeni": reason_label,
        "azaltma_yuzdesi": azaltma_yuzdesi,
        "reclassify": reclassify,
        "cycle_improvement_pct": cycle_improvement_pct,
        "scrap_rate": scrap_rate,
        "share": share,
        "reason_official_ms": reason_official_ms,
        "reduced_ms": reduced_ms,
        "work_total": work_total,
        "planned_stop": planned_stop, "new_planned": new_planned,
        "official_unplanned": official_unplanned, "new_unplanned": new_unplanned,
        "A_base": A_base, "A_new": A_new, "dA": A_new - A_base,
        "P_base": P_base, "P_new": P_new, "dP": P_new - P_base,
        "Q_base": Q_base, "Q_new": Q_new, "dQ": Q_new - Q_base,
        "P": P_base, "Q": Q_base,  # geriye dönük uyumluluk (CLI)
        "OEE_base": OEE_base, "OEE_new": OEE_new, "dOEE": OEE_new - OEE_base,
        "waterfall": {"a": a_contrib, "p": p_contrib, "q": q_contrib},
        "recovered_hours": ms_to_hours(reduced_ms),
        "extra_pieces_perf": extra_pieces_perf,
        "product_sum": product_sum,
        "running_hours": ms_to_hours(bd["availability"]["RunTime_ms"]),
    }


def print_whatif(machine: str, target_date: str, sim: dict) -> None:
    pp = lambda x: f"{x * 100:.2f}%"  # oran -> yüzde puanı

    print("=" * 72)
    print(f" WHAT-IF SİMÜLASYONU — '{sim['durus_nedeni']}' duruşunu %{sim['azaltma_yuzdesi'] * 100:.0f} azalt")
    print(f" Makine: {machine}   |   Vardiya günü: {target_date}")
    print("=" * 72)

    print(f"\n  Senaryo: '{sim['durus_nedeni']}' plansız duruşların %{sim['share'] * 100:.1f}'ini oluşturuyor.")
    print(f"  Bu nedenin resmi karşılığı : {fmt_hms(sim['reason_official_ms'])}")
    print(f"  Azaltılan süre (kazanılan) : {fmt_hms(sim['reduced_ms'])}  "
          f"(~{sim['recovered_hours']:.2f} saat geri kazanım)")

    print("\n  KARŞILAŞTIRMA TABLOSU (Önce -> Sonra):")
    rows = [
        ["UnPlannedStop", fmt_hms(sim["official_unplanned"]), fmt_hms(sim["new_unplanned"]),
         f"-{fmt_hms(sim['reduced_ms'])}"],
        ["Availability (A)", pp(sim["A_base"]), pp(sim["A_new"]), f"+{(sim['dA']) * 100:.2f} pp"],
        ["Performance (P)", pp(sim["P"]), pp(sim["P"]), "sabit"],
        ["Quality (Q)", pp(sim["Q"]), pp(sim["Q"]), "sabit"],
        ["OEE", pp(sim["OEE_base"]), pp(sim["OEE_new"]), f"+{(sim['dOEE']) * 100:.2f} pp"],
    ]
    print_table(["Metrik", "Önce", "Sonra", "Δ (Değişim)"], rows,
                aligns=["<", ">", ">", ">"])

    rel = (sim["dOEE"] / sim["OEE_base"] * 100) if sim["OEE_base"] else 0
    print(f"\n  >> SONUÇ: OEE {pp(sim['OEE_base'])} -> {pp(sim['OEE_new'])} "
          f"(ΔOEE = +{sim['dOEE'] * 100:.2f} puan, göreceli +%{rel:.1f})")
    print("=" * 72)


# ---------------------------------------------------------------------------
# DEMO / MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    units = load_units()
    unit_uid = resolve_unit_uid(units, TARGET_MACHINE_NAME)

    # GÖREV 1 — Pareto
    pareto = pareto_unplanned(unit_uid, TARGET_DATE, top_n=5)
    print_pareto(TARGET_MACHINE_NAME, TARGET_DATE, pareto)

    # GÖREV 2 — What-If (en büyük nedeni örnek alıp %20 azalt)
    if not pareto.empty:
        top_reason = pareto.iloc[0]["reason"]
        print()
        sim = simulate_whatif(unit_uid, TARGET_DATE, durus_nedeni=top_reason, azaltma_yuzdesi=0.20)
        print_whatif(TARGET_MACHINE_NAME, TARGET_DATE, sim)

        # FİNANSAL ROI (varsayılan varsayımlarla)
        fin = finance.compute_financial_impact(
            recovered_hours=sim["recovered_hours"],
            product_sum=sim["product_sum"],
            running_hours=sim["running_hours"],
            a=finance.FinanceAssumptions(),
        )
        finance.print_finance(fin)


if __name__ == "__main__":
    main()
