#!/bin/bash
# =============================================================================
# Canal Dark — Módulo 5: Montagem FFmpeg
# Monta o vídeo final em 9:16 com Ken Burns, voz, trilha e legendas.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Uso: ./ffmpeg_compose.sh <video_id> [data_dir]
# ---------------------------------------------------------------------------
VIDEO_ID="${1:?Erro: informe o video_id}"
DATA_DIR="${2:-./data}"

ASSETS_DIR="${DATA_DIR}/assets/${VIDEO_ID}"
OUTPUT_DIR="${DATA_DIR}/output/${VIDEO_ID}"

# Configurações de vídeo
WIDTH=1080
HEIGHT=1920
FPS=30
BACKGROUND_MUSIC_VOLUME=0.08  # Volume da trilha de fundo (0.0 a 1.0)

# Verificar se assets existem
if [ ! -d "${ASSETS_DIR}" ]; then
    echo "❌ Pasta de assets não encontrada: ${ASSETS_DIR}"
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

echo "🎬 Montando vídeo ${VIDEO_ID}..."
echo "   Assets: ${ASSETS_DIR}"
echo "   Output: ${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# 1. Descobrir imagens e áudios
# ---------------------------------------------------------------------------
SCENE_IMAGES=()
VOICE_FILES=()

for img in "${ASSETS_DIR}"/scene_*.png "${ASSETS_DIR}"/scene_*.jpg "${ASSETS_DIR}"/scene_*.webp; do
    [ -f "$img" ] && SCENE_IMAGES+=("$img")
done

for voice in "${ASSETS_DIR}"/voice_*.mp3; do
    [ -f "$voice" ] && VOICE_FILES+=("$voice")
done

GANCHO_VOICE="${ASSETS_DIR}/voice_gancho.mp3"
SUBTITLES="${ASSETS_DIR}/subtitles.ass"

echo "   Imagens encontradas: ${#SCENE_IMAGES[@]}"
echo "   Áudios encontrados: ${#VOICE_FILES[@]}"

if [ ${#SCENE_IMAGES[@]} -eq 0 ]; then
    echo "❌ Nenhuma imagem de cena encontrada!"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Calcular duração de cada cena baseado nos áudios
# ---------------------------------------------------------------------------
# Para cada cena, a duração = duração dos áudios correspondentes + padding
# Se não houver áudio, usa 3 segundos padrão
DEFAULT_SCENE_DURATION=3.0

get_audio_duration() {
    local file="$1"
    if [ -f "$file" ]; then
        ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$file" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# ---------------------------------------------------------------------------
# 3. Gerar clipes Ken Burns para cada imagem
# ---------------------------------------------------------------------------
echo ""
echo "🖼️  Gerando clipes Ken Burns..."

SCENE_CLIPS=()
TOTAL_DURATION=0

for i in "${!SCENE_IMAGES[@]}"; do
    img="${SCENE_IMAGES[$i]}"
    scene_num=$((i + 1))
    scene_num_padded=$(printf "%02d" ${scene_num})
    clip_path="${ASSETS_DIR}/clip_scene_${scene_num_padded}.mp4"

    # Calcular duração da cena baseado nos áudios
    narr_file="${ASSETS_DIR}/voice_narr_${scene_num_padded}.mp3"
    dial_file="${ASSETS_DIR}/voice_dial_${scene_num_padded}.mp3"

    narr_dur=$(get_audio_duration "$narr_file")
    dial_dur=$(get_audio_duration "$dial_file")

    # Duração = soma dos áudios + 0.5s padding, mínimo 3s
    scene_dur=$(echo "$narr_dur + $dial_dur + 0.5" | bc)
    scene_dur=$(echo "if ($scene_dur < $DEFAULT_SCENE_DURATION) $DEFAULT_SCENE_DURATION else $scene_dur" | bc)

    # Ken Burns: zoom suave de 1.0 para 1.15 (zoom in) ou 1.15 para 1.0 (zoom out)
    # Alternar entre zoom in e zoom out para variedade
    if [ $((scene_num % 2)) -eq 1 ]; then
        # Zoom in
        ZOOM_EXPR="min(zoom+0.0008,1.15)"
        X_EXPR="iw/2-(iw/zoom/2)"
        Y_EXPR="ih/2-(ih/zoom/2)"
    else
        # Zoom out (pan suave)
        ZOOM_EXPR="if(lte(zoom,1.0),1.15,max(zoom-0.0008,1.0))"
        X_EXPR="iw/2-(iw/zoom/2)"
        Y_EXPR="ih/2-(ih/zoom/2)"
    fi

    TOTAL_FRAMES=$(echo "$scene_dur * $FPS" | bc | cut -d. -f1)

    ffmpeg -y -loop 1 -i "$img" \
        -vf "scale=2160:3840,zoompan=z='${ZOOM_EXPR}':x='${X_EXPR}':y='${Y_EXPR}':d=${TOTAL_FRAMES}:s=${WIDTH}x${HEIGHT}:fps=${FPS},format=yuv420p" \
        -t "$scene_dur" \
        -c:v libx264 -preset fast -crf 23 \
        -an \
        "$clip_path" 2>/dev/null

    echo "  ✅ Cena ${scene_num}: ${scene_dur}s (Ken Burns)"
    SCENE_CLIPS+=("$clip_path")
    TOTAL_DURATION=$(echo "$TOTAL_DURATION + $scene_dur" | bc)
done

# ---------------------------------------------------------------------------
# 4. Concatenar todos os clipes de cena
# ---------------------------------------------------------------------------
echo ""
echo "🔗 Concatenando ${#SCENE_CLIPS[@]} clipes..."

# Criar lista de concat
CONCAT_LIST="${ASSETS_DIR}/concat_list.txt"
> "$CONCAT_LIST"
for clip in "${SCENE_CLIPS[@]}"; do
    echo "file '${clip}'" >> "$CONCAT_LIST"
done

CONCAT_VIDEO="${ASSETS_DIR}/concat_video.mp4"
ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" \
    -c:v libx264 -preset fast -crf 23 \
    -movflags +faststart \
    "$CONCAT_VIDEO" 2>/dev/null

echo "  ✅ Vídeo concatenado: ${TOTAL_DURATION}s"

# ---------------------------------------------------------------------------
# 5. Concatenar todos os áudios na ordem correta
# ---------------------------------------------------------------------------
echo ""
echo "🔊 Montando faixa de áudio..."

AUDIO_CONCAT_LIST="${ASSETS_DIR}/audio_concat_list.txt"
> "$AUDIO_CONCAT_LIST"

# Gancho primeiro (se existir)
if [ -f "$GANCHO_VOICE" ]; then
    echo "file '${GANCHO_VOICE}'" >> "$AUDIO_CONCAT_LIST"
fi

# Depois, para cada cena: narração + diálogo
for i in "${!SCENE_IMAGES[@]}"; do
    scene_num=$((i + 1))
    scene_num_padded=$(printf "%02d" ${scene_num})
    narr_file="${ASSETS_DIR}/voice_narr_${scene_num_padded}.mp3"
    dial_file="${ASSETS_DIR}/voice_dial_${scene_num_padded}.mp3"

    [ -f "$narr_file" ] && echo "file '${narr_file}'" >> "$AUDIO_CONCAT_LIST"
    [ -f "$dial_file" ] && echo "file '${dial_file}'" >> "$AUDIO_CONCAT_LIST"
done

CONCAT_AUDIO="${ASSETS_DIR}/concat_audio.mp3"
if [ -s "$AUDIO_CONCAT_LIST" ]; then
    ffmpeg -y -f concat -safe 0 -i "$AUDIO_CONCAT_LIST" \
        -c:a libmp3lame -b:a 192k \
        "$CONCAT_AUDIO" 2>/dev/null
    echo "  ✅ Áudio concatenado"
else
    echo "  ⚠️  Nenhum áudio encontrado, gerando silêncio"
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo \
        -t "$TOTAL_DURATION" -c:a libmp3lame \
        "$CONCAT_AUDIO" 2>/dev/null
fi

# ---------------------------------------------------------------------------
# 6. Combinar vídeo + voz + trilha de fundo + legendas
# ---------------------------------------------------------------------------
echo ""
echo "🎬 Renderização final..."

FINAL_OUTPUT="${OUTPUT_DIR}/final_9x16.mp4"

# Verificar se tem trilha de fundo
MUSIC_DIR="./config/music"
BACKGROUND_MUSIC=""
if [ -d "$MUSIC_DIR" ]; then
    BACKGROUND_MUSIC=$(find "$MUSIC_DIR" -name "*.mp3" -type f | head -1)
fi

# Construir comando final
FFMPEG_CMD=(ffmpeg -y -i "$CONCAT_VIDEO" -i "$CONCAT_AUDIO")

# Adicionar trilha de fundo se existir
if [ -n "$BACKGROUND_MUSIC" ] && [ -f "$BACKGROUND_MUSIC" ]; then
    FFMPEG_CMD+=(-i "$BACKGROUND_MUSIC")
    # Filtro: mixar voz (volume normal) + trilha (volume baixo)
    AUDIO_FILTER="[1:a]volume=1.0[voice];[2:a]volume=${BACKGROUND_MUSIC_VOLUME},aloop=loop=-1:size=2e+09[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    MAP_AUDIO="-map [aout]"
else
    AUDIO_FILTER="[1:a]volume=1.0[aout]"
    MAP_AUDIO="-map [aout]"
fi

# Adicionar legendas se existirem
if [ -f "$SUBTITLES" ]; then
    VIDEO_FILTER="ass=${SUBTITLES}"
else
    VIDEO_FILTER="null"
fi

# Renderizar
ffmpeg -y \
    -i "$CONCAT_VIDEO" \
    -i "$CONCAT_AUDIO" \
    ${BACKGROUND_MUSIC:+-i "$BACKGROUND_MUSIC"} \
    -filter_complex "${AUDIO_FILTER}" \
    -vf "$VIDEO_FILTER" \
    -map 0:v ${MAP_AUDIO} \
    -c:v libx264 -preset medium -crf 20 \
    -c:a aac -b:a 192k \
    -r $FPS \
    -movflags +faststart \
    -shortest \
    "$FINAL_OUTPUT" 2>/dev/null

echo ""
echo "============================================"
echo "✅ VÍDEO FINAL PRONTO!"
echo "   Arquivo: ${FINAL_OUTPUT}"
echo "   Duração: ~${TOTAL_DURATION}s"
echo "   Formato: ${WIDTH}x${HEIGHT} @ ${FPS}fps"
echo "============================================"

# ---------------------------------------------------------------------------
# 7. Limpeza de arquivos temporários
# ---------------------------------------------------------------------------
echo ""
echo "🧹 Limpando arquivos temporários..."
rm -f "${ASSETS_DIR}"/clip_scene_*.mp4
rm -f "$CONCAT_VIDEO"
rm -f "$CONCAT_AUDIO"
rm -f "$CONCAT_LIST"
rm -f "$AUDIO_CONCAT_LIST"
echo "  ✅ Limpo"
