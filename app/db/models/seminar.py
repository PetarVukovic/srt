from sqlmodel import SQLModel,Field,Relationship
from typing import Optional

class Seminar(SQLModel,table=True):
    __tablename__ = "seminar"
    id:Optional[int] = Field(default=None,primary_key=True)
    name: str = Field(max_length=100)
    description: Optional[str] = None
    batches: Optional[list["Batch"]] = Relationship(back_populates="seminar")

class Batch(SQLModel,table=True):
    __tablename__ = "batch"
    id:Optional[int] = Field(default=None,primary_key=True)
    seminar_id: int = Field(foreign_key="seminar.id")
    status: str = Field(max_length=10)
    seminar:"Seminar" = Relationship(back_populates="batches")
    seminars: Optional[list["PrijevodSeminara"]] = Relationship(back_populates="batch")

class PrijevodSeminara(SQLModel,table=True):
    __tablename__ = "prijevod_seminara"
    id:Optional[int] = Field(default=None,primary_key=True)
    batch_id: int = Field(foreign_key="batch.id")
    language: str = Field(max_length=10)
    content: str = Field(min_length=10)
    batch: Optional["Batch"] = Relationship(back_populates="seminars")
