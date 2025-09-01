import torch
import math
import comfy.utils

class FrameRateCalculator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "duration_seconds": ("FLOAT", {"default": 5.0, "min": 0.01, "max": 3600.0, "step": 0.1}),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 240.0, "step": 1.0}),
            },
        }

    RETURN_TYPES = ("FLOAT", "INT", "FLOAT")
    RETURN_NAMES = ("duration_seconds", "total_frames", "frame_rate")
    FUNCTION = "calculate"
    CATEGORY = "tools_zero"

    def calculate(self, duration_seconds, frame_rate):
        total_frames = math.floor(duration_seconds * frame_rate) + 1
        return (float(duration_seconds), int(total_frames), float(frame_rate))

NODE_CLASS_MAPPINGS = {
    "FrameRateCalculator": FrameRateCalculator
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FrameRateCalculator": "帧率计算器"
}
