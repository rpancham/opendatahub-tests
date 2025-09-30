import base64
import os
import shutil
from ast import literal_eval
from typing import Any, Callable, Generator

import pytest
import shortuuid
import yaml
from _pytest._py.path import LocalPath
from _pytest.legacypath import TempdirFactory
from _pytest.tmpdir import TempPathFactory
from kubernetes.dynamic.exceptions import ResourceNotFoundError

from ocp_resources.cluster_service_version import ClusterServiceVersion
from ocp_resources.config_map import ConfigMap
from ocp_resources.deployment import Deployment
from ocp_resources.dsc_initialization import DSCInitialization
from ocp_resources.mariadb_operator import MariadbOperator
from ocp_resources.node import Node
from ocp_resources.pod import Pod
from ocp_resources.secret import Secret
from ocp_resources.service import Service
from ocp_resources.subscription import Subscription
from ocp_utilities.monitoring import Prometheus
from pyhelper_utils.shell import run_command
from pytest import FixtureRequest, Config
from kubernetes.dynamic import DynamicClient
from ocp_resources.data_science_cluster import DataScienceCluster
from ocp_resources.namespace import Namespace
from ocp_resources.resource import get_client
from pytest_testconfig import config as py_config
from simple_logger.logger import get_logger
import json

from ocp_utilities.operators import uninstall_operator, install_operator
from utilities.certificates_utils import create_ca_bundle_file
from utilities.data_science_cluster_utils import update_components_in_dsc
from utilities.exceptions import ClusterLoginError
from utilities.infra import (
    verify_cluster_sanity,
    create_ns,
    login_with_user_password,
    get_openshift_token,
    download_oc_console_cli,
)
from utilities.constants import (
    AcceleratorType,
    DscComponents,
    Labels,
    MinIo,
    Protocols,
    Timeout,
    OPENSHIFT_OPERATORS,
)
from utilities.infra import update_configmap_data
from utilities.logger import RedactedString
from utilities.mariadb_utils import wait_for_mariadb_operator_deployments
from utilities.minio import create_minio_data_connection_secret
from utilities.operator_utils import get_csv_related_images, get_cluster_service_version

LOGGER = get_logger(name=__name__)

pytest_plugins = ["tests.fixtures.inference", "tests.fixtures.guardrails", "tests.fixtures.trustyai"]


@pytest.fixture(scope="session")
def admin_client() -> DynamicClient:
    return get_client()


@pytest.fixture(scope="session", autouse=True)
def tests_tmp_dir(request: FixtureRequest, tmp_path_factory: TempPathFactory) -> Generator[None, None, None]:
    base_path = os.path.join(request.config.option.basetemp, "tests")
    tests_tmp_path = tmp_path_factory.mktemp(basename=base_path)
    py_config["tmp_base_dir"] = str(tests_tmp_path)

    yield

    shutil.rmtree(path=str(tests_tmp_path), ignore_errors=True)


@pytest.fixture(scope="session")
def current_client_token(admin_client: DynamicClient) -> str:
    return RedactedString(value=get_openshift_token())


@pytest.fixture(scope="session")
def teardown_resources(pytestconfig: pytest.Config) -> bool:
    delete_resources = True

    if pytestconfig.option.pre_upgrade:
        if delete_resources := pytestconfig.option.delete_pre_upgrade_resources:
            LOGGER.warning("Upgrade resources will be deleted")

    return delete_resources


@pytest.fixture(scope="class")
def model_namespace(
    request: FixtureRequest,
    pytestconfig: pytest.Config,
    admin_client: DynamicClient,
    teardown_resources: bool,
) -> Generator[Namespace, Any, Any]:
    if request.param.get("modelmesh-enabled"):
        request.getfixturevalue(argname="enabled_modelmesh_in_dsc")

    ns = Namespace(client=admin_client, name=request.param["name"])

    if pytestconfig.option.post_upgrade:
        yield ns
        ns.clean_up()
    else:
        with create_ns(
            admin_client=admin_client,
            pytest_request=request,
            teardown=teardown_resources,
        ) as ns:
            yield ns


@pytest.fixture(scope="session")
def aws_access_key_id(pytestconfig: Config) -> str:
    access_key = pytestconfig.option.aws_access_key_id
    if not access_key:
        raise ValueError(
            "AWS access key id is not set. "
            "Either pass with `--aws-access-key-id` or set `AWS_ACCESS_KEY_ID` environment variable"
        )
    return access_key


@pytest.fixture(scope="session")
def aws_secret_access_key(pytestconfig: Config) -> str:
    secret_access_key = pytestconfig.option.aws_secret_access_key
    if not secret_access_key:
        raise ValueError(
            "AWS secret access key is not set. "
            "Either pass with `--aws-secret-access-key` or set `AWS_SECRET_ACCESS_KEY` environment variable"
        )
    return secret_access_key


@pytest.fixture(scope="session")
def registry_pull_secret(pytestconfig: Config) -> str:
    registry_pull_secret = pytestconfig.option.registry_pull_secret
    if not registry_pull_secret:
        raise ValueError(
            "Registry pull secret is not set. "
            "Either pass with `--registry_pull_secret` or set `OCI_REGISTRY_PULL_SECRET` environment variable"
        )
    return registry_pull_secret


@pytest.fixture(scope="session")
def registry_host(pytestconfig: pytest.Config) -> str | None:
    registry_host = pytestconfig.option.registry_host
    if not registry_host:
        raise ValueError(
            "Registry host for OCI images is not set. "
            "Either pass with `--registry_host` or set `REGISTRY_HOST` environment variable"
        )
    return registry_host


@pytest.fixture(scope="session")
def valid_aws_config(aws_access_key_id: str, aws_secret_access_key: str) -> tuple[str, str]:
    return aws_access_key_id, aws_secret_access_key


@pytest.fixture(scope="session")
def ci_s3_bucket_name(pytestconfig: Config) -> str:
    bucket_name = pytestconfig.option.ci_s3_bucket_name
    if not bucket_name:
        raise ValueError(
            "CI S3 bucket name is not set. "
            "Either pass with `--ci-s3-bucket-name` or set `CI_S3_BUCKET_NAME` environment variable"
        )
    return bucket_name


@pytest.fixture(scope="session")
def ci_s3_bucket_region(pytestconfig: pytest.Config) -> str:
    ci_bucket_region = pytestconfig.option.ci_s3_bucket_region
    if not ci_bucket_region:
        raise ValueError(
            "Region for the ci s3 bucket is not defined."
            "Either pass with `--ci-s3-bucket-region` or set `CI_S3_BUCKET_REGION` environment variable"
        )
    return ci_bucket_region


@pytest.fixture(scope="session")
def ci_s3_bucket_endpoint(pytestconfig: pytest.Config) -> str:
    ci_bucket_endpoint = pytestconfig.option.ci_s3_bucket_endpoint
    if not ci_bucket_endpoint:
        raise ValueError(
            "Endpoint for the ci s3 bucket is not defined."
            "Either pass with `--ci-s3-bucket-endpoint` or set `CI_S3_BUCKET_ENDPOINT` environment variable"
        )
    return ci_bucket_endpoint


@pytest.fixture(scope="session")
def serving_argument(pytestconfig: pytest.Config, modelcar_yaml_config: dict[str, Any] | None) -> tuple[list[str], int]:
    if modelcar_yaml_config:
        val = modelcar_yaml_config.get("serving_arguments", {})
        if isinstance(val, dict):
            args = val.get("args", [])
            gpu_count = val.get("gpu_count", 1)
        return args, gpu_count

    raw_arg = pytestconfig.option.serving_argument
    try:
        return json.loads(raw_arg)
    except json.JSONDecodeError:
        raise ValueError(
            "Serving arguments should be a valid JSON list. "
            "Either pass with `--serving-argument` or set it correctly in modelcar.yaml"
        )


@pytest.fixture(scope="session")
def modelcar_yaml_config(pytestconfig: pytest.Config) -> dict[str, Any] | None:
    """
    Fixture to get the path to the modelcar.yaml file.
    """
    config_path = pytestconfig.option.model_car_yaml_path
    if not config_path:
        return None
    with open(config_path, "r") as file:
        try:
            modelcar_yaml = yaml.safe_load(file)
            if not isinstance(modelcar_yaml, dict):
                raise ValueError("modelcar.yaml should contain a dictionary.")
            return modelcar_yaml
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing modelcar.yaml: {e}") from e


@pytest.fixture(scope="session")
def models_s3_bucket_name(pytestconfig: pytest.Config) -> str:
    models_bucket = pytestconfig.option.models_s3_bucket_name
    if not models_bucket:
        raise ValueError(
            "Bucket name for the models bucket is not defined."
            "Either pass with `--models-s3-bucket-name` or set `MODELS_S3_BUCKET_NAME` environment variable"
        )
    return models_bucket


@pytest.fixture(scope="session")
def models_s3_bucket_region(pytestconfig: pytest.Config) -> str:
    models_bucket_region = pytestconfig.option.models_s3_bucket_region
    if not models_bucket_region:
        raise ValueError(
            "region for the models bucket is not defined."
            "Either pass with `--models-s3-bucket-region` or set `MODELS_S3_BUCKET_REGION` environment variable"
        )
    return models_bucket_region


@pytest.fixture(scope="session")
def models_s3_bucket_endpoint(pytestconfig: pytest.Config) -> str:
    models_bucket_endpoint = pytestconfig.option.models_s3_bucket_endpoint
    if not models_bucket_endpoint:
        raise ValueError(
            "endpoint for the models bucket is not defined."
            "Either pass with `--models-s3-bucket-endpoint` or set `MODELS_S3_BUCKET_ENDPOINT` environment variable"
        )
    return models_bucket_endpoint


@pytest.fixture(scope="session")
def supported_accelerator_type(pytestconfig: pytest.Config) -> str | None:
    accelerator_type = pytestconfig.option.supported_accelerator_type
    if not accelerator_type:
        return None
    if accelerator_type.lower() not in AcceleratorType.SUPPORTED_LISTS:
        raise ValueError(
            "accelerator type is not defined."
            "Either pass with `--supported-accelerator-type` or set `SUPPORTED_ACCLERATOR_TYPE` environment variable"
        )
    return accelerator_type


@pytest.fixture(scope="session")
def vllm_runtime_image(pytestconfig: pytest.Config) -> str | None:
    runtime_image = pytestconfig.option.vllm_runtime_image
    if not runtime_image:
        return None
    return runtime_image


@pytest.fixture(scope="session")
def mlserver_runtime_image(pytestconfig: pytest.Config) -> str | None:
    runtime_image = pytestconfig.option.mlserver_runtime_image
    if not runtime_image:
        return None
    return runtime_image


@pytest.fixture(scope="session")
def triton_runtime_image(pytestconfig: pytest.Config) -> str | None:
    runtime_image = pytestconfig.option.triton_runtime_image
    if not runtime_image:
        return None
    return runtime_image


@pytest.fixture(scope="session")
def use_unprivileged_client(pytestconfig: pytest.Config) -> bool:
    _use_unprivileged_client = py_config.get("use_unprivileged_client")

    if isinstance(_use_unprivileged_client, bool):
        return _use_unprivileged_client

    elif isinstance(_use_unprivileged_client, str):
        return literal_eval(_use_unprivileged_client)

    else:
        raise ValueError(
            "use_unprivileged_client is not defined.\n"
            "Either pass with `--use-unprivileged-client` or "
            "set in `use_unprivileged_client` in `tests/global_config.py`"
        )


@pytest.fixture(scope="session")
def non_admin_user_password(admin_client: DynamicClient, use_unprivileged_client: bool) -> tuple[str, str] | None:
    def _decode_split_data(_data: str) -> list[str]:
        return base64.b64decode(_data).decode().split(",")

    if not use_unprivileged_client:
        return None

    if ldap_Secret := list(
        Secret.get(
            dyn_client=admin_client,
            name="openldap",
            namespace="openldap",
        )
    ):
        data = ldap_Secret[0].instance.data
        users = _decode_split_data(_data=data.users)
        passwords = _decode_split_data(_data=data.passwords)
        first_user_index = next(index for index, user in enumerate(users) if "user" in user)

        return users[first_user_index], passwords[first_user_index]

    LOGGER.error("ldap secret not found")
    return None


@pytest.fixture(scope="session")
def kubconfig_filepath() -> str:
    kubeconfig_path = os.path.join(os.path.expanduser("~"), ".kube/config")
    kubeconfig_path_from_env = os.getenv("KUBECONFIG", "")

    if os.path.isfile(kubeconfig_path_from_env):
        return kubeconfig_path_from_env

    return kubeconfig_path


@pytest.fixture(scope="session")
def unprivileged_client(
    admin_client: DynamicClient,
    use_unprivileged_client: bool,
    kubconfig_filepath: str,
    non_admin_user_password: tuple[str, str],
) -> Generator[DynamicClient, Any, Any]:
    """
    Provides none privileged API client. If non_admin_user_password is None, then it will raise.
    """
    if not use_unprivileged_client:
        LOGGER.warning("Unprivileged client is not enabled, using admin client")
        yield admin_client

    elif non_admin_user_password is None:
        raise ValueError("Unprivileged user not provisioned")

    else:
        current_user = run_command(command=["oc", "whoami"])[1].strip()
        non_admin_user_name = non_admin_user_password[0]

        if login_with_user_password(
            api_address=admin_client.configuration.host,
            user=non_admin_user_name,
            password=non_admin_user_password[1],
        ):
            with open(kubconfig_filepath) as fd:
                kubeconfig_content = yaml.safe_load(fd)

            unprivileged_context = kubeconfig_content["current-context"]

            unprivileged_client = get_client(config_file=kubconfig_filepath, context=unprivileged_context)

            # Get back to admin account
            login_with_user_password(
                api_address=admin_client.configuration.host,
                user=current_user.strip(),
            )
            yield unprivileged_client

        else:
            raise ClusterLoginError(user=non_admin_user_name)


@pytest.fixture(scope="session")
def dsci_resource(admin_client: DynamicClient) -> DSCInitialization:
    return DSCInitialization(client=admin_client, name=py_config["dsci_name"], ensure_exists=True)


@pytest.fixture(scope="session")
def dsc_resource(admin_client: DynamicClient) -> DataScienceCluster:
    return DataScienceCluster(client=admin_client, name=py_config["dsc_name"], ensure_exists=True)


@pytest.fixture(scope="package")
def enabled_modelmesh_in_dsc(
    dsc_resource: DataScienceCluster,
) -> Generator[DataScienceCluster, Any, Any]:
    with update_components_in_dsc(
        dsc=dsc_resource,
        components={DscComponents.MODELMESHSERVING: DscComponents.ManagementState.MANAGED},
    ) as dsc:
        yield dsc


@pytest.fixture(scope="package")
def enabled_kserve_in_dsc(
    dsc_resource: DataScienceCluster,
) -> Generator[DataScienceCluster, Any, Any]:
    with update_components_in_dsc(
        dsc=dsc_resource,
        components={DscComponents.KSERVE: DscComponents.ManagementState.MANAGED},
    ) as dsc:
        yield dsc


@pytest.fixture(scope="session")
def cluster_monitoring_config(
    admin_client: DynamicClient,
) -> Generator[ConfigMap, Any, Any]:
    data = {"config.yaml": yaml.dump({"enableUserWorkload": True})}

    with update_configmap_data(
        client=admin_client,
        name="cluster-monitoring-config",
        namespace="openshift-monitoring",
        data=data,
    ) as cm:
        yield cm


@pytest.fixture(scope="class")
def unprivileged_model_namespace(
    request: FixtureRequest, admin_client: DynamicClient, unprivileged_client: DynamicClient
) -> Generator[Namespace, Any, Any]:
    if request.param.get("modelmesh-enabled"):
        request.getfixturevalue(argname="enabled_modelmesh_in_dsc")

    with create_ns(admin_client=admin_client, unprivileged_client=unprivileged_client, pytest_request=request) as ns:
        yield ns


# MinIo
@pytest.fixture(scope="class")
def minio_namespace(admin_client: DynamicClient) -> Generator[Namespace, Any, Any]:
    with create_ns(
        name=f"{MinIo.Metadata.NAME}-{shortuuid.uuid().lower()}",
        admin_client=admin_client,
    ) as ns:
        yield ns


@pytest.fixture(scope="class")
def minio_pod(
    request: FixtureRequest,
    admin_client: DynamicClient,
    minio_namespace: Namespace,
) -> Generator[Pod, Any, Any]:
    pod_labels = {Labels.Openshift.APP: MinIo.Metadata.NAME}

    if labels := request.param.get("labels"):
        pod_labels.update(labels)

    with Pod(
        client=admin_client,
        name=MinIo.Metadata.NAME,
        namespace=minio_namespace.name,
        containers=[
            {
                "args": request.param.get("args"),
                "env": [
                    {
                        "name": MinIo.Credentials.ACCESS_KEY_NAME,
                        "value": MinIo.Credentials.ACCESS_KEY_VALUE,
                    },
                    {
                        "name": MinIo.Credentials.SECRET_KEY_NAME,
                        "value": MinIo.Credentials.SECRET_KEY_VALUE,
                    },
                ],
                "image": request.param.get("image"),
                "name": MinIo.Metadata.NAME,
                "securityContext": {
                    "allowPrivilegeEscalation": False,
                    "capabilities": {"drop": ["ALL"]},
                    "runAsNonRoot": True,
                    "seccompProfile": {"type": "RuntimeDefault"},
                },
            }
        ],
        label=pod_labels,
        annotations=request.param.get("annotations"),
    ) as minio_pod:
        minio_pod.wait_for_status(status=Pod.Status.RUNNING)
        yield minio_pod


@pytest.fixture(scope="class")
def minio_service(admin_client: DynamicClient, minio_namespace: Namespace) -> Generator[Service, Any, Any]:
    with Service(
        client=admin_client,
        name=MinIo.Metadata.NAME,
        namespace=minio_namespace.name,
        ports=[
            {
                "name": f"{MinIo.Metadata.NAME}-client-port",
                "port": MinIo.Metadata.DEFAULT_PORT,
                "protocol": Protocols.TCP,
                "targetPort": MinIo.Metadata.DEFAULT_PORT,
            }
        ],
        selector={
            Labels.Openshift.APP: MinIo.Metadata.NAME,
        },
        session_affinity="ClientIP",
    ) as minio_service:
        yield minio_service


@pytest.fixture(scope="class")
def minio_data_connection(
    request: FixtureRequest,
    admin_client: DynamicClient,
    model_namespace: Namespace,
    minio_service: Service,
) -> Generator[Secret, Any, Any]:
    with create_minio_data_connection_secret(
        minio_service=minio_service,
        model_namespace=model_namespace.name,
        aws_s3_bucket=request.param["bucket"],
        client=admin_client,
    ) as secret:
        yield secret


@pytest.fixture(scope="session")
def nodes(admin_client: DynamicClient) -> Generator[list[Node], Any, Any]:
    yield list(Node.get(dyn_client=admin_client))


@pytest.fixture(scope="session")
def junitxml_plugin(
    request: FixtureRequest, record_testsuite_property: Callable[[str, object], None]
) -> Callable[[str, object], None] | None:
    return record_testsuite_property if request.config.pluginmanager.has_plugin("junitxml") else None


@pytest.fixture(scope="session")
def cluster_sanity_scope_session(
    request: FixtureRequest,
    nodes: list[Node],
    dsci_resource: DSCInitialization,
    dsc_resource: DataScienceCluster,
    junitxml_plugin: Callable[[str, object], None],
) -> None:
    verify_cluster_sanity(
        request=request,
        nodes=nodes,
        dsc_resource=dsc_resource,
        dsci_resource=dsci_resource,
        junitxml_property=junitxml_plugin,
    )


@pytest.fixture(scope="session")
def prometheus(admin_client: DynamicClient) -> Prometheus:
    return Prometheus(
        client=admin_client,
        resource_name="thanos-querier",
        verify_ssl=create_ca_bundle_file(
            client=admin_client, ca_type="openshift"
        ),  # TODO: Verify SSL with appropriate certs
        bearer_token=get_openshift_token(),
    )


@pytest.fixture(scope="session")
def related_images_refs(admin_client: DynamicClient) -> set[str]:
    related_images = get_csv_related_images(admin_client=admin_client)
    related_images_refs = {img["image"] for img in related_images}
    return related_images_refs


@pytest.fixture(scope="session")
def os_path_environment() -> str:
    return os.environ["PATH"]


@pytest.fixture(scope="session")
def bin_directory(tmpdir_factory: TempdirFactory) -> LocalPath:
    return tmpdir_factory.mktemp(basename="bin")


@pytest.fixture(scope="session")
def bin_directory_to_os_path(os_path_environment: str, bin_directory: LocalPath, oc_binary_path: str) -> None:
    LOGGER.info(f"OC binary path: {oc_binary_path}")
    LOGGER.info(f"Adding {bin_directory} to $PATH")
    os.environ["PATH"] = f"{bin_directory}:{os_path_environment}"


@pytest.fixture(scope="session")
def oc_binary_path(bin_directory: LocalPath) -> str:
    installed_oc_binary_path = os.getenv("OC_BINARY_PATH")
    if installed_oc_binary_path:
        LOGGER.warning(f"Using previously installed: {installed_oc_binary_path}")
        return installed_oc_binary_path

    return download_oc_console_cli(tmpdir=bin_directory)


@pytest.fixture(scope="session", autouse=True)
@pytest.mark.early(order=0)
def autouse_fixtures(
    bin_directory_to_os_path: None,
    cluster_sanity_scope_session: None,
) -> None:
    """Fixture to control the order of execution of some of the fixtures"""
    return


@pytest.fixture(scope="session")
def installed_mariadb_operator(admin_client: DynamicClient) -> Generator[None, Any, Any]:
    operator_ns = Namespace(name="openshift-operators", ensure_exists=True)
    operator_name = "mariadb-operator"

    mariadb_operator_subscription = Subscription(client=admin_client, namespace=operator_ns.name, name=operator_name)

    if not mariadb_operator_subscription.exists:
        install_operator(
            admin_client=admin_client,
            target_namespaces=["openshift-operators"],
            name=operator_name,
            channel="alpha",
            source="community-operators",
            operator_namespace=operator_ns.name,
            timeout=Timeout.TIMEOUT_15MIN,
            install_plan_approval="Manual",
            starting_csv=f"{operator_name}.v25.8.1",
        )

        deployment = Deployment(
            client=admin_client,
            namespace=operator_ns.name,
            name=f"{operator_name}-helm-controller-manager",
            wait_for_resource=True,
        )
        deployment.wait_for_replicas()
    yield
    uninstall_operator(
        admin_client=admin_client, name=operator_name, operator_namespace=operator_ns.name, clean_up_namespace=False
    )


@pytest.fixture(scope="class")
def mariadb_operator_cr(
    admin_client: DynamicClient, installed_mariadb_operator: None
) -> Generator[MariadbOperator, Any, Any]:
    mariadb_csv: ClusterServiceVersion = get_cluster_service_version(
        client=admin_client, prefix="mariadb", namespace=OPENSHIFT_OPERATORS
    )
    alm_examples: list[dict[str, Any]] = mariadb_csv.get_alm_examples()
    mariadb_operator_cr_dict: dict[str, Any] = next(
        example for example in alm_examples if example["kind"] == "MariadbOperator"
    )
    if not mariadb_operator_cr_dict:
        raise ResourceNotFoundError(f"No MariadbOperator dict found in alm_examples for CSV {mariadb_csv.name}")

    mariadb_operator_cr_dict["metadata"]["namespace"] = OPENSHIFT_OPERATORS
    with MariadbOperator(kind_dict=mariadb_operator_cr_dict) as mariadb_operator_cr:
        mariadb_operator_cr.wait_for_condition(
            condition="Deployed", status=mariadb_operator_cr.Condition.Status.TRUE, timeout=Timeout.TIMEOUT_10MIN
        )
        wait_for_mariadb_operator_deployments(mariadb_operator=mariadb_operator_cr)
        yield mariadb_operator_cr


@pytest.fixture(scope="session")
def gpu_count_on_cluster(nodes: list[Any]) -> int:
    """Return total GPU count across all nodes in the cluster.

    Counts full-GPU extended resources only:
      - nvidia.com/gpu
      - amd.com/gpu
      - gpu.intel.com/*  (e.g., i915, xe)
    Note: MIG slice resources (nvidia.com/mig-*) are intentionally ignored.
    """
    total_gpus = 0
    allowed_exact = {"nvidia.com/gpu", "amd.com/gpu", "intel.com/gpu"}
    allowed_prefixes = ("gpu.intel.com/",)
    for node in nodes:
        allocatable = getattr(node.instance.status, "allocatable", {}) or {}
        for key, val in allocatable.items():
            if key in allowed_exact or any(key.startswith(p) for p in allowed_prefixes):
                try:
                    total_gpus += int(val)
                except (ValueError, TypeError):
                    LOGGER.debug(f"Skipping non-integer allocatable for {key} on {node.name}: {val!r}")
                    continue
    return total_gpus
