"""
World Garden — Default Article Templates.

Seeds the database with pre-built templates for common article types:
Character, Item, Location, and Creature.
"""

from __future__ import annotations

from database.manager import DatabaseManager
from database.models import ArticleTemplate, FieldDefinition
from database import crud


def _seed_template(
    type_name: str,
    fields: list[FieldDefinition],
    overwrite: bool = False,
) -> ArticleTemplate | None:
    """Create a default template if one doesn't already exist."""
    existing = crud.get_template_by_type_name(type_name)
    if existing and not overwrite:
        return existing
    if existing and overwrite:
        existing.field_definitions = fields
        return crud.update_template(existing)

    template = ArticleTemplate(
        type_name=type_name,
        field_definitions=fields,
    )
    return crud.create_template(template)


def seed_default_templates(overwrite: bool = False) -> list[ArticleTemplate]:
    """Seed all default templates into the database.

    Safe to call multiple times — skips existing templates unless *overwrite*
    is True.
    """
    templates = []

    # .................. Character ..................
    templates.append(
        _seed_template(
            "Character",
            [
                FieldDefinition(
                    name="full_name", label="Full Name", field_type="text",
                    placeholder="e.g. King Aldric III",
                ),
                FieldDefinition(
                    name="aliases", label="Aliases / Titles", field_type="text",
                    placeholder="e.g. The Wise, Lord of Avalon",
                ),
                FieldDefinition(
                    name="age", label="Age", field_type="number",
                    placeholder="e.g. 45",
                ),
                FieldDefinition(
                    name="gender", label="Gender", field_type="text",
                    placeholder="e.g. Male",
                ),
                FieldDefinition(
                    name="race", label="Race / Species", field_type="select",
                    options=["Human", "Elf", "Dwarf", "Halfling", "Orc",
                             "Gnome", "Dragonborn", "Tiefling", "Half-Elf",
                             "Half-Orc", "Aasimar", "Other"],
                ),
                FieldDefinition(
                    name="profession", label="Profession / Class",
                    field_type="text", placeholder="e.g. Paladin",
                ),
                FieldDefinition(
                    name="affiliation", label="Affiliation / Faction",
                    field_type="text", placeholder="e.g. Order of the Dawn",
                ),
                FieldDefinition(
                    name="residence", label="Place of Residence",
                    field_type="text", placeholder="e.g. Castle Avalon",
                ),
                FieldDefinition(
                    name="status", label="Status", field_type="select",
                    options=["Alive", "Deceased", "Unknown", "Undead",
                             "Immortal", "Missing"],
                ),
                FieldDefinition(
                    name="appearance", label="Physical Description",
                    field_type="longtext",
                    placeholder="Describe height, build, hair, eyes, scars, attire...",
                ),
                FieldDefinition(
                    name="personality", label="Personality & Traits",
                    field_type="longtext",
                    placeholder="Describe mannerisms, motivations, flaws...",
                ),
                FieldDefinition(
                    name="biography", label="Biography / Background",
                    field_type="longtext",
                    placeholder="Backstory, history, key life events...",
                ),
                FieldDefinition(
                    name="portrait", label="Portrait Image",
                    field_type="image",
                    placeholder="Path to portrait image file",
                ),
                FieldDefinition(
                    name="is_npc", label="Is NPC?", field_type="boolean",
                ),
            ],
            overwrite=overwrite,
        )
    )

    # .................. Item ..................
    templates.append(
        _seed_template(
            "Item",
            [
                FieldDefinition(
                    name="item_type", label="Item Type", field_type="select",
                    options=["Weapon", "Armor", "Potion", "Scroll", "Ring",
                             "Amulet", "Tool", "Artifact", "Book", "Food",
                             "Clothing", "Key", "Treasure", "Other"],
                ),
                FieldDefinition(
                    name="rarity", label="Rarity", field_type="select",
                    options=["Common", "Uncommon", "Rare", "Very Rare",
                             "Legendary", "Artifact", "Unique"],
                ),
                FieldDefinition(
                    name="value", label="Value (gp)", field_type="number",
                    placeholder="e.g. 500",
                ),
                FieldDefinition(
                    name="weight", label="Weight (lb)", field_type="number",
                    placeholder="e.g. 3.5",
                ),
                FieldDefinition(
                    name="attunement", label="Requires Attunement",
                    field_type="boolean",
                ),
                FieldDefinition(
                    name="properties", label="Properties",
                    field_type="longtext",
                    placeholder="Describe what this item does, its abilities...",
                ),
                FieldDefinition(
                    name="location", label="Current Location / Owner",
                    field_type="text",
                    placeholder="e.g. In the royal vault of Avalon",
                ),
                FieldDefinition(
                    name="image", label="Item Image", field_type="image",
                ),
            ],
            overwrite=overwrite,
        )
    )

    # .................. Location ..................
    templates.append(
        _seed_template(
            "Location",
            [
                FieldDefinition(
                    name="location_type", label="Location Type",
                    field_type="select",
                    options=["City", "Town", "Village", "Dungeon", "Forest",
                             "Mountain", "Cave", "Temple", "Castle", "Tavern",
                             "Shop", "Harbor", "Bridge", "Ruins", "Plains",
                             "Swamp", "Desert", "Island", "Other"],
                ),
                FieldDefinition(
                    name="region", label="Region / Continent",
                    field_type="text",
                    placeholder="e.g. Kingdom of Avalon",
                ),
                FieldDefinition(
                    name="population", label="Population", field_type="number",
                    placeholder="e.g. 5000",
                ),
                FieldDefinition(
                    name="ruler", label="Ruler / Leader",
                    field_type="text",
                    placeholder="e.g. King Aldric",
                ),
                FieldDefinition(
                    name="government", label="Government Type",
                    field_type="select",
                    options=["Monarchy", "Democracy", "Oligarchy", "Theocracy",
                             "Tribal", "Autocracy", "Magocracy", "Anarchy",
                             "Meritocracy", "Other"],
                ),
                FieldDefinition(
                    name="economy", label="Economy / Trade",
                    field_type="longtext",
                    placeholder="Main industries, trade routes, currency...",
                ),
                FieldDefinition(
                    name="notable_features", label="Notable Features",
                    field_type="longtext",
                    placeholder="Landmarks, architecture, natural features...",
                ),
                FieldDefinition(
                    name="danger_level", label="Danger Level",
                    field_type="select",
                    options=["Safe", "Low", "Medium", "High", "Extreme", "Deadly"],
                ),
                FieldDefinition(
                    name="map_image", label="Map Image",
                    field_type="image",
                ),
            ],
            overwrite=overwrite,
        )
    )

    # .................. Creature ..................
    templates.append(
        _seed_template(
            "Creature",
            [
                FieldDefinition(
                    name="creature_type", label="Creature Type",
                    field_type="select",
                    options=["Beast", "Dragon", "Monstrosity", "Undead",
                             "Fiend", "Celestial", "Fey", "Elemental",
                             "Construct", "Plant", "Giant", "Ooze",
                             "Aberration", "Humanoid", "Other"],
                ),
                FieldDefinition(
                    name="size", label="Size", field_type="select",
                    options=["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"],
                ),
                FieldDefinition(
                    name="alignment", label="Alignment",
                    field_type="select",
                    options=["Lawful Good", "Neutral Good", "Chaotic Good",
                             "Lawful Neutral", "True Neutral", "Chaotic Neutral",
                             "Lawful Evil", "Neutral Evil", "Chaotic Evil",
                             "Unaligned"],
                ),
                FieldDefinition(
                    name="habitat", label="Habitat",
                    field_type="text",
                    placeholder="e.g. Deep forests, caves",
                ),
                FieldDefinition(
                    name="diet", label="Diet", field_type="select",
                    options=["Herbivore", "Carnivore", "Omnivore",
                             "Scavenger", "Magical", "Unknown"],
                ),
                FieldDefinition(
                    name="behavior", label="Behavior & Temperament",
                    field_type="longtext",
                    placeholder="Typical behaviour, aggression level, social structure...",
                ),
                FieldDefinition(
                    name="abilities", label="Special Abilities",
                    field_type="longtext",
                    placeholder="Unique attacks, magical abilities, resistances...",
                ),
                FieldDefinition(
                    name="loot", label="Loot / Drops",
                    field_type="longtext",
                    placeholder="What can be harvested or looted from this creature...",
                ),
                FieldDefinition(
                    name="image", label="Creature Image",
                    field_type="image",
                ),
            ],
            overwrite=overwrite,
        )
    )

    return templates


def ensure_default_templates() -> int:
    """Ensure all default templates exist in the database.

    Uses the existing DatabaseManager singleton — does NOT open a new connection.
    Returns the number of templates created or already present.
    """
    templates = seed_default_templates()
    return len(templates)