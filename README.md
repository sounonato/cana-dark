# 🎬 Canal Dark — Pipeline Autônomo de Vídeos Virais

Pipeline automatizada para gerar vídeos curtos (Reels/TikTok) com um casal cartoon 3D em histórias de drama/fofoca viral com plot twist.

## Arquitetura

```
Roteiro (Gemini Flash) → Imagens (Gemini Image) → Voz (Edge-TTS)
    → Legendas (.ass) → Montagem (FFmpeg) → Upload (manual/API)
```

## Requisitos

### Na VPS (Ubuntu)
- Python 3.10+
- FFmpeg com suporte a libx264, libass
- Docker (para n8n)

### API Keys
- Google Gemini (AI Studio) — roteiro + imagens
- Telegram Bot — notificações de erro

## Setup Rápido

```bash
# 1. Clonar e configurar
cd /opt/canal-dark  # ou seu diretório
cp .env.example .env
# Editar .env com suas API keys

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Inicializar banco de dados
python scripts/init_db.py

# 4. Testar módulos isolados
python scripts/generate_script.py --theme "Ela achou uma caixa escondida no armário dele"
python scripts/generate_images.py <VIDEO_ID>
python scripts/generate_voice.py <VIDEO_ID>
python scripts/generate_subtitles.py <VIDEO_ID>
bash scripts/ffmpeg_compose.sh <VIDEO_ID>

# 5. Pipeline completo
python scripts/pipeline.py --theme "Ele esqueceu o aniversário dela"
```

## Estrutura de Pastas

```
cana-dark/
├── config/
│   ├── characters.json    # Descrição-mãe dos personagens
│   ├── music/             # Trilhas royalty-free
│   └── fonts/             # Fontes para legendas
├── scripts/
│   ├── pipeline.py        # Orquestrador principal
│   ├── generate_script.py # Módulo 1: Roteiro (Gemini)
│   ├── generate_images.py # Módulo 2: Imagens (Gemini)
│   ├── generate_voice.py  # Módulo 3: Voz (Edge-TTS)
│   ├── generate_subtitles.py # Módulo 4: Legendas (.ass)
│   ├── ffmpeg_compose.sh  # Módulo 5: Montagem FFmpeg
│   └── init_db.py         # Inicialização do SQLite
├── data/
│   ├── assets/{video_id}/ # Assets por vídeo
│   ├── output/{video_id}/ # Vídeos finais
│   ├── archive/           # Vídeos publicados
│   └── db/pipeline.sqlite # Estado do pipeline
├── n8n/workflows/         # Workflows exportados
└── logs/                  # Logs do sistema
```

## Custos Estimados

| Volume | Cenário | Custo/mês |
|--------|---------|-----------|
| 1/dia | Free tier total | R$ 0 |
| 1/dia | Imagen 4 Fast | ~R$ 15 |
| 3/dia | Imagen 4 Fast | ~R$ 45 |

## Módulos

Cada módulo roda isolado e pode ser testado independentemente:

1. **generate_script.py** — Gemini Flash gera roteiro JSON com cenas, diálogos e key_scenes
2. **generate_images.py** — Gera imagens com DESCRIÇÃO-MÃE fixa dos personagens
3. **generate_voice.py** — Edge-TTS com vozes distintas por personagem + timestamps
4. **generate_subtitles.py** — Gera .ass estilo viral (word-by-word highlight)
5. **ffmpeg_compose.sh** — Ken Burns + voz + trilha + legendas → MP4 9:16
6. **pipeline.py** — Encadeia tudo com logging e controle de estado

## Fases

- **Fase 1 (atual):** Scripts isolados, upload manual
- **Fase 2:** Workflow n8n com cron, upload semi-automático
- **Fase 3:** 100% autônomo, upload via API oficial
