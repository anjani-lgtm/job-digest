"""Pydantic models for jobs, profiles, and preferences."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, computed_field


class Education(BaseModel):
    degree: str
    school: str


class Experience(BaseModel):
    title: str
    company: str
    product: Optional[str] = None
    type: Optional[str] = None
    dates: str
    overview: str = ""
    accomplishments: List[str] = []


class Profile(BaseModel):
    name: str
    location: Optional[str] = None
    current_title: str
    years_experience: int
    skills: Union[List[str], Dict[str, List[str]]]
    domains: List[str]
    education: List[Education]
    experience: List[Experience] = []
    hands_on_designer: bool = False
    design_note: Optional[str] = None
    summary: str


class Preferences(BaseModel, extra="allow"):
    """Job preferences. Uses extra='allow' to accept rich nested config
    (functions, company traits, keywords, fit_weights, etc.) that the
    scorer prompt consumes directly."""

    target_titles: List[str]
    adjacent_titles: List[str] = []
    titles_to_deprioritize: List[str] = []
    title_exclusions: List[str]
    seniority: Optional[Dict[str, Any]] = None
    functions: Optional[Dict[str, List[str]]] = None
    locations: List[str]
    remote_ok: bool
    onsite_tolerance: Optional[str] = None
    locations_to_deprioritize: List[str] = []
    industries: List[str]
    industries_to_deprioritize: List[str] = []
    industries_to_exclude: List[str] = []
    company: Optional[Dict[str, Any]] = None
    compensation: Optional[Dict[str, Any]] = None
    employment_types: List[str] = ["Full-time"]
    open_to_fractional_or_consulting: bool = False
    open_to_contract: bool = False
    work_style: Optional[Dict[str, Any]] = None
    keywords: Optional[Dict[str, List[str]]] = None
    fit_weights: Optional[Dict[str, float]] = None
    hard_filters: Optional[Dict[str, List[str]]] = None
    digest: Optional[Dict[str, Any]] = None


class Job(BaseModel):
    source: str  # greenhouse, lever, ashby, apify
    source_id: str
    company: str
    title: str
    location: str
    workplace_type: Optional[str] = None
    department: Optional[str] = None
    description_plain: str = ""
    url: str
    posted_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None

    @computed_field
    @property
    def dedup_key(self) -> str:
        raw = f"{self.company}|{self.title}|{self.location}".lower()
        return hashlib.sha256(raw.encode()).hexdigest()


class ScoredJob(BaseModel):
    job_id: int
    fit_score: int  # 0-100
    match_reasons: List[str]
    scored_at: Optional[datetime] = None
