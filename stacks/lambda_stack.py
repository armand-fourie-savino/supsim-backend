from aws_cdk import Stack, aws_lambda as _lambda, aws_apigatewayv2 as apigwv2
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from aws_cdk import aws_iam as iam
import aws_cdk as cdk
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

        self.supsim_layer = _lambda.LayerVersion(
            self,
            "SupsimLayer",
            code=_lambda.Code.from_asset("layers/supsim"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.ARM_64],
        )

        health_function = _lambda.Function(
            self,
            "HealthFunction",
            function_name="supsim-health",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="app.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/health"),
            role=lambda_execution_role,
            layers=[self.supsim_layer],
            memory_size=256,
            timeout=cdk.Duration.seconds(5)
        )

        apigwv2.HttpRoute(
            self,
            "HealthRoute",
            http_api=http_api,
            route_key=apigwv2.HttpRouteKey.with_(path="/health", method=apigwv2.HttpMethod.GET),
            integration=HttpLambdaIntegration("HealthIntegration", health_function),
        )

        # --- Analytics Lambda functions ---

        analytics_code = _lambda.Code.from_asset("lambdas/analytics")

        stock_summary_function = _lambda.Function(
            self,
            "StockSummaryFunction",
            function_name="supsim-analytics-stock-summary",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="app.stock_summary",
            code=analytics_code,
            role=lambda_execution_role,
            layers=[self.supsim_layer],
            memory_size=3008,
            timeout=cdk.Duration.seconds(30)
        )

        customer_summary_function = _lambda.Function(
            self,
            "CustomerSummaryFunction",
            function_name="supsim-analytics-customer-summary",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="app.customer_summary",
            code=analytics_code,
            role=lambda_execution_role,
            layers=[self.supsim_layer],
            memory_size=3008,
            timeout=cdk.Duration.seconds(30)
        )

        movement_metrics_function = _lambda.Function(
            self,
            "MovementMetricsFunction",
            function_name="supsim-analytics-movement-metrics",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="app.movement_metrics",
            code=analytics_code,
            role=lambda_execution_role,
            layers=[self.supsim_layer],
            memory_size=3008,
            timeout=cdk.Duration.seconds(30)
        )

        apigwv2.HttpRoute(
            self,
            "StockSummaryRoute",
            http_api=http_api,
            route_key=apigwv2.HttpRouteKey.with_(
                path="/{customer_id}/stock_summary",
                method=apigwv2.HttpMethod.GET,
            ),
            integration=HttpLambdaIntegration(
                "StockSummaryIntegration", stock_summary_function
            ),
        )

        apigwv2.HttpRoute(
            self,
            "CustomerSummaryRoute",
            http_api=http_api,
            route_key=apigwv2.HttpRouteKey.with_(
                path="/{customer_id}/customer_summary",
                method=apigwv2.HttpMethod.GET,
            ),
            integration=HttpLambdaIntegration(
                "CustomerSummaryIntegration", customer_summary_function
            ),
        )

        apigwv2.HttpRoute(
            self,
            "MovementMetricsRoute",
            http_api=http_api,
            route_key=apigwv2.HttpRouteKey.with_(
                path="/{customer_id}/movement_metrics/{stock_code}",
                method=apigwv2.HttpMethod.GET,
            ),
            integration=HttpLambdaIntegration(
                "MovementMetricsIntegration", movement_metrics_function
            ),
        )
