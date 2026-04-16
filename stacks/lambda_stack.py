from aws_cdk import Stack, aws_lambda as _lambda, aws_apigatewayv2 as apigwv2
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from aws_cdk import aws_iam as iam
from constructs import Construct


class LambdaStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        http_api: apigwv2.HttpApi,
        lambda_execution_role: iam.IRole,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        health_function = _lambda.Function(
            self,
            "HealthFunction",
            function_name="supsim-health",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="app.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/health"),
            role=lambda_execution_role,
        )

        apigwv2.HttpRoute(
            self,
            "HealthRoute",
            http_api=http_api,
            route_key=apigwv2.HttpRouteKey.with_(path="/health", method=apigwv2.HttpMethod.GET),
            integration=HttpLambdaIntegration("HealthIntegration", health_function),
        )
