from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    snippet: str
    url: str


class SearchOutput(BaseModel):
    summary: str
    results: list[SearchResult]
