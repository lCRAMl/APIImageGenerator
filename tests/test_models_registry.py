from core.generation import build_input_payload
from core.models_registry import MODELS, get_model_by_display_name


def default_values(spec):
    return {param.name: param.default for param in spec.params}


def test_display_names_are_unique():
    names = [spec.display_name for spec in MODELS]
    assert len(names) == len(set(names))


def test_gpt_image_2_6_sunburst_payload():
    spec = get_model_by_display_name("GPT Image-2.6 Sunburst - Image to Image")
    assert spec.api_model == "gpt-image-2-6/sunburst-image-to-image"
    payload = build_input_payload(spec, "restyle", ["https://example.com/a.png"], default_values(spec))
    assert payload == {
        "prompt": "restyle",
        "input_urls": ["https://example.com/a.png"],
        "aspect_ratio": "auto",
        "resolution": "2K",
        "quality": "high",
        "output_format": "png",
        "background": "auto",
        "complexity": "high",
        "moderation": "low",
    }


def test_seedream_5_5_payload():
    spec = get_model_by_display_name("Seedream 5.5 - Image to Image")
    assert spec.api_model == "seedream/5-5-image-to-image"
    assert spec.max_images == 10
    payload = build_input_payload(spec, "edit it", ["https://example.com/a.webp"], default_values(spec))
    assert payload == {
        "prompt": "edit it",
        "image_urls": ["https://example.com/a.webp"],
        "aspect_ratio": "auto",
        "size": "2K",
        "output_format": "png",
        "background": "auto",
        "nsfw_checker": False,
    }
