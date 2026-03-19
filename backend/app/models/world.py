import enum
from datetime import datetime

from sqlmodel import Field, SQLModel


class WorldStatus(str, enum.Enum):
    draft = "draft"
    public = "public"
    private = "private"
    archived = "archived"


class NPCLinkType(str, enum.Enum):
    present = "present"
    excluded = "excluded"


class StatScope(str, enum.Enum):
    character = "character"
    world = "world"


class StatType(str, enum.Enum):
    int_ = "int"
    enum_ = "enum"
    set_ = "set"


class World(SQLModel, table=True):
    __tablename__ = "worlds"

    id: int = Field(primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    lore: str = Field(default="")
    system_prompt: str = Field(default="")
    character_template: str = Field(default="")
    initial_message: str = Field(default="")
    pipeline: str = Field(default="{}")
    status: WorldStatus = Field(default=WorldStatus.draft)
    owner_id: int | None = Field(default=None, index=True)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)


class WorldLocation(SQLModel, table=True):
    __tablename__ = "world_locations"

    id: int = Field(primary_key=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    name: str = Field(default="")
    content: str = Field(default="")
    exits: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)


class WorldNPC(SQLModel, table=True):
    __tablename__ = "world_npcs"

    id: int = Field(primary_key=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    name: str = Field(default="")
    content: str = Field(default="")
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)


class WorldLoreFact(SQLModel, table=True):
    __tablename__ = "world_lore_facts"

    id: int = Field(primary_key=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    content: str = Field(default="")
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)


class NPCLocationLink(SQLModel, table=True):
    __tablename__ = "npc_location_links"

    id: int = Field(primary_key=True)
    npc_id: int = Field(foreign_key="world_npcs.id", index=True)
    location_id: int = Field(foreign_key="world_locations.id", index=True)
    link_type: NPCLinkType = Field(default=NPCLinkType.present)


class WorldStatDefinition(SQLModel, table=True):
    __tablename__ = "world_stat_definitions"

    id: int = Field(primary_key=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    name: str = Field(default="")
    description: str = Field(default="")
    scope: StatScope = Field(default=StatScope.character)
    stat_type: StatType = Field(default=StatType.int_)
    default_value: str = Field(default="0")
    min_value: int | None = Field(default=None)
    max_value: int | None = Field(default=None)
    enum_values: str | None = Field(default=None)


class WorldRule(SQLModel, table=True):
    __tablename__ = "world_rules"

    id: int = Field(primary_key=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    rule_text: str = Field(default="")
    order: int = Field(default=0)
