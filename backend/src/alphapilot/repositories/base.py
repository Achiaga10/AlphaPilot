from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(
        self,
        session: AsyncSession,
        model: type[ModelType],
    ) -> None:
        self.session = session
        self.model = model

    async def get(
        self,
        object_id: Any,
    ) -> ModelType | None:
        return await self.session.get(
            self.model,
            object_id,
        )

    async def list(
        self,
    ) -> list[ModelType]:
        result = await self.session.execute(
            select(self.model),
        )

        return list(result.scalars().all())

    async def create(
        self,
        instance: ModelType,
    ) -> ModelType:
        self.session.add(instance)

        await self.session.flush()
        await self.session.refresh(instance)
        await self.session.commit()

        return instance

    async def delete(
        self,
        instance: ModelType,
    ) -> None:
        await self.session.delete(instance)
        await self.session.commit()
