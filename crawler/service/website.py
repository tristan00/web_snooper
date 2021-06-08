from pydantic import BaseModel, Field
from typing import Optional

class Website(BaseModel):
    timestamp: Optional[str] = Field()

    #url
    scheme: Optional[str] = Field()
    netloc: Optional[str] = Field()
    url: str = Field()
    query: Optional[str] = Field()
    fragment: Optional[str] = Field()

    #meta
    meta_kw: Optional[str] = Field()
    meta_title: Optional[str] = Field()
    meta_description: Optional[str] = Field()
    augmented_meta_kw: Optional[str] = Field()

    # stats
    scrape_time: Optional[float] = Field()
    data_size: Optional[float] = Field()

    # content
    content_title: Optional[str] = Field()
    content_headers: Optional[str] = Field()
    content_paragraphs: Optional[str] = Field()


class Link(BaseModel):
    source_url: Optional[str] = Field()
    timestamp: Optional[str] = Field()
    source_url_text_split: Optional[str] = Field()
    link_text: Optional[str] = Field()
    destination_url: Optional[str] = Field()
    destination_url_text: Optional[str] = Field()

