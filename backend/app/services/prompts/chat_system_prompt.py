"""Chat system prompt builder — placeholder until stage 2 step 2."""


def build_chat_system_prompt(
    world_name: str,
    world_description: str,
    world_lore: str,
    character_name: str,
    character_description: str,
    user_instructions: str,
) -> str:
    parts = [
        f"You are the narrator and game master for an RPG world called '{world_name}'.",
        f"World description: {world_description}" if world_description else "",
        f"Lore: {world_lore}" if world_lore else "",
        f"The player is playing as {character_name}: {character_description}",
        user_instructions if user_instructions else "",
    ]
    return "\n\n".join(p for p in parts if p)
