import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

import boto3

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
SF_LAT = 37.7749
SF_LON = -122.4194

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 
    2: "Partly cloudy", 
    3: "Overcast",
    45: "Foggy", 
    48: "Icy fog",
    51: "Light drizzle", 
    53: "Moderate drizzle", 
    55: "Dense drizzle",
    61: "Slight rain", 
    63: "Moderate rain", 
    65: "Heavy rain",
    71: "Slight snow", 
    73: "Moderate snow", 
    75: "Heavy snow",
    80: "Slight showers", 
    81: "Moderate showers", 
    82: "Heavy showers",
    95: "Thunderstorm", 
    96: "Thunderstorm with hail", 
    99: "Thunderstorm with heavy hail",
}


def get_weather() -> dict:
    params = urllib.parse.urlencode({
        "latitude": SF_LAT,
        "longitude": SF_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,precipitation",
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "timezone": "America/Los_Angeles",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{params}") as response:
        return json.loads(response.read())


def generate_summary(weather: dict) -> str:
    current = weather["current"]
    condition = WEATHER_CODES.get(current["weathercode"], "Unknown")

    prompt = (
        "You are a friendly weather assistant. Write a brief, engaging daily weather "
        "summary for San Francisco.\n\n"
        f"Current conditions:\n"
        f"- Temperature: {current['temperature_2m']}°F (feels like {current['apparent_temperature']}°F)\n"
        f"- Condition: {condition}\n"
        f"- Wind speed: {current['windspeed_10m']} mph\n"
        f"- Precipitation: {current['precipitation']} mm\n\n"
        "Write 2-3 sentences. Be conversational and include one practical tip for the day."
    )

    client = boto3.client("bedrock-runtime")
    response = client.invoke_model(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def send_email(subject: str, body: str) -> None:
    ses = boto3.client("ses")
    ses.send_email(
        Source=os.environ["SENDER_EMAIL"],
        Destination={"ToAddresses": [os.environ["RECIPIENT_EMAIL"]]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )


def handler(event: dict, context: object) -> dict:
    weather = get_weather()
    summary = generate_summary(weather)
    today = datetime.now().strftime("%A, %B %d")
    send_email(f"SF Weather for {today}", summary)
    return {"statusCode": 200, "body": summary}
