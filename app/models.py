from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Project:
    id: int
    name: str
    status: str = "concept"
    bloom_level: str | None = None


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
