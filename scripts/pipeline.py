"""
Canal Dark — Pipeline Orquestrador
Encadeia todos os módulos para gerar um vídeo completo.
Pode ser chamado por CLI ou pelo n8n.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Importar módulos do pipeline
from generate_script import generate_script
from generate_images import generate_all_images
from generate_voice import generate_voices_sync
from generate_subtitles import generate_subtitles
from init_db import init_database
from notify import notify_pipeline_start, notify_pipeline_success, notify_pipeline_error

DATA_DIR = os.getenv("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "db", "pipeline.sqlite")


class PipelineError(Exception):
    """Erro durante a execução do pipeline."""
    def __init__(self, step: str, message: str):
        self.step = step
        self.message = message
        super().__init__(f"[{step}] {message}")


def log_step(video_id: str, step: str, status: str, message: str = "", duration: float = 0):
    """Registra uma etapa no banco de dados."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """INSERT INTO pipeline_logs (video_id, step, status, message, duration_seconds)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, step, status, message, duration),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠️ Erro ao registrar log: {e}")


def update_video_status(video_id: str, status: str, **kwargs):
    """Atualiza o status de um vídeo no banco."""
    try:
        conn = sqlite3.connect(DB_PATH)
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values = [status]

        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)

        values.append(video_id)
        conn.execute(
            f"UPDATE videos SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠️ Erro ao atualizar status: {e}")


def create_video_record(video_id: str, theme: str = None) -> str:
    """Cria um registro de vídeo no banco."""
    conn = sqlite3.connect(DB_PATH)
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    conn.execute(
        """INSERT OR IGNORE INTO videos (id, theme, assets_dir)
           VALUES (?, ?, ?)""",
        (video_id, theme, assets_dir),
    )
    conn.commit()
    conn.close()
    return video_id


def run_pipeline(
    theme: str = None,
    video_id: str = None,
    skip_images: bool = False,
    skip_voice: bool = False,
) -> dict:
    """
    Executa o pipeline completo para gerar um vídeo.

    Args:
        theme: Tema da história. Se None, escolhe aleatório.
        video_id: ID do vídeo. Se None, gera automaticamente.
        skip_images: Se True, pula geração de imagens (para testes).
        skip_voice: Se True, pula geração de voz (para testes).

    Returns:
        Dict com resultado do pipeline.
    """
    # Garantir que o banco existe
    init_database(DB_PATH)

    if video_id is None:
        video_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    print("=" * 60)
    print(f"🚀 CANAL DARK — Pipeline Iniciado")
    print(f"   Video ID: {video_id}")
    print(f"   Tema: {theme or 'aleatório'}")
    print(f"   Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    create_video_record(video_id, theme)
    result = {"video_id": video_id, "steps": {}}

    # Notificar início no Telegram
    notify_pipeline_start(video_id, theme or "aleatório")

    # -----------------------------------------------------------------------
    # ETAPA 1: Roteiro
    # -----------------------------------------------------------------------
    print("\n📝 ETAPA 1: Gerando roteiro...")
    t0 = time.time()
    try:
        script_data = generate_script(theme=theme, video_id=video_id)
        duration = time.time() - t0
        result["steps"]["script"] = {
            "status": "success",
            "duration": duration,
            "title": script_data["script"].get("titulo", ""),
        }
        update_video_status(
            video_id, "script_generated",
            title=script_data["script"].get("titulo", ""),
            script_json=json.dumps(script_data, ensure_ascii=False),
            last_step_completed="script",
        )
        log_step(video_id, "script", "success", duration=duration)
    except Exception as e:
        duration = time.time() - t0
        log_step(video_id, "script", "failed", str(e), duration)
        update_video_status(video_id, "failed", last_error=str(e))
        notify_pipeline_error(video_id, "script", str(e))
        raise PipelineError("script", str(e))

    # -----------------------------------------------------------------------
    # ETAPA 2: Imagens
    # -----------------------------------------------------------------------
    if not skip_images:
        print("\n🎨 ETAPA 2: Gerando imagens...")
        t0 = time.time()
        try:
            image_paths = generate_all_images(video_id)
            duration = time.time() - t0
            success_count = len([p for p in image_paths if p])
            result["steps"]["images"] = {
                "status": "success",
                "duration": duration,
                "count": success_count,
            }
            update_video_status(video_id, "images_generated", last_step_completed="images")
            log_step(video_id, "images", "success", f"{success_count} images", duration)
        except Exception as e:
            duration = time.time() - t0
            log_step(video_id, "images", "failed", str(e), duration)
            update_video_status(video_id, "failed", last_error=str(e))
            raise PipelineError("images", str(e))
    else:
        print("\n⏭️  ETAPA 2: Imagens (pulada)")

    # -----------------------------------------------------------------------
    # ETAPA 3: Voz
    # -----------------------------------------------------------------------
    if not skip_voice:
        print("\n🎤 ETAPA 3: Gerando vozes...")
        t0 = time.time()
        try:
            voice_data = generate_voices_sync(video_id)
            duration = time.time() - t0
            result["steps"]["voice"] = {
                "status": "success",
                "duration": duration,
                "total_duration_s": voice_data.get("total_duration_seconds", 0),
            }
            update_video_status(video_id, "voice_generated", last_step_completed="voice")
            log_step(video_id, "voice", "success", duration=duration)
        except Exception as e:
            duration = time.time() - t0
            log_step(video_id, "voice", "failed", str(e), duration)
            update_video_status(video_id, "failed", last_error=str(e))
            raise PipelineError("voice", str(e))
    else:
        print("\n⏭️  ETAPA 3: Voz (pulada)")

    # -----------------------------------------------------------------------
    # ETAPA 4: Legendas
    # -----------------------------------------------------------------------
    if not skip_voice:
        print("\n📝 ETAPA 4: Gerando legendas...")
        t0 = time.time()
        try:
            subtitle_path = generate_subtitles(video_id)
            duration = time.time() - t0
            result["steps"]["subtitles"] = {
                "status": "success",
                "duration": duration,
                "path": subtitle_path,
            }
            update_video_status(video_id, "subtitles_ready", last_step_completed="subtitles")
            log_step(video_id, "subtitles", "success", duration=duration)
        except Exception as e:
            duration = time.time() - t0
            log_step(video_id, "subtitles", "failed", str(e), duration)
            update_video_status(video_id, "failed", last_error=str(e))
            raise PipelineError("subtitles", str(e))
    else:
        print("\n⏭️  ETAPA 4: Legendas (pulada)")

    # -----------------------------------------------------------------------
    # ETAPA 5: Montagem FFmpeg
    # -----------------------------------------------------------------------
    if not skip_images and not skip_voice:
        print("\n🎬 ETAPA 5: Montagem final...")
        t0 = time.time()
        try:
            update_video_status(video_id, "composing")
            scripts_dir = os.path.dirname(os.path.abspath(__file__))
            compose_script = os.path.join(scripts_dir, "ffmpeg_compose.sh")

            result_code = subprocess.run(
                ["bash", compose_script, video_id, DATA_DIR],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
            )

            if result_code.returncode != 0:
                raise Exception(f"FFmpeg falhou:\n{result_code.stderr}")

            output_path = os.path.join(DATA_DIR, "output", video_id, "final_9x16.mp4")
            duration = time.time() - t0

            if not os.path.exists(output_path):
                raise Exception("Vídeo final não foi gerado")

            file_size = os.path.getsize(output_path)
            result["steps"]["compose"] = {
                "status": "success",
                "duration": duration,
                "output_path": output_path,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
            }

            # Gerar caption para redes sociais
            caption = script_data["script"].get("caption", "")
            hashtags = " ".join(script_data["script"].get("hashtags", []))

            update_video_status(
                video_id,
                "ready_for_upload",
                output_path=output_path,
                caption=f"{caption}\n\n{hashtags}",
                hashtags=hashtags,
                last_step_completed="compose",
            )
            log_step(video_id, "compose", "success", f"{file_size/1024/1024:.1f}MB", duration)

        except Exception as e:
            duration = time.time() - t0
            log_step(video_id, "compose", "failed", str(e), duration)
            update_video_status(video_id, "failed", last_error=str(e))
            raise PipelineError("compose", str(e))
    else:
        print("\n⏭️  ETAPA 5: Montagem (pulada — faltam assets)")

    # -----------------------------------------------------------------------
    # RESULTADO FINAL
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("🏁 PIPELINE CONCLUÍDO!")
    print(f"   Video ID: {video_id}")

    total_time = sum(s.get("duration", 0) for s in result["steps"].values())
    print(f"   Tempo total: {total_time:.1f}s")

    if "compose" in result["steps"]:
        print(f"   Vídeo final: {result['steps']['compose'].get('output_path', 'N/A')}")
        print(f"   Tamanho: {result['steps']['compose'].get('file_size_mb', 'N/A')} MB")

    # Notificar sucesso no Telegram
    notify_pipeline_success(
        video_id,
        result.get("steps", {}).get("script", {}).get("title", "sem título"),
        total_time,
    )

    print("=" * 60)

    # Salvar resultado completo
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    result_path = os.path.join(assets_dir, "pipeline_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline completo do Canal Dark")
    parser.add_argument("--theme", "-t", type=str, help="Tema da história")
    parser.add_argument("--id", type=str, help="ID do vídeo")
    parser.add_argument("--skip-images", action="store_true", help="Pular geração de imagens")
    parser.add_argument("--skip-voice", action="store_true", help="Pular geração de voz")
    args = parser.parse_args()

    try:
        result = run_pipeline(
            theme=args.theme,
            video_id=args.id,
            skip_images=args.skip_images,
            skip_voice=args.skip_voice,
        )
    except PipelineError as e:
        print(f"\n❌ Pipeline falhou na etapa '{e.step}': {e.message}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrompido pelo usuário")
        sys.exit(130)
