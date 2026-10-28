"""Alert firing validation on a dedicated MaaS test cluster."""

import os
from collections.abc import Generator
from time import monotonic
from urllib.parse import urlsplit

import portforward
import pytest
import requests
import structlog
from kubernetes.dynamic import DynamicClient
from ocp_resources.deployment import Deployment
from ocp_resources.prometheus_rule import PrometheusRule
from ocp_resources.service import Service
from timeout_sampler import TimeoutSampler

from tests.ai_gateway.models_as_a_service.observability.authorino_alerts import (
    AuthorinoMetricsClient,
    query_alert_metrics,
)
from tests.ai_gateway.models_as_a_service.observability.utils import resolve_maas_monitoring_namespace
from utilities.certificates_utils import create_ca_bundle_file

LOGGER = structlog.get_logger(name=__name__)
ALERT_NAME = "MaaSAuthorinoAuthenticationHighFailureRate"
RULE_NAME = "authorino-maas-authentication-alerts"
POLL_SECONDS = 15
FIRING_TIMEOUT_SECONDS = 720
RECOVERY_TIMEOUT_SECONDS = 420


@pytest.fixture
def authorino_product_prometheus(
    admin_client: DynamicClient, kubconfig_filepath: str
) -> Generator[AuthorinoMetricsClient]:
    """Connect to product Thanos without filtering out namespace-less aggregated alerts."""
    namespace = resolve_maas_monitoring_namespace(admin_client=admin_client)
    assert namespace, "DSCI monitoring namespace is not configured"
    service = Service(
        client=admin_client,
        name="thanos-querier-data-science-thanos-querier",
        namespace=namespace,
    )
    assert service.exists, "DSCI-managed Thanos service is missing; enable the product monitoring stack"
    with portforward.forward(
        namespace=namespace,
        pod_or_service=service.name,
        from_port=0,
        to_port=10902,
        config_path=kubconfig_filepath,
        bind_ip="127.0.0.1",
        waiting=2,
    ) as forwarder:
        yield AuthorinoMetricsClient(
            api_url=f"http://127.0.0.1:{forwarder.from_port}",
            verify_ssl=create_ca_bundle_file(client=admin_client),
            monitoring_namespace=namespace,
        )


@pytest.mark.tier3
@pytest.mark.metrics
@pytest.mark.slow
def test_authorino_authentication_alert_fires(
    admin_client: DynamicClient,
    authorino_product_prometheus: AuthorinoMetricsClient,
) -> None:
    """Given an inactive shipped alert and a protected model in a test namespace,
    when sustained unauthenticated requests exceed its threshold,
    then the alert transitions through pending to firing and clears after traffic stops.
    """
    prometheus = authorino_product_prometheus
    target_url = os.environ.get("MAAS_AUTHORINO_ALERT_MODEL_URL", "")
    target = urlsplit(url=target_url)
    assert target.scheme == "https" and target.hostname, "Set MAAS_AUTHORINO_ALERT_MODEL_URL to a test model HTTPS URL"
    assert not (target.username or target.password or target.query or target.fragment), "Use a URL without credentials"
    rule_resource = PrometheusRule(
        client=admin_client,
        name=RULE_NAME,
        namespace=prometheus.monitoring_namespace,
        api_group="monitoring.rhobs",
    )
    assert rule_resource.exists, (
        "Authorino authentication rule is missing from DSCI monitoring (monitoring.rhobs); "
        "install the product-compatible rule before running this test"
    )
    alert_rules = [
        rule
        for group in rule_resource.instance.to_dict()["spec"]["groups"]
        for rule in group["rules"]
        if rule.get("alert") == ALERT_NAME
    ]
    assert len(alert_rules) == 1, "Shipped authentication failure alert is missing or duplicated"
    assert alert_rules[0].get("for") == "5m", "Review test timing if the shipped hold duration changes"
    assert "auth_server_authconfig_response_status_total" in alert_rules[0]["expr"], (
        "Authorino rule must use the OTEL-normalized authentication counter"
    )
    namespaces = [
        namespace
        for namespace in ("kuadrant-system", "rh-connectivity-link")
        if Deployment(client=admin_client, name="authorino", namespace=namespace).exists
    ]
    assert len(namespaces) == 1, "Expected one Authorino deployment in a supported policy-engine namespace"
    namespace = namespaces[0]
    alert_query = f'ALERTS{{alertname="{ALERT_NAME}"}}'
    target_up_query = f'min(up{{namespace="{namespace}",exported_service="authorino-controller-metrics"}})'
    target_up = query_alert_metrics(prometheus=prometheus, query=target_up_query)
    assert target_up and target_up[0]["value"][1] == "1", "Authorino scrape target is not healthy"
    source_query = f'auth_server_authconfig_response_status_total{{namespace="{namespace}"}}'
    failures_selector = (
        f'auth_server_authconfig_response_status_total{{namespace="{namespace}",status="UNAUTHENTICATED"}}'
    )
    failures_query = f"sum({failures_selector})"
    assert query_alert_metrics(prometheus=prometheus, query=source_query), (
        "Authorino authentication metrics are missing"
    )
    assert not query_alert_metrics(prometheus=prometheus, query=alert_query), "Alert is already pending or firing"
    baseline = query_alert_metrics(prometheus=prometheus, query=failures_query)
    failures_before = sum(float(sample["value"][1]) for sample in baseline)
    pending_seen = False
    firing_seen = False
    traffic_started = False
    request_count = 0
    started = monotonic()
    next_poll = started
    try:
        with requests.Session() as session:
            session.trust_env = False
            session.verify = prometheus.verify_ssl
            # No credentials: reject at gateway authentication before model inference.
            traffic_started = True
            for response in TimeoutSampler(
                wait_timeout=FIRING_TIMEOUT_SECONDS,
                sleep=2,
                func=session.post,
                exceptions_dict={requests.exceptions.ConnectionError: [], requests.exceptions.Timeout: []},
                url=target_url,
                json={"messages": [{"role": "user", "content": "alert test"}], "max_tokens": 1},
                timeout=10,
                allow_redirects=False,
            ):
                assert response.status_code == 401, (
                    f"Expected authentication rejection, got HTTP {response.status_code}"
                )
                request_count += 1
                if monotonic() >= next_poll:
                    try:
                        samples = query_alert_metrics(prometheus=prometheus, query=alert_query)
                    except requests.exceptions.ConnectionError, requests.exceptions.Timeout:
                        # Retry on the next iteration within the existing firing deadline.
                        continue
                    states = {sample["metric"]["alertstate"] for sample in samples}
                    pending_seen |= "pending" in states
                    LOGGER.info(
                        "Authorino alert observation",
                        states=sorted(states),
                        requests=request_count,
                        elapsed_seconds=round(monotonic() - started),
                    )
                    if "firing" in states:
                        firing_seen = True
                        assert monotonic() - started >= 300, "Alert fired before its five-minute hold duration"
                        break
                    next_poll = monotonic() + POLL_SECONDS
        assert pending_seen, "Never observed the shipped alert pending"
        assert firing_seen, "Alert did not fire within the hold window plus evaluation/scrape allowance"
        failures_after = query_alert_metrics(prometheus=prometheus, query=failures_query)
        assert sum(float(sample["value"][1]) for sample in failures_after) > failures_before, (
            "HTTP rejections did not increase Authorino UNAUTHENTICATED metrics"
        )
    finally:
        # No worker remains running on assertion failure; allow the five-minute rate window to drain.
        if traffic_started:
            for failure_rate in TimeoutSampler(
                wait_timeout=RECOVERY_TIMEOUT_SECONDS,
                sleep=POLL_SECONDS,
                func=query_alert_metrics,
                exceptions_dict={requests.exceptions.ConnectionError: [], requests.exceptions.Timeout: []},
                prometheus=prometheus,
                query=f"sum(rate({failures_selector}[5m]))",
            ):
                try:
                    alerts = query_alert_metrics(prometheus=prometheus, query=alert_query)
                    target_up = query_alert_metrics(prometheus=prometheus, query=target_up_query)
                except requests.exceptions.ConnectionError, requests.exceptions.Timeout:
                    # The sampler also bounds retries for queries made after it yields.
                    continue
                assert target_up and target_up[0]["value"][1] == "1", "Authorino scrape target failed during recovery"
                if not alerts and all(float(sample["value"][1]) <= 0 for sample in failure_rate):
                    LOGGER.info("Authorino failure traffic stopped and alert cleared")
                    break
