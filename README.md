# 🏭 OEE What-If & Kök Neden Analizi (RCA) Panosu

Endüstriyel üretim hatları için **OEE (Overall Equipment Effectiveness)** baz hesabı, plansız duruş Pareto analizi, What-If simülasyonu ve **AI destekli kök neden analizi** sunan tam yığın (full-stack) analitik platformu.

> **Uludağ Hackathon 2026** projesi

---

##  🤝 Yapanlar
- **Ahmet Aksoy**
- **Mehmet Turunç**
- **Enes KAYA** 

## 📋 İçindekiler

- [Özellikler](#-özellikler)
- [Mimari](#-mimari)
- [Teknoloji Yığını](#-teknoloji-yığını)
- [Kurulum](#-kurulum)
- [Çalıştırma](#-çalıştırma)
- [API Endpoint'leri](#-api-endpointleri)
- [Proje Yapısı](#-proje-yapısı)

---

## ✨ Özellikler

### 📊 Ana Sayfa
- **OEE Göstergesi**: Availability × Performance × Quality ayrıştırması ile gerçek zamanlı OEE skoru
- **OEE Trendi**: Seçilen tarih aralığında günlük OEE/A/P trend grafiği
- **KPI Kartları**: Anlık üretim metrikleri

### ⏸️ Duruşlar
- **Duruş KPI'ları**: Toplam duruş, plansız oran, MTBF, MTTR
- **Saatlik Duruş Trendi**: Planlı/plansız duruş süreleri (dakika bazında, saate kırpılmış)
- **Pareto Analizi**: En çok süre kaybettiren plansız duruş nedenleri (Top N)
- **What-If Simülasyonu**: 4 kaldıraçlı OEE + finansal etki (ROI) simülasyonu
  - **W1** — Duruş azaltma yüzdesi (Availability)
  - **W2** — Plansız → planlı yeniden sınıflandırma (Availability)
  - **W3** — Çevrim süresi iyileştirme (Performance)
  - **W4** — Fire oranı (Quality)

### 🔔 Alarmlar & Kök Neden Analizi (RCA)
- **Alarm Listesi**: Makine bazlı CNC alarm geçmişi
- **Alarm Pareto**: En sık tekrarlayan alarmlar (makine veya tesis geneli)
- **Kök Neden Kartı**: Alarm + telemetri kanıtı + hipotez + öneri
- **Zaman Çizelgesi**: Olay etrafında ±N dakika alarm + duruş + telemetri görselleştirmesi
- **İstatistiksel Sapma**: Telemetri sinyalinin olay anındaki z-skoru analizi
- **AI Analizi**: Google Gemini Flash ile detaylı Türkçe kök neden raporu (opsiyonel)

### 📦 İş Emirleri & Stok
- **İş Emirleri**: Vardiya günündeki iş emri çalışmaları (süre, çevrim, program)
- **Stok / Program Özeti**: Tarih aralığında program bazlı üretim metrikleri (gerçek sayaç verisi)

### 🏗️ Filo Yönetimi
- **Kuş Bakışı Dashboard**: Tesis geneli KPI + makine durum matrisi
- **Öncelik Panosu**: 7 günlük ortalama OEE sparkline ile makine sıralaması
- **Makine Ranking**: Tarih aralığında ortalama OEE sıralaması
- **Ortak Alarm Örüntüleri**: Birden fazla makinede tekrarlayan alarm analizi

### 📄 Raporlama
- **PDF Dışa Aktarma**: Aktif görünümden kurumsal PDF rapor oluşturma (KPI + grafik + tablo)
- **Tema Desteği**: Açık / koyu tema

---

## 🏗 Mimari

```
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│         React 18 + Vite + Recharts              │
│         (SPA, açık/koyu tema, PDF export)        │
└──────────────────────┬──────────────────────────┘
                       │ HTTP/JSON (REST)
                       │ CORS enabled
┌──────────────────────▼──────────────────────────┐
│                   Backend                        │
│              FastAPI + Uvicorn                   │
│                                                  │
│  api.py ──► service.py ──► oee_baseline.py      │
│                          ──► oee_whatif.py       │
│                          ──► rca.py             │
│                          ──► finance.py          │
│                          ──► ai.py (Gemini)      │
│                                                  │
│  repository.py  (CSV/Parquet → Pandas cache)     │
│  config.py      (.env → pydantic-settings)       │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │   uludag_hackathon_dataset  │
        │   (CSV / Parquet dosyaları) │
        └─────────────────────────────┘
```

---

## 🛠 Teknoloji Yığını

| Katman | Teknoloji | Sürüm |
|--------|-----------|-------|
| **Frontend** | React | 18.3 |
| | Vite | 6.x |
| | Recharts | 2.13 |
| | Lucide React | 1.17 |
| **Backend** | Python | 3.11+ |
| | FastAPI | ≥0.136 |
| | Uvicorn | ≥0.49 |
| | Pandas | ≥2.2 |
| | Pydantic | ≥2.10 |
| | DuckDB | ≥1.5 |
| | ReportLab | ≥4.0 |
| **AI (Opsiyonel)** | Google Gemini Flash | 2.0 |

---

## 🚀 Kurulum

### Gereksinimler
- Python 3.11+
- Node.js 18+
- npm veya yarn

### 1. Repoyu Klonlayın

```bash
git clone <repo-url>
cd hackathon_26
```

### 2. Backend kurulumu

```bash
cd backend

# Sanal ortam oluşturun (önerilir)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Ortam değişkenlerini yapılandırın
cp .env.example .env
# .env dosyasını düzenleyin (veri seti yolu, Gemini API anahtarı vb.)
```

### 3. Frontend kurulumu

```bash
cd frontend
npm install
```

### 4. Veri seti

`uludag_hackathon_dataset` klasörünün projenin bir üst dizininde (`hackathon_26/` ile aynı seviyede) bulunduğundan emin olun. Alternatif olarak `.env` dosyasında `OEE_DATA_DIR` ile özel yol belirleyebilirsiniz.

---

## ▶️ Çalıştırma

### Backend

```bash
cd backend
uvicorn api:app --reload --port 8000
```

API otomatik dokümantasyonu: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Frontend

```bash
cd frontend
npm run dev
```

Varsayılan adres: [http://localhost:5173](http://localhost:5173)

---

## 📡 API Endpoint'leri

### Katalog
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/machines` | Tüm makineleri listeler |
| `GET` | `/machines/{machine}/dates` | Makine için OEE kaydı olan günler |

### OEE
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/oee/baseline` | Baz OEE (A × P × Q) ayrıştırması |
| `GET` | `/oee/pareto` | Plansız duruş Pareto'su (Top N) |
| `GET` | `/oee/trend` | OEE/A/P trendi (tarih aralığı veya son N gün) |
| `GET` | `/oee/hourly-trend` | Saatlik OEE/A/P trendi |
| `GET` | `/oee/stoppage-trend` | Saatlik planlı/plansız duruş süresi |
| `GET` | `/oee/stoppage-kpis` | Duruş özet KPI'ları (MTBF, MTTR) |
| `GET` | `/oee/counter-trend` | Saatlik üretilen parça sayısı |
| `POST` | `/oee/whatif` | What-If simülasyonu (OEE + finansal ROI) |

### RCA (Kök Neden)
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/rca/alerts` | CNC alarmları (gün filtresi opsiyonel) |
| `GET` | `/rca/alert-pareto` | En sık tekrarlayan alarmlar |
| `GET` | `/rca/timeline` | Olay çevresinde alarm + duruş + telemetri |
| `GET` | `/rca/root-cause` | Kanıtlı kök neden kartı |
| `POST` | `/rca/analyze` | AI destekli kök neden analizi (Gemini) |
| `GET` | `/rca/deviation` | Telemetri sinyal sapma analizi |

### Filo
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/fleet/dashboard` | Tesis kuş bakışı dashboard |
| `GET` | `/fleet/ranking` | Makine OEE sıralaması |
| `GET` | `/fleet/alarm-patterns` | Ortak alarm örüntüleri |

### İş Emirleri & Stok
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/workorders` | İş emri çalışmaları |
| `GET` | `/stock` | Stok / program özeti |

### Finans & Rapor
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/finance/assumptions` | Varsayılan finansal parametreler |
| `POST` | `/report/pdf` | Kurumsal PDF rapor oluşturma |

---

## 📁 Proje Yapısı

```
hackathon_26/
├── backend/
│   ├── api.py                 # FastAPI endpoint tanımları
│   ├── service.py             # Orkestrasyon / iş mantığı katmanı
│   ├── oee_baseline.py        # OEE baz hesaplama çekirdeği
│   ├── oee_whatif.py          # What-If simülasyon motoru
│   ├── rca.py                 # Kök neden analizi (alarm + telemetri)
│   ├── finance.py             # Finansal etki hesaplama (ROI)
│   ├── ai.py                  # Gemini AI entegrasyonu
│   ├── repository.py          # Veri erişim katmanı (CSV/Parquet → cache)
│   ├── nightwatch_repo.py     # DuckDB telemetri sorguları
│   ├── report.py              # PDF rapor üretimi (ReportLab)
│   ├── config.py              # Pydantic-settings yapılandırma
│   ├── requirements.txt       # Python bağımlılıkları
│   ├── .env.example           # Ortam değişkenleri şablonu
│   └── .env                   # Yerel ortam değişkenleri (git'e eklenmez)
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx            # Ana uygulama bileşeni (sekme yönlendirme)
│       ├── api.js             # Backend API istemcisi
│       ├── main.jsx           # React giriş noktası
│       ├── pdf.js             # PDF dışa aktarma yardımcısı
│       ├── styles.css         # Uygulama stilleri (açık/koyu tema)
│       └── components/
│           ├── HomeView.jsx           # Ana sayfa (OEE gösterge + KPI)
│           ├── FleetView.jsx          # Filo yönetim paneli
│           ├── AlarmlarView.jsx       # Alarm listesi + RCA
│           ├── RootCauseCard.jsx      # Kök neden kartı bileşeni
│           ├── WorkOrdersView.jsx     # İş emirleri tablosu
│           ├── StockView.jsx          # Stok / program özeti
│           ├── WhatIfPanel.jsx        # What-If simülasyon paneli
│           ├── ParetoChart.jsx        # Pareto çubuk grafiği
│           ├── WaterfallChart.jsx     # OEE waterfall grafiği
│           ├── OeeTrendChart.jsx      # OEE trend çizgi grafiği
│           ├── StoppageTrendChart.jsx # Duruş trend grafiği
│           ├── StoppageKpiCards.jsx   # Duruş KPI kartları
│           ├── CounterTrendChart.jsx  # Üretim sayaç grafiği
│           ├── AlarmParetoChart.jsx   # Alarm Pareto grafiği
│           ├── DateRangePicker.jsx    # Tarih aralığı seçici
│           ├── ExportPdfButton.jsx    # PDF dışa aktarma butonu
│           ├── Gauge.jsx              # OEE gösterge bileşeni
│           ├── Donut.jsx              # Halka grafik bileşeni
│           └── Card.jsx              # Genel kart bileşeni
│
├── .gitignore
└── README.md
```

---

## ⚙️ Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `OEE_DATA_DIR` | `../uludag_hackathon_dataset` | Veri seti klasör yolu |
| `OEE_API_HOST` | `127.0.0.1` | API sunucu adresi |
| `OEE_API_PORT` | `8000` | API sunucu portu |
| `OEE_CORS_ORIGINS` | `*` | İzin verilen CORS origin'leri |
| `OEE_LOG_LEVEL` | `info` | Loglama seviyesi |
| `OEE_CURRENCY` | `₺` | Para birimi simgesi |
| `OEE_RCA_WINDOW_MINUTES` | `15` | RCA olay penceresi (dakika) |
| `OEE_GEMINI_API_KEY` | *(boş)* | Google Gemini API anahtarı |
| `OEE_GEMINI_MODEL` | `gemini-3.5-flash` | Gemini model adı |

---

## 📜 Lisans

Bu proje Uludağ Hackathon 2026 kapsamında geliştirilmiştir.
