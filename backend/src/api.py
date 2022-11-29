import asyncio
import logging
import functools
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

import sentry_sdk
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from client import fetch_report
from analyze import analyze


if os.environ.get("AWS_EXECUTION_ENV"):
    sentry_sdk.init(
        dsn="https://d5eb49442a8f433b86952081e5e42bfb@o4504244781711360.ingest.sentry.io/4504244816117760",
        traces_sample_rate=0.05,
    )
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
