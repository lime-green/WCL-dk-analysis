import asyncio
import functools
from concurrent.futures import ProcessPoolExecutor
from typing import Dict

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from client import fetch_report
from analyze import analyze


app = FastAPI()

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
async def analyze_fight(response: Response, report_id: str, fight_id: int, source_id: int):
    report = await fetch_report(
        report_id, fight_id, source_id
    )
    loop = asyncio.get_running_loop()
    events = await loop.run_in_executor(
        ProcessPoolExecutor(), functools.partial(analyze, report, fight_id)
    )

    response.headers["Cache-Control"] = "max-age=3600, public"
    return {"data": events}
