import torch
import numpy as np
from server import PromptServer
from threading import Event
from aiohttp import web
import json
import base64
import io
from PIL import Image
import traceback

# 全局变量用于存储裁剪节点数据
crop_node_data = {}

class ImageCropper:
    """图像裁剪专用节点"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "mask": ("MASK",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("裁剪图像", "裁剪遮罩")
    FUNCTION = "crop"
    CATEGORY = "tools_zero"
    OUTPUT_NODE = True

    def crop(self, image, unique_id, mask=None):
        try:
            node_id = unique_id
            event = Event()
            
            # 初始化节点数据
            crop_node_data[node_id] = {
                "event": event,
                "result": None,
                "result_mask": None,
                "processing_complete": False,
                "original_mask": mask,  # 存储原始遮罩
                "original_image": image,  # 存储原始图像
                "crop_info": None  # 存储裁剪信息(x, y, width, height)
            }
            
            # 发送预览图像
            preview_image = (torch.clamp(image.clone(), 0, 1) * 255).cpu().numpy().astype(np.uint8)[0]
            pil_image = Image.fromarray(preview_image)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            try:
                PromptServer.instance.send_sync("zero_image_cropper_update", {
                    "node_id": node_id,
                    "image_data": f"data:image/png;base64,{base64_image}"
                })
                
                # 等待前端裁剪完成
                if not event.wait(timeout=30):
                    print(f"[ImageCropper] 等待超时: 节点ID {node_id}")
                    if node_id in crop_node_data:
                        del crop_node_data[node_id]
                    return (image, mask if mask is not None else torch.zeros((1, image.shape[1], image.shape[2]), dtype=torch.float32))

                # 获取结果
                result_image = None
                result_mask = None
                
                if node_id in crop_node_data:
                    result_image = crop_node_data[node_id]["result"]
                    result_mask = crop_node_data[node_id]["result_mask"]
                    del crop_node_data[node_id]
                
                # 如果没有结果图像，返回原始图像
                if result_image is None:
                    result_image = image
                
                # 如果没有结果遮罩但有原始遮罩，返回原始遮罩
                if result_mask is None and mask is not None:
                    result_mask = mask
                # 如果没有任何遮罩，创建空遮罩
                elif result_mask is None:
                    result_mask = torch.zeros((1, result_image.shape[1], result_image.shape[2]), dtype=torch.float32)
                
                return (result_image, result_mask)
                
            except Exception as e:
                print(f"[ImageCropper] 处理过程中出错: {str(e)}")
                traceback.print_exc()
                if node_id in crop_node_data:
                    del crop_node_data[node_id]
                return (image, mask if mask is not None else torch.zeros((1, image.shape[1], image.shape[2]), dtype=torch.float32))
            
        except Exception as e:
            print(f"[ImageCropper] 节点执行出错: {str(e)}")
            traceback.print_exc()
            return (image, mask if mask is not None else torch.zeros((1, image.shape[1], image.shape[2]), dtype=torch.float32))

@PromptServer.instance.routes.post("/zero_image_cropper/apply")
async def apply_image_cropper(request):
    try:
        # 检查内容类型
        content_type = request.headers.get('Content-Type', '')
        print(f"[ImageCropper] 请求内容类型: {content_type}")
        
        node_id = None
        crop_width = None
        crop_height = None
        image_data = None
        crop_x = 0  # 裁剪起始X坐标
        crop_y = 0  # 裁剪起始Y坐标
        
        if 'multipart/form-data' in content_type:
            # 处理multipart/form-data请求
            reader = await request.multipart()
            
            # 读取表单字段
            while True:
                part = await reader.next()
                if part is None:
                    break
                
                if part.name == 'node_id':
                    node_id = await part.text()
                elif part.name == 'width':
                    crop_width = int(await part.text())
                elif part.name == 'height':
                    crop_height = int(await part.text())
                elif part.name == 'x':
                    crop_x = int(await part.text())
                elif part.name == 'y':
                    crop_y = int(await part.text())
                elif part.name == 'image_data':
                    image_data = await part.read(decode=False)
        else:
            # 处理JSON请求
            data = await request.json()
            node_id = data.get("node_id")
            crop_width = data.get("width")
            crop_height = data.get("height")
            crop_x = data.get("x", 0)
            crop_y = data.get("y", 0)
            
            cropped_data_base64 = data.get("cropped_data_base64")
            if cropped_data_base64:
                if cropped_data_base64.startswith('data:image'):
                    base64_data = cropped_data_base64.split(',')[1]
                else:
                    base64_data = cropped_data_base64
                image_data = base64.b64decode(base64_data)
        
        if node_id not in crop_node_data:
            crop_node_data[node_id] = {
                "event": Event(),
                "result": None,
                "result_mask": None,
                "processing_complete": False,
                "original_mask": None,
                "original_image": None,
                "crop_info": None
            }
        
        try:
            node_info = crop_node_data[node_id]
            
            # 存储裁剪信息
            node_info["crop_info"] = {
                "x": crop_x,
                "y": crop_y,
                "width": crop_width,
                "height": crop_height
            }
            
            if image_data:
                try:
                    buffer = io.BytesIO(image_data)
                    pil_image = Image.open(buffer)
                    
                    if pil_image.mode == 'RGBA':
                        pil_image = pil_image.convert('RGB')
                    
                    np_image = np.array(pil_image)
                    
                    if len(np_image.shape) == 3 and np_image.shape[2] == 3:
                        tensor_image = torch.from_numpy(np_image / 255.0).float().unsqueeze(0)
                        node_info["result"] = tensor_image
                        
                        # 处理遮罩裁剪
                        original_mask = node_info.get("original_mask")
                        if original_mask is not None:
                            # 获取原始图像尺寸
                            original_image = node_info.get("original_image")
                            if original_image is not None:
                                orig_height = original_image.shape[1]
                                orig_width = original_image.shape[2]
                                
                                # 确保遮罩与原始图像尺寸匹配
                                if original_mask.shape[1] == orig_height and original_mask.shape[2] == orig_width:
                                    # 确保裁剪坐标在有效范围内
                                    valid_x = min(max(0, crop_x), orig_width - 1)
                                    valid_y = min(max(0, crop_y), orig_height - 1)
                                    valid_width = min(crop_width, orig_width - valid_x)
                                    valid_height = min(crop_height, orig_height - valid_y)
                                    
                                    # 裁剪遮罩
                                    if valid_width > 0 and valid_height > 0:
                                        # 直接裁剪遮罩
                                        cropped_mask = original_mask[:, valid_y:valid_y+valid_height, valid_x:valid_x+valid_width]
                                        
                                        # 确保遮罩尺寸与图像一致
                                        if tensor_image.shape[1] != cropped_mask.shape[1] or tensor_image.shape[2] != cropped_mask.shape[2]:
                                            print(f"[ImageCropper] 调整遮罩尺寸以匹配图像: 遮罩={cropped_mask.shape}, 图像={tensor_image.shape}")
                                            # 调整遮罩尺寸以匹配图像
                                            cropped_mask = torch.nn.functional.interpolate(
                                                cropped_mask.unsqueeze(1),  # 添加通道维度 [B, 1, H, W]
                                                size=(tensor_image.shape[1], tensor_image.shape[2]),
                                                mode="nearest"
                                            ).squeeze(1)  # 移除通道维度 [B, H, W]
                                        
                                        node_info["result_mask"] = cropped_mask
                                    else:
                                        print(f"[ImageCropper] 警告: 裁剪区域无效: x={valid_x}, y={valid_y}, width={valid_width}, height={valid_height}")
                                else:
                                    print(f"[ImageCropper] 警告: 遮罩尺寸与原始图像不匹配: 遮罩={original_mask.shape}, 图像={original_image.shape}")
                        
                        node_info["event"].set()
                    else:
                        print(f"[ImageCropper] 警告: 图像数组形状不符合预期: {np_image.shape}")
                except Exception as e:
                    print(f"[ImageCropper] 处理图像数据时出错: {str(e)}")
                    traceback.print_exc()
                    node_info["event"].set()
            
            return web.json_response({"success": True})
            
        except Exception as e:
            print(f"[ImageCropper] 处理数据时出错: {str(e)}")
            traceback.print_exc()
            if node_id in crop_node_data and "event" in crop_node_data[node_id]:
                crop_node_data[node_id]["event"].set()
            return web.json_response({"success": False, "error": str(e)})

    except Exception as e:
        print(f"[ImageCropper] 请求处理出错: {str(e)}")
        traceback.print_exc()
        return web.json_response({"success": False, "error": str(e)})

@PromptServer.instance.routes.post("/zero_image_cropper/cancel")
async def cancel_crop(request):
    try:
        data = await request.json()
        node_id = data.get("node_id")
        
        if node_id in crop_node_data:
            # 设置事件，让节点继续执行
            crop_node_data[node_id]["event"].set()
            print(f"[ImageCropper] 取消裁剪操作: 节点ID {node_id}")
            return web.json_response({"success": True})
        
        return web.json_response({"success": False, "error": "节点未找到"})
        
    except Exception as e:
        print(f"[ImageCropper] 取消请求处理出错: {str(e)}")
        traceback.print_exc()
        return web.json_response({"success": False, "error": str(e)})
