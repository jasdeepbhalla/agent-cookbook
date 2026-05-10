"""
Daily Briefing Emailer — Multi-Agent Orchestrator

Agents and their models:
  - News Agent      → claude-haiku-4-5  (fast, cheap for data fetching)
  - Weather Agent   → claude-haiku-4-5  (fast, cheap for data formatting)
  - Calendar Agent  → claude-haiku-4-5  (fast, cheap for event parsing) [optional]
  - Email Composer  → claude-sonnet-4-6 (better writing quality)
"""

import json
import os
from datetime import datetime

import anthropic
import boto3
import requests

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

client = anthropic.Anthropic()
ses = boto3.client("ses")
secretsmanager = boto3.client("secretsmanager")


# ── External API helpers ──────────────────────────────────────────────────────

def _get_secret(secret_name: str) -> dict:
    resp = secretsmanager.get_secret_value(SecretId=secret_name)
    return json.loads(resp["SecretString"])


def fetch_news(count: int = 5) -> dict:
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": os.environ["NEWS_API_KEY"],
        "language": "en",
        "country": "us",
        "pageSize": count,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    articles = [
        {
            "title": a["title"],
            "source": a["source"]["name"],
            "description": a.get("description") or "",
        }
        for a in resp.json().get("articles", [])[:count]
    ]
    return {"articles": articles}


def fetch_weather(lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weathercode,windspeed_10m,relativehumidity_2m",
        "hourly": "temperature_2m,precipitation_probability,weathercode",
        "temperature_unit": "fahrenheit",
        "forecast_days": 1,
        "timezone": os.environ.get("TIMEZONE", "America/Los_Angeles"),
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_calendar_events(date_str: str) -> dict:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    secrets = _get_secret(os.environ["GOOGLE_SECRET_NAME"])
    creds = Credentials(
        token=secrets["access_token"],
        refresh_token=secrets["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=secrets["client_id"],
        client_secret=secrets["client_secret"],
    )
    service = build("calendar", "v3", credentials=creds)

    day = datetime.fromisoformat(date_str)
    time_min = day.replace(hour=0, minute=0, second=0).isoformat() + "Z"
    time_max = day.replace(hour=23, minute=59, second=59).isoformat() + "Z"

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = [
        {
            "title": e.get("summary", "Untitled"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
            "end": e["end"].get("dateTime", e["end"].get("date")),
        }
        for e in result.get("items", [])
    ]
    return {"date": date_str, "events": events}


# ── Tool definitions (passed to Claude) ──────────────────────────────────────

NEWS_TOOLS = [
    {
        "name": "fetch_news",
        "description": "Fetch the top US news headlines from NewsAPI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of articles to fetch (max 5)"},
            },
            "required": [],
        },
    }
]

WEATHER_TOOLS = [
    {
        "name": "fetch_weather",
        "description": "Fetch current weather and hourly forecast from Open-Meteo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude"},
                "lon": {"type": "number", "description": "Longitude"},
            },
            "required": ["lat", "lon"],
        },
    }
]

CALENDAR_TOOLS = [
    {
        "name": "fetch_calendar_events",
        "description": "Fetch Google Calendar events for a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            },
            "required": ["date_str"],
        },
    }
]

TOOL_DISPATCH = {
    "fetch_news": lambda inp: fetch_news(**inp),
    "fetch_weather": lambda inp: fetch_weather(**inp),
    "fetch_calendar_events": lambda inp: fetch_calendar_events(**inp),
}


# ── Generic agentic loop ──────────────────────────────────────────────────────

def run_agent(model: str, system: str, user_message: str, tools: list) -> str:
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = TOOL_DISPATCH[block.name](block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


# ── Individual agents ─────────────────────────────────────────────────────────

def news_agent() -> str:
    print("  [News Agent / Haiku] Fetching headlines...")
    return run_agent(
        model=HAIKU,
        system=(
            "You are a news summarizer. Fetch exactly 5 headlines and return them as a "
            "numbered list. For each: one sentence summary + source name. Be concise."
        ),
        user_message="Fetch the top 5 US news headlines for today and summarize them.",
        tools=NEWS_TOOLS,
    )


def weather_agent() -> str:
    lat = float(os.environ.get("LAT", "37.7749"))
    lon = float(os.environ.get("LON", "-122.4194"))
    location = os.environ.get("LOCATION_NAME", "San Francisco, CA")
    print(f"  [Weather Agent / Haiku] Fetching weather for {location}...")
    return run_agent(
        model=HAIKU,
        system=(
            f"You are a weather reporter for {location}. Fetch the weather data and write "
            "2-3 sentences: current conditions (temp, sky, wind) and what to expect today. "
            "Include a clothing tip if relevant."
        ),
        user_message=f"Fetch the weather for lat={lat}, lon={lon} and summarize today's conditions.",
        tools=WEATHER_TOOLS,
    )


def calendar_agent() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"  [Calendar Agent / Haiku] Fetching events for {today}...")
    return run_agent(
        model=HAIKU,
        system=(
            "You are a calendar assistant. Fetch today's events and clearly list: "
            "1) each event with its time, 2) the longest free blocks during work hours (9am-6pm). "
            "If no events, say the day is wide open."
        ),
        user_message=f"Fetch my calendar events for {today} and summarize my schedule.",
        tools=CALENDAR_TOOLS,
    )


def email_composer_agent(news: str, weather: str, calendar: str | None) -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    print("  [Email Composer / Sonnet] Writing briefing email...")

    calendar_section = f"CALENDAR SUMMARY:\n{calendar}" if calendar else "CALENDAR: Not configured."

    return run_agent(
        model=SONNET,
        system=(
            "You are a personal assistant writing a warm, scannable daily briefing email. "
            "Structure: greeting, then sections for Weather and News (always present), "
            "and Calendar only if provided. Use bullet points. Keep total under 400 words. "
            "End with one short encouraging sentence."
        ),
        user_message=f"""Write a daily briefing email for {today}.

WEATHER SUMMARY:
{weather}

NEWS SUMMARY:
{news}

{calendar_section}""",
        tools=[],
    )


# ── Orchestrator ──────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    print("Starting daily briefing multi-agent pipeline...")

    news = news_agent()
    weather = weather_agent()

    calendar = None
    if os.environ.get("GOOGLE_SECRET_NAME"):
        calendar = calendar_agent()
    else:
        print("  [Calendar Agent] Skipped — GOOGLE_SECRET_NAME not configured.")

    email_body = email_composer_agent(news, weather, calendar)

    today = datetime.now().strftime("%A, %B %d")
    ses.send_email(
        Source=os.environ["SENDER_EMAIL"],
        Destination={"ToAddresses": [os.environ["RECIPIENT_EMAIL"]]},
        Message={
            "Subject": {"Data": f"Your Daily Briefing — {today}"},
            "Body": {"Text": {"Data": email_body}},
        },
    )

    print("Daily briefing sent successfully.")
    return {"statusCode": 200, "body": "Briefing sent."}
