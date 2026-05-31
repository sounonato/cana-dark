"""
Canal Dark — Módulo 3: Geração de Voz (Edge-TTS)
Gera áudio em PT-BR com vozes naturais gratuitas.
Retorna timestamps por palavra para legendas.
"""

import asyncio
import json
import os
import re
from pathlib import Path

import edge_tts
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
TTS_VOICE_MALE = os.getenv("TTS_VOICE_MALE", "pt-BR-AntonioNeural")
TTS_VOICE_FEMALE = os.getenv("TTS_VOICE_FEMALE", "pt-BR-FranciscaNeural")
DATA_DIR = os.getenv("DATA_DIR", "./data")

# Voz do narrador (para narração que não é diálogo)
TTS_VOICE_NARRATOR = os.getenv("TTS_VOICE_NARRATOR", "pt-BR-AntonioNeural")


async def generate_speech_segment(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> list[dict]:
    """
    Gera um segmento de áudio com Edge-TTS e captura timestamps por palavra.

    Args:
        text: Texto para sintetizar.
        voice: Nome da voz Edge-TTS.
        output_path: Caminho do arquivo de saída (.mp3).
        rate: Velocidade da fala (ex: "+10%", "-5%").
        pitch: Pitch da voz (ex: "+2Hz", "-3Hz").

    Returns:
        Lista de dicts com timestamps por palavra:
        [{"word": "olá", "start_ms": 0, "end_ms": 350}, ...]
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")

    word_timestamps = []

    # Coletar timestamps via SubMaker
    submaker = edge_tts.SubMaker()

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timestamps.append({
                    "word": chunk["text"],
                    "start_ms": chunk["offset"] // 10000,  # 100-nanosecond units → ms
                    "end_ms": (chunk["offset"] + chunk["duration"]) // 10000,
                })

    return word_timestamps


def get_voice_for_segment(segment_type: str, character: str = None) -> str:
    """Retorna a voz correta baseado no tipo de segmento."""
    if segment_type == "dialogo":
        if character and character.lower() in ("ele", "him", "masc", "masculino"):
            return TTS_VOICE_MALE
        elif character and character.lower() in ("ela", "her", "fem", "feminino"):
            return TTS_VOICE_FEMALE
    return TTS_VOICE_NARRATOR


async def generate_scene_voice(
    scene: dict,
    scene_index: int,
    video_id: str,
) -> dict:
    """
    Gera os áudios de uma cena (narração + diálogo).

    Returns:
        Dict com paths e timestamps:
        {
            "narration": {"path": "...", "timestamps": [...], "duration_ms": ...},
            "dialogue": {"path": "...", "timestamps": [...], "duration_ms": ...},
        }
    """
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    Path(assets_dir).mkdir(parents=True, exist_ok=True)

    result = {}

    # 1. Narração
    narration_text = scene.get("narração", scene.get("narracao", ""))
    if narration_text and narration_text.strip():
        narr_path = os.path.join(assets_dir, f"voice_narr_{scene_index:02d}.mp3")
        timestamps = await generate_speech_segment(
            text=narration_text.strip(),
            voice=TTS_VOICE_NARRATOR,
            output_path=narr_path,
        )
        duration_ms = timestamps[-1]["end_ms"] if timestamps else 0
        result["narration"] = {
            "path": narr_path,
            "text": narration_text.strip(),
            "timestamps": timestamps,
            "duration_ms": duration_ms,
        }
        print(f"  🎙️  Narração cena {scene_index}: {duration_ms}ms")

    # 2. Diálogo
    dialogo = scene.get("dialogo", {})
    if isinstance(dialogo, dict) and dialogo.get("fala"):
        character = dialogo.get("personagem", "")
        voice = get_voice_for_segment("dialogo", character)
        dial_path = os.path.join(assets_dir, f"voice_dial_{scene_index:02d}.mp3")
        timestamps = await generate_speech_segment(
            text=dialogo["fala"].strip(),
            voice=voice,
            output_path=dial_path,
        )
        duration_ms = timestamps[-1]["end_ms"] if timestamps else 0
        result["dialogue"] = {
            "path": dial_path,
            "text": dialogo["fala"].strip(),
            "character": character,
            "voice": voice,
            "timestamps": timestamps,
            "duration_ms": duration_ms,
        }
        print(f"  🗣️  Diálogo cena {scene_index} ({character}): {duration_ms}ms")

    return result


async def generate_all_voices(video_id: str) -> dict:
    """
    Gera todos os áudios de um vídeo.

    Returns:
        Dict com dados de voz por cena + gancho.
    """
    # Carregar roteiro
    script_path = os.path.join(DATA_DIR, "assets", video_id, "roteiro.json")
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Roteiro não encontrado: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    script = script_data["script"]
    scenes = script["cenas"]
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)

    print(f"🎤 Gerando vozes para {len(scenes)} cenas do vídeo {video_id}...")

    voice_data = {"scenes": []}
    total_duration_ms = 0

    # Gancho (se existir)
    gancho = script.get("gancho", "")
    if gancho:
        gancho_path = os.path.join(assets_dir, "voice_gancho.mp3")
        timestamps = await generate_speech_segment(
            text=gancho,
            voice=TTS_VOICE_NARRATOR,
            output_path=gancho_path,
            rate="+5%",  # Gancho um pouco mais rápido = mais urgência
        )
        duration = timestamps[-1]["end_ms"] if timestamps else 0
        voice_data["hook"] = {
            "path": gancho_path,
            "text": gancho,
            "timestamps": timestamps,
            "duration_ms": duration,
        }
        total_duration_ms += duration
        print(f"  🪝 Gancho: {duration}ms")

    # Cenas
    for i, scene in enumerate(scenes, 1):
        scene_voice = await generate_scene_voice(scene, i, video_id)
        voice_data["scenes"].append(scene_voice)

        for segment in scene_voice.values():
            total_duration_ms += segment.get("duration_ms", 0)

    voice_data["total_duration_ms"] = total_duration_ms
    voice_data["total_duration_seconds"] = total_duration_ms / 1000

    # Salvar metadados de voz
    voice_meta_path = os.path.join(assets_dir, "voice_metadata.json")
    with open(voice_meta_path, "w", encoding="utf-8") as f:
        json.dump(voice_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Vozes geradas! Duração total: {total_duration_ms/1000:.1f}s")
    print(f"   Metadados salvos em: {voice_meta_path}")

    return voice_data


def generate_voices_sync(video_id: str) -> dict:
    """Wrapper síncrono para generate_all_voices."""
    return asyncio.run(generate_all_voices(video_id))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerar vozes das cenas")
    parser.add_argument("video_id", type=str, help="ID do vídeo")
    args = parser.parse_args()

    generate_voices_sync(args.video_id)
