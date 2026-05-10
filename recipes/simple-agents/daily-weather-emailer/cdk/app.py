import aws_cdk as cdk
from stack import DailyWeatherEmailerStack

app = cdk.App()

DailyWeatherEmailerStack(
    app,
    "DailyWeatherEmailer",
    env=cdk.Environment(region="us-west-2"),
)

app.synth()
