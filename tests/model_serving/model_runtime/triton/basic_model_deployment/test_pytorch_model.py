# # tests/model_serving/model_runtime/triton/basic_model_deployment/test_pytorch_model.py

# import json
# import logging
# import pytest
# import requests
# from typing import Dict, Any
# from time import sleep
# from simple_logger.logger import get_logger

# from tests.model_serving.model_runtime.triton.constant import TEMPLATE_MAP, PREDICT_RESOURCES
# from utilities.constants import KServeDeploymentType, Protocols

# LOGGER = get_logger(name=__name__)


# @pytest.mark.tier2
# @pytest.mark.parametrize("deprecated", [True], ids=["RHOAIENG-11561"])
# class TestPyTorchModelInference:
#     @pytest.fixture(scope="class")
#     def pytorch_model_data(self):
#         """Load PyTorch model test data"""
#         # These paths should be defined in your constants or fixtures
#         input_path = "tests/model_serving/model_runtime/triton/test_data/pytorch_input.json"
#         expected_path = "tests/model_serving/model_runtime/triton/test_data/pytorch_expected_output.json"
        
#         with open(input_path) as f:
#             input_data = json.load(f)
        
#         with open(expected_path) as f:
#             expected_output = json.load(f)
        
#         return {
#             "input": input_data,
#             "expected_output": expected_output
#         }

#     @pytest.fixture(scope="class")
#     def triton_inference_service_kwargs(self):
#         """Configuration for the PyTorch InferenceService"""
#         return {
#             "name": "pytorch-model",
#             "deployment_type": KServeDeploymentType.SERVERLESS,
#             "deployment_mode": KServeDeploymentType.SERVERLESS,
#             "gpu_count": 1,
#             "runtime_argument": ["--model-repository=/mnt/models"],
#             "min-replicas": 1
#         }

#     def test_pytorch_model_rest_inference(
#         self,
#         triton_inference_service,
#         pytorch_model_data,
#         response_snapshot,
#         request
#     ):
#         """
#         Test PyTorch model inference via Triton on KServe using REST API
#         """
#         LOGGER.info(f"Running test: {request.node.name}")
        
#         # 1. Verify inference service is ready
#         assert triton_inference_service.instance.is_ready(), "InferenceService is not ready"
        
#         # 2. Get inference URL
#         inference_url = self._get_inference_url(triton_inference_service)
#         LOGGER.info(f"Inference URL: {inference_url}")
        
#         # 3. Verify inference
#         self._verify_inference(
#             inference_url,
#             pytorch_model_data["input"],
#             pytorch_model_data["expected_output"],
#             response_snapshot
#         )

#     def _get_inference_url(self, inference_service) -> str:
#         """Construct the inference URL from the InferenceService status"""
#         if not inference_service.instance.status.get("url"):
#             pytest.fail("InferenceService does not have a URL in status")
        
#         # Use REST protocol endpoint
#         return f"{inference_service.instance.status['url']}/v2/models/pytorch-model/infer"

#     def _verify_inference(
#         self,
#         inference_url: str,
#         input_data: Dict,
#         expected_output: Dict,
#         snapshot,
#         max_retries: int = 5,
#         retry_delay: int = 5
#     ) -> None:
#         """
#         Verify model inference with retries
#         """
#         for attempt in range(max_retries):
#             try:
#                 response = requests.post(
#                     inference_url,
#                     json=input_data,
#                     headers={"Content-Type": "application/json"},
#                     timeout=30
#                 )
#                 response.raise_for_status()
                
#                 actual_output = response.json()
                
#                 # Verify against expected output
#                 assert actual_output == expected_output, \
#                     f"Inference output mismatch. Expected: {expected_output}, Actual: {actual_output}"
                
#                 # Verify against snapshot if needed
#                 snapshot.assert_match(actual_output)
                
#                 LOGGER.info("Inference verification successful")
#                 return
            
#             except (AssertionError, requests.RequestException) as e:
#                 if attempt == max_retries - 1:
#                     LOGGER.error(f"Final attempt failed: {e}")
#                     raise
#                 LOGGER.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
#                 sleep(retry_delay * (attempt + 1))

# # tests/model_serving/model_runtime/triton/basic_model_deployment/test_pytorch_model.py
# import json
# import logging
# import pytest
# import requests
# from typing import Dict, Any
# from time import sleep
# from simple_logger.logger import get_logger

# from tests.model_serving.model_runtime.triton.constant import TEMPLATE_MAP, PREDICT_RESOURCES
# from utilities.constants import KServeDeploymentType, Protocols

# LOGGER = get_logger(name=__name__)

# @pytest.mark.tier2
# # @pytest.mark.parametrize("deprecated", [True], ids=["RHOAIENG-11561"])
# class TestPyTorchModelInference:
#     @pytest.fixture(scope="class")
#     def pytorch_model_data(self):
#         """Load PyTorch model test data"""
#         input_path = "tests/model_serving/model_runtime/triton/basic_model_deployment/kserve-triton-resnet-rest-input.json"
#         expected_path = "tests/model_serving/model_runtime/triton/basic_model_deployment/kserve-triton-resnet-rest-output.json"
        
#         with open(input_path) as f:
#             input_data = json.load(f)
        
#         with open(expected_path) as f:
#             expected_output = json.load(f)
        
#         return {
#             "input": input_data,
#             "expected_output": expected_output
#         }

#     @pytest.fixture(scope="class")
#     def triton_inference_service_kwargs(self):
#         """Configuration for the PyTorch InferenceService"""
#         return {
#             "name": "pytorch-model",
#             "deployment_type": KServeDeploymentType.SERVERLESS,
#             "deployment_mode": KServeDeploymentType.SERVERLESS,
#             "gpu_count": 1,
#             "runtime_argument": ["--model-repository=/mnt/models"],
#             "min-replicas": 1
#         }

#     def test_pytorch_model_rest_inference(
#         self,
#         triton_inference_service,
#         pytorch_model_data,
#         response_snapshot,
#         request
#     ):
#         """
#         Test PyTorch model inference via Triton on KServe using REST API
#         """
#         LOGGER.info(f"Running test: {request.node.name}")
        
#         # 1. Verify inference service is ready
#         assert triton_inference_service.instance.is_ready(), "InferenceService is not ready"
        
#         # 2. Get inference URL
#         inference_url = self._get_inference_url(triton_inference_service)
#         LOGGER.info(f"Inference URL: {inference_url}")
        
#         # 3. Verify inference
#         self._verify_inference(
#             inference_url,
#             pytorch_model_data["input"],
#             pytorch_model_data["expected_output"],
#             response_snapshot
#         )

#     def _get_inference_url(self, inference_service) -> str:
#         """Construct the inference URL from the InferenceService status"""
#         if not inference_service.instance.status.get("url"):
#             pytest.fail("InferenceService does not have a URL in status")
        
#         # Use REST protocol endpoint
#         return f"{inference_service.instance.status['url']}/v2/models/pytorch-model/infer"

#     def _verify_inference(
#         self,
#         inference_url: str,
#         input_data: Dict,
#         expected_output: Dict,
#         snapshot,
#         max_retries: int = 5,
#         retry_delay: int = 5
#     ) -> None:
#         """
#         Verify model inference with retries
#         """
#         for attempt in range(max_retries):
#             try:
#                 response = requests.post(
#                     inference_url,
#                     json=input_data,
#                     headers={"Content-Type": "application/json"},
#                     timeout=30
#                 )
#                 response.raise_for_status()
                
#                 actual_output = response.json()
                
#                 # Verify against expected output
#                 assert actual_output == expected_output, \
#                     f"Inference output mismatch. Expected: {expected_output}, Actual: {actual_output}"
                
#                 # Verify against snapshot if needed
#                 snapshot.assert_match(actual_output)
                
#                 LOGGER.info("Inference verification successful")
#                 return
            
#             except (AssertionError, requests.RequestException) as e:
#                 if attempt == max_retries - 1:
#                     LOGGER.error(f"Final attempt failed: {e}")
#                     raise
#                 LOGGER.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
#                 sleep(retry_delay * (attempt + 1))



import json
import logging
import pytest
import requests
from typing import Dict, Any
from time import sleep
from simple_logger.logger import get_logger

from tests.model_serving.model_runtime.triton.constant import TEMPLATE_MAP, PREDICT_RESOURCES
from utilities.constants import KServeDeploymentType, Protocols

LOGGER = get_logger(name=__name__)

@pytest.mark.tier2
class TestPyTorchModelInference:  # Removed deprecated parameterization
    @pytest.fixture(scope="class")
    def pytorch_model_data(self):
        """Load PyTorch model test data"""
        input_path = "tests/model_serving/model_runtime/triton/basic_model_deployment/kserve-triton-resnet-rest-input.json"
        expected_path = "tests/model_serving/model_runtime/triton/basic_model_deployment/kserve-triton-resnet-rest-output.json"
        
        with open(input_path) as f:
            input_data = json.load(f)
        
        with open(expected_path) as f:
            expected_output = json.load(f)
        
        return {
            "input": input_data,
            "expected_output": expected_output
        }

    @pytest.fixture(scope="class")
    def triton_inference_service_kwargs(self):
        """Configuration for the PyTorch InferenceService"""
        return {
            "name": "pytorch-model",
            "deployment_type": KServeDeploymentType.SERVERLESS,
            "deployment_mode": KServeDeploymentType.SERVERLESS,
            "gpu_count": 1,
            "runtime_argument": ["--model-repository=/mnt/models"],
            "min-replicas": 1
        }

    def test_pytorch_model_rest_inference(
        self,
        triton_inference_service,
        pytorch_model_data,
        response_snapshot,
        request
    ):
        """
        Test PyTorch model inference via Triton on KServe using REST API
        """
        LOGGER.info(f"Running test: {request.node.name}")
        
        # 1. Verify inference service is ready
        assert triton_inference_service.instance.is_ready(), "InferenceService is not ready"
        
        # 2. Get inference URL
        inference_url = self._get_inference_url(triton_inference_service)
        LOGGER.info(f"Inference URL: {inference_url}")
        
        # 3. Verify inference
        self._verify_inference(
            inference_url,
            pytorch_model_data["input"],
            pytorch_model_data["expected_output"],
            response_snapshot
        )

    def _get_inference_url(self, inference_service) -> str:
        """Construct the inference URL from the InferenceService status"""
        if not inference_service.instance.status.get("url"):
            pytest.fail("InferenceService does not have a URL in status")
        
        # Use REST protocol endpoint
        return f"{inference_service.instance.status['url']}/v2/models/pytorch-model/infer"

    def _verify_inference(
        self,
        inference_url: str,
        input_data: Dict,
        expected_output: Dict,
        snapshot,
        max_retries: int = 5,
        retry_delay: int = 5
    ) -> None:
        """
        Verify model inference with retries
        """
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    inference_url,
                    json=input_data,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                response.raise_for_status()
                
                actual_output = response.json()
                
                # Verify against expected output
                assert actual_output == expected_output, \
                    f"Inference output mismatch. Expected: {expected_output}, Actual: {actual_output}"
                
                # Verify against snapshot if needed
                snapshot.assert_match(actual_output)
                
                LOGGER.info("Inference verification successful")
                return
            
            except (AssertionError, requests.RequestException) as e:
                if attempt == max_retries - 1:
                    LOGGER.error(f"Final attempt failed: {e}")
                    raise
                LOGGER.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
                sleep(retry_delay * (attempt + 1))