import asyncio
import functools
from concurrent.futures import ProcessPoolExecutor
from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel

from client import fetch_report
from analyze import analyze


app = FastAPI()


class AnalyzeRequest(BaseModel):
    character_name: str
    encounter_name: str
    report_code: str


class AnalyzeResponse(BaseModel):
    data: Dict


@app.get("/analyze_fight")
async def analyze_fight(data: AnalyzeRequest):
    report = await fetch_report(
        data.report_code, data.character_name, data.encounter_name
    )
    loop = asyncio.get_running_loop()
    events = await loop.run_in_executor(
        ProcessPoolExecutor(), functools.partial(analyze, report, data.encounter_name)
    )

    return {"data": events}
