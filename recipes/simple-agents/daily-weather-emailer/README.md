# Daily Weather Emailer

Fetches the current weather for San Francisco and emails a Bedrock-generated summary every day at 9:00 AM.

No API keys required — uses [Open-Meteo](https://open-meteo.com/) (free, public) for weather data.

## Architecture

```
EventBridge Scheduler (9am daily)
        │
        ▼
    Lambda (Python 3.12)
        ├── Open-Meteo API  →  current SF weather
        ├── Amazon Bedrock  →  friendly summary
        └── Amazon SES      →  sends the email
```

## Prerequisites

- AWS CLI configured (`aws configure`)
- CDK v2 installed (`npm install -g aws-cdk`)
- Python 3.8+
- SES sender email [verified](https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html) in your AWS account

## Configuration

Edit `cdk/cdk.json` and update the context values:

| Key | Description | Default |
|---|---|---|
| `sender_email` | SES-verified sender address | *(required)* |
| `recipient_email` | Where to send the daily email | *(required)* |
| `bedrock_model_id` | Bedrock model to use | `anthropic.claude-3-haiku-20240307-v1:0` |
| `schedule_timezone` | Timezone for 9am trigger | `America/Los_Angeles` |
| `schedule_hour` | Hour to send (24h format) | `9` |

Or pass them at deploy time without editing any file:

```bash
cdk deploy \
  --context sender_email=you@example.com \
  --context recipient_email=you@example.com
```

## Deploy

```bash
cd cdk
pip install -r requirements.txt
cdk bootstrap   # first time only, per AWS account/region
cdk deploy
```

Default region: **us-west-2**. Override with `CDK_DEFAULT_REGION=us-east-1 cdk deploy`.

## Destroy

```bash
cd cdk
cdk destroy
```

## Cost estimate

All services are near-zero cost at this scale:
- Lambda: well within free tier (1 invocation/day)
- Bedrock (Claude Haiku): ~$0.001 per email
- SES: free up to 62,000 emails/month
- EventBridge Scheduler: free tier covers 14M invocations/month
