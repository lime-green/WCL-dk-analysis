import asyncio
import logging
import functools
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict

import sentry_sdk
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

from client import fetch_report, PrivateReport, TemporaryUnavailable
from analysis.analyze import analyze

SENTRY_ENABLED = os.environ.get("AWS_EXECUTION_ENV") is not None
if SENTRY_ENABLED:
    sentry_sdk.init(
        dsn="https://d5eb49442a8f433b86952081e5e42bfb@o4504244781711360.ingest.sentry.io/4504244816117760",
        traces_sample_rate=0.05,
        attach_stacktrace=True,
        integrations=[AwsLambdaIntegration()],
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
    if report_id == "compare":
        response.status_code = 400
        return {"error": "Can not analyze while using the 'Compare' feature"}

    try:
        report = await fetch_report(report_id, fight_id, source_id)
    except PrivateReport:
        response.status_code = 403
        return {"error": "Can not analyze private reports"}
    except TemporaryUnavailable:
        response.status_code = 503
        return {"error": "Bad response from Warcraft Logs, try again"}

    loop = asyncio.get_running_loop()

    events = await loop.run_in_executor(
        ThreadPoolExecutor(), functools.partial(analyze, report, fight_id)
    )

    # don't cache reports that are less than a day old
    ended_ago = datetime.now() - datetime.fromtimestamp(report.end_time / 1000)
    if fight_id == -1 and ended_ago < timedelta(days=1):
        response.headers["Cache-Control"] = "no-cache"
    else:
        response.headers["Cache-Control"] = "max-age=86400"
    return {"data": events}
