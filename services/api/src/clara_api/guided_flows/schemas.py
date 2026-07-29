"""Client-neutral schemas for server-backed guided-flow drafts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GuidedFlowType = Literal["lifemap_episode"]
LifeMapEpisodeStep = Literal["title", "goal", "priority", "review"]
LifeMapPriority = Literal["routine", "soon", "urgent"]


class LifeMapEpisodeDraftPayload(BaseModel):
    """The complete allowlist for the first guided-flow payload."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    goal: str | None = Field(default=None, max_length=4000)
    priority: LifeMapPriority | None = None


class GuidedFlowCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow_type: GuidedFlowType
    current_step: LifeMapEpisodeStep = "title"
    payload: LifeMapEpisodeDraftPayload = Field(
        default_factory=LifeMapEpisodeDraftPayload
    )


class GuidedFlowUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: LifeMapEpisodeStep
    payload: LifeMapEpisodeDraftPayload


class CommittedResourceLink(BaseModel):
    type: Literal["lifemap_episode"]
    id: str


class GuidedFlowDraftResponse(BaseModel):
    id: str
    flow_type: GuidedFlowType
    current_step: LifeMapEpisodeStep
    payload: LifeMapEpisodeDraftPayload
    status: Literal["active", "committed", "abandoned"]
    revision: int
    expires_at: datetime
    committed_resource: CommittedResourceLink | None = None


class GuidedFlowDraftListResponse(BaseModel):
    items: list[GuidedFlowDraftResponse]
