"""
Canal Dark — Módulo 2: Geração de Imagens
Usa Gemini Flash Image (free tier) ou Imagen 4 Fast (pago).
Injeta DESCRIÇÃO-MÃE dos personagens em cada prompt de cena.
"""

import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp")
DATA_DIR = os.getenv("DATA_DIR", "./data")


def load_characters() -> dict:
    """Carrega a configuração dos personagens."""
    config_path = os.path.join(
        os.getenv("CONFIG_DIR", "./config"), "characters.json"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_image_prompt(
    scene: dict,
    characters: dict,
    characters_in_scene: list[str] = None,
) -> str:
    """
    Constrói o prompt de imagem injetando a DESCRIÇÃO-MÃE dos personagens.

    Args:
        scene: Dict da cena (do roteiro JSON).
        characters: Config completa de characters.json.
        characters_in_scene: Lista de quais personagens estão na cena ["him", "her"].
    """
    if characters_in_scene is None:
        characters_in_scene = ["him", "her"]

    style = characters["style_global"]
    scene_desc = scene.get("descricao_visual", "")
    mood = scene.get("humor", "neutro")
    camera = scene.get("angulo_camera", "medium shot, eye level")

    # Construir descrições dos personagens presentes
    char_descs = []
    for char_key in characters_in_scene:
        char = characters["characters"].get(char_key)
        if char:
            char_descs.append(char["description_mother"])

    char_descriptions_text = " AND ".join(char_descs)

    # Montar prompt completo usando o template
    prompt = characters["scene_prompt_template"].format(
        style_global=style,
        scene_description=scene_desc,
        characters_in_scene=", ".join(characters_in_scene),
        camera_angle=camera,
        mood=mood,
        character_descriptions=char_descriptions_text,
    )

    # Adicionar orientação extra para consistência
    prompt += (
        " IMPORTANT: The characters must have fruit/vegetable heads as described. "
        "Their facial expressions should convey the mood of the scene. "
        "Vertical composition optimized for 9:16 aspect ratio (phone screen). "
        "No text or letters in the image."
    )

    return prompt


def generate_scene_image(
    scene: dict,
    scene_index: int,
    video_id: str,
    characters: dict = None,
) -> str:
    """
    Gera uma imagem para uma cena do roteiro.

    Args:
        scene: Dict da cena (do roteiro JSON).
        scene_index: Número da cena (1-based).
        video_id: ID do vídeo.
        characters: Config de personagens. Se None, carrega do arquivo.

    Returns:
        Path da imagem salva.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não configurada no .env")

    if characters is None:
        characters = load_characters()

    # Determinar quais personagens estão na cena
    characters_in_scene = ["him", "her"]  # Padrão: ambos
    dialogo = scene.get("dialogo", {})
    if isinstance(dialogo, dict):
        personagem = dialogo.get("personagem", "").lower()
        if personagem == "ele":
            characters_in_scene = ["him"]
        elif personagem == "ela":
            characters_in_scene = ["her"]

    # Construir prompt
    prompt = build_image_prompt(scene, characters, characters_in_scene)

    # Chamar Gemini Image
    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_modalities=["image", "text"],
        ),
    )

    # Extrair imagem da resposta
    image_data = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data
            mime_type = part.inline_data.mime_type
            break

    if image_data is None:
        raise ValueError(f"Gemini não retornou imagem para a cena {scene_index}")

    # Determinar extensão
    ext = "png"
    if mime_type and "jpeg" in mime_type:
        ext = "jpg"
    elif mime_type and "webp" in mime_type:
        ext = "webp"

    # Salvar imagem
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    Path(assets_dir).mkdir(parents=True, exist_ok=True)
    image_path = os.path.join(assets_dir, f"scene_{scene_index:02d}.{ext}")

    # image_data pode ser bytes ou base64 string
    if isinstance(image_data, str):
        image_bytes = base64.b64decode(image_data)
    else:
        image_bytes = image_data

    with open(image_path, "wb") as f:
        f.write(image_bytes)

    print(f"  🖼️  Cena {scene_index} salva: {image_path}")
    return image_path


def generate_all_images(video_id: str) -> list[str]:
    """
    Gera imagens para todas as cenas de um roteiro.

    Args:
        video_id: ID do vídeo (roteiro deve existir em data/assets/{video_id}/roteiro.json).

    Returns:
        Lista de paths das imagens geradas.
    """
    # Carregar roteiro
    script_path = os.path.join(DATA_DIR, "assets", video_id, "roteiro.json")
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Roteiro não encontrado: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    scenes = script_data["script"]["cenas"]
    characters = load_characters()

    print(f"🎨 Gerando {len(scenes)} imagens para vídeo {video_id}...")

    image_paths = []
    for i, scene in enumerate(scenes, 1):
        try:
            path = generate_scene_image(scene, i, video_id, characters)
            image_paths.append(path)
        except Exception as e:
            print(f"  ❌ Erro na cena {i}: {e}")
            image_paths.append(None)

    success_count = len([p for p in image_paths if p is not None])
    print(f"\n✅ {success_count}/{len(scenes)} imagens geradas com sucesso")

    return image_paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerar imagens das cenas")
    parser.add_argument("video_id", type=str, help="ID do vídeo")
    args = parser.parse_args()

    generate_all_images(args.video_id)
