from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Union
from datetime import datetime


class PlaceInfo(BaseModel):
    name: str
    geoname_id: int
    admin_name: Optional[str] = None
    country_name: Optional[str] = None


class TwitterInfo(BaseModel):
    url: HttpUrl
    id: str


class Event(BaseModel):
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None
    event_name: Optional[str] = None


class Trip(BaseModel):
    date: Optional[datetime] = None
    location_name: Optional[str] = None
    location: str


class Travel(BaseModel):
    map: Optional[bytes] = None
    map_location: Optional[str] = None
    trips: List[Trip] = Field(default_factory=list)


class ReplyTo(BaseModel):
    url: HttpUrl


class BlogPost(BaseModel):
    photo: Optional[List[str]] = None
    twitter: Optional[TwitterInfo] = None
    location_id: Optional[int] = None
    event: Optional[Event] = None
    category: Optional[List[str]] = None
    location_name: Optional[str] = None
    title: Optional[str] = None
    travel: Travel = Field(default_factory=Travel)
    content: str
    location: Optional[str] = None
    updated: Optional[datetime] = None
    in_reply_to: Optional[List[Union[str, ReplyTo]]] = None
    slug: str
    u_uid: str
    url: str
    h: Optional[str] = None
    syndication: Optional[List[str]] = None
    summary: Optional[str] = None
    published: datetime
    repost_of: Optional[str] = None
    geo_check: Optional[str] = None
    bridgy_twitter: Optional[str] = None
    event_name: Optional[str] = None
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None

    class Config:
        extra = "ignore"  # This will ignore any extra fields not defined in the model
