# agent-cookbook

A collection of AI agent recipes built on AWS Bedrock, deployed with CDK.

## Recipes

### Simple Agents

| Agent | Description |
|---|---|
| [Daily Weather Emailer](recipes/simple-agents/daily-weather-emailer/) | Fetches SF weather daily and emails a Bedrock-generated summary at 9am |

## Structure

```
recipes/
└── simple-agents/
    └── daily-weather-emailer/
```

## Prerequisites

- AWS CLI configured
- CDK v2 installed (`npm install -g aws-cdk`)
- Python 3.11+
- SES sender email verified in your AWS account
