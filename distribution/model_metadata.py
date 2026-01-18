"""
Shared model metadata for video generation models.

This module provides centralized model configuration data to avoid duplication
between CLI and GUI components.
"""

# Model metadata with duration options and defaults
MODEL_METADATA = [
    {
        "name": "Kling 2.1 Professional",
        "endpoint": "fal-ai/kling-video/v2.1/pro/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Professional quality video generation",
    },
    {
        "name": "Kling 2.5 Turbo Pro",
        "endpoint": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Fast turbo video generation",
    },
    {
        "name": "Kling O1",
        "endpoint": "fal-ai/kling-video/o1/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Kling O1 model",
    },
    {
        "name": "Wan 2.5",
        "endpoint": "fal-ai/wan-25-preview/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Best open source video model with sound",
    },
    {
        "name": "Wan 2.6",
        "endpoint": "fal-ai/wan/v2.6/image-to-video",
        "duration_options": [5, 10, 15],
        "duration_default": 5,
        "description": "Wan 2.6 with extended 15-second support",
    },
    {
        "name": "Veo 3",
        "endpoint": "fal-ai/veo3/image-to-video",
        "duration_options": [5, 6, 7, 8],
        "duration_default": 5,
        "description": "Google Veo 3 video generation",
    },
    {
        "name": "Ovi",
        "endpoint": "fal-ai/ovi/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Ovi video generation",
    },
    {
        "name": "LTX-2",
        "endpoint": "fal-ai/ltx-2/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "LTX-2 video model",
    },
    {
        "name": "Pixverse V5",
        "endpoint": "fal-ai/pixverse/v5/image-to-video",
        "duration_options": [5, 8],
        "duration_default": 5,
        "description": "Pixverse V5 video generation",
    },
    {
        "name": "Pixverse V5.5",
        "endpoint": "fal-ai/pixverse/v5.5/image-to-video",
        "duration_options": [5, 8, 10],
        "duration_default": 5,
        "description": "Pixverse V5.5 with extended duration support",
    },
    {
        "name": "Hunyuan Video",
        "endpoint": "fal-ai/hunyuan-video/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Tencent Hunyuan video model",
    },
    {
        "name": "MiniMax Video",
        "endpoint": "fal-ai/minimax-video/image-to-video",
        "duration_options": [6],
        "duration_default": 6,
        "description": "MiniMax video generation",
    },
    {
        "name": "Vidu Q2",
        "endpoint": "fal-ai/vidu/image-to-video",
        "duration_options": [2, 3, 4, 5, 6, 7, 8],
        "duration_default": 4,
        "description": "Vidu Q2 with flexible 2-8 second durations",
    },
]


def get_model_by_endpoint(endpoint: str) -> dict:
    """Get model metadata by endpoint.
    
    Args:
        endpoint: Model endpoint (e.g., "fal-ai/kling-video/v2.5-turbo/pro/image-to-video")
        
    Returns:
        Model metadata dictionary or None if not found
    """
    for model in MODEL_METADATA:
        if model["endpoint"] == endpoint:
            return model.copy()
    return None


def get_duration_options(endpoint: str) -> list:
    """Get duration options for a model.
    
    Args:
        endpoint: Model endpoint
        
    Returns:
        List of valid duration values in seconds, or [5, 10] as default
    """
    model = get_model_by_endpoint(endpoint)
    if model:
        return model.get("duration_options", [5, 10])
    return [5, 10]  # Safe default


def get_duration_default(endpoint: str) -> int:
    """Get default duration for a model.
    
    Args:
        endpoint: Model endpoint
        
    Returns:
        Default duration in seconds, or 5 as fallback
    """
    model = get_model_by_endpoint(endpoint)
    if model:
        return model.get("duration_default", 5)
    return 5  # Safe default
