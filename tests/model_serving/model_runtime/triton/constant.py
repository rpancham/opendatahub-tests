from typing import Union

class Protocols:
    REST = "rest"
    GRPC = "grpc"

# Define template files
TEMPLATE_FILE: dict[str, str] = {
    Protocols.REST: "triton_onnx_rest_servingruntime.yaml",
    Protocols.GRPC: "triton_grpc_serving_template.yaml",
}

# Template mapping
TEMPLATE_MAP: dict[str, str] = {
    Protocols.REST: "triton-rest",
    Protocols.GRPC: "triton-grpc",
}

# Resource definitions
PREDICT_RESOURCES: dict[str, Union[list[dict[str, Union[str, dict[str, str]]]], dict[str, dict[str, str]]]] = {
    "volumes": [
        {"name": "shared-memory", "emptyDir": {"medium": "Memory", "sizeLimit": "16Gi"}},
        {"name": "tmp", "emptyDir": {}},
        {"name": "home", "emptyDir": {}},
    ],
    "volume_mounts": [
        {"name": "shared-memory", "mountPath": "/dev/shm"},
        {"name": "tmp", "mountPath": "/tmp"},
        {"name": "home", "mountPath": "/home/triton"},
    ],
    "resources": {
        "requests": {"cpu": "2", "memory": "15Gi"},
        "limits": {"cpu": "3", "memory": "16Gi"}
    },
}
