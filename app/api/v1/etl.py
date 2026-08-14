from fastapi import APIRouter, BackgroundTasks
from app.etl.pipeline import run_etl_pipeline

router = APIRouter(prefix="/etl", tags=["ETL Pipeline"])

@router.post("/run")
async def trigger_etl_run(background_tasks: BackgroundTasks):
    """Dispara la re-ingesta de Excels en segundo plano."""
    background_tasks.add_task(run_etl_pipeline)
    return {"status": "started", "message": "Proceso ETL iniciado en segundo plano."}
