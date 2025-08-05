from typing import Any

from kubernetes.dynamic import DynamicClient
from kubernetes.dynamic.exceptions import ResourceNotFoundError
from ocp_resources.inference_service import InferenceService
from ocp_resources.utils.constants import DEFAULT_CLUSTER_RETRY_EXCEPTIONS
from simple_logger.logger import get_logger
from timeout_sampler import TimeoutSampler
from timeout_sampler import TimeoutExpiredError

from tests.model_serving.model_server.utils import verify_inference_response
from utilities.constants import Timeout
from utilities.exceptions import InferenceCanaryTrafficError
from utilities.infra import get_pods_by_isvc_label


LOGGER = get_logger(name=__name__)


def verify_no_inference_pods(
    client: DynamicClient, isvc: InferenceService, wait_timeout: int = Timeout.TIMEOUT_4MIN
) -> bool:
    """
    Verify that no inference pods are running for the given InferenceService.

    Args:
        client (DynamicClient): DynamicClient object
        isvc (InferenceService): InferenceService object
        wait_timeout (int): Timeout in seconds, default is 4 minutes

    Returns:
        bool: True if no pods are running, False otherwise
    Raises:
        TimeoutError: If pods exist after the timeout.

    """
    pods = []

    try:
        for pods in TimeoutSampler(
            wait_timeout=wait_timeout,
            sleep=5,
            exceptions_dict=DEFAULT_CLUSTER_RETRY_EXCEPTIONS,
            func=get_pods_by_isvc_label,
            client=client,
            isvc=isvc,
        ):
            if not pods:
                return True

    except TimeoutExpiredError as e:
        if isinstance(e.last_exp, ResourceNotFoundError):
            return True
        LOGGER.error(f"{[pod.name for pod in pods]} were not deleted")
        return False
    return True


def wait_for_canary_rollout(isvc: InferenceService, percentage: int, timeout: int = Timeout.TIMEOUT_5MIN) -> None:
    """
    Wait for inference service to be updated with canary rollout.

    Args:
        isvc (InferenceService): InferenceService object
        percentage (int): Percentage of canary rollout
        timeout (int): Timeout in seconds

    Raises:
        TimeoutExpired: If canary rollout is not updated

    """
    sample = None

    try:
        for sample in TimeoutSampler(
            wait_timeout=timeout,
            sleep=5,
            func=lambda: isvc.instance.status.components.predictor.get("traffic", []),
        ):
            if sample:
                for traffic_info in sample:
                    if traffic_info.get("latestRevision") and traffic_info.get("percent") == percentage:
                        return

    except TimeoutExpiredError:
        LOGGER.error(
            f"InferenceService {isvc.name} canary rollout is not updated to {percentage}. Traffic info:\n{sample}"
        )
        raise


def verify_canary_traffic(
    isvc: InferenceService,
    inference_config: dict[str, Any],
    inference_type: str,
    protocol: str,
    iterations: int,
    expected_percentage: int,
    model_name: str | None = None,
    tolerance: int = 0,
) -> None:
    """
    Verify canary traffic percentage against inference_config.

    Args:
        isvc (InferenceService): Inference service.
        inference_config (dict[str, Any]): Inference config.
        inference_type (str): Inference type.
        protocol (str): Protocol.
        model_name (str): Model name.
        iterations (int): Number of iterations.
        expected_percentage (int): Percentage of canary rollout.
        tolerance (int): Tolerance of traffic percentage distribution;
            difference between actual and expected percentage.

    Raises:
        InferenceCanaryTrafficError: If canary rollout is not updated

    """
    successful_inferences = 0

    for iteration in range(iterations):
        try:
            verify_inference_response(
                inference_service=isvc,
                inference_config=inference_config,
                inference_type=inference_type,
                protocol=protocol,
                model_name=model_name,
                use_default_query=True,
            )
            LOGGER.info(f"Successful inference. Iteration: {iteration + 1}")

            successful_inferences += 1

        except Exception as ex:
            LOGGER.warning(f"Inference failed. Error: {ex}. Previous model was used.")

    LOGGER.info(f"Number of inference requests to the new model: {successful_inferences}")
    successful_inferences_percentage = successful_inferences / iterations * 100

    diff_percentage = abs(expected_percentage - successful_inferences_percentage)

    if successful_inferences == 0 or diff_percentage > tolerance:
        raise InferenceCanaryTrafficError(
            f"Percentage of inference requests {successful_inferences_percentage} "
            f"to the new model does not match the expected percentage {expected_percentage}. "
        )
