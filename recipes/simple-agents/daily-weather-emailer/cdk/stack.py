import aws_cdk as cdk
from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_scheduler as scheduler,
)
from constructs import Construct


class DailyWeatherEmailerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sender_email = self.node.try_get_context("sender_email")
        recipient_email = self.node.try_get_context("recipient_email")
        model_id = self.node.try_get_context("bedrock_model_id") or "anthropic.claude-3-haiku-20240307-v1:0"
        timezone = self.node.try_get_context("schedule_timezone") or "America/Los_Angeles"
        hour = self.node.try_get_context("schedule_hour") or "9"

        if not sender_email or sender_email == "your-verified-sender@example.com":
            raise ValueError("Set 'sender_email' in cdk.json or via --context sender_email=you@example.com")
        if not recipient_email or recipient_email == "your-recipient@example.com":
            raise ValueError("Set 'recipient_email' in cdk.json or via --context recipient_email=you@example.com")

        fn = lambda_.Function(
            self,
            "WeatherEmailerFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambda"),
            timeout=Duration.seconds(30),
            environment={
                "SENDER_EMAIL": sender_email,
                "RECIPIENT_EMAIL": recipient_email,
                "BEDROCK_MODEL_ID": model_id,
            },
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"],
            )
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=["*"],
            )
        )

        scheduler_role = iam.Role(
            self,
            "SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )
        fn.grant_invoke(scheduler_role)

        scheduler.CfnSchedule(
            self,
            "DailySchedule",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
                mode="OFF",
            ),
            schedule_expression=f"cron(0 {hour} * * ? *)",
            schedule_expression_timezone=timezone,
            target=scheduler.CfnSchedule.TargetProperty(
                arn=fn.function_arn,
                role_arn=scheduler_role.role_arn,
            ),
        )
