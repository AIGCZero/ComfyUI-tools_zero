from .py.color_adjustment import ColorAdjustment
from .py.image_cropper import ImageCropper
from .py.CleanCache import CleanCache
from .py.text_image import NODE_CLASS_MAPPINGS as TEXT_IMAGE_NODES
from .py.File_import_image import NODE_CLASS_MAPPINGS as FILE_IMPORT_IMAGE_NODES
from .py.Batch_text_saving import NODE_CLASS_MAPPINGS as BATCH_TEXT_SAVING_NODES
from .py.Wan_Prompt import NODE_CLASS_MAPPINGS as Wan_Prompt
from .py.Qwen2_prompt import Qwen2VL_prompt, Qwen2_prompt
from .py.Frame_Rate import NODE_CLASS_MAPPINGS as Frame_Rate_NODES
from .py.ReservedVRAM import NODE_CLASS_MAPPINGS as RESERVED_VRAM_NODES
# 定义web目录
WEB_DIRECTORY = "./web"

# 注册节点
NODE_CLASS_MAPPINGS = {
    "Zero_ColorAdjustment": ColorAdjustment,
    "Zero_ImageCropper": ImageCropper,
    "Zero_CleanCache": CleanCache,
    **TEXT_IMAGE_NODES,
    **FILE_IMPORT_IMAGE_NODES,
    **BATCH_TEXT_SAVING_NODES,
    **Wan_Prompt,
    "Qwen2VL_prompt": Qwen2VL_prompt,
    "Qwen2_prompt": Qwen2_prompt,
    **Frame_Rate_NODES,
    **RESERVED_VRAM_NODES
}

# 设置节点显示名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "Zero_ColorAdjustment": "实时颜色调整",
    "Zero_ImageCropper": "可视化图像裁剪",
    "Zero_CleanCache": "强力清除缓存",
    "文本图像": "文本图像",
    "文件导入图像": "文件导入图像",
    "批量文本保存": "批量文本保存",
    "Wan_Prompt": "万相提示词",
    "Qwen2VL_prompt": "Qwen2VL反推提示词",
    "Qwen2_prompt": "Qwen2提示词",
    "FrameRateCalculator": "帧率计算器",
    "ReservedVRAMNode": "显存预留管理"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

# 注册ReservedVRAM API路由
try:
    from .py.ReservedVRAM import register_routes
    import server
    
    # 检查服务器是否已启动
    if hasattr(server, 'PromptServer') and hasattr(server.PromptServer, 'instance'):
        if server.PromptServer.instance is not None:
            register_routes(server.PromptServer.instance.app)
            print("ReservedVRAM API routes registered successfully")
except Exception as e:
    print(f"Failed to register ReservedVRAM API routes: {e}")
    # 尝试延迟注册
    try:
        import asyncio
        from .py.ReservedVRAM import register_routes
        
        async def delayed_register():
            await asyncio.sleep(2)  # 等待2秒
            try:
                import server
                if hasattr(server, 'PromptServer') and hasattr(server.PromptServer, 'instance'):
                    if server.PromptServer.instance is not None:
                        register_routes(server.PromptServer.instance.app)
                        print("ReservedVRAM API routes registered successfully (delayed)")
            except Exception as e2:
                print(f"Delayed registration also failed: {e2}")
        
        # 创建异步任务
        asyncio.create_task(delayed_register())
    except Exception as e2:
        print(f"Failed to create delayed registration task: {e2}")