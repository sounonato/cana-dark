#!/bin/bash
# =============================================================================
# Canal Dark — Script de Setup da VPS (Ubuntu)
# Rodar UMA VEZ na VPS após clonar o repositório
# Uso: bash setup_vps.sh
# =============================================================================
set -euo pipefail

echo "============================================"
echo "🚀 Canal Dark — Setup VPS"
echo "============================================"

# ---------------------------------------------------------------------------
# 1. Atualizar sistema
# ---------------------------------------------------------------------------
echo ""
echo "📦 [1/6] Atualizando pacotes..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ---------------------------------------------------------------------------
# 2. Instalar FFmpeg
# ---------------------------------------------------------------------------
echo ""
echo "🎬 [2/6] Instalando FFmpeg..."
sudo apt-get install -y ffmpeg

# Verificar instalação
ffmpeg_version=$(ffmpeg -version 2>&1 | head -1)
echo "  ✅ $ffmpeg_version"

# Verificar suporte a libass (legendas)
ffmpeg -filters 2>/dev/null | grep -q "ass" && echo "  ✅ libass suportado" || echo "  ⚠️  libass não encontrado — instalando..."
sudo apt-get install -y libass-dev 2>/dev/null || true

# ---------------------------------------------------------------------------
# 3. Instalar Python e pip
# ---------------------------------------------------------------------------
echo ""
echo "🐍 [3/6] Verificando Python..."
python3 --version
pip3 --version || sudo apt-get install -y python3-pip

# ---------------------------------------------------------------------------
# 4. Criar ambiente virtual e instalar dependências Python
# ---------------------------------------------------------------------------
echo ""
echo "📚 [4/6] Instalando dependências Python..."

cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "  ✅ Dependências instaladas:"
pip list | grep -E "google-genai|edge-tts|faster-whisper|python-dotenv|Pillow"

# ---------------------------------------------------------------------------
# 5. Criar estrutura de pastas de dados
# ---------------------------------------------------------------------------
echo ""
echo "📁 [5/6] Criando estrutura de pastas..."

mkdir -p data/{assets,output,archive,db}
mkdir -p config/{music,fonts}
mkdir -p logs
mkdir -p n8n/workflows

echo "  ✅ Pastas criadas"

# ---------------------------------------------------------------------------
# 6. Inicializar banco de dados
# ---------------------------------------------------------------------------
echo ""
echo "🗄️  [6/6] Inicializando banco de dados..."

python3 scripts/init_db.py

echo "  ✅ SQLite inicializado"

# ---------------------------------------------------------------------------
# Instruções finais
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "✅ SETUP COMPLETO!"
echo "============================================"
echo ""
echo "🔑 PRÓXIMO PASSO: Configurar o .env"
echo ""
echo "  cp .env.example .env"
echo "  nano .env"
echo ""
echo "  Preencha pelo menos:"
echo "  GEMINI_API_KEY=sua_chave_aqui"
echo "  TELEGRAM_BOT_TOKEN=seu_bot_token"
echo "  TELEGRAM_CHAT_ID=seu_chat_id"
echo ""
echo "🧪 DEPOIS: Teste o pipeline"
echo ""
echo "  source .venv/bin/activate"
echo "  python3 scripts/pipeline.py --skip-images --skip-voice"
echo "  # (testa só o roteiro primeiro)"
echo ""
echo "  python3 scripts/generate_script.py --theme 'Ela achou o celular dele desbloqueado'"
echo ""
echo "============================================"
