from .py.color_adjustment import ColorAdjustment
from .py.image_cropper import ImageCropper
from .py.text_image import NODE_CLASS_MAPPINGS as TEXT_IMAGE_NODES

# 定义web目录
WEB_DIRECTORY = "./web"

# 注册节点
NODE_CLASS_MAPPINGS = {
    "Zero_ColorAdjustment": ColorAdjustment,
    "Zero_ImageCropper": ImageCropper,
    **TEXT_IMAGE_NODES
}

# 设置节点显示名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "Zero_ColorAdjustment": "实时颜色调整",
    "Zero_ImageCropper": "可视化图像裁剪",
    "文本图像": "文本图像"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]