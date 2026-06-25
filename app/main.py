from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from .database import engine, Base
from .routers import routes, stops, search

HERE = Path(__file__).parent

app = FastAPI(title="Transito CTBA", description="Consulta de horários GTFS — Curitiba")

app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

app.include_router(routes.router)
app.include_router(stops.router)
app.include_router(search.router)


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((HERE / "templates" / "index.html").read_text(encoding="utf-8"))


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
