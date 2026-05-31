"""
Canal Dark — Módulo 1: Geração de Roteiro
Usa Gemini Flash (free tier) para gerar histórias de drama/fofoca viral.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
DATA_DIR = os.getenv("DATA_DIR", "./data")

# ---------------------------------------------------------------------------
# Pydantic Schemas para Structured Output
# ---------------------------------------------------------------------------
class Dialogo(BaseModel):
    personagem: str = Field(description="O personagem que está falando: 'Léo' ou 'Pati'")
    fala: str = Field(description="A fala dramática do personagem")

class Cena(BaseModel):
    numero: int = Field(description="O número da cena (1, 2, 3...)")
    narracao: str = Field(description="Texto da narração desta cena")
    dialogo: Optional[Dialogo] = Field(default=None, description="Diálogo opcional do personagem na cena")
    descricao_visual: str = Field(description="Descrição detalhada em português do cenário e ação dos personagens para gerar imagem por IA")
    angulo_camera: str = Field(description="Ângulo da câmera: medium shot / close-up / wide shot")
    humor: str = Field(description="Humor predominante: surpresa / raiva / tristeza / felicidade / choque")
    key_scene: bool = Field(description="Se esta é uma cena de destaque visual/dramático")

class Roteiro(BaseModel):
    titulo: str = Field(description="Título chamativo para o vídeo")
    gancho: str = Field(description="Frase de gancho para os 2 primeiros segundos do vídeo")
    cenas: List[Cena] = Field(description="Cenas sequenciais do vídeo")
    plot_twist: str = Field(description="Explicação do plot twist no final da história")
    hashtags: List[str] = Field(description="Lista com 3 a 5 hashtags relevantes")
    caption: str = Field(description="Legenda engajadora para postar nas redes sociais")

# ---------------------------------------------------------------------------
# Prompt Template para Drama/Fofoca Viral
# ---------------------------------------------------------------------------
SCRIPT_SYSTEM_PROMPT = """Você é um roteirista especializado em vídeos curtos virais para Instagram Reels e TikTok.

Seu trabalho é criar histórias CURTAS de DRAMA e FOFOCA envolvendo um casal cartoon.
O formato é narração + diálogos curtos, com PLOT TWIST no final.

REGRAS:
1. Duração total: 30-60 segundos quando narrado (máximo ~150 palavras)
2. Formato: 4 a 6 cenas curtas
3. Estrutura: GANCHO forte (2 primeiras segundos) → DESENVOLVIMENTO → PLOT TWIST
4. Linguagem: português brasileiro informal, como se estivesse contando uma fofoca
5. Diálogos curtos e dramáticos (1-2 frases por personagem por cena)
6. Marcar 1-2 cenas como "key_scene" (as mais dramáticas/visuais)
7. Cada cena deve ter descrição visual clara para geração de imagem

PERSONAGENS:
- ELE: {nome_ele} — {personalidade_ele}
- ELA: {nome_ela} — {personalidade_ela}

Responda APENAS com o JSON, sem markdown, sem explicações."""

SCRIPT_USER_PROMPT = """Gere uma história de drama viral sobre o seguinte tema:
"{tema}"

Descreva um roteiro completo de 4 a 6 cenas. Para cada cena, escreva o texto narrado da fofoca, a descrição visual detalhada do cenário e ação dos personagens para geração de imagem por IA, o ângulo da câmera, o humor predominante, e opcionalmente um diálogo dinâmico e curto entre os personagens (Léo e Pati). No final, explique o plot twist surpreendente. Adicione também um título viral chamativo, um gancho inicial forte de 2 segundos, hashtags relevantes e a legenda completa para postagem."""

# ---------------------------------------------------------------------------
# Temas de Drama (pool para rotação automática)
# ---------------------------------------------------------------------------
DRAMA_THEMES = [
    "Ela descobriu uma mensagem estranha no celular dele",
    "Ele preparou uma surpresa mas ela entendeu tudo errado",
    "A melhor amiga dela contou um segredo sobre ele",
    "Ele encontrou o ex dela no shopping e fingiu que não viu",
    "Ela mentiu sobre onde estava e ele descobriu pela foto do Instagram",
    "Ele pediu ela em namoro mas ela ouviu ele falando de outra",
    "O vizinho novo começou a dar em cima dela e ele percebeu",
    "Ela achou uma caixa escondida no armário dele",
    "Ele esqueceu o aniversário dela e tentou disfarçar",
    "Ela viu ele curtindo foto de outra e fez uma cena",
    "A mãe dele não gosta dela e armou uma situação",
    "Ele recebeu uma ligação misteriosa e ficou nervoso",
    "Ela mudou a senha do WiFi e ele não sabe por quê",
    "Ele disse que ia dormir cedo mas ela viu ele online",
    "A prima dela deu em cima dele no churrasco da família",
]


def load_characters() -> dict:
    """Carrega a configuração dos personagens."""
    config_path = os.path.join(
        os.getenv("CONFIG_DIR", "./config"), "characters.json"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_script(
    theme: str = None,
    video_id: str = None,
) -> dict:
    """
    Gera um roteiro de drama viral usando Gemini Flash.

    Args:
        theme: Tema da história. Se None, escolhe aleatório do pool.
        video_id: ID do vídeo. Se None, gera UUID.

    Returns:
        Dict com roteiro completo + metadados.
    """
    import random

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não configurada no .env")

    if theme is None:
        theme = random.choice(DRAMA_THEMES)

    if video_id is None:
        video_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    # Carregar personagens
    characters = load_characters()
    him = characters["characters"]["him"]
    her = characters["characters"]["her"]

    # Montar prompts
    system_prompt = SCRIPT_SYSTEM_PROMPT.format(
        nome_ele=f"{him['name']} (apelido: {him.get('nickname', him['name'])})",
        personalidade_ele="sarcástico, irônico, sempre com aquela sobrancelha levantada de 'eu já sabia disso'",
        nome_ela=f"{her['name']} (apelido: {her.get('nickname', her['name'])})",
        personalidade_ela="super dramática e expressiva, reage tudo com intensidade máxima, sempre com o bocão aberto de choque",
    )

    user_prompt = SCRIPT_USER_PROMPT.format(tema=theme)

    # Chamar Gemini com mecanismo de retry e exponential backoff
    client = genai.Client(api_key=GEMINI_API_KEY)

    import time
    max_retries = 5
    base_delay = 2  # 2s, 4s, 8s, 16s, 32s
    response = None

    for attempt in range(max_retries):
        try:
            print(f"Tentativa {attempt + 1}/{max_retries} de gerar roteiro com Gemini...")
            response = client.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                    response_schema=Roteiro,
                ),
            )
            
            # Parsear e validar imediatamente dentro do try para forçar retry se falhar
            response_text = response.text.strip()
            validated_roteiro = Roteiro.model_validate(json.loads(response_text))
            script_data = validated_roteiro.model_dump(by_alias=True)
            break  # Sucesso total!
        except Exception as e:
            error_msg = str(e)
            print(f"  ⚠️ Tentativa {attempt + 1} falhou: {error_msg}")
            if attempt == max_retries - 1:
                raise e
            delay = base_delay * (2 ** attempt)
            print(f"  ⏳ Aguardando {delay} segundos antes de tentar novamente...")
            time.sleep(delay)

    # Adicionar metadados
    result = {
        "video_id": video_id,
        "theme": theme,
        "generated_at": datetime.now().isoformat(),
        "model": GEMINI_TEXT_MODEL,
        "script": script_data,
    }

    # Salvar em disco
    assets_dir = os.path.join(DATA_DIR, "assets", video_id)
    Path(assets_dir).mkdir(parents=True, exist_ok=True)
    script_path = os.path.join(assets_dir, "roteiro.json")

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ Roteiro gerado: {script_data.get('titulo', 'sem título')}")
    print(f"   Tema: {theme}")
    print(f"   Cenas: {len(script_data.get('cenas', []))}")
    print(f"   Salvo em: {script_path}")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerar roteiro de drama viral")
    parser.add_argument("--theme", "-t", type=str, help="Tema da história (opcional)")
    parser.add_argument("--id", type=str, help="ID do vídeo (opcional)")
    args = parser.parse_args()

    result = generate_script(theme=args.theme, video_id=args.id)
    print("\n📜 Roteiro completo:")
    print(json.dumps(result["script"], ensure_ascii=False, indent=2))
