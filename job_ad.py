from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, UTC
from zoneinfo import ZoneInfo
from functools import total_ordering


@total_ordering
class JobAd(BaseModel):
    role: str
    company: str
    location: str
    min_experience: (
        str | None
    )  # No need for default as None will be passed
    employment_type: str
    category: str
    remote: str | None
    details: List[str]
    tags: List[str]
    ad_link: str
    date_posted: datetime
    date_updated: datetime | None = (
        None  # Default None is needed here because it is not passed
    )
    report: bool = False
    renewals: int = (
        0  # Default 0 is needed here because it is not passed
    )

    class Config:
        validate_assignment = True

    def __eq__(self, other: object) -> bool:
        """
        Metadata (created_at, updated_at) is ignored by design
        ad_link is the primary (unique) key.
        """
        if not isinstance(other, JobAd):
            return NotImplemented
        return self.ad_link == other.ad_link

    def __lt__(self, other: object):
        if not isinstance(other, JobAd):
            return NotImplemented
        return self.date_posted < other.date_posted

    def __hash__(self) -> int:
        """
        Metadata (created_at, updated_at) is ignored by design
        ad_link is the primary (unique) key.
        """
        return hash(self.ad_link)

    def __str__(self) -> str:
        """
        Returns Markdown style string
        """
        return f"{self.date_posted.astimezone(ZoneInfo('Europe/Athens')).strftime('%Y-%m-%d')} r{str(self.renewals).zfill(2)} [{self.role} - {self.company} - {self.category} - {self.location}]({self.ad_link})"
