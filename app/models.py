from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Project:
    id: int
    name: str
    status: str = "concept"
    bloom_level: str | None = None
    reader_title: str | None = None
    module_code: str | None = None
    academic_year: str | None = None


@dataclass
class Source:
    id: int
    project_id: int
    kind: str  # "document" | "video"
    title: str
    position: int
    included: bool
    text: str
    filename: str | None = None
    page_count: int | None = None
    youtube_url: str | None = None
    video_id: str | None = None
    channel: str | None = None
    duration: str | None = None
    thumbnail_url: str | None = None
    synopsis: str | None = None
    quote: str | None = None
    processing: bool = False


@dataclass
class Question:
    id: int
    source_id: int
    position: int
    text: str


@dataclass
class LearningOutcome:
    id: int
    project_id: int
    code: str
    title: str
    weight: float  # relatieve weging binnen het project (bijv. 0.6)
    bloom_level: str | None = None  # stuurt de mc/open-mix per leeruitkomst
    position: int = 0


@dataclass
class ToetsVraag:
    id: int
    project_id: int
    type: str  # "mc" | "open"
    stem: str  # de stam van de vraag
    learning_outcome_id: int | None = None
    source_id: int | None = None  # herkomst (document of video)
    bloom_level: str | None = None
    options: list[str] = field(default_factory=list)  # afleiders + sleutel (mc)
    answer: str = ""  # sleutel (mc) of modelantwoord (open)
    # kwaliteitsborging (handboek toetssamenstelling), elk 1-5
    validity: int | None = None
    reliability: int | None = None
    technical: int | None = None
    notes: str | None = None  # toelichtingen bij de beoordeling
    position: int = 0
