from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_404(self, model_class: type[ModelT], id: Any) -> ModelT:
        instance = await self.db.get(model_class, id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model_class.__name__} not found",
            )
        return instance

    async def paginate(self, query: Select[Any], page: int, per_page: int) -> Select[Any]:
        offset = max(page - 1, 0) * per_page
        return query.offset(offset).limit(per_page)
