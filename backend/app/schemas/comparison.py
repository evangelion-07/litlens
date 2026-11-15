from pydantic import BaseModel, Field, field_validator


class CompareRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=2, max_length=5)

    @field_validator("paper_ids")
    @classmethod
    def require_distinct_papers(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Select each paper only once.")
        return value
