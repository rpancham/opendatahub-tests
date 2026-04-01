# Triton Inference Server Tests

This directory contains comprehensive test suites for NVIDIA Triton Inference Server runtime validation across multiple model frameworks and protocols.

## Overview

Tests validate Triton's ability to serve models in various formats using both REST and gRPC protocols. Each model type test suite includes deployment, inference, and response validation.

## Supported Model Types

| Framework | Backend | Test Module | Status |
| --------- | ------- | ----------- | ------ |
| DALI | Custom | `test_dali_model.py` | ✅ GPU Required |
| FIL (Forest Inference Library) | FIL | `test_fil_model.py` | ✅ CPU |
| Keras | TensorFlow | `test_keras_model.py` | ✅ See TensorFlow Note |
| ONNX | ONNX Runtime | `test_onnx_model.py` | ✅ |
| Python | Python Backend | `test_python_model.py` | ✅ |
| PyTorch | LibTorch | `test_pytorch_model.py` | ✅ |
| TensorFlow | TensorFlow | `test_tensorflow_model.py` | ✅ See TensorFlow Note |

## Triton Version Compatibility

### Current Default Version

- **Image**: `nvcr.io/nvidia/tritonserver:25.02-py3`
- **Triton Server Version**: 2.50.0
- **Status**: Last stable release with TensorFlow backend included

### TensorFlow Backend Availability

⚠️ **IMPORTANT**: The TensorFlow backend was **deprecated in Triton 25.03** and **removed in Triton 26.x+**.

| Triton Version | TensorFlow Backend | Recommendation |
| -------------- | ------------------ | -------------- |
| ≤ 25.02 | ✅ Included | **Use for TensorFlow/Keras models** |
| 25.03+ | ⚠️ Deprecated | Build from source required |
| 26.x+ | ❌ Removed | Not supported by default |

### Using Triton 26.x with TensorFlow Models

If you need to test against Triton 26.x with TensorFlow models, you have three options:

1. **Build Custom Container** (Complex)

   ```bash
   # Build TensorFlow backend from source
   # See: https://github.com/triton-inference-server/tensorflow_backend
   git clone https://github.com/triton-inference-server/tensorflow_backend
   cd tensorflow_backend
   git checkout r26.02  # Match your Triton version
   # Follow build instructions in repository README
   ```

2. **Convert Models to ONNX** (Recommended for long-term)

   ```python
   # Convert TensorFlow model to ONNX
   import tf2onnx
   # ... conversion code
   ```

   - ONNX backend fully supported in all Triton versions
   - Often provides better performance
   - Requires model revalidation

3. **Stay on Triton 25.02** (Current approach)
   - Default in `constant.py`
   - All backends supported
   - Proven stable

### Backend Support by Version

| Backend | Triton 25.02 | Triton 26.02 |
| ------- | ------------ | ------------ |
| ONNX Runtime | ✅ | ✅ |
| PyTorch (LibTorch) | ✅ | ✅ |
| Python | ✅ | ✅ |
| FIL | ✅ | ✅ |
| DALI | ✅ | ✅ |
| **TensorFlow** | ✅ | ❌ |

## Test Execution

### Running All Triton Tests

```bash
pytest tests/model_serving/model_runtime/triton/basic_model_deployment/ -v
```

### Running Specific Model Type

```bash
# PyTorch models
pytest tests/model_serving/model_runtime/triton/basic_model_deployment/test_pytorch_model.py -v

# TensorFlow models
pytest tests/model_serving/model_runtime/triton/basic_model_deployment/test_tensorflow_model.py -v
```

### Testing with Different Triton Version

```bash
# Override default Triton image (use with caution for 26.x)
pytest tests/model_serving/model_runtime/triton/basic_model_deployment/ \
  --triton-runtime-image=nvcr.io/nvidia/tritonserver:25.01-py3 -v
```

⚠️ **Warning**: Using `--triton-runtime-image` with version 26.x will cause TensorFlow and Keras tests to fail.

## Configuration

### Default Image

File: `tests/model_serving/model_runtime/triton/constant.py`

```python
TRITON_IMAGE: str = "nvcr.io/nvidia/tritonserver:25.02-py3"
```

### Runtime Template

Tests create temporary ServingRuntime templates with:

- Model store: `/mnt/models`
- REST port: 8080
- gRPC port: 9000
- Resource limits: 1 CPU, 2Gi memory

### Supported Protocols

- **REST**: HTTP/1.1 on port 8080
- **gRPC**: HTTP/2 on port 9000

## Requirements

### Infrastructure

- Kubernetes/OpenShift cluster
- GPU nodes (for DALI models)
- S3-compatible storage for model artifacts

### Permissions

- Namespace creation
- ServingRuntime template creation
- InferenceService deployment
- Secret management (S3 credentials)

## Test Structure

Each model type test includes:

1. **Fixtures** (`conftest.py`)
   - ServingRuntime template creation
   - InferenceService deployment
   - Model service account setup

2. **Test Cases**
   - REST protocol inference
   - gRPC protocol inference
   - Response snapshot validation

3. **Input Data**
   - JSON input files for each protocol
   - Located in `basic_model_deployment/*.json`

## Troubleshooting

### TensorFlow Backend Missing Error

```text
E0326 10:10:41.293702 1 model_lifecycle.cc:654] "failed to load 'model_name' version 1:
Invalid argument: unable to find backend library for backend 'tensorflow',
try specifying runtime on the model configuration."
```

**Solution**: You are using Triton 26.x which doesn't include TensorFlow backend. Either:

- Use Triton 25.02 or earlier (default)
- Build custom container with TensorFlow backend
- Convert models to ONNX format

### Model Loading Fails

- Check model format matches backend
- Verify S3 storage is accessible
- Confirm model repository structure is correct
- Review pod logs: `kubectl logs <pod-name>`

### GPU Not Available (DALI tests)

- Ensure cluster has GPU nodes
- Check GPU resource requests in pod spec
- Verify NVIDIA device plugin is installed

## References

- [NVIDIA Triton Documentation](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/)
- [Triton Release Notes](https://docs.nvidia.com/deeplearning/triton-inference-server/release-notes/)
- [TensorFlow Backend Repository](https://github.com/triton-inference-server/tensorflow_backend)
- [Triton Container on NGC](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver)

## Maintenance Notes

**Last Updated**: 2026-03-27
**Default Triton Version**: 25.02
**Reason**: Last release with TensorFlow backend support

When updating the default Triton version:

1. Review [release notes](https://docs.nvidia.com/deeplearning/triton-inference-server/release-notes/) for breaking changes
2. Check backend availability (especially TensorFlow)
3. Run full test suite before merging
4. Update this README with any compatibility changes
