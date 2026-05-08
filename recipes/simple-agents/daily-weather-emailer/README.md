# Daily Weather Emailer

Fetches the current weather for San Francisco and emails a Bedrock-generated summary every day at 9:00 AM.

## Architecture

- **EventBridge Scheduler** — triggers daily at 9am PT
- **Lambda** — fetches weather from Open-Meteo (free, no API key) and invokes Bedrock
- **Amazon Bedrock** (Claude Haiku) — generates a friendly weather summary
- **Amazon SES** — sends the email

## Deploy

```bash
cd cdk
pip install -r requirements.txt
cdk bootstrap   # first time only
cdk deploy
```

## Destroy

```bash
cdk destroy
```

## Configuration

Copy `.env.example` to `.env` and fill in your values before deploying.
