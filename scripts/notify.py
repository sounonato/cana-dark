"""
Canal Dark — Módulo de Notificações Telegram
Envia alertas de erro e status do pipeline para o Telegram.
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """
    Envia mensagem para o Telegram.

    Returns:
        True se enviado com sucesso, False se falhou.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠️  Telegram não configurado — pulando notificação")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"  ⚠️  Falha ao enviar Telegram: {e}")
        return False


def notify_pipeline_start(video_id: str, theme: str) -> None:
    send_telegram(
        f"🎬 <b>Pipeline iniciado</b>\n"
        f"📹 ID: <code>{video_id}</code>\n"
        f"🎭 Tema: {theme}"
    )


def notify_pipeline_success(video_id: str, title: str, duration_s: float) -> None:
    send_telegram(
        f"✅ <b>Vídeo pronto para upload!</b>\n"
        f"📹 ID: <code>{video_id}</code>\n"
        f"🎬 Título: <i>{title}</i>\n"
        f"⏱️ Gerado em: {duration_s:.0f}s\n\n"
        f"📲 Faça upload manualmente no celular."
    )


def notify_pipeline_error(video_id: str, step: str, error: str) -> None:
    send_telegram(
        f"❌ <b>Pipeline falhou!</b>\n"
        f"📹 ID: <code>{video_id}</code>\n"
        f"⚠️ Etapa: <b>{step}</b>\n"
        f"💬 Erro: <code>{error[:300]}</code>"
    )


def notify_daily_summary(videos_generated: int, videos_failed: int) -> None:
    status = "✅" if videos_failed == 0 else "⚠️"
    send_telegram(
        f"{status} <b>Resumo diário — Canal Dark</b>\n"
        f"✅ Gerados: {videos_generated}\n"
        f"❌ Falharam: {videos_failed}"
    )


# ---------------------------------------------------------------------------
# Teste de configuração
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("🔔 Testando configuração do Telegram...")
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN não configurado no .env")
    elif not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID não configurado no .env")
    else:
        ok = send_telegram(
            "🎬 <b>Canal Dark — Teste de conexão</b>\n"
            "✅ Pipeline configurado e funcionando!\n"
            "🍋🍑 Léo e Pati estão prontos para o drama!"
        )
        print("✅ Mensagem enviada!" if ok else "❌ Falha ao enviar")
