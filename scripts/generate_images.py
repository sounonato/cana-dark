"""
Canal Dark — Módulo 2: Geração de Imagens
Usa Gemini Flash Image (free tier) ou Imagen 4 Fast (pago).
Injeta DESCRIÇÃO-MÃE dos personagens em cada prompt de cena.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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
    Suporta Google (Imagen 3) e Pollinations.ai (Flux) com fallback automatico.

    Args:
        scene: Dict da cena (do roteiro JSON).
        scene_index: Numero da cena (1-based).
        video_id: ID do video.
        characters: Config de personagens. Se None, carrega do arquivo.

    Returns:
        Path da imagem salva.
    """
    if characters is None:
        characters = load_characters()

    # Determinar quais personagens estao na cena
    characters_in_scene = ["him", "her"]  # Padrao: ambos
    dialogo = scene.get("dialogo", {})
    if isinstance(dialogo, dict):
        personagem = dialogo.get("personagem", "").lower()
        if personagem == "ele":
            characters_in_scene = ["him"]
        elif personagem == "ela":
            characters_in_scene = ["her"]

    # Construir prompt
    prompt = build_image_prompt(scene, characters, characters_in_scene)
    image_bytes = None
    provider_used = "pollinations"
    ext = "png"

    image_provider = os.getenv("IMAGE_PROVIDER", "google").lower()
    
    # Tentativa 1: Google Imagen 3 (se configurado como google)
    if image_provider == "google":
        if not GEMINI_API_KEY:
            print("    ⚠️  GEMINI_API_KEY nao configurada no .env. Usando fallback Pollinations.ai...")
        else:
            try:
                print(f"    Tentando gerar imagem {scene_index} com Google Imagen 3...")
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=GEMINI_API_KEY)
                model_name = os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")
                
                result = client.models.generate_images(
                    model=model_name,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="9:16",
                    )
                )
                
                if result and result.generated_images:
                    image_bytes = result.generated_images[0].image.image_bytes
                    provider_used = "google"
                    ext = "jpg"
                    print(f"    ✅ Imagem gerada com sucesso via Google ({model_name})!")
                else:
                    raise ValueError("Nenhuma imagem retornada pelo Google Imagen 3")
            except Exception as e:
                print(f"    ⚠️ Falha no Google Imagen 3: {e}")
                print("    ⏳ Ativando fallback automatico para Pollinations.ai (Flux)...")

    # Tentativa 2: Pollinations.ai (se configurado como pollinations ou se Google falhou)
    if not image_bytes:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&private=true&model=flux"
        
        max_retries = 5
        base_delay = 2
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        for attempt in range(max_retries):
            try:
                print(f"    Tentativa {attempt + 1}/{max_retries} de gerar imagem com Pollinations (Flux)...")
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=45) as response:
                    if response.status == 200:
                        image_bytes = response.read()
                        provider_used = "pollinations"
                        ext = "png"
                        break
                    else:
                        raise Exception(f"HTTP Status {response.status}")
            except Exception as e:
                print(f"    ⚠️ Tentativa {attempt + 1} falhou: {e}")
                if attempt == max_retries - 1:
                    raise e
                delay = base_delay * (2 ** attempt)
                print(f"    ⏳ Aguardando {delay} segundos antes de tentar novamente...")
                time.sleep(delay)

    if not image_bytes:
        raise ValueError(f"Não foi possível obter imagem para a cena {scene_index}")

    # Salvar imagem
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    Path(assets_dir).mkdir(parents=True, exist_ok=True)
    image_path = os.path.join(assets_dir, f"scene_{scene_index:02d}.{ext}")

    with open(image_path, "wb") as f:
        f.write(image_bytes)

    print(f"  🖼️  Cena {scene_index} salva ({provider_used}): {image_path}")
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
