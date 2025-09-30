import pytest
from utilities.constants import DscComponents

from ocp_resources.data_science_cluster import DataScienceCluster
from ocp_resources.namespace import Namespace

from simple_logger.logger import get_logger
from pytest_testconfig import config as py_config


LOGGER = get_logger(name=__name__)


@pytest.mark.cluster_health
class TestMrDefault:
    def test_mr_management_state(self, dsc_resource: DataScienceCluster):
        """Verify MODELREGISTRY managementState is MANAGED in DSC."""
        assert (
            dsc_resource.instance.spec.components[DscComponents.MODELREGISTRY].managementState
            == DscComponents.ManagementState.MANAGED
        )

    def test_mr_namespace_exists_and_active(self, dsc_resource: DataScienceCluster):
        """Verify MR namespace exists and is in Active state."""
        namespace = Namespace(
            name=dsc_resource.instance.spec.components[DscComponents.MODELREGISTRY].registriesNamespace,
            ensure_exists=True,
        )
        assert namespace.instance.status.phase == Namespace.Status.ACTIVE
        assert namespace.instance.metadata.name == py_config["model_registry_namespace"]

    def test_mr_condition_in_dsc(self, dsc_resource: DataScienceCluster):
        """Verify MR ready condition is True in DSC."""
        for condition in dsc_resource.instance.status.conditions:
            if condition.type == DscComponents.COMPONENT_MAPPING[DscComponents.MODELREGISTRY]:
                assert condition.status == "True"
                break
        else:
            pytest.fail("MR ready condition not found in DSC")
