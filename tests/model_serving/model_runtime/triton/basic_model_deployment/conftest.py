# # from typing import Any, Generator
# # import copy
# # import pytest
# # from kubernetes.dynamic import DynamicClient
# # from ..constant import TEMPLATE_MAP, PREDICT_RESOURCES
# # from ocp_resources.namespace import Namespace
# # from ocp_resources.serving_runtime import ServingRuntime
# # from ocp_resources.inference_service import InferenceService
# # from ocp_resources.pod import Pod
# # from ocp_resources.secret import Secret
# # from ocp_resources.template import Template
# # from ocp_resources.service_account import ServiceAccount
# # from tests.model_serving.model_runtime.vllm.utils import (
# #     kserve_s3_endpoint_secret,
# #     validate_supported_quantization_schema,
# #     skip_if_deployment_mode,
# # )
# # from utilities.constants import KServeDeploymentType, Labels, RuntimeTemplates, Protocols
# # from pytest import FixtureRequest
# # from syrupy.extensions.json import JSONSnapshotExtension
# # from tests.model_serving.model_runtime.triton.constant import TEMPLATE_MAP, PREDICT_RESOURCES
# # from tests.model_serving.model_runtime.triton.constant import TEMPLATE_FILE
# # from simple_logger.logger import get_logger

# # from utilities.inference_utils import create_isvc
# # from utilities.infra import get_pods_by_isvc_label
# # from utilities.serving_runtime import ServingRuntimeFromTemplate

# # LOGGER = get_logger(name=__name__)

# # @pytest.fixture(scope="session")
# # def triton_runtime_image(pytestconfig: pytest.Config) -> str | None:
# #     runtime_image = pytestconfig.option.triton_runtime_image
# #     if not runtime_image:
# #         return None
# #     return runtime_image

# # @pytest.fixture(scope="class")
# # def triton_grpc_serving_runtime_template(admin_client: DynamicClient) -> Template:
# #     grpc_template_yaml = TEMPLATE_FILE.get(Protocols.GRPC)
# #     with Template(
# #         client=admin_client,
# #         yaml_file=grpc_template_yaml,
# #     ) as tp:
# #         yield tp


# # @pytest.fixture(scope="class")
# # def triton_rest_serving_runtime_template(admin_client: DynamicClient) -> Template:
# #     rest_template_yaml = TEMPLATE_FILE.get(Protocols.REST)
# #     with Template(
# #         client=admin_client,
# #         yaml_file=rest_template_yaml,
# #     ) as tp:
# #         yield tp


# # @pytest.fixture(scope="class")
# # def serving_runtime(
# #     request: FixtureRequest,
# #     admin_client: DynamicClient,
# #     model_namespace: Namespace,
# #     protocol: str,
# #     triton_runtime_image: str,  # Injected here from above fixture
# # ) -> Generator[ServingRuntime, None, None]:
# #     protocol = protocol.lower()
# #     template_name = TEMPLATE_MAP.get(protocol, RuntimeTemplates.TRITON_REST)
# #     with ServingRuntimeFromTemplate(
# #         client=admin_client,
# #         name="triton-runtime",
# #         namespace=model_namespace.name,
# #         template_name=template_name,
# #         deployment_type=request.param["deployment_type"],
# #         runtime_image=triton_runtime_image,
# #     ) as model_runtime:
# #         yield model_runtime


# # @pytest.fixture(scope="class")
# # def triton_inference_service(
# #     request: FixtureRequest,
# #     admin_client: DynamicClient,
# #     model_namespace: Namespace,
# #     serving_runtime: ServingRuntime,
# #     s3_models_storage_uri: str,
# #     model_service_account: ServiceAccount,
# # ) -> Generator[InferenceService, Any, Any]:
# #     isvc_kwargs = {
# #         "client": admin_client,
# #         "name": request.param["name"],
# #         "namespace": model_namespace.name,
# #         "runtime": serving_runtime.name,
# #         "storage_uri": s3_models_storage_uri,
# #         "model_format": serving_runtime.instance.spec.supportedModelFormats[0].name,
# #         "model_service_account": model_service_account.name,
# #         "deployment_mode": request.param.get("deployment_mode", KServeDeploymentType.SERVERLESS),
# #     }

# #     gpu_count = request.param.get("gpu_count")
# #     timeout = request.param.get("timeout")
# #     resources: Any = copy.deepcopy(PREDICT_RESOURCES["resources"])

# #     if gpu_count:
# #         identifier = Labels.Nvidia.NVIDIA_COM_GPU
# #         resources["requests"][identifier] = gpu_count
# #         resources["limits"][identifier] = gpu_count
# #         isvc_kwargs["resources"] = resources

# #         if gpu_count > 1:
# #             isvc_kwargs["volumes"] = PREDICT_RESOURCES["volumes"]
# #             isvc_kwargs["volume_mounts"] = PREDICT_RESOURCES["volume_mounts"]

# #     if timeout:
# #         isvc_kwargs["timeout"] = timeout

# #     arguments = request.param.get("runtime_argument", [])
# #     arguments = [
# #         arg for arg in arguments
# #         if not (arg.startswith("--tensor-parallel-size") or arg.startswith("--quantization"))
# #     ]
# #     if gpu_count:
# #         arguments.append(f"--tensor-parallel-size={gpu_count}")
# #     if quantization := request.param.get("quantization"):
# #         validate_supported_quantization_schema(q_type=quantization)
# #         arguments.append(f"--quantization={quantization}")
# #     if arguments:
# #         isvc_kwargs["argument"] = arguments

# #     isvc_kwargs["min_replicas"] = request.param.get("min-replicas")

# #     with create_isvc(**isvc_kwargs) as isvc:
# #         yield isvc


# # @pytest.fixture(scope="class")
# # def model_service_account(admin_client: DynamicClient, kserve_endpoint_s3_secret: Secret) -> ServiceAccount:
# #     with ServiceAccount(
# #         client=admin_client,
# #         namespace=kserve_endpoint_s3_secret.namespace,
# #         name="models-bucket-sa",
# #         secrets=[{"name": kserve_endpoint_s3_secret.name}],
# #     ) as sa:
# #         yield sa


# # @pytest.fixture(scope="class")
# # def kserve_endpoint_s3_secret(
# #     admin_client: DynamicClient,
# #     model_namespace: Namespace,
# #     aws_access_key_id: str,
# #     aws_secret_access_key: str,
# #     models_s3_bucket_region: str,
# #     models_s3_bucket_endpoint: str,
# # ) -> Secret:
# #     with kserve_s3_endpoint_secret(
# #         admin_client=admin_client,
# #         name="models-bucket-secret",
# #         namespace=model_namespace.name,
# #         aws_access_key=aws_access_key_id,
# #         aws_secret_access_key=aws_secret_access_key,
# #         aws_s3_region=models_s3_bucket_region,
# #         aws_s3_endpoint=models_s3_bucket_endpoint,
# #     ) as secret:
# #         yield secret


# # @pytest.fixture
# # def response_snapshot(snapshot: Any) -> Any:
# #     return snapshot.use_extension(extension_class=JSONSnapshotExtension)


# # @pytest.fixture
# # def triton_pod_resource(admin_client: DynamicClient, triton_inference_service: InferenceService) -> Pod:
# #     return get_pods_by_isvc_label(client=admin_client, isvc=triton_inference_service)[0]


# # @pytest.fixture
# # def skip_if_serverless_deployemnt(triton_inference_service: InferenceService) -> None:
# #     skip_if_deployment_mode(
# #         isvc=triton_inference_service,
# #         deployment_type=KServeDeploymentType.SERVERLESS,
# #         deployment_message="Test is being skipped because model is being deployed in serverless mode",
# #     )


# # @pytest.fixture
# # def skip_if_raw_deployemnt(triton_inference_service: InferenceService) -> None:
# #     skip_if_deployment_mode(
# #         isvc=triton_inference_service,
# #         deployment_type=KServeDeploymentType.RAW_DEPLOYMENT,
# #         deployment_message="Test is being skipped because model is being deployed in raw mode",
# #     )


# from typing import Any, Generator
# import pytest
# from kubernetes.dynamic import DynamicClient
# from ocp_resources.namespace import Namespace
# from ocp_resources.serving_runtime import ServingRuntime
# from ocp_resources.inference_service import InferenceService
# from ocp_resources.pod import Pod
# from ocp_resources.secret import Secret
# from ocp_resources.template import Template
# from ocp_resources.service_account import ServiceAccount
# from tests.model_serving.model_runtime.vllm.utils import (
#     kserve_s3_endpoint_secret,
#     validate_supported_quantization_schema,
#     skip_if_deployment_mode,
# )

# from pytest import FixtureRequest
# from syrupy.extensions.json import JSONSnapshotExtension
# from simple_logger.logger import get_logger
# from utilities.inference_utils import create_isvc
# from utilities.infra import get_pods_by_isvc_label
# from utilities.serving_runtime import ServingRuntimeFromTemplate

# LOGGER = get_logger(name=__name__)
# try:
#     from utilities.constants import RuntimeTemplates, Protocols, KServeDeploymentType, Labels
# except ImportError:
#     class Protocols:
#         REST = "rest"
#         GRPC = "grpc"
#     class RuntimeTemplates:
#         TRITON_REST = "triton-rest"
#         TRITON_GRPC = "triton-grpc"
#     class KServeDeploymentType:
#         SERVERLESS = "Serverless"
#         RAW_DEPLOYMENT = "RawDeployment"
#     class Labels:
#         class Nvidia:
#             NVIDIA_COM_GPU = "nvidia.com/gpu"
# if not hasattr(RuntimeTemplates, 'TRITON_REST'):
#     RuntimeTemplates.TRITON_REST = "triton-rest"
# if not hasattr(RuntimeTemplates, 'TRITON_GRPC'):
#     RuntimeTemplates.TRITON_GRPC = "triton-grpc"

# from ..constant import TEMPLATE_MAP, PREDICT_RESOURCES
# @pytest.fixture(scope="class")
# def triton_grpc_serving_runtime_template(admin_client: DynamicClient) -> Template:
#     grpc_template_yaml = "triton_grpc_serving_template.yaml"
#     with Template(
#         client=admin_client,
#         name="triton-grpc-template",
#         namespace="default",
#     ) as tp:
#         yield tp
# @pytest.fixture(scope="class")

# def triton_rest_serving_runtime_template(admin_client: DynamicClient) -> Template:
#     rest_template_yaml = "triton_onnx_rest_servingruntime.yaml"
#     with Template(
#         client=admin_client,
#         name="triton-rest-template",
#         namespace="default",
#     ) as tp:
#         yield tp
# @pytest.fixture(scope="class")

# def serving_runtime(
#     request: FixtureRequest,
#     admin_client: DynamicClient,
#     model_namespace: Namespace,
#     protocol: str,
#     triton_runtime_image: str,
# ) -> Generator[ServingRuntime, None, None]:
#     protocol = protocol.lower()
#     template_name = TEMPLATE_MAP.get(protocol, RuntimeTemplates.TRITON_REST)
#     with ServingRuntimeFromTemplate(
#         client=admin_client,
#         name="triton-runtime",
#         namespace=model_namespace.name,
#         template_name=template_name,
#         deployment_type=request.param["deployment_type"],
#         runtime_image=triton_runtime_image,
#     ) as model_runtime:
#         yield model_runtime

# @pytest.fixture(scope="class")
# def triton_inference_service(
#     request: FixtureRequest,
#     admin_client: DynamicClient,
#     model_namespace: Namespace,
#     serving_runtime: ServingRuntime,
#     s3_models_storage_uri: str,
#     model_service_account: ServiceAccount,
# ) -> Generator[InferenceService, Any, Any]:
#     isvc_kwargs = {
#         "client": admin_client,
#         "name": request.param["name"],
#         "namespace": model_namespace.name,
#         "runtime": serving_runtime.name,
#         "storage_uri": s3_models_storage_uri,
#         "model_format": serving_runtime.instance.spec.supportedModelFormats[0].name,
#         "model_service_account": model_service_account.name,
#         "deployment_mode": request.param.get("deployment_mode", KServeDeploymentType.SERVERLESS),
#     }

#     gpu_count = request.param.get("gpu_count")
#     timeout = request.param.get("timeout")
#     resources: Any = copy.deepcopy(PREDICT_RESOURCES["resources"])

#     if gpu_count:
#         identifier = Labels.Nvidia.NVIDIA_COM_GPU
#         resources["requests"][identifier] = gpu_count
#         resources["limits"][identifier] = gpu_count
#         isvc_kwargs["resources"] = resources

#         if gpu_count > 1:
#             isvc_kwargs["volumes"] = PREDICT_RESOURCES["volumes"]
#             isvc_kwargs["volume_mounts"] = PREDICT_RESOURCES["volume_mounts"]

#     if timeout:
#         isvc_kwargs["timeout"] = timeout

#     arguments = request.param.get("runtime_argument", [])
#     arguments = [
#         arg for arg in arguments
#         if not (arg.startswith("--tensor-parallel-size") or arg.startswith("--quantization"))
#     ]
#     if gpu_count:
#         arguments.append(f"--tensor-parallel-size={gpu_count}")
#     if quantization := request.param.get("quantization"):
#         validate_supported_quantization_schema(q_type=quantization)
#         arguments.append(f"--quantization={quantization}")
#     if arguments:
#         isvc_kwargs["argument"] = arguments

#     isvc_kwargs["min_replicas"] = request.param.get("min-replicas")

#     with create_isvc(**isvc_kwargs) as isvc:
#         yield isvc


# @pytest.fixture(scope="class")
# def model_service_account(admin_client: DynamicClient, kserve_endpoint_s3_secret: Secret) -> ServiceAccount:
#     with ServiceAccount(
#         client=admin_client,
#         namespace=kserve_endpoint_s3_secret.namespace,
#         name="models-bucket-sa",
#         secrets=[{"name": kserve_endpoint_s3_secret.name}],
#     ) as sa:
#         yield sa


# @pytest.fixture(scope="class")
# def kserve_endpoint_s3_secret(
#     admin_client: DynamicClient,
#     model_namespace: Namespace,
#     aws_access_key_id: str,
#     aws_secret_access_key: str,
#     models_s3_bucket_region: str,
#     models_s3_bucket_endpoint: str,
# ) -> Secret:
#     with kserve_s3_endpoint_secret(
#         admin_client=admin_client,
#         name="models-bucket-secret",
#         namespace=model_namespace.name,
#         aws_access_key=aws_access_key_id,
#         aws_secret_access_key=aws_secret_access_key,
#         aws_s3_region=models_s3_bucket_region,
#         aws_s3_endpoint=models_s3_bucket_endpoint,
#     ) as secret:
#         yield secret


# @pytest.fixture
# def response_snapshot(snapshot: Any) -> Any:
#     return snapshot.use_extension(extension_class=JSONSnapshotExtension)


# @pytest.fixture
# def triton_pod_resource(admin_client: DynamicClient, triton_inference_service: InferenceService) -> Pod:
#     return get_pods_by_isvc_label(client=admin_client, isvc=triton_inference_service)[0]


# @pytest.fixture
# def skip_if_serverless_deployemnt(triton_inference_service: InferenceService) -> None:
#     skip_if_deployment_mode(
#         isvc=triton_inference_service,
#         deployment_type=KServeDeploymentType.SERVERLESS,
#         deployment_message="Test is being skipped because model is being deployed in serverless mode",
#     )


# @pytest.fixture
# def skip_if_raw_deployemnt(triton_inference_service: InferenceService) -> None:
#     skip_if_deployment_mode(
#         isvc=triton_inference_service,
#         deployment_type=KServeDeploymentType.RAW_DEPLOYMENT,
#         deployment_message="Test is being skipped because model is being deployed in raw mode",
#     )

# tests/model_serving/model_runtime/triton/basic_model_deployment/conftest.py 
import copy
import os
import pytest
from typing import Any, Generator
from kubernetes.dynamic import DynamicClient
from ocp_resources.namespace import Namespace
from ocp_resources.serving_runtime import ServingRuntime
from ocp_resources.inference_service import InferenceService
from ocp_resources.pod import Pod
from ocp_resources.secret import Secret
from ocp_resources.template import Template
from ocp_resources.service_account import ServiceAccount
from tests.model_serving.model_runtime.vllm.utils import (
    kserve_s3_endpoint_secret,
    validate_supported_quantization_schema,
    skip_if_deployment_mode,
)
from pytest import FixtureRequest
from syrupy.extensions.json import JSONSnapshotExtension
from simple_logger.logger import get_logger
from utilities.inference_utils import create_isvc
from utilities.infra import get_pods_by_isvc_label
from utilities.serving_runtime import ServingRuntimeFromTemplate


LOGGER = get_logger(name=__name__)
try:
    from utilities.constants import RuntimeTemplates, Protocols, KServeDeploymentType, Labels
except ImportError:
    class Protocols:
        REST = "rest"
        GRPC = "grpc"
    class RuntimeTemplates:
        TRITON_REST = "triton-rest"
        TRITON_GRPC = "triton-grpc"
    class KServeDeploymentType:
        SERVERLESS = "Serverless"
        RAW_DEPLOYMENT = "RawDeployment"
    class Labels:
        class Nvidia:
            NVIDIA_COM_GPU = "nvidia.com/gpu"
if not hasattr(RuntimeTemplates, 'TRITON_REST'):
    RuntimeTemplates.TRITON_REST = "triton-rest"
if not hasattr(RuntimeTemplates, 'TRITON_GRPC'):
    RuntimeTemplates.TRITON_GRPC = "triton-grpc"

from ..constant import TEMPLATE_MAP, PREDICT_RESOURCES

# Add command-line options
def pytest_addoption(parser):
    parser.addoption("--model-s3-bucket-name", action="store", default="")
    parser.addoption("--model-s3-bucket-region", action="store", default="")
    parser.addoption("--model-s3-bucket-endpoint", action="store", default="")
    parser.addoption("--aws-access-key-id", action="store", default="")
    parser.addoption("--aws-secret-access-key", action="store", default="")

@pytest.fixture(scope="session")
def aws_access_key_id(request):
    # Use the existing option from root conftest
    return request.config.getoption("--aws-access-key-id")

@pytest.fixture(scope="session")
def aws_secret_access_key(request):
    # Use the existing option from root conftest
    return request.config.getoption("--aws-secret-access-key")

@pytest.fixture(scope="session")
def models_s3_bucket_region(request):
    # Use the existing option from root conftest
    return request.config.getoption("--models-s3-bucket-region")

@pytest.fixture(scope="session")
def models_s3_bucket_endpoint(request):
    # Use the existing option from root conftest
    return request.config.getoption("--models-s3-bucket-endpoint")

@pytest.fixture(scope="session")
def s3_models_storage_uri(request):
    # Use the existing option from root conftest
    bucket_name = request.config.getoption("--models-s3-bucket-name")
    return f"s3://{bucket_name}/triton/model_repository/"




# @pytest.fixture(scope="session")
# def aws_access_key_id():
#     return os.environ.get("AWS_ACCESS_KEY_ID")

# @pytest.fixture(scope="session")
# def aws_secret_access_key():
#     return os.environ.get("AWS_SECRET_ACCESS_KEY")

# @pytest.fixture(scope="session")
# def models_s3_bucket_region():
#     return os.environ.get("MODEL_S3_BUCKET_REGION", "us-east-1")  

# @pytest.fixture(scope="session")
# def models_s3_bucket_endpoint():
#     return os.environ.get("MODEL_S3_BUCKET_ENDPOINT", "https://s3.us-east-1.amazonaws.com/")

# @pytest.fixture(scope="session")
# def s3_models_storage_uri():
#     bucket_name = os.environ["MODEL_S3_BUCKET_NAME"]  
#     return f"s3://{bucket_name}/triton/model_repository/"

@pytest.fixture(scope="class")
def triton_grpc_serving_runtime_template(admin_client: DynamicClient) -> Template:
    grpc_template_yaml = "triton_grpc_serving_template.yaml"
    with Template(
        client=admin_client,
        name="triton-grpc-template",
        namespace="default",
    ) as tp:
        yield tp

@pytest.fixture(scope="class")
def triton_rest_serving_runtime_template(admin_client: DynamicClient) -> Template:
    rest_template_yaml = "triton_onnx_rest_servingruntime.yaml"
    with Template(
        client=admin_client,
        name="triton-rest-template",
        namespace="default",
    ) as tp:
        yield tp

@pytest.fixture(scope="class")
def serving_runtime(
    request: FixtureRequest,
    admin_client: DynamicClient,
    model_namespace: Namespace,
    protocol: str,
    triton_runtime_image: str,
) -> Generator[ServingRuntime, None, None]:
    protocol = protocol.lower()
    template_name = TEMPLATE_MAP.get(protocol, RuntimeTemplates.TRITON_REST)
    with ServingRuntimeFromTemplate(
        client=admin_client,
        name="triton-runtime",
        namespace=model_namespace.name,
        template_name=template_name,
        deployment_type=request.param["deployment_type"],
        runtime_image=triton_runtime_image,
    ) as model_runtime:
        yield model_runtime

@pytest.fixture(scope="class")
def triton_inference_service(
    request: FixtureRequest,
    admin_client: DynamicClient,
    model_namespace: Namespace,
    serving_runtime: ServingRuntime,
    s3_models_storage_uri: str,
    model_service_account: ServiceAccount,
) -> Generator[InferenceService, Any, Any]:
    isvc_kwargs = {
        "client": admin_client,
        "name": request.param["name"],
        "namespace": model_namespace.name,
        "runtime": serving_runtime.name,
        "storage_uri": s3_models_storage_uri,
        "model_format": serving_runtime.instance.spec.supportedModelFormats[0].name,
        "model_service_account": model_service_account.name,
        "deployment_mode": request.param.get("deployment_mode", KServeDeploymentType.SERVERLESS),
    }

    gpu_count = request.param.get("gpu_count")
    timeout = request.param.get("timeout")
    resources: Any = copy.deepcopy(PREDICT_RESOURCES["resources"])

    if gpu_count:
        identifier = Labels.Nvidia.NVIDIA_COM_GPU
        resources["requests"][identifier] = gpu_count
        resources["limits"][identifier] = gpu_count
        isvc_kwargs["resources"] = resources

        if gpu_count > 1:
            isvc_kwargs["volumes"] = PREDICT_RESOURCES["volumes"]
            isvc_kwargs["volume_mounts"] = PREDICT_RESOURCES["volume_mounts"]

    if timeout:
        isvc_kwargs["timeout"] = timeout

    arguments = request.param.get("runtime_argument", [])
    arguments = [
        arg for arg in arguments
        if not (arg.startswith("--tensor-parallel-size") or arg.startswith("--quantization"))
    ]
    if gpu_count:
        arguments.append(f"--tensor-parallel-size={gpu_count}")
    if quantization := request.param.get("quantization"):
        validate_supported_quantization_schema(q_type=quantization)
        arguments.append(f"--quantization={quantization}")
    if arguments:
        isvc_kwargs["argument"] = arguments

    isvc_kwargs["min_replicas"] = request.param.get("min-replicas")

    with create_isvc(**isvc_kwargs) as isvc:
        yield isvc

@pytest.fixture(scope="class")
def model_service_account(admin_client: DynamicClient, kserve_endpoint_s3_secret: Secret) -> ServiceAccount:
    with ServiceAccount(
        client=admin_client,
        namespace=kserve_endpoint_s3_secret.namespace,
        name="models-bucket-sa",
        secrets=[{"name": kserve_endpoint_s3_secret.name}],
    ) as sa:
        yield sa

@pytest.fixture(scope="class")
def kserve_endpoint_s3_secret(
    admin_client: DynamicClient,
    model_namespace: Namespace,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    models_s3_bucket_region: str,
    models_s3_bucket_endpoint: str,
) -> Secret:
    with kserve_s3_endpoint_secret(
        admin_client=admin_client,
        name="models-bucket-secret",
        namespace=model_namespace.name,
        aws_access_key=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_s3_region=models_s3_bucket_region,
        aws_s3_endpoint=models_s3_bucket_endpoint,
    ) as secret:
        yield secret

@pytest.fixture
def response_snapshot(snapshot: Any) -> Any:
    return snapshot.use_extension(extension_class=JSONSnapshotExtension)

@pytest.fixture
def triton_pod_resource(admin_client: DynamicClient, triton_inference_service: InferenceService) -> Pod:
    return get_pods_by_isvc_label(client=admin_client, isvc=triton_inference_service)[0]

@pytest.fixture
def skip_if_serverless_deployemnt(triton_inference_service: InferenceService) -> None:
    skip_if_deployment_mode(
        isvc=triton_inference_service,
        deployment_type=KServeDeploymentType.SERVERLESS,
        deployment_message="Test is being skipped because model is being deployed in serverless mode",
    )

@pytest.fixture
def skip_if_raw_deployemnt(triton_inference_service: InferenceService) -> None:
    skip_if_deployment_mode(
        isvc=triton_inference_service,
        deployment_type=KServeDeploymentType.RAW_DEPLOYMENT,
        deployment_message="Test is being skipped because model is being deployed in raw mode",
    )