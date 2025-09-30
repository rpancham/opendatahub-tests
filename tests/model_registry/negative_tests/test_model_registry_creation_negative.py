import pytest
from typing import Self
from simple_logger.logger import get_logger
from ocp_resources.data_science_cluster import DataScienceCluster
from ocp_resources.deployment import Deployment
from ocp_resources.model_registry_modelregistry_opendatahub_io import ModelRegistry
from pytest_testconfig import config as py_config
from ocp_resources.namespace import Namespace
from ocp_resources.secret import Secret
from utilities.constants import Annotations
from tests.model_registry.constants import (
    MR_OPERATOR_NAME,
    MR_INSTANCE_NAME,
    DB_RESOURCE_NAME,
    OAUTH_PROXY_CONFIG_DICT,
)
from kubernetes.dynamic.exceptions import ForbiddenError


LOGGER = get_logger(name=__name__)


@pytest.mark.usefixtures(
    "model_registry_namespace_for_negative_tests",
    "updated_dsc_component_state_scope_session",
    "model_registry_db_secret_negative_test",
    "model_registry_db_deployment_negative_test",
)
@pytest.mark.custom_namespace
class TestModelRegistryCreationNegative:
    @pytest.mark.sanity
    def test_registering_model_negative(
        self: Self,
        current_client_token: str,
        model_registry_namespace_for_negative_tests: Namespace,
        updated_dsc_component_state_scope_session: DataScienceCluster,
        model_registry_db_secret_negative_test: Secret,
        model_registry_db_deployment_negative_test: Deployment,
    ):
        my_sql_dict: dict[str, str] = {
            "host": f"{model_registry_db_deployment_negative_test.name}."
            f"{model_registry_db_deployment_negative_test.namespace}.svc.cluster.local",
            "database": model_registry_db_secret_negative_test.string_data["database-name"],
            "passwordSecret": {"key": "database-password", "name": DB_RESOURCE_NAME},
            "port": 3306,
            "skipDBCreation": False,
            "username": model_registry_db_secret_negative_test.string_data["database-user"],
        }
        with pytest.raises(
            ForbiddenError,  # UnprocessibleEntityError
            match=f"namespace must be {py_config['model_registry_namespace']}",
        ):
            with ModelRegistry(
                name=MR_INSTANCE_NAME,
                namespace=model_registry_namespace_for_negative_tests.name,
                label={
                    Annotations.KubernetesIo.NAME: MR_INSTANCE_NAME,
                    Annotations.KubernetesIo.INSTANCE: MR_INSTANCE_NAME,
                    Annotations.KubernetesIo.PART_OF: MR_OPERATOR_NAME,
                    Annotations.KubernetesIo.CREATED_BY: MR_OPERATOR_NAME,
                },
                grpc={},
                rest={},
                oauth_proxy=OAUTH_PROXY_CONFIG_DICT,
                mysql=my_sql_dict,
                wait_for_resource=True,
            ):
                return
