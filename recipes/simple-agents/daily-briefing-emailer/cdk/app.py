import aws_cdk as cdk
from stack import DailyBriefingEmailerStack

app = cdk.App()
DailyBriefingEmailerStack(app, "DailyBriefingEmailerStack")
app.synth()
