import requests
import time

# 定义一个特殊的类型，用于匹配任何类型
class AlwaysEqualProxy(str):
    def __eq__(self, _):
        return True
    
    def __ne__(self, _):
        return False

# 创建一个通用类型标识符
any_type = AlwaysEqualProxy("*")

class CleanCache:
    """
    强力清除缓存节点：当数据通过此节点时，发送请求到后端free路由，清理内存和模型
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "卸载模型": ("BOOLEAN", {"default": True}),  # 是否卸载模型
                "释放内存": ("BOOLEAN", {"default": True}),  # 是否释放内存
                "停止时间": ("INT", {"default": 0, "min": 0, "max": 10, "step": 1}),  # 停止时间(秒)
                "输入数据": (any_type, {}),  # 任意类型输入端口
            }
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("输出数据",)

    FUNCTION = "clean"
    CATEGORY = "tools_zero"

    def clean(self, 卸载模型, 释放内存, 停止时间, 输入数据):
        # 发送请求到后端free路由
        try:
            url = "http://127.0.0.1:8188/free"
            payload = {
                "unload_models": 卸载模型,
                "free_memory": 释放内存
            }
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                print(f"清除缓存请求返回状态码: {response.status_code}")
        except Exception as e:
            print(f"清除缓存失败: {str(e)}")
        
        # 如果指定了停止时间，则暂停工作流程
        if 停止时间 > 0:
            print(f"工作流程暂停 {停止时间} 秒...")
            time.sleep(停止时间)
            print("工作流程继续执行")
            
        # 将输入原样返回
        return (输入数据,)

NODE_CLASS_MAPPINGS = {
    "CleanCache": CleanCache,    
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CleanCache": "强力清除缓存",
}
