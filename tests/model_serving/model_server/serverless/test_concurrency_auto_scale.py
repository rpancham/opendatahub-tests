import pytest

from tests.model_serving.model_server.utils import (
    inference_service_pods_sampler,
)
from utilities.constants import (
    KServeDeploymentType,
    ModelFormat,
    ModelInferenceRuntime,
    ModelStoragePath,
    RuntimeTemplates,
    Timeout,
)

pytestmark = [
    pytest.mark.serverless,
    pytest.mark.sanity,
    pytest.mark.usefixtures("valid_aws_config"),
]


@pytest.mark.parametrize(
    "unprivileged_model_namespace, serving_runtime_from_template, s3_models_inference_service",
    [
        pytest.param(
            {"name": "serverless-auto-scale"},
            {
                "name": f"{ModelInferenceRuntime.CAIKIT_TGIS_RUNTIME}-concurrency",
                "template-name": RuntimeTemplates.CAIKIT_TGIS_SERVING,
                "multi-model": False,
                "enable-http": True,
            },
            {
                "name": f"{ModelFormat.CAIKIT}-concurrency",
                "deployment-mode": KServeDeploymentType.SERVERLESS,
                "model-dir": ModelStoragePath.FLAN_T5_SMALL_CAIKIT,
                "scale-metric": "concurrency",
                "scale-target": 1,
            },
        )
    ],
    indirect=True,
)
class TestConcurrencyAutoScale:
    @pytest.mark.dependency(name="test_auto_scale_using_concurrency")
    def test_auto_scale_using_concurrency(
        self,
        unprivileged_client,
        s3_models_inference_service,
        multiple_onnx_inference_requests,
    ):
        """Verify model is successfully scaled up based on concurrency metrics (KPA)"""
        for pods in inference_service_pods_sampler(
            client=unprivileged_client,
            isvc=s3_models_inference_service,
            timeout=Timeout.TIMEOUT_2MIN,
            sleep=10,
        ):
            if pods:
                if len(pods) > 1 and all([pod.status == pod.Status.RUNNING for pod in pods]):
                    return

    @pytest.mark.dependency(requires=["test_auto_scale_using_concurrency"])
    def test_pods_scaled_down_when_no_requests(self, unprivileged_client, s3_models_inference_service):
        """Verify auto-scaled pods are deleted when there are no inference requests"""
        for pods in inference_service_pods_sampler(
            client=unprivileged_client,
            isvc=s3_models_inference_service,
            timeout=Timeout.TIMEOUT_4MIN,
            sleep=10,
        ):
            if pods and len(pods) == 1:
                return
