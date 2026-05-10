from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_scheduler as scheduler,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class DailyBriefingEmailerStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ctx = self.node.try_get_context
        sender_email = ctx("sender_email")
        recipient_email = ctx("recipient_email")
        news_api_key = ctx("news_api_key")
        timezone = ctx("schedule_timezone") or "America/Los_Angeles"
        hour = ctx("schedule_hour") or "7"
        lat = ctx("lat") or "37.7749"
        lon = ctx("lon") or "-122.4194"
        location_name = ctx("location_name") or "San Francisco, CA"

        # Optional: Google Calendar OAuth tokens — populate manually after deploy
        enable_calendar = ctx("enable_google_calendar") == "true"
        google_secret = None
        if enable_calendar:
            google_secret = secretsmanager.Secret(
                self,
                "GoogleCalendarSecret",
                secret_name="daily-briefing/google-calendar",
                description="Google Calendar OAuth2 credentials",
            )

        env_vars = {
            "SENDER_EMAIL": sender_email,
            "RECIPIENT_EMAIL": recipient_email,
            "NEWS_API_KEY": news_api_key,
            "TIMEZONE": timezone,
            "LAT": lat,
            "LON": lon,
            "LOCATION_NAME": location_name,
        }
        if google_secret:
            env_vars["GOOGLE_SECRET_NAME"] = google_secret.secret_name

        fn = lambda_.Function(
            self,
            "BriefingFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda_build"),
            timeout=Duration.minutes(3),
            memory_size=512,
            environment=env_vars,
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )
        if google_secret:
            google_secret.grant_read(fn)

        # EventBridge Scheduler — fires daily at the configured hour
        scheduler_role = iam.Role(
            self,
            "SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )
        fn.grant_invoke(scheduler_role)

        scheduler.CfnSchedule(
            self,
            "DailySchedule",
            schedule_expression=f"cron(0 {hour} * * ? *)",
            schedule_expression_timezone=timezone,
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
                mode="OFF"
            ),
            target=scheduler.CfnSchedule.TargetProperty(
                arn=fn.function_arn,
                role_arn=scheduler_role.role_arn,
            ),
        )
