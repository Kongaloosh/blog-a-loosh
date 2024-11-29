from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Union
from datetime import datetime
import base64


class PlaceInfo(BaseModel):
    name: str
    geoname_id: int
    admin_name: Optional[str] = None
    country_name: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TwitterInfo(BaseModel):
    url: HttpUrl
    id: str


class Event(BaseModel):
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None
    event_name: Optional[str] = None


class Trip(BaseModel):
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None
    event_name: Optional[str] = None


class Travel(BaseModel):
    map_data: Optional[bytes] = None
    map_path: Optional[str] = None
    map_url: Optional[str] = None
    trips: List[Trip] = Field(default_factory=list)

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        if self.map_data:
            data["map_data"] = base64.b64encode(self.map_data).decode("utf-8")
        return data


class ReplyTo(BaseModel):
    url: HttpUrl


class DraftPost(BaseModel):
    """Model for posts being created/edited before storage"""

    # Content fields
    content: str  # Only required field for a draft
    title: Optional[str] = None
    summary: Optional[str] = None

    # Metadata
    updated: Optional[datetime] = None
    category: Optional[List[str]] = None

    # Media
    photo: Optional[List[str]] = None

    # Location
    location: Optional[str] = None
    location_name: Optional[str] = None
    location_id: Optional[int] = None

    # Social/Webmention
    in_reply_to: Optional[List[Union[str, ReplyTo]]] = None
    syndication: Optional[List[str]] = None
    bridgy_twitter: Optional[str] = None
    twitter: Optional[TwitterInfo] = None

    # Events
    event: Optional[Event] = None
    event_name: Optional[str] = None
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None

    # Travel
    travel: Travel = Field(default_factory=Travel)


class BlogPost(DraftPost):
    """Model for stored posts with all required fields"""

    # Required fields for stored posts
    slug: str
    u_uid: str
    url: str
    published: datetime  # Required when stored

    # Optional but specific to stored posts
    h: Optional[str] = None  # Microformat type
    repost_of: Optional[str] = None
    geo_check: Optional[str] = None

    class Config:
        extra = "ignore"
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            HttpUrl: str,
            bytes: lambda v: base64.b64encode(v).decode("utf-8") if v else None,
        }

    def model_dump(self, **kwargs):
        if kwargs.get("mode") == "json":
            # Ensure datetime objects are converted to ISO format strings
            data = super().model_dump(**kwargs)
            if self.travel and self.travel.map_data:
                data["travel"]["map_data"] = base64.b64encode(
                    self.travel.map_data
                ).decode("utf-8")
            return data
        return super().model_dump(**kwargs)
