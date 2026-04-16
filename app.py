#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.iam_stack import IamStack
from stacks.api_stack import ApiStack
from stacks.lambda_stack import LambdaStack


app = cdk.App()
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

iam_stack = IamStack(app, "SupsimIamStack", env=env)
api_stack = ApiStack(app, "SupsimApiStack", env=env)
lambda_stack = LambdaStack(
    app,
    "SupsimLambdaStack",
    http_api=api_stack.http_api,
    lambda_execution_role=iam_stack.lambda_execution_role,
    env=env,
)

lambda_stack.add_dependency(iam_stack)
lambda_stack.add_dependency(api_stack)

app.synth()
