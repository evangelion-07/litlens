from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Conversation turns cannot be blank.")
        return cleaned


class QuestionRequest(BaseModel):
    use_llm: bool = False
    question: str = Field(min_length=3, max_length=1000)
    paper_ids: list[str] = Field(default_factory=list, max_length=25)
    top_k: int = Field(default=5, ge=1, le=10)
    conversation: list[ConversationTurn] = Field(default_factory=list, max_length=12)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Question must contain at least three non-space characters.")
        return cleaned
