"""
Canal Dark — Módulo 4: Geração de Legendas Estilo Viral
Gera arquivo .ass (Advanced SubStation Alpha) com estilo word-by-word highlight.
Usa os timestamps do Edge-TTS (sem precisar de Whisper).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")

# ---------------------------------------------------------------------------
# Template ASS para legendas estilo viral
# ---------------------------------------------------------------------------
ASS_HEADER = """[Script Info]
Title: Canal Dark Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Viral,Montserrat,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,200,1
Style: ViralHighlight,Montserrat,78,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,40,40,200,1
Style: Hook,Montserrat,84,&H0000D4FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,40,40,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ms_to_ass_time(ms: int) -> str:
    """Converte milissegundos para formato de tempo ASS (H:MM:SS.CC)."""
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    centiseconds = int((seconds % 1) * 100)
    seconds = int(seconds)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def build_word_highlight_line(
    words: list[dict],
    style: str = "Viral",
) -> list[str]:
    """
    Constrói linhas ASS com highlight word-by-word.
    Agrupa palavras em chunks de 3-5 para legibilidade.

    Args:
        words: Lista de {"word": str, "start_ms": int, "end_ms": int}
        style: Nome do estilo ASS a usar.

    Returns:
        Lista de linhas ASS formatadas.
    """
    if not words:
        return []

    lines = []
    chunk_size = 4  # Palavras por grupo
    padding_ms = 50  # Padding entre chunks

    for i in range(0, len(words), chunk_size):
        chunk = words[i : i + chunk_size]
        if not chunk:
            continue

        chunk_start = max(0, chunk[0]["start_ms"] - padding_ms)
        chunk_end = chunk[-1]["end_ms"] + padding_ms

        # Texto do chunk (todas as palavras juntas)
        chunk_text = " ".join(w["word"] for w in chunk)

        start_time = ms_to_ass_time(chunk_start)
        end_time = ms_to_ass_time(chunk_end)

        # Usar {\fad(150,150)} para fade suave
        line = f"Dialogue: 0,{start_time},{end_time},{style},,0,0,0,,{{\\fad(100,100)}}{chunk_text}"
        lines.append(line)

    return lines


def generate_subtitles(video_id: str) -> str:
    """
    Gera arquivo de legendas .ass a partir dos metadados de voz.

    Args:
        video_id: ID do vídeo.

    Returns:
        Caminho do arquivo .ass gerado.
    """
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    voice_meta_path = os.path.join(assets_dir, "voice_metadata.json")

    if not os.path.exists(voice_meta_path):
        raise FileNotFoundError(
            f"Metadados de voz não encontrados: {voice_meta_path}\n"
            "Execute generate_voice.py primeiro."
        )

    with open(voice_meta_path, "r", encoding="utf-8") as f:
        voice_data = json.load(f)

    ass_lines = [ASS_HEADER]
    current_offset_ms = 0  # Offset acumulado entre segmentos

    # Gancho
    hook = voice_data.get("hook")
    if hook and hook.get("timestamps"):
        hook_lines = build_word_highlight_line(
            hook["timestamps"],
            style="Hook",
        )
        ass_lines.extend(hook_lines)
        current_offset_ms = hook["duration_ms"] + 200  # Gap entre gancho e cenas

    # Cenas
    for scene_idx, scene_voice in enumerate(voice_data.get("scenes", []), 1):
        # Narração
        narration = scene_voice.get("narration")
        if narration and narration.get("timestamps"):
            # Ajustar timestamps com offset
            adjusted = [
                {
                    "word": w["word"],
                    "start_ms": w["start_ms"] + current_offset_ms,
                    "end_ms": w["end_ms"] + current_offset_ms,
                }
                for w in narration["timestamps"]
            ]
            lines = build_word_highlight_line(adjusted, style="Viral")
            ass_lines.extend(lines)
            current_offset_ms += narration["duration_ms"] + 100

        # Diálogo
        dialogue = scene_voice.get("dialogue")
        if dialogue and dialogue.get("timestamps"):
            adjusted = [
                {
                    "word": w["word"],
                    "start_ms": w["start_ms"] + current_offset_ms,
                    "end_ms": w["end_ms"] + current_offset_ms,
                }
                for w in dialogue["timestamps"]
            ]
            lines = build_word_highlight_line(adjusted, style="ViralHighlight")
            ass_lines.extend(lines)
            current_offset_ms += dialogue["duration_ms"] + 100

        # Gap entre cenas
        current_offset_ms += 300

    # Salvar arquivo .ass
    ass_path = os.path.join(assets_dir, "subtitles.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_lines))

    total_events = len([l for l in ass_lines if l.startswith("Dialogue:")])
    print(f"✅ Legendas geradas: {ass_path}")
    print(f"   Eventos de legenda: {total_events}")
    print(f"   Duração total: {current_offset_ms/1000:.1f}s")

    return ass_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerar legendas estilo viral")
    parser.add_argument("video_id", type=str, help="ID do vídeo")
    args = parser.parse_args()

    generate_subtitles(args.video_id)
