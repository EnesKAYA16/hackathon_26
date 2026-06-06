"""
OEE BAZ (BASELINE) HESAPLAMA İSKELETİ — Makine 1 (M1)
=====================================================

Amaç:
    Belirli bir makine ve belirli bir GÜN için baz (mevcut) OEE değerini,
    Availability (A) x Performance (P) x Quality (Q) formülüyle hesaplamak.

    Bu iskeletin odak noktası: PLANSIZ DURUŞLARIN (UnPlannedStop) OEE'ye
    nasıl yansıdığını açıkça göstermek. Plansız duruşlar yalnızca
    Availability (Kullanılabilirlik) faktörünü düşürür.

Kritik veri seti notları (README + docs/02_WHAT_IF_ANALYSIS.md'den):
    - TÜM süreler MİLİSANİYE (ms) cinsindendir.
    - Kalite (Q) bu veri setinde her zaman 1.0'dır (ScrapeSum = 0).
    - Vardiya günü sınırı UTC 21:00'dir (trans_date böyle saklanır).
    - level = 0 -> tesis (plant) toplamı, level = 1 -> tek makine. Biz level=1 kullanırız.
    - A, P, Q hem skaler kolon hem de JSON blob olarak saklanır; biz JSON
      içindeki HAM BİLEŞENLERDEN yeniden hesaplayıp saklanan değerle doğrularız.

Formüller:
    RunTime       = WorkTotal - PlannedStop - UnPlannedStop
    ScheduledTime = WorkTotal - PlannedStop
    A = RunTime / ScheduledTime
    P = WorkingTime / PlannedTime          (trexCloud P'yi 1'de sınırlayabilir)
    Q = (ProductSum - ScrapeSum) / ProductSum   (bu veri setinde her zaman 1)
    OEE = A * P * Q

ÖNEMLİ — Performance (P) hakkında:
    A ve Q, JSON'daki ham ms bileşenlerinden BİREBİR yeniden üretilebilir.
    Ancak P, trexCloud tarafından ideal cycle-time'lardan hesaplanır ve
    elimizdeki WorkingTime/PlannedTime alanlarından sağlıklı şekilde geri
    üretilemez (ham oran 1'i çok aşar). Bu nedenle baz OEE'de P için
    trexCloud'un saklanan (resmi) değerini KABUL EDİYORUZ; ham oranı yalnızca
    bilgi amaçlı gösteriyoruz. Kullanıcının asıl odağı olan PLANSIZ DURUŞLAR
    Availability (A) üzerinden tam olarak yeniden hesaplanır.

Çalıştırma:
    python3 oee_baseline.py
"""

from __future__ import annotations

import json

import pandas as pd

import repository
# Yol sabitleri artık tek kaynak: repository (geriye dönük uyumluluk için re-export).
from repository import DATA_DIR, STOPPAGE_CSV  # noqa: F401

# ---------------------------------------------------------------------------
# 0) AYARLAR — Burayı değiştirerek farklı makine/gün analiz edebilirsin.
# ---------------------------------------------------------------------------

# Veri dosyaları ve cache'li yükleyiciler repository.py içinde tanımlı.
# (DATA_DIR ve STOPPAGE_CSV yukarıda repository'den import edildi.)

# "M1" = veri setindeki "Makine 1". İsimden unit_uid'yi otomatik çözeceğiz.
TARGET_MACHINE_NAME = "Makine 1"

# Analiz edilecek vardiya günü (trans_date'in tarih kısmı).
# Örnek günler (Makine 1): 2025-11-05 (A=0, plansız duruş senaryosu),
#                          2025-11-10 (OEE ~0.031, A/P/Q hepsi anlamlı).
TARGET_DATE = "2025-11-10"

# Sabitler
MS_PER_MINUTE = 60_000
MS_PER_HOUR = 3_600_000


# ---------------------------------------------------------------------------
# 1) YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------------------------

def ms_to_hours(ms: float) -> float:
    """Milisaniyeyi saate çevirir."""
    return ms / MS_PER_HOUR


def ms_to_minutes(ms: float) -> float:
    """Milisaniyeyi dakikaya çevirir."""
    return ms / MS_PER_MINUTE


def fmt_hms(ms: float) -> str:
    """Milisaniyeyi okunabilir 'Xh Ym' formatına çevirir (raporlama için)."""
    total_minutes = int(round(ms / MS_PER_MINUTE))
    return f"{total_minutes // 60}h {total_minutes % 60}m"


def safe_json(value) -> dict:
    """
    oee_summary'deki availability/performance/quality kolonları JSON string'tir.
    Bazı satırlar boş/NaN olabilir; güvenli şekilde dict'e çeviririz.
    """
    if isinstance(value, dict):
        return value
    if pd.isna(value):
        return {}
    return json.loads(value)


# ---------------------------------------------------------------------------
# 2) VERİ YÜKLEME
# ---------------------------------------------------------------------------

def load_units() -> pd.DataFrame:
    """Makine ana verisini (isim <-> uid eşlemesi) yükler (cache'li)."""
    return repository.units()


def resolve_unit_uid(units: pd.DataFrame, machine_name: str) -> str:
    """Makine adından unit_uid'yi bulur. 'M1' gibi kısaltmaları da destekler."""
    # 'M1' -> 'Makine 1' normalizasyonu (kullanıcı kısaltma yazarsa)
    name = machine_name.strip()
    if name.upper().startswith("M") and name[1:].strip().isdigit():
        name = f"Makine {name[1:].strip()}"

    match = units.loc[units["name"].str.strip() == name]
    if match.empty:
        available = ", ".join(sorted(units["name"].str.strip().unique()))
        raise ValueError(f"'{machine_name}' bulunamadı. Mevcut makineler: {available}")
    return match.iloc[0]["uid"]


def load_oee_summary() -> pd.DataFrame:
    """OEE özet tablosunu yükler (cache'li; trans_date UTC datetime'a çevrili)."""
    return repository.oee_summary()


# ---------------------------------------------------------------------------
# 3) FİLTRELEME / TEMİZLEME — baz satırı seçimi
# ---------------------------------------------------------------------------

def select_baseline_row(oee: pd.DataFrame, unit_uid: str, target_date: str) -> pd.Series:
    """
    Tek bir makine + tek bir gün için baz OEE satırını döndürür.

    Filtreler:
      - level == 1            -> tek makine (tesis toplamı level=0'ı dışla)
      - unit_uid == hedef     -> sadece Makine 1
      - trans_date == hedef gün (vardiya günü, tarih kısmı eşleşmesi)
    """
    target = pd.Timestamp(target_date).date()

    mask = (
        (oee["level"] == 1)
        & (oee["unit_uid"] == unit_uid)
        & (oee["trans_date"].dt.date == target)
    )
    rows = oee.loc[mask]

    if rows.empty:
        # Hangi günlerin mevcut olduğunu göstererek kibarca hata ver.
        avail = (
            oee.loc[(oee["level"] == 1) & (oee["unit_uid"] == unit_uid), "trans_date"]
            .dt.date.astype(str).sort_values().unique()
        )
        raise ValueError(
            f"{unit_uid} için {target_date} gününde level=1 kaydı yok.\n"
            f"Mevcut ilk birkaç gün: {list(avail[:10])}"
        )
    if len(rows) > 1:
        # Aynı gün birden fazla satır olursa (beklenmez) ilkini al, uyar.
        print(f"[UYARI] {target_date} için {len(rows)} satır bulundu; ilki kullanılıyor.")
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# 4) OEE BİLEŞENLERİNİ HAM (ms) VERİDEN YENİDEN HESAPLA
# ---------------------------------------------------------------------------

def compute_availability(work_total: float, planned_stop: float, unplanned_stop: float) -> dict:
    """
    Availability hesabı — plansız duruşların etkisini AÇIKÇA gösterir.

        ScheduledTime = WorkTotal - PlannedStop      (planlı duruş paydadan çıkar)
        RunTime       = ScheduledTime - UnPlannedStop (plansız duruş A'yı DÜŞÜRÜR)
        A             = RunTime / ScheduledTime
    """
    scheduled_time = work_total - planned_stop
    run_time = scheduled_time - unplanned_stop
    availability = run_time / scheduled_time if scheduled_time > 0 else 0.0
    return {
        "WorkTotal_ms": work_total,
        "PlannedStop_ms": planned_stop,
        "UnPlannedStop_ms": unplanned_stop,
        "ScheduledTime_ms": scheduled_time,
        "RunTime_ms": run_time,
        "A": availability,
    }


def compute_performance(working_time: float, planned_time: float, stored_p: float | None) -> dict:
    """
    Performance.

    trexCloud P'yi kendi içinde ideal cycle-time'lardan hesaplar; elimizdeki
    WorkingTime/PlannedTime alanları bu değeri geri üretmez (ham oran genelde
    1'i çok aşar). Bu yüzden baz hesapta P olarak trexCloud'un SAKLANAN
    değerini kullanırız; ham oranı sadece referans/bilgi olarak döndürürüz.
    """
    raw_ratio = working_time / planned_time if planned_time > 0 else 0.0
    performance = float(stored_p) if stored_p is not None else min(raw_ratio, 1.0)
    return {
        "WorkingTime_ms": working_time,
        "PlannedTime_ms": planned_time,
        "P_raw_ratio": raw_ratio,   # bilgi amaçlı (güvenilir değil)
        "P": performance,           # baz hesapta kullanılan resmi P
    }


def compute_quality(product_sum: float, scrape_sum: float) -> dict:
    """
    Quality = (ProductSum - ScrapeSum) / ProductSum.
    Bu veri setinde ScrapeSum = 0 olduğundan Q her zaman 1.0'dır.
    """
    quality = (product_sum - scrape_sum) / product_sum if product_sum > 0 else 1.0
    return {
        "ProductSum": product_sum,
        "ScrapeSum": scrape_sum,
        "Q": quality,
    }


def build_oee_breakdown(row: pd.Series) -> dict:
    """
    Tek bir oee_summary satırından JSON bileşenlerini ayrıştırır,
    A/P/Q'yu ham ms'den yeniden hesaplar ve saklanan değerlerle karşılaştırır.
    """
    a_json = safe_json(row["availability"])
    p_json = safe_json(row["performance"])
    q_json = safe_json(row["quality"])

    avail = compute_availability(
        work_total=a_json.get("WorkTotal", 0),
        planned_stop=a_json.get("PlannedStop", 0),
        unplanned_stop=a_json.get("UnPlannedStop", 0),
    )
    perf = compute_performance(
        working_time=p_json.get("WorkingTime", 0),
        planned_time=p_json.get("PlannedTime", 0),
        stored_p=p_json.get("P"),
    )
    qual = compute_quality(
        product_sum=q_json.get("ProductSum", 0),
        scrape_sum=q_json.get("ScrapeSum", 0),
    )

    oee_recomputed = avail["A"] * perf["P"] * qual["Q"]

    return {
        "trans_date": row["trans_date"],
        "availability": avail,
        "performance": perf,
        "quality": qual,
        "OEE_recomputed": oee_recomputed,
        # Doğrulama için tablodaki hazır (pre-computed) değerler:
        "stored": {
            "A": a_json.get("A"),
            "P": p_json.get("P"),
            "Q": q_json.get("Q"),
            "OEE": row.get("oee"),
        },
    }


# ---------------------------------------------------------------------------
# 5) (OPSİYONEL) DOĞRULAMA — Plansız duruşu event tablosundan tekrar topla
# ---------------------------------------------------------------------------

def cross_check_unplanned_from_slices(unit_uid: str, target_date: str) -> dict:
    """
    UnPlannedStop'u stoppage_slice'tan event-replay ile bağımsız doğrular.

    Vardiya penceresi: [hedef gün 21:00 UTC, ertesi gün 21:00 UTC).
    Filtreler (RCA/What-If kılavuzuna göre):
      - is_planned == False        -> sadece plansız duruşlar
      - exclude_from_oee == False  -> OEE dışı işaretlileri at
      - is_test_prod == False      -> test üretimini at

    Not: Bu, oee_summary'deki UnPlannedStop ile birebir tutmayabilir
    (vardiya penceresi sınırları / kısmi dilimler nedeniyle); amaç
    büyüklük mertebesini teyit etmek ve plansız duruş NEDENLERİNİ görmektir.
    """
    shift_start = pd.Timestamp(target_date, tz="UTC") + pd.Timedelta(hours=21)
    shift_end = shift_start + pd.Timedelta(hours=24)

    slices = repository.stoppage_slices()  # cache'li, tarih/boolean parse edilmiş

    mask = (
        (slices["unit_uid"] == unit_uid)
        & (slices["started_on"] >= shift_start)
        & (slices["started_on"] < shift_end)
        & (~slices["is_planned"])
        & (~slices["exclude_from_oee"])
        & (~slices["is_test_prod"])
    )
    unplanned = slices.loc[mask]

    return {
        "shift_window": (shift_start, shift_end),
        "event_count": len(unplanned),
        "unplanned_total_ms": float(unplanned["duration_milliseconds"].sum()),
        # Plansız duruşları nedene (reading_def_uid) göre ms toplamıyla sırala — RCA için
        "by_reason_ms": (
            unplanned.groupby("reading_def_uid")["duration_milliseconds"]
            .sum().sort_values(ascending=False).head(10).to_dict()
        ),
    }


# ---------------------------------------------------------------------------
# 6) RAPOR
# ---------------------------------------------------------------------------

def print_report(machine: str, unit_uid: str, breakdown: dict, check: dict | None) -> None:
    a = breakdown["availability"]
    p = breakdown["performance"]
    q = breakdown["quality"]
    stored = breakdown["stored"]

    print("=" * 64)
    print(f" BAZ OEE RAPORU — {machine}  ({unit_uid})")
    print(f" Vardiya günü: {breakdown['trans_date']}")
    print("=" * 64)

    print("\n[ AVAILABILITY (Kullanılabilirlik) ]")
    print(f"  WorkTotal       : {fmt_hms(a['WorkTotal_ms']):>10}  ({ms_to_hours(a['WorkTotal_ms']):.2f} h)")
    print(f"  PlannedStop  (-): {fmt_hms(a['PlannedStop_ms']):>10}  -> paydadan çıkar")
    print(f"  UnPlannedStop(-): {fmt_hms(a['UnPlannedStop_ms']):>10}  -> A'yı DÜŞÜREN plansız duruş")
    print(f"  ScheduledTime   : {fmt_hms(a['ScheduledTime_ms']):>10}  (WorkTotal - PlannedStop)")
    print(f"  RunTime         : {fmt_hms(a['RunTime_ms']):>10}  (ScheduledTime - UnPlannedStop)")
    print(f"  => A = RunTime/ScheduledTime = {a['A']:.4f}   (tablo: {stored['A']})")

    print("\n[ PERFORMANCE ]")
    print(f"  WorkingTime     : {fmt_hms(p['WorkingTime_ms']):>10}")
    print(f"  PlannedTime     : {fmt_hms(p['PlannedTime_ms']):>10}")
    print(f"  Ham oran (bilgi): {p['P_raw_ratio']:.4f}  (WorkingTime/PlannedTime — güvenilir DEĞİL)")
    print(f"  => P = {p['P']:.4f}   (trexCloud resmi değeri kullanıldı; tablo: {stored['P']})")

    print("\n[ QUALITY ]")
    print(f"  ProductSum      : {q['ProductSum']:.0f} adet,  ScrapeSum: {q['ScrapeSum']:.0f}")
    print(f"  => Q = {q['Q']:.4f}   (tablo: {stored['Q']})")

    print("\n[ OEE = A x P x Q ]")
    print(f"  Yeniden hesaplanan OEE : {breakdown['OEE_recomputed']:.6f}")
    print(f"  Tablodaki (saklanan)   : {stored['OEE']:.6f}")
    delta = breakdown["OEE_recomputed"] - float(stored["OEE"])
    print(f"  Fark (doğrulama)       : {delta:+.6f}")

    if check is not None:
        print("\n[ DOĞRULAMA — stoppage_slice'tan plansız duruş (event replay) ]")
        ws, we = check["shift_window"]
        print(f"  Vardiya penceresi : {ws}  ->  {we}")
        print(f"  Plansız event     : {check['event_count']} adet")
        print(f"  Plansız toplam    : {fmt_hms(check['unplanned_total_ms'])}  "
              f"(oee_summary: {fmt_hms(a['UnPlannedStop_ms'])})")
        print("  En uzun plansız duruş nedenleri (reading_def_uid -> süre):")
        for reason, ms in check["by_reason_ms"].items():
            print(f"    - {reason} : {fmt_hms(ms)}")

    print("\n" + "=" * 64)


# ---------------------------------------------------------------------------
# 7) MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    units = load_units()
    unit_uid = resolve_unit_uid(units, TARGET_MACHINE_NAME)

    oee = load_oee_summary()
    baseline_row = select_baseline_row(oee, unit_uid, TARGET_DATE)
    breakdown = build_oee_breakdown(baseline_row)

    # Plansız duruş doğrulamasını event tablosundan yap (büyük dosya, opsiyonel).
    try:
        check = cross_check_unplanned_from_slices(unit_uid, TARGET_DATE)
    except Exception as exc:  # noqa: BLE001 - iskelet aşamasında hatayı yutup devam et
        print(f"[BİLGİ] stoppage_slice doğrulaması atlandı: {exc}")
        check = None

    print_report(TARGET_MACHINE_NAME, unit_uid, breakdown, check)


if __name__ == "__main__":
    main()
