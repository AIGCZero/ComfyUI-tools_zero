class Wan_Prompt:

    # 提示词数据
    PROMPT_DATA = {
        "光源类型": ["日光", "人工光", "月光", "火光", "荧光", "烛光", "霓虹灯", "汽车灯", "星光"],
        "光线类型": ["阴天光", "混合光", "晴天光", "柔光", "硬光", "顶光", "侧光", "背光", "底光", "边缘光", "剪影", "低对比度", "高对比度", "直射光", "散射光", "环境光"],
        "时间段": ["白天", "夜晚", "黄昏", "日落", "黎明", "日出", "上午", "中午", "下午"],
        "景别": ["特写", "近景", "中近景","中景", "中远景", "全景", "远景"],
        "构图类型": ["中心构图", "平衡构图", "侧重构图", "对称构图", "短边构图", "三分法构图", "井字构图", "三角形构图"],
        "镜头描述": ["中标距", "广角", "长焦", "望远", "超广角", "鱼眼机位", "全景镜头", "单人镜头", "双人镜头", "群像镜头", "定场镜头", "无人机镜头", "航拍镜头"],
        "镜头角度": ["尖角度", "高角度", "低角度", "倾斜角度", "航拍俯视角度", "仰角度", "俯角度"],
        "色调": ["暖色调", "冷色调", "高饱和度", "低饱和度", "中性色调", "金属色调", "明亮色调"],
        "运动描述": ["跳霹雳舞", "跑步", "滑滑板", "踢足球", "网球", "乒乓", "滑雪", "篮球", "跳现代舞", "跳民族舞", "骑自行车", "游泳", "击剑", "攀岩", "登山"],
        "人物情绪": ["愤怒", "恐惧", "高兴", "悲伤", "惊讶", "焦虑", "沮丧", "平静", "期待", "兴奋", "嫉妒"],
        "基础运镜": ["镜头推进", "镜头拉远", "镜头向右移动", "镜头向左移动", "镜头上摇", "镜头下摇", "手持镜头", "复合运镜", "跟随镜头", "环绕运镜", "摇镜头", "移镜头", "跟镜头", "快速穿越", ],
        "运镜速度": [ "缓慢地", "悠闲地", "舒缓地", "快速地", "急促地", "急速地"],
        "视觉风格": ["毛毡风格", "3D卡通", "像素风格", "木偶动画", "3D游戏", "黄土风格", "二次元水彩画", "黑白动画", "油画风格", "水彩风格", "素描风格", "剪纸风格", "玻璃画风格", "赛博朋克风格", "蒸汽朋克风格", "奇幻风格", "武侠风格", "写实风格"],
        "特效镜头": ["移轴摄影", "延时拍摄", "慢动作拍摄", "快动作拍摄", "多重曝光", "希区柯克变焦", "希区柯克推进", "希区柯克拉远"]
    }
    
    # 随机提示词类型列表
    RANDOM_CATEGORIES = ["光源类型", "光线类型", "时间段", "景别", "基础运镜", "色调", "运镜速度"]

    @classmethod
    def INPUT_TYPES(cls):
        # 创建每个类别的选择列表
        inputs = {
            "required": {
                "用户输入": ("STRING", {"default": "", "multiline": True}),
                "开启随机提示词": (["否", "是"], {"default": "否"}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 99999}),
            },
            "optional": {
                # 所有类别作为可选输入
                "光源类型": (["none"] + cls.PROMPT_DATA["光源类型"], {"default": "none"}),
                "光线类型": (["none"] + cls.PROMPT_DATA["光线类型"], {"default": "none"}),
                "时间段": (["none"] + cls.PROMPT_DATA["时间段"], {"default": "none"}),
                "景别": (["none"] + cls.PROMPT_DATA["景别"], {"default": "none"}),
                "构图类型": (["none"] + cls.PROMPT_DATA["构图类型"], {"default": "none"}),
                "镜头描述": (["none"] + cls.PROMPT_DATA["镜头描述"], {"default": "none"}),
                "镜头角度": (["none"] + cls.PROMPT_DATA["镜头角度"], {"default": "none"}),
                "色调": (["none"] + cls.PROMPT_DATA["色调"], {"default": "none"}),
                "运动描述": (["none"] + cls.PROMPT_DATA["运动描述"], {"default": "none"}),
                "人物情绪": (["none"] + cls.PROMPT_DATA["人物情绪"], {"default": "none"}),
                "基础运镜": (["none"] + cls.PROMPT_DATA["基础运镜"], {"default": "none"}),
                "运镜速度": (["none"] + cls.PROMPT_DATA["运镜速度"], {"default": "none"}),
                "视觉风格": (["none"] + cls.PROMPT_DATA["视觉风格"], {"default": "none"}),
                "特效镜头": (["none"] + cls.PROMPT_DATA["特效镜头"], {"default": "none"}),                
            }
        }
        
        return inputs
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "Wan_Prompt"
    CATEGORY = "tools_zero"
    
    def Wan_Prompt(self, 用户输入="", 开启随机提示词="否", seed=-1, **kwargs):
        """根据选择生成视频提示词"""
        import random
        
        # 设置随机种子，如果指定了种子值
        original_state = None
        if seed != -1:
            original_state = random.getstate()  # 保存当前随机状态
            random.seed(seed)
        
        # 收集用户手动选择的提示词
        user_selections = {}
        selected_categories = set()
        
        for category, value in kwargs.items():
            if category in self.PROMPT_DATA and value != "none":
                user_selections[category] = value
                selected_categories.add(category)
        
        # 生成最终的提示词部分
        final_parts = []
        
        # 处理运镜速度和基础运镜的组合变量
        camera_movement_speed = None
        basic_camera_movement = None
        
        # 处理随机提示词和用户选择
        if 开启随机提示词 == "是":
            # 预先为所有随机类别生成随机选择结果
            random_selections = {}
            for category in self.RANDOM_CATEGORIES:
                random_selections[category] = random.choice(self.PROMPT_DATA[category])
            
            # 用户选择会覆盖随机选择的结果
            for category, value in user_selections.items():
                if category in self.RANDOM_CATEGORIES:
                    random_selections[category] = value
                else:
                    # 非随机类别的用户选择直接添加，除了运镜速度和基础运镜
                    if category != "运镜速度" and category != "基础运镜":
                        final_parts.append(value)
                    elif category == "运镜速度":
                        camera_movement_speed = value
                    elif category == "基础运镜":
                        basic_camera_movement = value
            
            # 添加所有随机类别的结果（可能包含用户选择的覆盖），除了运镜速度和基础运镜
            for category in self.RANDOM_CATEGORIES:
                if category in random_selections:
                    if category == "运镜速度":
                        camera_movement_speed = random_selections[category]
                    elif category == "基础运镜":
                        basic_camera_movement = random_selections[category]
                    else:
                        final_parts.append(random_selections[category])
        else:
            # 如果不启用随机提示词，收集所有用户选择，特殊处理运镜速度和基础运镜
            for category, value in user_selections.items():
                if category == "运镜速度":
                    camera_movement_speed = value
                elif category == "基础运镜":
                    basic_camera_movement = value
                else:
                    final_parts.append(value)
        
        # 处理运镜速度和基础运镜的组合
        if camera_movement_speed and basic_camera_movement:
            # 如果两者都有，组合它们（运镜速度在前，基础运镜在后，中间不加逗号）
            final_parts.append(camera_movement_speed + basic_camera_movement)
        else:
            # 如果只有其中一个，单独添加
            if camera_movement_speed:
                final_parts.append(camera_movement_speed)
            if basic_camera_movement:
                final_parts.append(basic_camera_movement)
        
        # 添加用户输入（放在最后）
        if 用户输入.strip():
            final_parts.append(用户输入.strip())
        
        # 恢复随机状态，避免影响其他使用随机数的节点
        if original_state:
            random.setstate(original_state)
        
        # 组合提示词
        final_prompt = "，".join(final_parts) if final_parts else ""
        
        return (final_prompt,)

# 节点注册
NODE_CLASS_MAPPINGS = {
    "Wan_Prompt": Wan_Prompt
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Wan_Prompt": "万相提示词"
}
