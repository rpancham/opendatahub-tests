from typing import Any
from ocp_resources.resource import Resource
from utilities.constants import ModelFormat


class ModelRegistryEndpoints:
    REGISTERED_MODELS: str = "/api/model_registry/v1alpha3/registered_models"


MR_OPERATOR_NAME: str = "model-registry-operator"
MODEL_NAME: str = "my-model"
MODEL_DICT: dict[str, Any] = {
    "model_name": MODEL_NAME,
    "model_uri": "https://storage-place.my-company.com",
    "model_version": "2.0.0",
    "model_description": "lorem ipsum",
    "model_format": ModelFormat.ONNX,
    "model_format_version": "1",
    "model_storage_key": "my-data-connection",
    "model_storage_path": "path/to/model",
    "model_metadata": {
        "int_key": 1,
        "bool_key": False,
        "float_key": 3.14,
        "str_key": "str_value",
    },
}
MR_INSTANCE_BASE_NAME: str = "model-registry"
MR_INSTANCE_NAME: str = f"{MR_INSTANCE_BASE_NAME}0"
SECURE_MR_NAME: str = "secure-db-mr"
OAUTH_PROXY_CONFIG_DICT: dict[str, Any] = {
    "port": 8443,
    "routePort": 443,
    "serviceRoute": "enabled",
}
DB_BASE_RESOURCES_NAME: str = "db-model-registry"
DB_RESOURCE_NAME: str = f"{DB_BASE_RESOURCES_NAME}0"
MR_DB_IMAGE_DIGEST: str = (
    "public.ecr.aws/docker/library/mysql@sha256:9de9d54fecee6253130e65154b930978b1fcc336bcc86dfd06e89b72a2588ebe"
)
MODEL_REGISTRY_DB_SECRET_STR_DATA: dict[str, str] = {
    "database-name": "model_registry",
    "database-password": "TheBlurstOfTimes",  # pragma: allowlist secret
    "database-user": "mlmduser",  # pragma: allowlist secret
}
MODEL_REGISTRY_DB_SECRET_ANNOTATIONS = {
    f"{Resource.ApiGroup.TEMPLATE_OPENSHIFT_IO}/expose-database_name": "'{.data[''database-name'']}'",
    f"{Resource.ApiGroup.TEMPLATE_OPENSHIFT_IO}/expose-password": "'{.data[''database-password'']}'",
    f"{Resource.ApiGroup.TEMPLATE_OPENSHIFT_IO}/expose-username": "'{.data[''database-user'']}'",
}

CA_CONFIGMAP_NAME = "odh-trusted-ca-bundle"
CA_MOUNT_PATH = "/etc/pki/ca-trust/extracted/pem"
CA_FILE_PATH = f"{CA_MOUNT_PATH}/ca-bundle.crt"
NUM_RESOURCES = {"num_resources": 3}
NUM_MR_INSTANCES: int = 2
MARIADB_MY_CNF = (
    "[mysqld]\nbind-address=0.0.0.0\ndefault_storage_engine=InnoDB\n"
    "binlog_format=row\ninnodb_autoinc_lock_mode=2\ninnodb_buffer_pool_size=1024M"
    "\nmax_allowed_packet=256M\n"
)
PORT_MAP = {
    "mariadb": 3306,
    "mysql": 3306,
}
MODEL_REGISTRY_POD_FILTER: str = "component=model-registry"
DEFAULT_MODEL_CATALOG: str = "model-catalog-sources"
