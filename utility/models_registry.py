# models_registry.py
"""
Registry aller unterstützten Bild-Generierungsmodelle.

Jeder Eintrag beschreibt das Modell so, dass die GUI dynamisch Eingabe-Widgets
(Dropdown / Checkbox / Spinbox) aufbauen kann und der Worker einen passenden
kie.ai-kompatiblen Payload erzeugen kann:

    {
      "model":       "<api_model>",
      "callBackUrl": "<callback>",
      "input": {
        "<prompt_field>": "...",
        "<images_field>": [...]  oder  "https://...",
        "<param1>": ...,
        "<param2>": ...,
      }
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# =====================================================================
# Parameter-Spezifikation
# =====================================================================

@dataclass
class ParamSpec:
    name: str                                   # API-Feldname
    label: str                                  # UI-Label
    kind: str                                   # 'enum' | 'bool' | 'int' | 'float' | 'string'
    options: list = field(default_factory=list) # Nur für 'enum'
    default: Any = None
    min_value: float = 0
    max_value: float = 100
    step: float = 1


@dataclass
class ModelSpec:
    display_name: str                           # Anzeige-Name im Dropdown
    api_model: str                              # Wert für das "model"-Feld im Payload
    prompt_field: str = "prompt"                # Feldname für den Prompt
    images_field: str = "image_urls"            # Feldname für Referenzbilder
    images_is_list: bool = True                 # False => ein einzelner String statt Liste
    max_images: int = 10                        # maximale Anzahl Referenzbilder
    params: list[ParamSpec] = field(default_factory=list)


# =====================================================================
# Gemeinsame Konstanten
# =====================================================================

SEED_MAX = 2_147_483_647


# =====================================================================
# Modell-Registry
# =====================================================================

MODELS: list[ModelSpec] = [

    # ----- Google - Nano Banana 2 -----
    ModelSpec(
        display_name="Google - Nano Banana 2",
        api_model="nano-banana-2",
        images_field="image_input",
        images_is_list=True,
        max_images=14,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "1:4", "1:8", "2:3", "3:2",
                               "3:4", "4:1", "4:3", "4:5", "5:4",
                               "8:1", "9:16", "16:9", "21:9", "auto"],
                      default="auto"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K", "4K"], default="4K"),
            ParamSpec("output_format", "Output Format", "enum",
                      options=["png", "jpg"], default="png"),
        ],
    ),
    
    # ----- Google - Nano Banana Pro -----
    ModelSpec(
        display_name="Google - Nano Banana Pro",
        api_model="nano-banana-pro",
        images_field="image_input",
        images_is_list=True,
        max_images=8,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "2:3", "3:2", "3:4", "4:3",
                               "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                      default="1:1"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K", "4K"], default="1K"),
            ParamSpec("output_format", "Output Format", "enum",
                      options=["png", "jpg"], default="png"),
        ],
    ),
    
    # ----- Google - Nano Banana Edit -----
    ModelSpec(
        display_name="Google - Nano Banana Edit",
        api_model="google/nano-banana-edit",
        images_field="image_urls",
        images_is_list=True,
        max_images=10,
        params=[
            ParamSpec("output_format", "Output Format", "enum",
                      options=["png", "jpeg"], default="png"),
            ParamSpec("image_size", "Image Size", "enum",
                      options=["1:1", "9:16", "16:9", "3:4", "4:3",
                               "3:2", "2:3", "5:4", "4:5", "21:9", "auto"],
                      default="1:1"),
        ],
    ),

    # ----- GPT Image 2 - Image to Image -----
    ModelSpec(
        display_name="GPT Image-2 - Image to Image",
        api_model="gpt-image-2-image-to-image",
        images_field="input_urls",
        images_is_list=True,
        max_images=16,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["auto", "1:1", "3:2", "2:3", "4:3", "3:4", "5:4", "4:5", "16:9", "9:16", "2:1", "1:2", "3:1", "1:3", "21:9", "9:21"], default="auto"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K", "4K"], default="4K"),
        ],
    ),

    # ----- Seedream 4.0 - Edit -----
    ModelSpec(
        display_name="Seedream 4.0 - Edit",
        api_model="bytedance/seedream-v4-edit",
        images_field="image_urls",
        images_is_list=True,
        max_images=10,
        params=[
            ParamSpec("image_size", "Image Size", "enum",
                      options=["square", "square_hd",
                               "portrait_4_3", "portrait_3_2", "portrait_16_9",
                               "landscape_4_3", "landscape_3_2",
                               "landscape_16_9", "landscape_21_9"],
                      default="square_hd"),
            ParamSpec("image_resolution", "Resolution", "enum",
                      options=["1K", "2K", "4K"], default="1K"),
            ParamSpec("max_images", "Max Images", "int",
                      default=1, min_value=1, max_value=6, step=1),
            ParamSpec("seed", "Seed", "int",
                      default=0, min_value=0, max_value=SEED_MAX, step=1),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Seedream 4.5 - Edit -----
    ModelSpec(
        display_name="Seedream 4.5 - Edit",
        api_model="seedream/4.5-edit",
        images_field="image_urls",
        images_is_list=True,
        max_images=14,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "4:3", "3:4", "16:9", "9:16",
                               "2:3", "3:2", "21:9"],
                      default="1:1"),
            ParamSpec("quality", "Quality", "enum",
                      options=["basic", "high"], default="basic"),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Seedream 5.0 Lite - Image to Image -----
    ModelSpec(
        display_name="Seedream 5.0 Lite - Image to Image",
        api_model="seedream/5-lite-image-to-image",
        images_field="image_urls",
        images_is_list=True,
        max_images=14,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "4:3", "3:4", "16:9", "9:16",
                               "2:3", "3:2", "21:9"],
                      default="1:1"),
            ParamSpec("quality", "Quality", "enum",
                      options=["basic", "high"], default="basic"),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Flux-2 - Pro Image to Image -----
    ModelSpec(
        display_name="Flux-2 - Pro Image to Image",
        api_model="flux-2/pro-image-to-image",
        images_field="input_urls",
        images_is_list=True,
        max_images=8,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "4:3", "3:4", "16:9", "9:16",
                               "3:2", "2:3", "auto"],
                      default="1:1"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K"], default="1K"),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Flux-2 - Image to Image (flex) -----
    ModelSpec(
        display_name="Flux-2 - Image to Image",
        api_model="flux-2/flex-image-to-image",
        images_field="input_urls",
        images_is_list=True,
        max_images=8,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "4:3", "3:4", "16:9", "9:16",
                               "3:2", "2:3", "auto"],
                      default="1:1"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K"], default="1K"),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Grok Imagine - Image to Image -----
    ModelSpec(
        display_name="Grok Imagine - Image to Image",
        api_model="grok-imagine/image-to-image",
        images_field="image_urls",
        images_is_list=True,
        max_images=5,
        params=[
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- GPT Image 1.5 - Image to Image -----
    ModelSpec(
        display_name="GPT Image-1.5 - Image to Image",
        api_model="gpt-image/1.5-image-to-image",
        images_field="input_urls",
        images_is_list=True,
        max_images=16,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "2:3", "3:2"], default="3:2"),
            ParamSpec("quality", "Quality", "enum",
                      options=["medium", "high"], default="medium"),
        ],
    ),

    # ----- Qwen - Image to Image -----
    ModelSpec(
        display_name="Qwen - Image to Image",
        api_model="qwen/image-to-image",
        images_field="image_url",
        images_is_list=False,
        max_images=1,
        params=[
            ParamSpec("strength", "Strength", "float",
                      default=0.8, min_value=0.0, max_value=1.0, step=0.01),
            ParamSpec("output_format", "Output Format", "enum",
                      options=["png", "jpeg"], default="png"),
            ParamSpec("acceleration", "Acceleration", "enum",
                      options=["none", "regular", "high"], default="none"),
            ParamSpec("negative_prompt", "Negative Prompt", "string",
                      default="blurry, ugly"),
            ParamSpec("num_inference_steps", "Inference Steps", "int",
                      default=30, min_value=2, max_value=250, step=1),
            ParamSpec("guidance_scale", "Guidance Scale", "float",
                      default=2.5, min_value=0.0, max_value=20.0, step=0.1),
            ParamSpec("enable_safety_checker", "Safety Checker", "bool", default=True),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
            ParamSpec("seed", "Seed", "int",
                      default=0, min_value=0, max_value=SEED_MAX, step=1),
        ],
    ),

    # ----- Qwen2 - Image Edit -----
    ModelSpec(
        display_name="Qwen2 - Image Edit",
        api_model="qwen2/image-edit",
        images_field="image_url",
        images_is_list=False,
        max_images=1,
        params=[
            ParamSpec("image_size", "Image Size", "enum",
                      options=["1:1", "2:3", "3:2", "3:4", "4:3",
                               "9:16", "16:9", "21:9"],
                      default="16:9"),
            ParamSpec("output_format", "Output Format", "enum",
                      options=["jpeg", "png"], default="png"),
            ParamSpec("seed", "Seed", "int",
                      default=0, min_value=0, max_value=SEED_MAX, step=1),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Wan 2.7 Image -----
    ModelSpec(
        display_name="Wan 2.7 - Image",
        api_model="wan/2-7-image",
        images_field="input_urls",
        images_is_list=True,
        max_images=9,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "16:9", "4:3", "21:9", "3:4",
                               "9:16", "8:1", "1:8"],
                      default="1:1"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K", "4K"], default="2K"),
            ParamSpec("n", "Number of Images", "int",
                      default=4, min_value=1, max_value=12, step=1),
            ParamSpec("enable_sequential", "Sequential Mode", "bool", default=False),
            ParamSpec("thinking_mode", "Thinking Mode", "bool", default=False),
            ParamSpec("watermark", "Watermark", "bool", default=False),
            ParamSpec("seed", "Seed", "int",
                      default=0, min_value=0, max_value=SEED_MAX, step=1),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),

    # ----- Wan 2.7 Image Pro -----
    ModelSpec(
        display_name="Wan 2.7 - Image Pro",
        api_model="wan/2-7-image-pro",
        images_field="input_urls",
        images_is_list=True,
        max_images=9,
        params=[
            ParamSpec("aspect_ratio", "Aspect Ratio", "enum",
                      options=["1:1", "16:9", "4:3", "21:9", "3:4",
                               "9:16", "8:1", "1:8"],
                      default="1:1"),
            ParamSpec("resolution", "Resolution", "enum",
                      options=["1K", "2K", "4K"], default="2K"),
            ParamSpec("n", "Number of Images", "int",
                      default=4, min_value=1, max_value=12, step=1),
            ParamSpec("enable_sequential", "Sequential Mode", "bool", default=False),
            ParamSpec("thinking_mode", "Thinking Mode", "bool", default=False),
            ParamSpec("watermark", "Watermark", "bool", default=False),
            ParamSpec("seed", "Seed", "int",
                      default=0, min_value=0, max_value=SEED_MAX, step=1),
            ParamSpec("nsfw_checker", "NSFW Checker", "bool", default=False),
        ],
    ),
]


def get_model_by_display_name(name: str) -> ModelSpec | None:
    """Hilfsfunktion zum Auflösen der Dropdown-Auswahl."""
    for m in MODELS:
        if m.display_name == name:
            return m
    return None
