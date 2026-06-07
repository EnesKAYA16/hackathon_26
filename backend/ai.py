"""
GEMINI (Google) AI İSTEMCİSİ
============================

Kök neden verisini Gemini Flash'a gönderip metinsel analiz alır.

GÜVENLİK: API anahtarı KODDA YOK. Yalnızca .env / ortam değişkeninden
(OEE_GEMINI_API_KEY) okunur ve istekte 'x-goog-api-key' header'ı ile gider
(URL'de görünmez, log'lara sızmaz). Harici paket gerekmez (stdlib urllib).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from config import settings

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def is_configured() -> bool:
    """Gemini anahtarı tanımlı mı?"""
    return bool(settings.gemini_api_key.strip())


def call_gemini(prompt: str, temperature: float = 0.4, max_tokens: int = 4096) -> str:
    """Gemini'ye prompt gönderir, üretilen metni döndürür. Hata -> RuntimeError.
    (Yüksek max_tokens: 'düşünen' modellerde düşünme + cevap için yeterli bütçe.)"""
    if not is_configured():
        raise RuntimeError("Gemini API anahtarı tanımlı değil (.env: OEE_GEMINI_API_KEY).")

    # Google'ın resmi yöntemi: API anahtarı ?key= query param olarak (header değil).
    # Anahtar kodda yok (.env'den), URL'i log'lamıyoruz -> sızıntı yok.
    key = urllib.parse.quote(settings.gemini_api_key.strip(), safe="")
    url = _URL.format(model=settings.gemini_model) + f"?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"Gemini API hatası {e.code}: {detail}")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Gemini çağrısı başarısız: {e}")

    try:
        cand = data["candidates"][0]
        parts = cand.get("content", {}).get("parts", [])
        # Tüm metin parçalarını birleştir (düşünen modeller çok parçalı dönebilir).
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    except (KeyError, IndexError):
        raise RuntimeError(f"Gemini yanıtı çözümlenemedi: {str(data)[:300]}")
    if not text:
        reason = cand.get("finishReason", "?")
        raise RuntimeError(f"Gemini boş yanıt (finishReason={reason}). "
                           f"Token limitini artırmayı veya farklı model denemeyi düşünün.")
    return text
