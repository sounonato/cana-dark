"""
Canal Dark — Inicialização do Banco de Dados SQLite
Rastreia o estado de cada vídeo no pipeline.
"""

import sqlite3
import os
from pathlib import Path


def init_database(db_path: str = None) -> None:
    """Cria o banco SQLite com as tabelas do pipeline."""
    if db_path is None:
        db_path = os.path.join(
            os.getenv("DATA_DIR", "./data"), "db", "pipeline.sqlite"
        )

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tabela principal: cada vídeo no pipeline
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Status do pipeline
            status TEXT DEFAULT 'pending' 
                CHECK(status IN (
                    'pending',           -- aguardando processamento
                    'script_generated',  -- roteiro pronto
                    'images_generated',  -- imagens prontas
                    'voice_generated',   -- áudios prontos
                    'subtitles_ready',   -- legendas prontas
                    'composing',         -- montagem em andamento
                    'ready_for_upload',  -- vídeo final pronto
                    'uploaded',          -- publicado
                    'failed',            -- erro em alguma etapa
                    'archived'           -- movido para arquivo
                )),
            
            -- Dados do roteiro
            title TEXT,
            script_json TEXT,           -- roteiro completo em JSON
            theme TEXT,                  -- tema/categoria do vídeo
            
            -- Metadados de publicação
            caption TEXT,                -- legenda para redes sociais
            hashtags TEXT,               -- hashtags separadas por vírgula
            instagram_post_id TEXT,      -- ID do post no Instagram (após upload)
            tiktok_post_id TEXT,         -- ID do post no TikTok (após upload)
            
            -- Caminhos dos assets
            assets_dir TEXT,             -- path da pasta de assets
            output_path TEXT,            -- path do vídeo final
            
            -- Controle de erro e retry
            last_error TEXT,
            retry_count INTEGER DEFAULT 0,
            last_step_completed TEXT      -- última etapa concluída com sucesso
        )
    """)

    # Tabela de log: cada etapa executada
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            step TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('started', 'success', 'failed')),
            message TEXT,
            duration_seconds REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        )
    """)

    # Tabela de custos: rastrear gastos por serviço
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            service TEXT NOT NULL,         -- 'gemini_text', 'imagen', 'veo', etc.
            operation TEXT,                -- 'generate_script', 'generate_image', etc.
            cost_usd REAL DEFAULT 0.0,
            tokens_used INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        )
    """)

    # Índices para consultas frequentes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_video ON pipeline_logs(video_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_costs_video ON cost_tracking(video_id)
    """)

    conn.commit()
    conn.close()
    print(f"✅ Banco de dados inicializado em: {db_path}")


if __name__ == "__main__":
    init_database()
