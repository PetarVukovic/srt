import asyncio
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.db.models import Seminar, Batch, PrijevodSeminara


async def seed_data():
    async with AsyncSessionLocal() as session:

        # 1️⃣ Provjera – da ne seedamo 2x
        result = await session.exec(select(Seminar))
        if result.first():
            print("⚠️ Dummy podaci već postoje – preskačem.")
            return

        # 2️⃣ Seminar
        seminar = Seminar(
            name="Uvod u SQLModel",
            description="Osnovni seminar o SQLModelu, relacijama i async radu.",
        )
        session.add(seminar)
        await session.flush()  # dobijemo seminar.id

        # 3️⃣ Batch
        batch = Batch(
            seminar_id=seminar.id,
            status="active",
        )
        session.add(batch)
        await session.flush()  # dobijemo batch.id

        # 4️⃣ Prijevodi
        prijevod_hr = PrijevodSeminara(
            batch_id=batch.id,
            language="hr",
            content="Ovo je sadržaj seminara na hrvatskom jeziku.",
        )

        prijevod_en = PrijevodSeminara(
            batch_id=batch.id,
            language="en",
            content="This is the seminar content in English.",
        )

        session.add(prijevod_hr)
        session.add(prijevod_en)

        # 5️⃣ Commit svega
        await session.commit()

        print("✅ Dummy podaci uspješno ubačeni!")


if __name__ == "__main__":
    asyncio.run(seed_data())