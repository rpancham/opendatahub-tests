from typing import Any, Generator
import os
from kubernetes.dynamic import DynamicClient
import pytest
import copy

from tests.model_registry.rest_api.constants import MODEL_REGISTRY_BASE_URI, MODEL_REGISTER_DATA
from tests.model_registry.rest_api.utils import (
    register_model_rest_api,
    execute_model_registry_patch_command,
    get_mr_deployment,
)
from utilities.general import generate_random_name
from ocp_resources.deployment import Deployment
from tests.model_registry.utils import (
    get_model_registry_deployment_template_dict,
    apply_mysql_args_and_volume_mounts,
    add_mysql_certs_volumes_to_deployment,
    wait_for_pods_running,
    get_mr_standard_labels,
    get_mysql_config,
)

from tests.model_registry.constants import (
    DB_RESOURCE_NAME,
    CA_MOUNT_PATH,
    CA_FILE_PATH,
    CA_CONFIGMAP_NAME,
    OAUTH_PROXY_CONFIG_DICT,
    SECURE_MR_NAME,
)
from ocp_resources.resource import ResourceEditor
from ocp_resources.secret import Secret
from ocp_resources.config_map import ConfigMap
from simple_logger.logger import get_logger
from ocp_resources.model_registry_modelregistry_opendatahub_io import ModelRegistry
from pytest_testconfig import config as py_config
from utilities.exceptions import MissingParameter
import tempfile
from tests.model_registry.rest_api.utils import generate_ca_and_server_cert
from utilities.certificates_utils import create_k8s_secret, create_ca_bundle_with_router_cert

LOGGER = get_logger(name=__name__)


@pytest.fixture(scope="class")
def registered_model_rest_api(
    request: pytest.FixtureRequest,
    model_registry_rest_url: list[str],
    model_registry_rest_headers: dict[str, str],
) -> dict[str, Any]:
    return register_model_rest_api(
        model_registry_rest_url=model_registry_rest_url[0],
        model_registry_rest_headers=model_registry_rest_headers,
        data_dict=request.param,
    )


@pytest.fixture()
def updated_model_registry_resource(
    request: pytest.FixtureRequest,
    model_registry_rest_url: list[str],
    model_registry_rest_headers: dict[str, str],
    registered_model_rest_api: dict[str, Any],
) -> dict[str, Any]:
    """
    Generic fixture to update any model registry resource via PATCH request.

    Expects request.param to contain:
        - resource_name: Key to identify the resource in registered_model_rest_api
        - api_name: API endpoint name for the resource type
        - data: JSON data to send in the PATCH request

    Returns:
       Dictionary containing the updated resource data
    """
    resource_name = request.param.get("resource_name")
    api_name = request.param.get("api_name")
    if not (api_name and resource_name):
        raise MissingParameter("resource_name and api_name are required parameters for this fixture.")
    resource_id = registered_model_rest_api[resource_name]["id"]
    assert resource_id, f"Resource id not found: {registered_model_rest_api[resource_name]}"
    return execute_model_registry_patch_command(
        url=f"{model_registry_rest_url[0]}{MODEL_REGISTRY_BASE_URI}{api_name}/{resource_id}",
        headers=model_registry_rest_headers,
        data_json=request.param["data"],
    )


@pytest.fixture(scope="class")
def patch_invalid_ca(
    admin_client: DynamicClient,
    model_registry_namespace: str,
    request: pytest.FixtureRequest,
) -> Generator[str, Any, Any]:
    """
    Patches the ConfigMap with an invalid CA certificate.
    """
    ca_configmap_name = request.param.get("ca_configmap_name", "odh-trusted-ca-bundle")
    ca_file_name = request.param.get("ca_file_name", "invalid-ca.crt")
    ca_file_path = f"{CA_MOUNT_PATH}/{ca_file_name}"
    LOGGER.info(f"Patching the {ca_configmap_name} ConfigMap with an invalid CA certificate: {ca_file_path}")
    ca_data = {ca_file_name: "-----BEGIN CERTIFICATE-----\nINVALIDCERTIFICATE\n-----END CERTIFICATE-----"}
    ca_configmap = ConfigMap(
        client=admin_client,
        name=ca_configmap_name,
        namespace=model_registry_namespace,
        ensure_exists=True,
    )
    patch = {
        "metadata": {
            "name": ca_configmap_name,
            "namespace": model_registry_namespace,
        },
        "data": ca_data,
    }
    with ResourceEditor(patches={ca_configmap: patch}):
        LOGGER.info(f"Patched the {ca_configmap_name} ConfigMap with an invalid CA certificate: {ca_file_path}")
        yield ca_file_path


@pytest.fixture(scope="class")
def mysql_template_with_ca(model_registry_metadata_db_resources: dict[Any, Any]) -> dict[str, Any]:
    """
    Patches the MySQL template with the CA file path and volume mount.
    """
    mysql_template = get_model_registry_deployment_template_dict(
        secret_name=model_registry_metadata_db_resources[Secret][0].name,
        resource_name=DB_RESOURCE_NAME,
        db_backend="mysql",
    )
    mysql_template["spec"]["containers"][0]["args"].append(f"--ssl-ca={CA_FILE_PATH}")
    mysql_template["spec"]["containers"][0]["volumeMounts"].append({
        "mountPath": CA_MOUNT_PATH,
        "name": CA_CONFIGMAP_NAME,
        "readOnly": True,
    })
    mysql_template["spec"]["volumes"].append({"name": CA_CONFIGMAP_NAME, "configMap": {"name": CA_CONFIGMAP_NAME}})
    return mysql_template


@pytest.fixture(scope="class")
def deploy_secure_mysql_and_mr(
    request: pytest.FixtureRequest,
    admin_client: DynamicClient,
    model_registry_namespace: str,
    mysql_template_with_ca: dict[str, Any],
    patch_mysql_deployment_with_ssl_ca: Deployment,
) -> Generator[ModelRegistry, None, None]:
    """
    Deploy a secure MySQL and Model Registry instance.
    """
    param = getattr(request, "param", {})
    mysql = get_mysql_config(base_name=DB_RESOURCE_NAME, namespace=model_registry_namespace, db_backend="mysql")
    if "sslRootCertificateConfigMap" in param:
        mysql["sslRootCertificateConfigMap"] = param["sslRootCertificateConfigMap"]
    with ModelRegistry(
        name=SECURE_MR_NAME,
        namespace=model_registry_namespace,
        label=get_mr_standard_labels(resource_name=SECURE_MR_NAME),
        grpc={},
        rest={},
        istio=None,
        oauth_proxy=OAUTH_PROXY_CONFIG_DICT,
        mysql=mysql,
        wait_for_resource=True,
    ) as mr:
        mr.wait_for_condition(condition="Available", status="True")
        mr.wait_for_condition(condition="OAuthProxyAvailable", status="True")
        wait_for_pods_running(
            admin_client=admin_client, namespace_name=model_registry_namespace, number_of_consecutive_checks=6
        )
        yield mr


@pytest.fixture()
def local_ca_bundle(request: pytest.FixtureRequest, admin_client: DynamicClient) -> Generator[str, Any, Any]:
    """
    Creates a local CA bundle file by fetching the CA bundle from a ConfigMap and appending the router CA from a Secret.
    Args:
        request: The pytest request object
        admin_client: The admin client to get the CA bundle from a ConfigMap and append the router CA from a Secret.
    Returns:
        Generator[str, Any, Any]: A generator that yields the CA bundle path.
    """
    ca_bundle_path = getattr(request, "param", {}).get("cert_name", "ca-bundle.crt")
    create_ca_bundle_with_router_cert(
        client=admin_client,
        namespace=py_config["model_registry_namespace"],
        ca_bundle_path=ca_bundle_path,
        cert_name=ca_bundle_path,
    )
    yield ca_bundle_path

    os.remove(ca_bundle_path)


@pytest.fixture(scope="class")
def ca_configmap_for_test(
    admin_client: DynamicClient,
    model_registry_namespace: str,
    mysql_ssl_artifact_paths: dict[str, Any],
) -> Generator[ConfigMap, None, None]:
    """
    Creates a test-specific ConfigMap for the CA bundle, using the generated CA cert.

    Args:
        admin_client: The admin client to create the ConfigMap
        model_registry_namespace: The namespace of the model registry
        mysql_ssl_artifact_paths: The artifacts and secrets for the MySQL SSL connection

    Returns:
        Generator[ConfigMap, None, None]: A generator that yields the ConfigMap instance.
    """
    with open(mysql_ssl_artifact_paths["ca_crt"], "r") as f:
        ca_content = f.read()
    if not ca_content:
        LOGGER.info("CA content is empty")
        raise Exception("CA content is empty")
    cm_name = "mysql-ca-configmap"
    with ConfigMap(
        client=admin_client,
        name=cm_name,
        namespace=model_registry_namespace,
        data={"ca-bundle.crt": ca_content},
    ) as cm:
        yield cm


@pytest.fixture(scope="class")
def patch_mysql_deployment_with_ssl_ca(
    request: pytest.FixtureRequest,
    admin_client: DynamicClient,
    model_registry_namespace: str,
    mysql_ssl_secrets: dict[str, Any],
) -> Generator[Deployment, Any, Any]:
    """
    Patch the MySQL deployment to use the test CA bundle (mysql-ca-configmap),
    and mount the server cert/key for SSL.
    """
    model_registry_db_deployments = get_mr_deployment(admin_client=admin_client, mr_namespace=model_registry_namespace)
    if request.param.get("ca_configmap_for_test"):
        LOGGER.info("Invoking ca_configmap_for_test fixture")
        request.getfixturevalue(argname="ca_configmap_for_test")
    CA_CONFIGMAP_NAME = request.param.get("ca_configmap_name", "mysql-ca-configmap")
    CA_MOUNT_PATH = request.param.get("ca_mount_path", "/etc/mysql/ssl")

    deployment = model_registry_db_deployments[0].instance.to_dict()
    spec = deployment["spec"]["template"]["spec"]
    my_sql_container = next(container for container in spec["containers"] if container["name"] == "mysql")
    assert my_sql_container is not None, "Mysql container not found"

    my_sql_container = apply_mysql_args_and_volume_mounts(
        my_sql_container=my_sql_container, ca_configmap_name=CA_CONFIGMAP_NAME, ca_mount_path=CA_MOUNT_PATH
    )
    volumes = add_mysql_certs_volumes_to_deployment(spec=spec, ca_configmap_name=CA_CONFIGMAP_NAME)

    patch = {"spec": {"template": {"spec": {"volumes": volumes, "containers": [my_sql_container]}}}}
    with ResourceEditor(patches={model_registry_db_deployments[0]: patch}):
        wait_for_pods_running(
            admin_client=admin_client, namespace_name=model_registry_namespace, number_of_consecutive_checks=3
        )
        model_registry_db_deployments[0].wait_for_condition(condition="Available", status="True")
        yield model_registry_db_deployments[0]


@pytest.fixture(scope="class")
def mysql_ssl_artifact_paths() -> Generator[dict[str, str], None, None]:
    """
    Generates MySQL SSL certificate and key files in a temporary directory
    and provides their paths.

    Args:
        admin_client: The admin client to create the ConfigMap
        model_registry_namespace: The namespace of the model registry
        mysql_ssl_artifacts_and_secrets: The artifacts and secrets for the MySQL SSL connection

    Returns:
        Generator[dict[str, str], None, None]: A generator that yields the CA certificate and key file paths.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield generate_ca_and_server_cert(tmp_dir=tmp_dir)


@pytest.fixture(scope="class")
def mysql_ssl_secrets(
    admin_client: DynamicClient,
    model_registry_namespace: str,
    mysql_ssl_artifact_paths: dict[str, str],
) -> Generator[dict[str, Secret], None, None]:
    """
    Creates Kubernetes secrets for MySQL SSL artifacts.

    Args:
        admin_client: The admin client to create the ConfigMap
        model_registry_namespace: The namespace of the model registry
        mysql_ssl_artifacts_and_secrets: The artifacts and secrets for the MySQL SSL connection

    Returns:
        Generator[dict[str, str], None, None]: A generator that yields the CA certificate and key file paths.
    """
    ca_secret = create_k8s_secret(
        client=admin_client,
        namespace=model_registry_namespace,
        name="mysql-ca",
        file_path=mysql_ssl_artifact_paths["ca_crt"],
        key_name="ca.crt",
    )
    server_cert_secret = create_k8s_secret(
        client=admin_client,
        namespace=model_registry_namespace,
        name="mysql-server-cert",
        file_path=mysql_ssl_artifact_paths["server_crt"],
        key_name="tls.crt",
    )
    server_key_secret = create_k8s_secret(
        client=admin_client,
        namespace=model_registry_namespace,
        name="mysql-server-key",
        file_path=mysql_ssl_artifact_paths["server_key"],
        key_name="tls.key",
    )

    yield {
        "ca_secret": ca_secret,
        "server_cert_secret": server_cert_secret,
        "server_key_secret": server_key_secret,
    }
    if ca_secret.exists:
        ca_secret.delete(wait=True)
    if server_cert_secret.exists:
        server_cert_secret.delete(wait=True)
    if server_key_secret.exists:
        server_key_secret.delete(wait=True)


@pytest.fixture(scope="function")
def model_data_for_test() -> Generator[dict[str, Any], None, None]:
    """
    Generates a model data for the test.

    Returns:
        dict[str, Any]: The model data for the test
    """
    model_name = generate_random_name(prefix="model-rest-api")
    model_data = copy.deepcopy(MODEL_REGISTER_DATA)
    model_data["register_model_data"]["name"] = model_name
    yield model_data
