from typing import Generator, Any

import pytest
from _pytest.fixtures import FixtureRequest
from kubernetes.dynamic import DynamicClient
from ocp_resources.config_map import ConfigMap
from ocp_resources.deployment import Deployment
from ocp_resources.guardrails_orchestrator import GuardrailsOrchestrator
from ocp_resources.namespace import Namespace
from ocp_resources.pod import Pod
from ocp_resources.resource import ResourceEditor
from ocp_resources.route import Route

from utilities.constants import Labels, Annotations

GUARDRAILS_ORCHESTRATOR_NAME: str = "guardrails-orchestrator"


@pytest.fixture(scope="class")
def guardrails_orchestrator(
    request: FixtureRequest,
    admin_client: DynamicClient,
    model_namespace: Namespace,
) -> Generator[GuardrailsOrchestrator, Any, Any]:
    gorch_kwargs = {
        "client": admin_client,
        "name": GUARDRAILS_ORCHESTRATOR_NAME,
        "namespace": model_namespace.name,
        "log_level": "DEBUG",
        "replicas": 1,
        "wait_for_resource": True,
    }

    if request.param.get("auto_config"):
        gorch_kwargs["auto_config"] = request.param.get("auto_config")

    if request.param.get("orchestrator_config"):
        orchestrator_config = request.getfixturevalue(argname="orchestrator_config")
        gorch_kwargs["orchestrator_config"] = orchestrator_config.name

    if request.param.get("enable_guardrails_gateway"):
        gorch_kwargs["enable_guardrails_gateway"] = True

    if request.param.get("guardrails_gateway_config"):
        guardrails_gateway_config = request.getfixturevalue(argname="guardrails_gateway_config")
        gorch_kwargs["guardrails_gateway_config"] = guardrails_gateway_config.name

    if enable_built_in_detectors := request.param.get("enable_built_in_detectors"):
        gorch_kwargs["enable_built_in_detectors"] = enable_built_in_detectors

    with GuardrailsOrchestrator(**gorch_kwargs) as gorch:
        gorch_deployment = Deployment(name=gorch.name, namespace=gorch.namespace, wait_for_resource=True)
        gorch_deployment.wait_for_replicas()
        yield gorch


@pytest.fixture(scope="class")
def orchestrator_config(
    request: FixtureRequest, admin_client: DynamicClient, model_namespace: Namespace
) -> Generator[ConfigMap, Any, Any]:
    with ConfigMap(
        client=admin_client,
        name="fms-orchestr8-config-nlp",
        namespace=model_namespace.name,
        data=request.param["orchestrator_config_data"],
    ) as cm:
        yield cm


@pytest.fixture(scope="class")
def guardrails_gateway_config(
    request: FixtureRequest, admin_client: DynamicClient, model_namespace: Namespace
) -> Generator[ConfigMap, Any, Any]:
    with ConfigMap(
        client=admin_client,
        name="fms-orchestr8-config-gateway",
        namespace=model_namespace.name,
        label={Labels.Openshift.APP: "fmstack-nlp"},
        data=request.param["guardrails_gateway_config_data"],
    ) as cm:
        yield cm


@pytest.fixture(scope="class")
def guardrails_orchestrator_pod(
    admin_client: DynamicClient,
    model_namespace: Namespace,
    guardrails_orchestrator: GuardrailsOrchestrator,
) -> Pod:
    return list(
        Pod.get(
            namespace=model_namespace.name, label_selector=f"app.kubernetes.io/instance={GUARDRAILS_ORCHESTRATOR_NAME}"
        )
    )[0]


@pytest.fixture(scope="class")
def guardrails_orchestrator_route(
    admin_client: DynamicClient,
    model_namespace: Namespace,
    guardrails_orchestrator: GuardrailsOrchestrator,
) -> Generator[Route, Any, Any]:
    guardrails_orchestrator_route = Route(
        name=f"{guardrails_orchestrator.name}",
        namespace=guardrails_orchestrator.namespace,
        wait_for_resource=True,
        ensure_exists=True,
    )
    with ResourceEditor(
        patches={
            guardrails_orchestrator_route: {
                "metadata": {
                    "annotations": {Annotations.HaproxyRouterOpenshiftIo.TIMEOUT: "10m"},
                }
            }
        }
    ):
        yield guardrails_orchestrator_route


@pytest.fixture(scope="class")
def guardrails_orchestrator_url(
    guardrails_orchestrator_route: Route,
) -> str:
    return f"https://{guardrails_orchestrator_route.host}"


@pytest.fixture(scope="class")
def guardrails_orchestrator_health_route(
    admin_client: DynamicClient,
    model_namespace: Namespace,
    guardrails_orchestrator: GuardrailsOrchestrator,
) -> Generator[Route, Any, Any]:
    guardrails_orchestrator_health_route = Route(
        name=f"{guardrails_orchestrator.name}-health",
        namespace=guardrails_orchestrator.namespace,
        wait_for_resource=True,
        ensure_exists=True,
    )
    with ResourceEditor(
        patches={
            guardrails_orchestrator_health_route: {
                "metadata": {
                    "annotations": {Annotations.HaproxyRouterOpenshiftIo.TIMEOUT: "10m"},
                }
            }
        }
    ):
        yield guardrails_orchestrator_health_route


@pytest.fixture(scope="class")
def guardrails_orchestrator_gateway_route(
    admin_client: DynamicClient,
    model_namespace: Namespace,
    guardrails_orchestrator: GuardrailsOrchestrator,
) -> Generator[Route, Any, Any]:
    guardrails_orchestrator_gateway_route = Route(
        name=f"{guardrails_orchestrator.name}-gateway",
        namespace=guardrails_orchestrator.namespace,
        wait_for_resource=True,
        ensure_exists=True,
    )
    with ResourceEditor(
        patches={
            guardrails_orchestrator_gateway_route: {
                "metadata": {
                    "annotations": {Annotations.HaproxyRouterOpenshiftIo.TIMEOUT: "10m"},
                }
            }
        }
    ):
        yield guardrails_orchestrator_gateway_route
