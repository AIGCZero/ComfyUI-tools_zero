import os
import sys
import torch
import logging
import json
from aiohttp import web

# 全局变量存储显存预留设置
RESERVED_VRAM_GB = 0

def get_vram_info():
    """获取显存信息"""
    try:
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            total_memory = torch.cuda.get_device_properties(device).total_memory
            allocated_memory = torch.cuda.memory_allocated(device)
            reserved_memory = torch.cuda.memory_reserved(device)
            
            return {
                "total_gb": round(total_memory / (1024**3), 2),
                "allocated_gb": round(allocated_memory / (1024**3), 2),
                "reserved_gb": round(reserved_memory / (1024**3), 2),
                "free_gb": round((total_memory - reserved_memory) / (1024**3), 2),
                "reserved_vram_gb": RESERVED_VRAM_GB
            }
        else:
            return {"error": "CUDA not available"}
    except Exception as e:
        logging.error(f"Error getting VRAM info: {e}")
        return {"error": str(e)}

def set_reserved_vram(gb):
    """设置显存预留"""
    global RESERVED_VRAM_GB
    try:
        gb = float(gb)
        if 0 <= gb <= 48:  # 限制在0-48GB范围内
            RESERVED_VRAM_GB = gb
            
            # 尝试设置ComfyUI的显存预留
            try:
                # 导入ComfyUI的model_management模块
                import comfy.model_management as model_management
                # 设置显存预留（转换为字节）
                model_management.EXTRA_RESERVED_VRAM = int(gb * 1024 * 1024 * 1024)
                logging.info(f"Successfully set EXTRA_RESERVED_VRAM to {gb} GB ({int(gb * 1024 * 1024 * 1024)} bytes)")
            except ImportError:
                logging.warning("Could not import comfy.model_management, using fallback method")
            except Exception as e:
                logging.error(f"Error setting EXTRA_RESERVED_VRAM: {e}")
            
            logging.info(f"Set reserved VRAM to {gb} GB")
            return {"success": True, "reserved_vram_gb": RESERVED_VRAM_GB}
        else:
            return {"error": "Reserved VRAM must be between 0 and 48 GB"}
    except ValueError:
        return {"error": "Invalid value for reserved VRAM"}

def get_reserved_vram():
    """获取当前显存预留设置"""
    return {"reserved_vram_gb": RESERVED_VRAM_GB}

# 在ComfyUI启动时注册路由
def register_to_server(server):
    """注册到ComfyUI服务器"""
    routes = web.RouteTableDef()
    
    @routes.get("/reserved_vram/info")
    async def get_vram_info_handler(request):
        """获取显存信息"""
        try:
            info = get_vram_info()
            return web.json_response(info)
        except Exception as e:
            logging.error(f"Error in get_vram_info_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)

    @routes.post("/reserved_vram/set")
    async def set_reserved_vram_handler(request):
        """设置显存预留"""
        try:
            data = await request.json()
            gb = data.get("gb", 0)
            result = set_reserved_vram(gb)
            
            if "error" in result:
                return web.json_response(result, status=400)
            else:
                return web.json_response(result)
        except Exception as e:
            logging.error(f"Error in set_reserved_vram_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)

    @routes.get("/reserved_vram/get")
    async def get_reserved_vram_handler(request):
        """获取显存预留设置"""
        try:
            result = get_reserved_vram()
            return web.json_response(result)
        except Exception as e:
            logging.error(f"Error in get_reserved_vram_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    server.app.add_routes(routes)
    logging.info("ReservedVRAM API routes registered")

# 兼容性：如果没有使用扩展系统，直接注册路由
def register_routes(app):
    """直接注册路由（兼容性）"""
    routes = web.RouteTableDef()
    
    @routes.get("/reserved_vram/info")
    async def get_vram_info_handler(request):
        """获取显存信息"""
        try:
            info = get_vram_info()
            return web.json_response(info)
        except Exception as e:
            logging.error(f"Error in get_vram_info_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)

    @routes.post("/reserved_vram/set")
    async def set_reserved_vram_handler(request):
        """设置显存预留"""
        try:
            data = await request.json()
            gb = data.get("gb", 0)
            result = set_reserved_vram(gb)
            
            if "error" in result:
                return web.json_response(result, status=400)
            else:
                return web.json_response(result)
        except Exception as e:
            logging.error(f"Error in set_reserved_vram_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)

    @routes.get("/reserved_vram/get")
    async def get_reserved_vram_handler(request):
        """获取显存预留设置"""
        try:
            result = get_reserved_vram()
            return web.json_response(result)
        except Exception as e:
            logging.error(f"Error in get_reserved_vram_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    app.add_routes(routes)

# 尝试导入ComfyUI扩展系统
try:
    from comfy_extras.extension_manager import ComfyExtension
    
    class ReservedVRAMExtension(ComfyExtension):
        def __init__(self):
            super().__init__()
            self.name = "ReservedVRAM"
            self.description = "显存预留管理工具"
            self.version = "1.0.0"
        
        def register_api_routes(self, app):
            """注册API路由"""
            register_routes(app)
    
    def comfy_entrypoint():
        """ComfyUI扩展入口点"""
        return ReservedVRAMExtension()
        
except ImportError:
    # 如果没有扩展系统，使用简单的注册方式
    def comfy_entrypoint():
        """ComfyUI扩展入口点（兼容模式）"""
        return None

# ComfyUI节点类定义
class ReservedVRAMNode:
    """显存预留管理节点"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "reserved_gb": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 48.0,
                    "step": 0.1,
                    "display": "number"
                }),
            },
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("vram_info",)
    FUNCTION = "set_and_get_vram_info"
    CATEGORY = "Zero工具"
    
    def set_and_get_vram_info(self, reserved_gb):
        """设置显存预留并返回显存信息"""
        # 设置显存预留
        result = set_reserved_vram(reserved_gb)
        
        # 获取显存信息
        vram_info = get_vram_info()
        
        if "error" in result:
            return (f"设置失败: {result['error']}",)
        
        if "error" in vram_info:
            return (f"获取显存信息失败: {vram_info['error']}",)
        
        # 格式化返回信息
        info_str = (
            f"显存总量: {vram_info['total_gb']}GB\n"
            f"已分配: {vram_info['allocated_gb']}GB\n"
            f"已预留: {vram_info['reserved_gb']}GB\n"
            f"可用: {vram_info['free_gb']}GB\n"
            f"预留设置: {vram_info['reserved_vram_gb']}GB"
        )
        
        return (info_str,)

# 节点映射
NODE_CLASS_MAPPINGS = {
    "ReservedVRAMNode": ReservedVRAMNode
}

#代码参考：https://github.com/Windecay/ComfyUI-ReservedVRAM