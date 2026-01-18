---
created: 2026-01-15T02:14
title: How to Programmatically Discover All Model Parameters
area: documentation
files:
  - fal.ai
---

## Problem

We need a way to programmatically discover all available parameters for fal.ai models, specifically for models like `fal-ai/bytedance/seedance/v1.5/pro/image-to-video` where documentation might be sparse or specific parameters (like `negative_prompt`) might be unsupported. Relying on assumptions about supported parameters can lead to errors.

## Solution

Implement a discovery mechanism using the fal.ai API:

1.  **Platform API with OpenAPI Expansion:**
    Use `GET https://api.fal.ai/v1/models?endpoint_id={model_id}&expand=openapi-3.0` to fetch the complete OpenAPI 3.0 schema. This provides names, types, constraints, defaults, and descriptions.

2.  **Direct API Documentation Page:**
    Check `https://fal.ai/models/{endpoint_id}/api` (e.g., `https://fal.ai/models/fal-ai/bytedance/seedance/v1.5/pro/image-to-video/api`) for human-readable schema.

3.  **Programmatic Parsing:**
    Write a Python script (example provided in the todo description) to fetch and parse this schema to verify supported parameters dynamically.

**Important Note for Seedance 1.5 Pro:**
It specifically does **NOT** support `negative_prompt`.

Supported parameters for Seedance 1.5 Pro (as of Jan 2026):
- `prompt` (required)
- `image_url` (required)
- `end_image_url`
- `aspect_ratio`
- `resolution`
- `duration`
- `camera_fixed`
- `seed`
- `generate_audio`
- `enable_safety_checker`
