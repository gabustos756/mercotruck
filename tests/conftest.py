import pytest
import asyncio
from app.core.database import async_engine

@pytest.fixture(autouse=True)
def cleanup_db_engine():
    yield
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if not loop.is_closed():
            if loop.is_running():
                asyncio.create_task(async_engine.dispose())
            else:
                loop.run_until_complete(async_engine.dispose())
    except Exception:
        pass
