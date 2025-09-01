import os
import torch
from transformers import (
    Qwen2_5_VLForConditionalGeneration,
    AutoModelForCausalLM,
    AutoTokenizer,
    AutoProcessor,
    BitsAndBytesConfig,
)
from qwen_vl_utils import process_vision_info
from PIL import Image
import numpy as np
import folder_paths
import subprocess
import uuid
import sys
import gc
import requests

# 导入自定义提示词模板配置
try:
    # 尝试从上级目录导入qwen_prompt配置
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from qwen_prompt import get_prompt_config
    CUSTOM_PROMPT_CONFIG = get_prompt_config()
    USE_CUSTOM_PROMPT = True
except ImportError:
    # 如果导入失败，使用默认配置
    CUSTOM_PROMPT_CONFIG = None
    USE_CUSTOM_PROMPT = False


def get_optimal_device_map():
    """获取最优的设备映射策略"""
    if torch.cuda.is_available():
        # 检查GPU内存
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
        print(f"检测到GPU内存: {gpu_memory:.1f}GB")
        
        if gpu_memory >= 24:  # 24GB以上
            return "auto"
        elif gpu_memory >= 16:  # 16-24GB
            return "auto"
        elif gpu_memory >= 8:   # 8-16GB
            return "auto"
        else:  # 8GB以下
            return "auto"  # 仍然使用auto，但会启用CPU卸载
    else:
        return "cpu"


def clear_gpu_memory():
    """清理GPU内存"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        gc.collect()
        print("GPU内存已清理")


def auto_clean_cache_when_oom():
    """当出现显存不足时，自动清理缓存"""
    print("检测到显存不足，正在自动清理缓存...")
    
    # 首先尝试本地清理
    clear_gpu_memory()
    
    # 然后发送请求到后端free路由进行深度清理
    try:
        url = "http://127.0.0.1:8188/free"
        payload = {
            "unload_models": True,
            "free_memory": True
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("后端缓存清理成功")
        else:
            print(f"后端缓存清理请求返回状态码: {response.status_code}")
    except Exception as e:
        print(f"后端缓存清理失败: {str(e)}")
    
    # 等待2秒让清理生效
    import time
    time.sleep(2)
    
    # 再次清理本地内存
    clear_gpu_memory()
    print("缓存清理完成，准备重新加载模型")


def is_oom_error(error_msg):
    """检查是否为显存不足错误"""
    oom_indicators = [
        "Some modules are dispatched on the CPU or the disk",
        "Some parameters are on the meta device because they were offloaded to the cpu",
        "CUDA out of memory",
        "GPU out of memory",
        "not enough memory",
        "insufficient memory"
    ]
    return any(indicator.lower() in error_msg.lower() for indicator in oom_indicators)


def handle_oom_and_retry(model_loading_func, *args, **kwargs):
    """处理显存不足错误并重试"""
    try:
        # 首先尝试正常加载
        return model_loading_func(*args, **kwargs)
    except Exception as e:
        if is_oom_error(str(e)):
            print("检测到显存不足，正在自动清理缓存...")
            # 自动清理缓存
            auto_clean_cache_when_oom()
            
            # 清理完成后重新尝试加载模型
            try:
                result = model_loading_func(*args, **kwargs)
                print("模型加载成功")
                return result
            except Exception as retry_e:
                if is_oom_error(str(retry_e)):
                    # 如果清理后仍然显存不足，弹出提示
                    error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                    print(error_msg)
                    raise RuntimeError(error_msg)
                else:
                    # 其他错误直接抛出
                    raise retry_e
        else:
            # 非显存不足错误直接抛出
            raise e


def tensor_to_pil(image_tensor, batch_index=0) -> Image:
    # Convert tensor of shape [batch, height, width, channels] at the batch_index to PIL Image
    image_tensor = image_tensor[batch_index].unsqueeze(0)
    i = 255.0 * image_tensor.cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8).squeeze())
    return img


class Qwen2VL_prompt:
    def __init__(self):
        self.model_checkpoint = None
        self.processor = None
        self.model = None
        self.device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        self.bf16_support = (
            torch.cuda.is_available()
            and torch.cuda.get_device_capability(self.device)[0] >= 8
        )

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "user_input": ("STRING", {"default": "", "multiline": True}),
                "prompt_type": (["图像分析", "图像分析（详细）", "姿态分析", "视频描述", "视频描述（多段运镜）", "视频描述（快速运镜）", "视频描述（首尾帧）", "电影分镜", "kontext（打标）", "用户输入"], {"default": "图像分析"}),
                "model": (
                    [
                        "Qwen2.5-VL-3B-Instruct",
                        "Qwen2.5-VL-3B-Instruct-bnb-4bit",
                        "Qwen2.5-VL-7B-Instruct",
                        "Qwen2.5-VL-7B-Instruct-bnb-4bit",
                        "SkyCaptioner-V1",
                    ],
                    {"default": "Qwen2.5-VL-7B-Instruct-bnb-4bit"},
                ),
                "quantization": (
                    ["none", "4bit", "8bit"],
                    {"default": "none"},
                ),
                "keep_model_loaded": ("BOOLEAN", {"default": False}),
                "temperature": (
                    "FLOAT", 
                    {"default": 0.6, "min": 0.1, "max": 1.0, "step": 0.1, "display": "slider"}
                ),
                "seed": ("INT", {"default": -1, "min": -1, "max": 99999}),
                "max_new_tokens": (
                    "INT",
                    {"default": 512, "min": 128, "max": 2048, "step": 1},
                ),
                "image": ("IMAGE",),
                "output_language": (["english", "中文"], {"default": "english"}),
            },
            "optional": {
                "video_path": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "inference"
    CATEGORY = "tools_zero"

    def inference(
        self,
        user_input,
        prompt_type,
        model,
        quantization,
        keep_model_loaded,
        temperature,
        seed,
        max_new_tokens,
        image,
        output_language,
        video_path=None,
    ):
        # 根据提示类型构建完整提示
        language_suffix = "输出提示词必须全部为中文。" if output_language == "中文" else "输出提示词必须全部为英文。"
        
        prompt_map = {}
        
        prompt_map["图像分析"] = (
            f"请根据输入的\"{user_input}\"详细描述这张图片，包括主要内容、场景、人物、物体、背景等细节信息。{language_suffix}"
        )
        prompt_map["姿态分析"] = (
            f"请根据输入的\"{user_input}\"详细描述这张图片的主体姿态信息，只详细描述主体的姿态动作，包括主体的姿态、表情、眼神，手部动作，身体动作，头部动作。不要描述场景、背景、物体等其他信息。{language_suffix}"
        )
        prompt_map["图像分析（详细）"] = (
            f"请根据输入的\"{user_input}\"详细描述这张图片，描述应包括以下方面：\n"
            f"主要主体：描述场景中的主体特征（如外貌、表情，数量、种族、姿态等）。\n"
            f"次要主体与背景：描述场景中的次要物体或背景元素，包括其与主要主体的关系。\n"
            f"材质与质感：描述主要主体和背景的材质类型、质感、光泽度、透明度等。\n"
            f"细节与纹理：描述场景中的细节，如纹理、图案、装饰、标记等。\n"
            f"风格与时代特征：描述场景的艺术风格、时代特征、文化背景等。\n"
            f"色调与色彩对比：描述场景的色调、色彩对比、饱和度、冷暖色调等。\n"
            f"光影与阴影：描述场景中的光源方向、阴影的强度、光线的柔和度等。\n"
            f"构图与视角：描述场景的构图方式、视角、动态与静态元素等。\n"
            f"请按照从整体到细节的顺序，层次分明地进行描述。{language_suffix}"
        )
        prompt_map["视频描述"] = (
            f"你是一位Prompt优化师，根据用户输入的\"{user_input}\"和图像内容，再不改变原意的情况下进行改写，"
            f"任务要求：1. 根据用户的输入，和图像内容，合理推断并补充细节，使得画面更加完整，故事性，运动和运镜感更强；"
            f"2.改写后的prompt字数控制在256字左右，不要做任何不必要的输出，只输出提示词部分；"
            f"3.提示词内容参考：运动加运镜，运动描述：结合图像中的元素（如人物、动物），描述其相动态的过程，如奔跑、打招呼，可以通过形容词来控制动态的程度与速度，如\"快速地\"、\"缓慢地\"。运镜：通过提示词如：镜头推进、镜头拉远、镜头向右移动镜头、向左移动镜头上摇、手持镜头、复合运镜跟随镜头、环绕运镜、等， 以上仅做参考，不要完全照搬。{language_suffix}"
        )
        prompt_map["视频描述（多段运镜）"] = (
            f"你是一位Prompt优化师，根据用户输入的\"{user_input}\"和图像内容，再不改变原意的情况下进行改写，"
            f"任务要求：1. 根据用户的输入，和图像内容，合理推断并补充细节，使得画面更加完整，故事性，运动和运镜感更强；"
            f"2.改写后的prompt字数控制在256字左右，不要做任何不必要的输出，只输出提示词部分；"
            f"3.以下仅做提示词参考，不要完全照搬：“古风女子身着传统汉服，立于古典长廊中。0-1.5秒：镜头从精致的发型和发饰特写开始，挽起的发髻几缕碎发被微风拂动，尽显灵动，随后镜头缓慢下移，展示女子的肩部和外袍上的金色花纹刺绣。1.5-4秒：镜头切换至侧后方，以平滑的追踪运镜展现女子微微侧身的姿态，双手轻握在身前，外袍袖口处白色花纹在微风中飘动，裙摆层层叠叠，带有红色花纹装饰，背景古典长廊的木质立柱在移动中逐渐显露出其古朴质感。4-5秒：镜头仰视追随女子缓缓抬头的动作，阳光透过长廊的屋檐洒下，照亮她清秀的面容，神情温柔且坚定，远处山水在虚化中若隐若现，营造出宁静而唯美的氛围。（衣摆飘动/发丝飘动），8K细节锐化，超现实主义风格，色彩柔和且真实，织物纹理分明，光泽感强，氛围感十足，仿佛置身于古代画卷之中。以上仅做参考，不要完全照搬；”"
            f"4.以下仅做提示词参考，不要完全照搬：“(0-1.5秒)： 镜头以长征五号火箭引擎喷口特写为起点，液氢液氧推进剂喷涌的蓝色火焰；镜头沿箭体弧形上掠90°，掠过箭体‘中国航天’标识，展现箭体蓄势震颤的姿态，(1.5-4秒)： 镜头瞬切至侧后方黄金追随位，与火箭同步垂直攀升，捕捉长征五号突破音障的锥形云环；整流罩反射朝阳金光，助推器分离瞬间的金属碎片在真空中悬浮（动态速率：1.5秒缓加速至3倍音速模拟），(4-5秒)： 镜头仰视追随火箭刺入苍穹，尾焰在稀薄大气中膨胀为巨型羽流；背景地球弧线显现，整流罩分离后露出深空探测器，箭体化作星轨冲向日冕级耀斑。助推器脱离时液压杆机械运动特写，螺栓爆炸螺栓触发火星四溅。海南文昌发射场黎明，椰子林被冲击波压低，摄像机震动尘埃飞扬；太空段背景为银河与晨昏线地球。（尾焰膨胀/碎片失重），8K细节锐化，以上仅做参考，不要完全照搬；”"
            f"5.在不改变用户输入原意的情况下进行改写，主体、场景、运动、美学控制和风格化部分需有机融合在语段中；{language_suffix}"
        )
        prompt_map["视频描述（快速运镜）"] = (
            f"你是一位Prompt优化师，根据用户输入的\"{user_input}\"和图像内容，再不改变原意的情况下进行改写，"
            f"任务要求：1. 根据用户的输入，和图像内容，合理推断并补充细节，使得画面更加完整，故事性，运动和运镜感更强；"
            f"2.改写后的prompt字数控制在256字左右，不要做任何不必要的输出，只输出提示词部分；"
            f"3.提示词格式参考：“主体描述：霓虹闪烁的广告牌；场景描述：画面从昏暗的街道开始，逐渐拉近到闪烁的霓虹灯招牌前，周围是高楼大厦的轮廓，上午的冷色调光线透过云层投射下来，营造出一种都市夜晚的氛围；运动描述：快速地手持镜头推进，捕捉霓虹灯的光影变化，同时轻微晃动，增加画面的真实感；美学控制：使用侧光，增强霓虹灯的立体感和色彩饱和度，景别为近景，保持主体清晰突出，采用平视角度拍摄，以展现细节；风格化：现代都市风格，带有冷峻和科技感。以上仅做参考，不要完全照搬；”"
            f"4.以下仅做提示词参考，不要完全照搬：“主体描述：一位傲慢的女人，穿着现代太空服，头发凌乱。场景描述：画面从浩瀚的外太空开始，穿过璀璨的星系，逐渐接近月球表面，展示月球坑洞和冷色调的景观。运动描述：快速镜头推进，从广阔星空过渡到月球表面的特写，女人的动作从远至近，最终定格在她对着镜头挑衅的姿态。美学控制：使用冷色调滤镜，增强月球表面的荒凉感，采用低角度俯视镜头，营造出一种压迫感。风格化：科幻风格，结合现实与未来元素，展现科技与自然的冲突美感。以上仅做参考，不要完全照搬；”"
            f"5.在不改变用户输入和图像内容原意的情况下进行改写，主体、场景、运动、美学控制和风格化部分需有机融合在语段中；{language_suffix}"
        )
        prompt_map["视频描述（首尾帧）"] = (
            f"你是一位Prompt优化师，旨在参考用户输入的图像内容， 描述左边图像变成右边图像的主要变化（回复的Prompt只描述变化，不要有左边右边的Prompt）。"
            f"任务要求：\n"
            f"1.根据图像内容，合理推断并补充细节，讲述图像变化的过程，使图像变化更加具有运动感；"
            f"2.改写后的prompt字数控制在80字左右，以整段自然语言描述提示词，不要做任何不必要的输出，只输出提示词部分；"
            f"3.输出提示词最好有运动描述，和运镜描述，两者要跟主体的变化，自然的融合整段提示词中，不能生硬和冲突；{language_suffix}"
        )
        prompt_map["电影分镜"] = (
            f"你是一位Prompt优化师，旨在帮助用户根据输入的\"{user_input}\"和图像内容，生成高质量的分镜脚本。请合理推断并补充细节，使画面更加完整，故事性更强。\n"
            f"根据参考图片生成一个分镜脚本，要求如下：\n"
            f"1、需要3个有故事的分镜脚本\n"
            f"2、对分镜脚本的描述都是目前发生的故事，不要过多考虑后续的发展\n"
            f"3、分镜脚本之间需要有故事关联性\n"
            f"4、场景是统筹3个分镜脚本的故事线，分镜脚本内容需要非常贴合场景故事线\n"
            f"5、分镜内容尽量详细，描述场景的构图方式、视角、分镜场景中的动态与静态元素、人物的动态与位置关系\n"
            f"6、输出的Prompt，要用适合扩散模型的自然语言进行描述\n"
            f"#输出格式：\n"
            f"[STYLE]摄影，写实，影视级\n"
            f"[DESCRIPTION]{{场景}}\n"
            f"[SCENE-1]\n"
            f"[SCENE-2]\n"
            f"[SCENE-3]\n"
            f"{language_suffix}"
        )
        prompt_map["kontext（打标）"] = (
            f"你是一位Prompt优化师，旨在参考用户输入的图像内容， 描述左边图像变成右边图像的变化（回复的Prompt只描述变化，不要有左边右边的Prompt）。请重点关注具体发生的修改、添加、删除或变更。\n"
            f"任务要求：\n"
            f"1.Define the core, describe variables, instructions should be concise, clear, and include instruction categories (such as subject replacement, background replacement, style conversion, object removal, etc.)\n"
            f"2.Key functionalities of the script:\n"
            f"Data Loading: Reads and parses the metadata.jsonl file, extracting instructions.\n"
            f"Text Preprocessing: Cleans the instruction text by converting to lowercase, removing punctuation, and tokenizing words.\n"
            f"Frequency Analysis: Calculates the frequency of individual words, bigrams (pairs of words), and trigrams (sequences of three words).\n"
            f"Structure Analysis: Identifies common starting words (verbs) used in the instructions.\n"
            f"Output Generation: Summarizes the findings in a markdown file (analysis.md), detailing the most frequent words, bigrams, trigrams, and common instruction structures.\n"
            f"请提供至少50字的详细描述来解释这个转变过程。{language_suffix}"
        )
        prompt_map["用户输入"] = (
            f"用户输入：{user_input}\n{language_suffix}"
        )
        
        # 确保提示类型存在于映射中，如果不存在则使用默认提示
        if prompt_type not in prompt_map:
            print(f"警告：提示类型 '{prompt_type}' 不存在，使用默认的'图像分析'提示类型")
            prompt_type = "图像分析"
            
        text = prompt_map[prompt_type]
        model_name = model
        quantization_type = quantization
        keep_loaded = keep_model_loaded
        temp = temperature
        max_tokens = max_new_tokens
        img = image
        video_file_path = video_path
        
        # 处理种子参数，确保它是一个有效的整数
        seed_value = -1  # 默认值
        
        # 检查种子是否为None或NaN
        if seed is None or seed == "NaN":
            print(f"使用默认种子值: -1 (随机)")
        else:
            try:
                seed_value = int(seed)
                print(f"使用种子值: {seed_value}")
            except (ValueError, TypeError):
                print(f"警告: 无效的种子值 '{seed}', 使用默认值 -1")
                
        if seed_value != -1:
            torch.manual_seed(seed_value)

        # 保存原始模型名称，用于后续查找本地模型
        original_model_name = model

        if model_name.startswith("Qwen"):
            model_id = f"qwen/{model_name}"
        else:
            model_id = f"Skywork/{model_name}"

        # 首先检查是否存在带有原始名称的模型目录
        original_model_path = os.path.join(folder_paths.models_dir, "LLM", os.path.basename(original_model_name))
        if os.path.exists(original_model_path):
            print(f"使用本地模型: {original_model_path}")
            self.model_checkpoint = original_model_path
        else:
            # 如果不存在原始名称的模型目录，则使用标准路径
            self.model_checkpoint = os.path.join(
                folder_paths.models_dir, "LLM", os.path.basename(model_id)
            )

            if not os.path.exists(self.model_checkpoint):
                from huggingface_hub import snapshot_download
                print(f"从HuggingFace下载模型: {model_id}")
                snapshot_download(
                    repo_id=model_id,
                    local_dir=self.model_checkpoint,
                    local_dir_use_symlinks=False,
                )
            else:
                print(f"使用本地模型: {self.model_checkpoint}")

        if self.processor is None:
            # Define min_pixels and max_pixels:
            # Images will be resized to maintain their aspect ratio
            # within the range of min_pixels and max_pixels.
            min_pixels = 256*28*28
            max_pixels = 1024*28*28 

            self.processor = AutoProcessor.from_pretrained(
                self.model_checkpoint,
                min_pixels=min_pixels,
                max_pixels=max_pixels,
            )

        if self.model is None:
            # Load the model on the available device(s)
            # 检查模型名称是否已经包含量化信息
            is_pre_quantized = any(suffix in original_model_name for suffix in ["-bnb-4bit", "-bnb-8bit"])
            
            if is_pre_quantized:
                print("模型本身已包含量化配置，跳过额外量化设置")
                # 清理GPU内存
                clear_gpu_memory()
                
                # 使用统一的显存不足处理函数
                try:
                    self.model = handle_oom_and_retry(
                        Qwen2_5_VLForConditionalGeneration.from_pretrained,
                        self.model_checkpoint,
                        torch_dtype=torch.bfloat16 if self.bf16_support else torch.float16,
                        device_map=get_optimal_device_map(),
                    )
                    
                    # 检查模型是否被卸载到CPU
                    if hasattr(self.model, 'hf_device_map'):
                        for module_name, device in self.model.hf_device_map.items():
                            if device == 'cpu':
                                print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                                auto_clean_cache_when_oom()
                                error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                                print(error_msg)
                                raise RuntimeError(error_msg)
                                
                except Exception as e:
                    if "Some parameters are on the meta device because they were offloaded to the cpu" in str(e):
                        print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                        auto_clean_cache_when_oom()
                        error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                        print(error_msg)
                        raise RuntimeError(error_msg)
                    else:
                        raise e
            else:
                # 对于非预量化模型，根据用户选择应用量化
                if quantization_type == "4bit":
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        llm_int8_enable_fp32_cpu_offload=True,  # 启用CPU卸载
                    )
                elif quantization_type == "8bit":
                    quantization_config = BitsAndBytesConfig(
                        load_in_8bit=True,
                        llm_int8_enable_fp32_cpu_offload=True,  # 启用CPU卸载
                    )
                else:
                    quantization_config = None

                # 使用统一的显存不足处理函数
                try:
                    self.model = handle_oom_and_retry(
                        Qwen2_5_VLForConditionalGeneration.from_pretrained,
                        self.model_checkpoint,
                        torch_dtype=torch.bfloat16 if self.bf16_support else torch.float16,
                        device_map=get_optimal_device_map(),
                        quantization_config=quantization_config,
                    )
                    
                    # 检查模型是否被卸载到CPU
                    if hasattr(self.model, 'hf_device_map'):
                        for module_name, device in self.model.hf_device_map.items():
                            if device == 'cpu':
                                print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                                auto_clean_cache_when_oom()
                                error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                                print(error_msg)
                                raise RuntimeError(error_msg)
                                
                except Exception as e:
                    if "Some parameters are on the meta device because they were offloaded to the cpu" in str(e):
                        print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                        auto_clean_cache_when_oom()
                        error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                        print(error_msg)
                        raise RuntimeError(error_msg)
                    else:
                        raise e

        with torch.no_grad():
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                    ],
                }
            ]

            if video_file_path:
                print("deal video_path", video_file_path)
                # 使用FFmpeg处理视频
                unique_id = uuid.uuid4().hex  # 生成唯一标识符
                processed_video_path = f"/tmp/processed_video_{unique_id}.mp4"  # 临时文件路径
                ffmpeg_command = [
                    "ffmpeg",
                    "-i", video_file_path,
                    "-vf", "fps=1,scale='min(256,iw)':min'(256,ih)':force_original_aspect_ratio=decrease",
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "18",
                    processed_video_path
                ]
                subprocess.run(ffmpeg_command, check=True)

                # 添加处理后的视频信息到消息
                messages[0]["content"].insert(0, {
                    "type": "video",
                    "video": processed_video_path,
                })

            # 处理图像输入
            else:
                print("deal image")
                pil_image = tensor_to_pil(img)
                messages[0]["content"].insert(0, {
                    "type": "image",
                    "image": pil_image,
                })

            # 准备输入
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            
            # 智能设备分配
            if torch.cuda.is_available():
                inputs = inputs.to("cuda")
            else:
                inputs = inputs.to("cpu")

            # 推理
            try:
                generated_ids = self.model.generate(**inputs, max_new_tokens=max_tokens)
                generated_ids_trimmed = [
                    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                result = self.processor.batch_decode(
                    generated_ids_trimmed,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                    temperature=temp,
                )
            except Exception as e:
                if is_oom_error(str(e)):
                    print("推理过程中检测到显存不足，正在自动清理缓存...")
                    # 自动清理缓存
                    auto_clean_cache_when_oom()
                    
                    # 清理完成后重新尝试推理
                    try:
                        generated_ids = self.model.generate(**inputs, max_new_tokens=max_tokens)
                        generated_ids_trimmed = [
                            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                        ]
                        result = self.processor.batch_decode(
                            generated_ids_trimmed,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,
                            temperature=temp,
                        )
                    except Exception as retry_e:
                        if is_oom_error(str(retry_e)):
                            print("显存GPU不足，已经清除显存占用，请重新运行节点！")
                            return ("显存GPU不足，已经清除显存占用，请重新运行节点！",)
                        else:
                            print(f"推理过程中出错: {str(retry_e)}")
                            return (f"推理过程中出错: {str(retry_e)}",)
                else:
                    print(f"推理过程中出错: {str(e)}")
                    return (f"推理过程中出错: {str(e)}",)

            if not keep_loaded:
                del self.processor
                del self.model
                self.processor = None
                self.model = None
                clear_gpu_memory()

            # 删除临时视频文件
            if video_file_path:
                os.remove(processed_video_path)

            return result


class Qwen2_prompt:
    def __init__(self):
        self.model_checkpoint = None
        self.tokenizer = None
        self.model = None
        self.device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        self.bf16_support = (
            torch.cuda.is_available()
            and torch.cuda.get_device_capability(self.device)[0] >= 8
        )

    @classmethod
    def INPUT_TYPES(s):
        # 动态获取提示词类型列表
        if USE_CUSTOM_PROMPT and CUSTOM_PROMPT_CONFIG:
            # 合并自定义类型和默认类型，避免重复
            custom_types = CUSTOM_PROMPT_CONFIG["prompt_type"]
            default_types = ["视频提示词（多段运镜）", "视频提示词（快速运镜）", "智能扩写"]
            
            # 合并列表，自定义类型在前，默认类型在后，去重
            all_types = []
            for t in custom_types:
                if t not in all_types:
                    all_types.append(t)
            for t in default_types:
                if t not in all_types:
                    all_types.append(t)
            
            prompt_types = all_types
        else:
            # 默认提示词类型
            prompt_types = ["视频提示词（多段运镜）", "视频提示词（快速运镜）", "智能扩写"]
        
        return {
            "required": {
                "user_input": ("STRING", {"default": "", "multiline": True}),
                "prompt_type": (prompt_types, {"default": prompt_types[0]}),
                "model": (
                    [
                        "Qwen2.5-3B-Instruct",
                        "Qwen2.5-3B-Instruct-bnb-4bit",
                        "Qwen2.5-7B-Instruct",
                        "Qwen2.5-7B-Instruct-bnb-4bit",
                        "Qwen2.5-14B-Instruct-bnb-4bit",
                    ],
                    {"default": "Qwen2.5-7B-Instruct-bnb-4bit"},
                ),
                "quantization": (
                    ["none", "4bit", "8bit"],
                    {"default": "none"},
                ),
                "keep_model_loaded": ("BOOLEAN", {"default": False}),
                "temperature": (
                    "FLOAT",
                    {"default": 0.7, "min": 0, "max": 1, "step": 0.1},
                ),
                "seed": ("INT", {"default": -1, "min": -1, "max": 99999}),
                "max_new_tokens": (
                    "INT",
                    {"default": 512, "min": 128, "max": 2048, "step": 1},
                ),
                "output_language": (["english", "中文"], {"default": "english"}),
            },
            "optional": {
                "system_prompt": ("STRING",),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "inference"
    CATEGORY = "tools_zero"

    def inference(
        self,
        user_input,
        prompt_type,
        model,
        quantization,
        keep_model_loaded,
        temperature,
        seed,
        max_new_tokens,
        output_language,
        system_prompt=None,
    ):
        # 检查是否提供了系统提示词
        if system_prompt and system_prompt.strip():
            # 如果提供了系统提示词，直接使用它，忽略prompt_type
            print("检测到系统提示词输入，将使用自定义系统提示词")
            prompt = system_prompt.format(user_input=user_input) if "{user_input}" in system_prompt else system_prompt
        else:
            # 如果没有提供系统提示词，使用原有的prompt_type逻辑
            language_suffix = "输出提示词必须全部为中文。" if output_language == "中文" else "输出提示词必须全部为英文。"
            
            # 构建提示词映射
            prompt_map = {}
            
            # 首先添加自定义配置（如果存在）
            if USE_CUSTOM_PROMPT and CUSTOM_PROMPT_CONFIG:
                custom_prompt_map = CUSTOM_PROMPT_CONFIG["prompt_map"]
                # 将自定义模板中的占位符替换为实际值
                for key, template in custom_prompt_map.items():
                    prompt_map[key] = template.format(
                        user_input=user_input,
                        language_suffix=language_suffix
                    )
            
            # 然后添加默认配置（如果自定义配置中没有的话）
            if "视频提示词（多段运镜）" not in prompt_map:
                prompt_map["视频提示词（多段运镜）"] = (
                    f"你是一位Prompt优化师，根据用户输入的\"{user_input}\"，在不改变用户输入原意的情况下进行改写；"
                    f"任务要求：1. 根据用户的输入，合理推断并补充细节；"
                    f"2.改写后的prompt字数控制在256字左右，不要做任何不必要的输出，只输出提示词部分；"
                    f"3.内容=主体（主体描述）+ 场景（场景描述）+ 运动（运动描述）+ 美学控制 + 风格化"
                    f"主体描述：主体描述是对主体外观特征细节的描述，可通过形容词或短句列举，例如\"一位身着少数民族服饰的黑发苗族少女\"、\"一位来自异世界的飞天仙子，身着破旧却华丽的服饰，背后展开一对由废墟碎片构成的奇异翅膀\"。只是参考，不要完全照搬。"
                    f"场景描述：场景描述需要对整个场景的镜头和运动产生的内容变化进行描述。"
                    f"运动描述：运动描述是对运动特征细节的描述，包含运动的幅度、速率和运动作用的效果，例如\"猛烈地摇摆\"、\"缓慢地移动\"、\"打碎了玻璃\"。"
                    f"美学控制：包含光源、光线环境、景别、视角、镜头、运镜等，常见镜头语言。"
                    f"风格化：风格化是对画面风格语言的描述，例如\"赛博朋克\"、\"勾线插画\"、\"废土风格\"。"
                    f"4.提示词格式参考：\"古风女子身着传统汉服，立于古典长廊中。0-1.5秒：镜头从精致的发型和发饰特写开始，挽起的发髻几缕碎发被微风拂动，尽显灵动，随后镜头缓慢下移，展示女子的肩部和外袍上的金色花纹刺绣。1.5-4秒：镜头切换至侧后方，以平滑的追踪运镜展现女子微微侧身的姿态，双手轻握在身前，外袍袖口处白色花纹在微风中飘动，裙摆层层叠叠，带有红色花纹装饰，背景古典长廊的木质立柱在移动中逐渐显露出其古朴质感。4-5秒：镜头仰视追随女子缓缓抬头的动作，阳光透过长廊的屋檐洒下，照亮她清秀的面容，神情温柔且坚定，远处山水在虚化中若隐若现，营造出宁静而唯美的氛围。（衣摆飘动/发丝飘动），8K细节锐化，超现实主义风格，色彩柔和且真实，织物纹理分明，光泽感强，氛围感十足，仿佛置身于古代画卷之中。以上仅做参考，不要完全照搬；\""
                    f"(0-1.5秒)： 镜头以长征五号火箭引擎喷口特写为起点，液氢液氧推进剂喷涌的蓝色火焰；镜头沿箭体弧形上掠90°，掠过箭体'中国航天'标识，展现箭体蓄势震颤的姿态，(1.5-4秒)： 镜头瞬切至侧后方黄金追随位，与火箭同步垂直攀升，捕捉长征五号突破音障的锥形云环；整流罩反射朝阳金光，助推器分离瞬间的金属碎片在真空中悬浮（动态速率：1.5秒缓加速至3倍音速模拟），(4-5秒)： 镜头仰视追随火箭刺入苍穹，尾焰在稀薄大气中膨胀为巨型羽流；背景地球弧线显现，整流罩分离后露出深空探测器，箭体化作星轨冲向日冕级耀斑。助推器脱离时液压杆机械运动特写，螺栓爆炸螺栓触发火星四溅。海南文昌发射场黎明，椰子林被冲击波压低，摄像机震动尘埃飞扬；太空段背景为银河与晨昏线地球。（尾焰膨胀/碎片失重），8K细节锐化，以上仅做参考，不要完全照搬；"   
                    f"5. 在不改变用户输入原意的情况下进行改写，主体、场景、运动、美学控制和风格化部分需有机融合在语段中；{language_suffix}"
                )

            if "视频提示词（快速运镜）" not in prompt_map:
                prompt_map["视频提示词（快速运镜）"] = (
                    f"你是一位Prompt优化师，根据用户输入的\"{user_input}\"，在不改变用户输入原意的情况下进行改写；"
                    f"任务要求：1. 根据用户的输入，合理推断并补充细节；"
                    f"2.改写后的prompt字数控制在256字左右，不要做任何不必要的输出，只输出提示词部分；"
                    f"3.内容=主体（主体描述）+ 场景（场景描述）+ 运动（运动描述）+ 美学控制 + 风格化"
                    f"主体描述：主体描述是对主体外观特征细节的描述，可通过形容词或短句列举，例如\"一位身着少数民族服饰的黑发苗族少女\"、\"一位来自异世界的飞天仙子，身着破旧却华丽的服饰，背后展开一对由废墟碎片构成的奇异翅膀\"。只是参考，不要完全照搬。"
                    f"场景描述：场景描述需要对整个场景的镜头和运动产生的内容变化进行描述，例如\"从外太空开始，镜头快速穿越宇宙星云和行星，进入地球大气层，经过田野、森林和山脉，最终定格在自然场景中，阳光透过薄雾洒下，地面有草地和泥土纹理。\"只是参考，不要完全照搬。"
                    f"运动描述：运动描述是对运动特征细节的描述，包含运动的幅度、速率和运动作用的效果，例如\"猛烈地摇摆\"、\"缓慢地移动\"、\"打碎了玻璃\"。镜头快速推进，速度逐渐减缓，最终聚焦在猫的特写上，猫的动作和表情被捕捉得清晰且充满动态感。\"只是参考，不要完全照搬。"
                    f"美学控制：包含光源、光线环境、景别、视角、镜头、运镜等，常见镜头语言。"
                    f"风格化：风格化是对画面风格语言的描述，例如\"赛博朋克\"、\"勾线插画\"、\"废土风格\"。"
                    f"4. 在不改变用户输入原意的情况下进行改写，主体、场景、运动、美学控制和风格化部分需有机融合在语段中；{language_suffix}"
                )
                    
            if "智能扩写" not in prompt_map:
                prompt_map["智能扩写"] = (  
                    f"请基于以下输入内容进行创意扩展：\"{user_input}\"。"
                    f"要求：1. 保留原文核心信息，进行有针对性的扩展；"
                    f"2. 不要做任何不必要的输出，只输出扩写的提示词部分；"
                    f"3. 扩展内容要符合逻辑，与原文风格一致；"
                    f"4. 需要有背景，光影，氛围，主体描述，构图，质量词等信息；"
                    f"5. 保留原文核心信息的情况下，可以适当调整句式，增加描述性和生动性。{language_suffix}"
                )
            
            # 确保提示类型存在于映射中，如果不存在则使用默认提示
            if prompt_type not in prompt_map:
                print(f"警告：提示类型 '{prompt_type}' 不存在，使用默认的'智能扩写'提示类型")
                prompt_type = "智能扩写"
                
            prompt = prompt_map[prompt_type]
 
        # 处理种子参数，确保它是一个有效的整数
        seed_value = -1  # 默认值
        
        # 检查种子是否为None或NaN
        if seed is None or seed == "NaN":
            print(f"使用默认种子值: -1 (随机)")
        else:
            try:
                seed_value = int(seed)
                print(f"使用种子值: {seed_value}")
            except (ValueError, TypeError):
                print(f"警告: 无效的种子值 '{seed}', 使用默认值 -1")
                
        if seed_value != -1:
            torch.manual_seed(seed_value)
        
        # 处理特殊模型名称
        is_bnb_4bit = False
        original_model_name = model  # 保存原始模型名称
        if "-bnb-4bit" in model:
            is_bnb_4bit = True
            model_name = model.replace("-bnb-4bit", "")
            print(f"检测到4bit量化模型，将使用: {model_name}")
        else:
            model_name = model
            
        # 首先检查是否存在带有原始名称的模型目录
        original_model_path = os.path.join(folder_paths.models_dir, "LLM", os.path.basename(original_model_name))
        if os.path.exists(original_model_path):
            print(f"使用本地模型: {original_model_path}")
            self.model_checkpoint = original_model_path
        else:
            # 如果不存在原始名称的模型目录，则使用标准路径
            model_id = f"qwen/{model_name}"
            self.model_checkpoint = os.path.join(
                folder_paths.models_dir, "LLM", os.path.basename(model_id)
            )

            if not os.path.exists(self.model_checkpoint):
                from huggingface_hub import snapshot_download
                print(f"从HuggingFace下载模型: {model_id}")
                snapshot_download(
                    repo_id=model_id,
                    local_dir=self.model_checkpoint,
                    local_dir_use_symlinks=False,
                )
            else:
                print(f"使用本地模型: {self.model_checkpoint}")

        if self.tokenizer is None:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_checkpoint)

        if self.model is None:
            # Load the model on the available device(s)
            # 如果模型名称包含 -bnb-4bit，说明模型本身已经量化，不需要额外的量化配置
            if is_bnb_4bit:
                print("模型本身已包含4bit量化配置，跳过额外量化设置")
                # 清理GPU内存
                clear_gpu_memory()
                
                # 使用统一的显存不足处理函数
                try:
                    self.model = handle_oom_and_retry(
                        AutoModelForCausalLM.from_pretrained,
                        self.model_checkpoint,
                        torch_dtype=torch.bfloat16 if self.bf16_support else torch.float16,
                        device_map=get_optimal_device_map(),
                    )
                    
                    # 检查模型是否被卸载到CPU
                    if hasattr(self.model, 'hf_device_map'):
                        for module_name, device in self.model.hf_device_map.items():
                            if device == 'cpu':
                                print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                                auto_clean_cache_when_oom()
                                error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                                print(error_msg)
                                raise RuntimeError(error_msg)
                                
                except Exception as e:
                    if "Some parameters are on the meta device because they were offloaded to the cpu" in str(e):
                        print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                        auto_clean_cache_when_oom()
                        error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                        print(error_msg)
                        raise RuntimeError(error_msg)
                    else:
                        raise e
            else:
                # 对于非预量化模型，根据用户选择应用量化
                if quantization == "4bit":
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        llm_int8_enable_fp32_cpu_offload=True,  # 启用CPU卸载
                    )
                elif quantization == "8bit":
                    quantization_config = BitsAndBytesConfig(
                        load_in_8bit=True,
                        llm_int8_enable_fp32_cpu_offload=True,  # 启用CPU卸载
                    )
                else:
                    quantization_config = None

                # 使用统一的显存不足处理函数
                try:
                    self.model = handle_oom_and_retry(
                        AutoModelForCausalLM.from_pretrained,
                        self.model_checkpoint,
                        torch_dtype=torch.bfloat16 if self.bf16_support else torch.float16,
                        device_map=get_optimal_device_map(),
                        quantization_config=quantization_config,
                    )
                    
                    # 检查模型是否被卸载到CPU
                    if hasattr(self.model, 'hf_device_map'):
                        for module_name, device in self.model.hf_device_map.items():
                            if device == 'cpu':
                                print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                                auto_clean_cache_when_oom()
                                error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                                print(error_msg)
                                raise RuntimeError(error_msg)
                                
                except Exception as e:
                    if "Some parameters are on the meta device because they were offloaded to the cpu" in str(e):
                        print("检测到模型参数被卸载到CPU，显存不足，正在清理...")
                        auto_clean_cache_when_oom()
                        error_msg = "显存GPU不足，已经清除显存占用，请重新运行节点！"
                        print(error_msg)
                        raise RuntimeError(error_msg)
                    else:
                        raise e

        with torch.no_grad():
            messages = [
                {"role": "user", "content": prompt},
            ]

            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            inputs = self.tokenizer([text], return_tensors="pt")
            
            # 智能设备分配
            if torch.cuda.is_available():
                inputs = inputs.to("cuda")
            else:
                inputs = inputs.to("cpu")

            try:
                generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
                generated_ids_trimmed = [
                    out_ids[len(in_ids) :]
                    for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                result = self.tokenizer.batch_decode(
                    generated_ids_trimmed,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                    temperature=temperature,
                )
            except Exception as e:
                if is_oom_error(str(e)):
                    print("推理过程中检测到显存不足，正在自动清理缓存...")
                    # 自动清理缓存
                    auto_clean_cache_when_oom()
                    
                    # 清理完成后重新尝试推理
                    try:
                        generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
                        generated_ids_trimmed = [
                            out_ids[len(in_ids) :]
                            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                        ]
                        result = self.tokenizer.batch_decode(
                            generated_ids_trimmed,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,
                            temperature=temperature,
                        )
                    except Exception as retry_e:
                        if is_oom_error(str(retry_e)):
                            print("显存GPU不足，已经清除显存占用，请重新运行节点！")
                            return ("显存GPU不足，已经清除显存占用，请重新运行节点！",)
                        else:
                            print(f"推理过程中出错: {str(retry_e)}")
                            return (f"推理过程中出错: {str(retry_e)}",)
                else:
                    print(f"推理过程中出错: {str(e)}")
                    return (f"推理过程中出错: {str(e)}",)

            if not keep_model_loaded:
                del self.tokenizer
                del self.model
                self.tokenizer = None
                self.model = None
                clear_gpu_memory()

            return result
