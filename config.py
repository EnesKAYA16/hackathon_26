"""
YAPILANDIRMA (Settings)
=======================

Tüm ortam-bağımlı ayarlar tek yerde. Değerler `.env` dosyasından (OEE_ önekiyle)
veya ortam değişkenlerinden okunur; yoksa buradaki varsayılanlar kullanılır.

Örnek .env satırı:  OEE_API_PORT=9000
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CONFIG_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="OEE_",
        extra="ignore",
    )

    # Veri seti klasörü (göreli verilirse config.py'ye göre çözülür)
    data_dir: Path = CONFIG_DIR.parent / "uludag_hackathon_dataset"

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "*"  # virgülle ayrılmış origin listesi
    log_level: str = "info"

    # Alan ayarları
    currency: str = "₺"
    rca_window_minutes: int = 15  # RCA zaman çizelgesi penceresi (±dakika)

    # Gemini (Google) — AI kök neden analizi. Anahtar SADECE .env'den okunur (kodda yok).
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, v: Path) -> Path:
        v = Path(v)
        return v if v.is_absolute() else (CONFIG_DIR / v).resolve()

    @property
    def cors_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Uygulama genelinde tek örnek
settings = Settings()
