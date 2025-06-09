# import pytest
# import requests
# import portforward

# from contextlib import contextmanager
# from typing import Generator, Any
# from kubernetes.dynamic import DynamicClient
# from ocp_resources.secret import Secret
# from ocp_resources.inference_service import InferenceService
# from utilities.constants import KServeDeploymentType


# @contextmanager
# def kserve_s3_endpoint_secret(
#     admin_client: DynamicClient,
#     name: str,
#     namespace: str,
#     aws_access_key: str,
#     aws_secret_access_key: str,
#     aws_s3_endpoint: str,
#     aws_s3_region: str,
# ) -> Generator[Secret, Any, Any]:
#     with Secret(
#         client=admin_client,
#         name=name,
#         namespace=namespace,
#         annotations={
#             "serving.kserve.io/s3-endpoint": aws_s3_endpoint.replace("https://", ""),
#             "serving.kserve.io/s3-region": aws_s3_region,
#             "serving.kserve.io/s3-useanoncredential": "false",
#             "serving.kserve.io/s3-verifyssl": "0",
#             "serving.kserve.io/s3-usehttps": "1",
#         },
#         string_data={
#             "AWS_ACCESS_KEY_ID": aws_access_key,
#             "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
#         },
#         wait_for_resource=True,
#     ) as secret:
#         yield secret


# def run_triton_inference(pod_name: str, isvc: InferenceService, input_data: dict, model_version: str) -> Any:
#     """
#     Run inference against a Triton model, handling RAW and SERVERLESS deployments.
#     For RAW, port-forward to the pod and POST to localhost.
#     For SERVERLESS, POST to the service URL.
#     """
#     deployment_mode = isvc.instance.metadata.annotations.get("serving.kserve.io/deploymentMode")
#     model_name = isvc.instance.metadata.name

#     # Triton REST inference endpoint format
#     endpoint = f"/v2/models/{model_name}/infer"
#     if model_version:
#         endpoint = f"/v2/models/{model_name}/versions/{model_version}/infer"

#     if deployment_mode == KServeDeploymentType.RAW_DEPLOYMENT:
#         with portforward.forward(
#             pod_or_service=pod_name,
#             namespace=isvc.namespace,
#             from_port=8000,
#             to_port=8000,
#         ):
#             url = f"http://localhost:8000{endpoint}"
#             response = requests.post(url, json=input_data, verify=False, timeout=60)
#             response.raise_for_status()
#             return response.json()
#     elif deployment_mode == KServeDeploymentType.SERVERLESS:
#         url = f"{isvc.instance.status.url}{endpoint}"
#         response = requests.post(url, json=input_data, verify=False, timeout=60)
#         response.raise_for_status()
#         return response.json()
#     else:
#         raise ValueError(f"Invalid deployment_mode {deployment_mode}")


# def validate_inference_request(
#     pod_name: str,
#     isvc: InferenceService,
#     response_snapshot: Any,
#     input_query: Any,
#     model_version: str,
# ) -> None:
#     response = run_triton_inference(pod_name, isvc, input_query, model_version)
#     assert response == response_snapshot, f"Output mismatch: {response} != {response_snapshot}"


# def skip_if_deployment_mode(isvc: InferenceService, deployment_type: str, deployment_message: str) -> None:
#     if isvc.instance.metadata.annotations.get("serving.kserve.io/deploymentMode") == deployment_type:
#         pytest.skip(deployment_message)


# tests/model_serving/model_runtime/triton/basic_model_deployment/utils.py
import pytest
import requests
import portforward

from contextlib import contextmanager
from typing import Generator, Any
from kubernetes.dynamic import DynamicClient
from ocp_resources.secret import Secret
from ocp_resources.inference_service import InferenceService
from utilities.constants import KServeDeploymentType

@contextmanager
def kserve_s3_endpoint_secret(
    admin_client: DynamicClient,
    name: str,
    namespace: str,
    aws_access_key: str,
    aws_secret_access_key: str,
    aws_s3_endpoint: str,
    aws_s3_region: str,
) -> Generator[Secret, Any, Any]:
    with Secret(
        client=admin_client,
        name=name,
        namespace=namespace,
        annotations={
            "serving.kserve.io/s3-endpoint": aws_s3_endpoint.replace("https://", ""),
            "serving.kserve.io/s3-region": aws_s3_region,
            "serving.kserve.io/s3-useanoncredential": "false",
            "serving.kserve.io/s3-verifyssl": "0",
            "serving.kserve.io/s3-usehttps": "1",
        },
        string_data={
            "AWS_ACCESS_KEY_ID": aws_access_key,
            "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
        },
        wait_for_resource=True,
    ) as secret:
        yield secret

def run_triton_inference(pod_name: str, isvc: InferenceService, input_data: dict, model_version: str) -> Any:
    """
    Run inference against a Triton model, handling RAW and SERVERLESS deployments.
    For RAW, port-forward to the pod and POST to localhost.
    For SERVERLESS, POST to the service URL.
    """
    deployment_mode = isvc.instance.metadata.annotations.get("serving.kserve.io/deploymentMode")
    model_name = isvc.instance.metadata.name

    # Triton REST inference endpoint format
    endpoint = f"/v2/models/{model_name}/infer"
    if model_version:
        endpoint = f"/v2/models/{model_name}/versions/{model_version}/infer"

    if deployment_mode == KServeDeploymentType.RAW_DEPLOYMENT:
        with portforward.forward(
            pod_or_service=pod_name,
            namespace=isvc.namespace,
            from_port=8000,
            to_port=8000,
        ):
            url = f"http://localhost:8000{endpoint}"
            response = requests.post(url, json=input_data, verify=False, timeout=60)
            response.raise_for_status()
            return response.json()
    elif deployment_mode == KServeDeploymentType.SERVERLESS:
        url = f"{isvc.instance.status.url}{endpoint}"
        response = requests.post(url, json=input_data, verify=False, timeout=60)
        response.raise_for_status()
        return response.json()
    else:
        raise ValueError(f"Invalid deployment_mode {deployment_mode}")

def validate_inference_request(
    pod_name: str,
    isvc: InferenceService,
    response_snapshot: Any,
    input_query: Any,
    model_version: str,
) -> None:
    response = run_triton_inference(pod_name, isvc, input_query, model_version)
    assert response == response_snapshot, f"Output mismatch: {response} != {response_snapshot}"

def skip_if_deployment_mode(isvc: InferenceService, deployment_type: str, deployment_message: str) -> None:
    if isvc.instance.metadata.annotations.get("serving.kserve.io/deploymentMode") == deployment_type:
        pytest.skip(deployment_message)