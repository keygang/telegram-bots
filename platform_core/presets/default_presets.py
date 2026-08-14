from typing import Dict, List, Optional
from platform_core.presets.base import PromptPreset

DEFAULT_IMAGE_PRESETS: List[PromptPreset] = [
    PromptPreset(
        id="odyssey",
        title="Homer's Odyssey Warrior",
        description="Transform into an epic ancient Greek hero from Homer's Odyssey",
        icon="🏛️",
        prompt_template="Heroic portrait of {user_prompt} as an ancient Greek epic warrior from Homer's Odyssey, cinematic lighting, gold-trimmed mythic armor, dramatic Mount Olympus background, 8k resolution",
        category="Popular Legends",
        media_type="image",
        default_model="google/gemini-2.5-flash-image",
        supports_reference_photo=True,
    ),
    PromptPreset(
        id="harry_potter",
        title="Hogwarts Wizard",
        description="Become a powerful wizard in Hogwarts robes with glowing magic wand",
        icon="🧙‍♂️",
        prompt_template="Epic portrait of {user_prompt} as a famous Hogwarts wizard student, wearing house robes, holding a glowing magical wand, floating magic spell particles, atmospheric Hogwarts castle library",
        category="Popular Legends",
        media_type="image",
        default_model="google/gemini-2.5-flash-image",
        supports_reference_photo=True,
    ),
    PromptPreset(
        id="cyberpunk",
        title="Cyberpunk 2077",
        description="Futuristic neon cyber portrait with high-tech implants",
        icon="🏙️",
        prompt_template="High-detail Cyberpunk 2077 aesthetic portrait of {user_prompt}, neon reflection, glowing eye cybernetics, rainy night in futuristic Neo-Tokyo street, octane render",
        category="Sci-Fi & Cyber",
        media_type="image",
        default_model="google/gemini-2.5-flash-image",
        supports_reference_photo=True,
    ),
    PromptPreset(
        id="renaissance",
        title="Renaissance Oil Painting",
        description="Classic master portrait in Da Vinci & Rembrandt oil style",
        icon="🖼️",
        prompt_template="Masterpiece Renaissance oil painting of {user_prompt}, chiaroscuro dramatic lighting, rich canvas texture, detailed clothing in style of Leonardo da Vinci",
        category="Fine Art",
        media_type="image",
        default_model="google/gemini-2.5-flash-image",
        supports_reference_photo=True,
    ),
    PromptPreset(
        id="anime_hero",
        title="Anime Key Visual",
        description="Dynamic anime hero artwork inspired by Studio Ghibli & Shonen",
        icon="⚔️",
        prompt_template="High octane anime key visual of {user_prompt}, vibrant colors, sharp cell shading, dramatic camera angle, epic fantasy background",
        category="Anime",
        media_type="image",
        default_model="google/gemini-2.5-flash-image",
        supports_reference_photo=True,
    ),
]

def get_preset_by_id(preset_id: str) -> Optional[PromptPreset]:
    """Retrieve a preset model by its unique ID across available presets."""
    for preset in DEFAULT_IMAGE_PRESETS:
        if preset.id == preset_id:
            return preset
    return None
