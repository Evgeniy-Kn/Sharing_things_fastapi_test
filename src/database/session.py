from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(url="sqlite+aiosqlite:///db.sqlite3")

async_session = async_sessionmaker(engine)


async def get_db():
    async with async_session() as session:
        yield session
