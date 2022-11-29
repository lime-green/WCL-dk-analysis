import asyncio
import logging
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from client import fetch_report
from analyze import analyze


app = FastAPI()


async def catch_exceptions_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logging.exception(e)
        return Response("Internal server error", status_code=500)

# Add this middleware first so 500 errors have CORS headers
app.middleware("http")(catch_exceptions_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://classic.warcraftlogs.com",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeResponse(BaseModel):
    data: Dict


@app.get("/analyze_fight")
async def analyze_fight(
    response: Response, report_id: str, fight_id: int, source_id: int
):
    report = await fetch_report(report_id, fight_id, source_id)
    loop = asyncio.get_running_loop()

    events = await loop.run_in_executor(
        ThreadPoolExecutor(), functools.partial(analyze, report, fight_id)
    )

    response.headers["Cache-Control"] = "max-age=86400"
    return {"data": events}
