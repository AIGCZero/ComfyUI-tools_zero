import torch
import time
import random
import numpy as np
from PIL import Image, ImageFont, ImageDraw, ImageColor
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "ComfyUI"))

class TextImage:
    def __init__(self):
        self.NODE_NAME = 'TextImage'

    @classmethod
    def INPUT_TYPES(cls):
        # 获取字体目录
        font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'fonts')
        if not os.path.exists(font_path):
            os.makedirs(font_path, exist_ok=True)
            
        font_files = []
        for file in os.listdir(font_path):
            if file.lower().endswith(('.ttf', '.otf')):
                font_files.append(file)
                
        if not font_files:
            font_files = ["Arial.ttf"]  # 默认字体，用户需要自己添加

        layout_list = ['horizontal', 'vertical']
        random_seed = int(time.time())
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "Text"}),
                "font_file": (font_files,),
                "spacing": ("INT", {"default": 0, "min": -9999, "max": 9999, "step": 1}),
                "leading": ("INT", {"default": 0, "min": -9999, "max": 9999, "step": 1}),
                "x_offset": ("INT", {"default": 0, "min": -9999, "max": 9999, "step": 1}),
                "y_offset": ("INT", {"default": 0, "min": -9999, "max": 9999, "step": 1}),
                "scale": ("FLOAT", {"default": 80, "min": 0.1, "max": 999, "step": 0.01}),
                "variation_range": ("INT", {"default": 0, "min": 0, "max": 100, "step": 1}),
                "variation_seed": ("INT", {"default": random_seed, "min": 0, "max": 999999999999, "step": 1}),
                "layout": (layout_list,),
                "width": ("INT", {"default": 512, "min": 4, "max": 999999, "step": 1}),
                "height": ("INT", {"default": 512, "min": 4, "max": 999999, "step": 1}),
                "font_color": ("COLOR", {"default": "#000000"}),
                "background_color": ("COLOR", {"default": "#FFFFFF"}),
                "h_align": (["left", "center", "right"], {"default": "center"}),
                "v_align": (["top", "center", "bottom"], {"default": "center"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK",)
    RETURN_NAMES = ("图像", "遮罩",)
    FUNCTION = 'text_image'
    CATEGORY = 'tools_zero'
    
    def random_numbers(self, total, random_range=10, seed=None, sum_of_numbers=0):
        if seed is not None:
            random.seed(seed)
        
        numbers = [random.randint(-random_range, random_range) for _ in range(total)]
        
        # 如果需要让这些数字加起来为指定值
        if sum_of_numbers is not None:
            current_sum = sum(numbers)
            diff = sum_of_numbers - current_sum
            adjustment = diff // total
            
            for i in range(total):
                numbers[i] += adjustment
            
            # 处理余数
            remainder = diff - adjustment * total
            for i in range(remainder):
                numbers[i] += 1
        
        return numbers
    
    def convert_to_rgba(self, rgb_image, mask):
        rgba = rgb_image.copy()
        rgba.putalpha(mask.convert('L'))
        return rgba

    def text_image(self, text, font_file, spacing, leading, x_offset, y_offset, scale,
                    variation_range, variation_seed, layout, width, height, font_color, background_color,
                    h_align, v_align):
        """
        生成文本图像
        
        参数:
            text: 要显示的文本
            font_file: 字体文件
            spacing: 字符间距
            leading: 行距
            x_offset: X轴偏移（像素）
            y_offset: Y轴偏移（像素）
            scale: 整体缩放比例
            variation_range: 随机变化范围
            variation_seed: 随机种子
            layout: 布局方式（水平/垂直）
            width: 图像宽度
            height: 图像高度
            font_color: 字体颜色
            background_color: 背景颜色
            h_align: 水平对齐方式
            v_align: 垂直对齐方式
        """
        # 获取字体路径
        font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'fonts')
        font_path = os.path.join(font_dir, font_file)
        
        if not os.path.exists(font_path):
            print(f"[TextImage] 警告：字体文件 {font_path} 不存在，尝试使用系统字体")
            try:
                # 尝试使用PIL默认字体
                font = ImageFont.load_default()
            except:
                raise Exception(f"无法加载字体 {font_file}")
        else:
            try:
                # 尝试加载字体用于后续计算
                test_font = ImageFont.truetype(font_path, 100)  # 使用100pt作为测试大小
            except:
                test_font = ImageFont.load_default()
                
        # 处理文本行
        text_table = []
        max_char_in_line = 0
        total_char = 0
        lines = []
        text_lines = text.split("\n")
        for l in text_lines:
            if len(l) > 0:
                lines.append(l)
                total_char += len(l)
                if len(l) > max_char_in_line:
                    max_char_in_line = len(l)
            else:
                lines.append(" ")
                
        # 防止空文本情况
        if max_char_in_line == 0:
            max_char_in_line = 1
        if len(lines) == 0:
            lines = [" "]

        # 计算字符大小（基于整个画布）
        if layout == 'vertical':
            char_horizontal_size = width // max(1, len(lines))
            char_vertical_size = height // max(1, max_char_in_line)
            char_size = min(char_horizontal_size, char_vertical_size)
        else:
            char_horizontal_size = width // max(1, max_char_in_line)
            char_vertical_size = height // max(1, len(lines))
            char_size = min(char_horizontal_size, char_vertical_size)

        # 根据缩放比例调整字符大小
        char_size = int(char_size * scale / 100)
        spacing = int(spacing * scale / 100)
        leading = int(leading * scale / 100)
        
        # 获取字符实际尺寸
        def get_text_dimensions(text, font):
            try:
                if hasattr(font, 'getbbox'):
                    bbox = font.getbbox(text)
                    return bbox[2] - bbox[0], bbox[3] - bbox[1]
                else:
                    return font.getsize(text)
            except:
                # 如果无法获取确切尺寸，使用估算值
                return len(text) * char_size, char_size
        
        # 计算每行/列的实际尺寸
        lines_dimensions = []
        max_line_width = 0
        total_height = 0
        
        for line in lines:
            try:
                font = ImageFont.truetype(font_path, char_size)
            except:
                font = ImageFont.load_default()
                
            line_width, line_height = get_text_dimensions(line, font)
            
            if layout == 'horizontal':
                # 水平布局：考虑间距
                if len(line) > 1:
                    line_width += spacing * (len(line) - 1)
                max_line_width = max(max_line_width, line_width)
                lines_dimensions.append((line_width, line_height))
                total_height += line_height
            else:
                # 垂直布局
                if len(line) > 1:
                    line_height += spacing * (len(line) - 1)
                lines_dimensions.append((line_width, line_height))
                max_line_width = max(max_line_width, line_width)
                total_height += line_height
        
        # 添加行间距
        if layout == 'horizontal' and len(lines) > 1:
            total_height += leading * (len(lines) - 1)
        
        # 计算整个文本区域的宽高
        text_width = max_line_width
        text_height = total_height
        
        # 确保文本不超出画布
        if text_width > width:
            # 等比缩小字体
            scale_factor = width / text_width
            char_size = int(char_size * scale_factor)
            spacing = int(spacing * scale_factor)
            leading = int(leading * scale_factor)
            
            # 重新计算
            lines_dimensions = []
            max_line_width = 0
            total_height = 0
            
            for line in lines:
                try:
                    font = ImageFont.truetype(font_path, char_size)
                except:
                    font = ImageFont.load_default()
                    
                line_width, line_height = get_text_dimensions(line, font)
                
                if layout == 'horizontal':
                    if len(line) > 1:
                        line_width += spacing * (len(line) - 1)
                    max_line_width = max(max_line_width, line_width)
                    lines_dimensions.append((line_width, line_height))
                    total_height += line_height
                else:
                    if len(line) > 1:
                        line_height += spacing * (len(line) - 1)
                    lines_dimensions.append((line_width, line_height))
                    max_line_width = max(max_line_width, line_width)
                    total_height += line_height
            
            if layout == 'horizontal' and len(lines) > 1:
                total_height += leading * (len(lines) - 1)
            
            text_width = max_line_width
            text_height = total_height
            
        if text_height > height:
            # 等比缩小字体
            scale_factor = height / text_height
            char_size = int(char_size * scale_factor)
            spacing = int(spacing * scale_factor)
            leading = int(leading * scale_factor)
            
            # 重新计算
            lines_dimensions = []
            max_line_width = 0
            total_height = 0
            
            for line in lines:
                try:
                    font = ImageFont.truetype(font_path, char_size)
                except:
                    font = ImageFont.load_default()
                    
                line_width, line_height = get_text_dimensions(line, font)
                
                if layout == 'horizontal':
                    if len(line) > 1:
                        line_width += spacing * (len(line) - 1)
                    max_line_width = max(max_line_width, line_width)
                    lines_dimensions.append((line_width, line_height))
                    total_height += line_height
                else:
                    if len(line) > 1:
                        line_height += spacing * (len(line) - 1)
                    lines_dimensions.append((line_width, line_height))
                    max_line_width = max(max_line_width, line_width)
                    total_height += line_height
            
            if layout == 'horizontal' and len(lines) > 1:
                total_height += leading * (len(lines) - 1)
            
            text_width = max_line_width
            text_height = total_height

        # 根据对齐方式计算起始位置
        if h_align == "left":
            start_x = 0
        elif h_align == "center":
            start_x = (width - text_width) // 2
        else:  # right
            start_x = width - text_width

        if v_align == "top":
            start_y = 0
        elif v_align == "center":
            start_y = (height - text_height) // 2
        else:  # bottom
            start_y = height - text_height
            
        # 应用偏移
        start_x += x_offset
        start_y += y_offset
            
        # 初始字符位置
        current_x = start_x
        current_y = start_y

        # 计算每个字符的位置和大小
        for i in range(len(lines)):
            line_table = []
            line_text = lines[i]
            line_width, line_height = lines_dimensions[i]
            
            # 创建用于当前行的字体
            try:
                font = ImageFont.truetype(font_path, char_size)
            except:
                font = ImageFont.load_default()
            
            # 随机变化因子
            line_random = self.random_numbers(total=len(line_text),
                                         random_range=int(char_size * variation_range / 25),
                                         seed=variation_seed+i, sum_of_numbers=0)
            
            # 设置行起始位置
            if layout == 'vertical':
                # 重新计算每个字符在垂直布局中的尺寸
                column_width = lines_dimensions[i][0]
                column_height = 0
                column_chars = []
                
                # 首先计算所有字符的高度，并存储起来
                for j in range(len(line_text)):
                    # 应用可能的随机变化到字体大小
                    font_size_variation = 0
                    if variation_range > 0:
                        font_size_variation = line_random[j]
                        try:
                            char_font = ImageFont.truetype(font_path, char_size + font_size_variation)
                        except:
                            char_font = font
                        char_width, char_height = get_text_dimensions(line_text[j], char_font)
                    else:
                        char_width, char_height = get_text_dimensions(line_text[j], font)
                    
                    column_chars.append((char_width, char_height))
                    column_height += char_height
                
                # 添加字符间距到总高度
                if len(line_text) > 1:
                    column_height += spacing * (len(line_text) - 1)
                
                # 计算所有列的总宽度(每列宽度+列间距)
                total_width = 0
                for j in range(len(lines)):
                    if j < len(lines_dimensions):
                        total_width += lines_dimensions[j][0]
                        if j < len(lines) - 1:  # 最后一列后面不加间距
                            total_width += spacing
                
                # 根据水平对齐计算水平位置
                if h_align == "center":
                    # 总宽度居中
                    base_x = (width - total_width) // 2
                elif h_align == "right":
                    # 总宽度右对齐
                    base_x = width - total_width
                else:  # left
                    base_x = 0
                
                # 计算当前列的起始x位置
                current_x = base_x
                for j in range(i):
                    if j < len(lines_dimensions):
                        current_x += lines_dimensions[j][0] + spacing
                
                # 应用x偏移
                current_x += x_offset
                
                # 行内垂直对齐 - 不使用start_y，直接计算垂直位置
                if v_align == "center":
                    current_y = (height - column_height) // 2
                elif v_align == "bottom":
                    current_y = height - column_height
                else:  # top
                    current_y = 0
                
                # 应用y偏移
                current_y += y_offset
            else:
                if i > 0:
                    current_y += lines_dimensions[i-1][1] + leading
                
                # 行内水平对齐
                if h_align == "center":
                    current_x = start_x + (text_width - line_width) // 2
                elif h_align == "right":
                    current_x = start_x + text_width - line_width
                else:  # left
                    current_x = start_x
            
            # 绘制每个字符
            for j in range(len(line_text)):
                char = line_text[j]
                
                # 单字符尺寸
                char_width, char_height = get_text_dimensions(char, font)
                
                # 应用随机变化
                font_size_variation = 0
                if variation_range > 0:
                    font_size_variation = line_random[j]
                    # 重新创建字体
                    try:
                        char_font = ImageFont.truetype(font_path, char_size + font_size_variation)
                    except:
                        char_font = font
                    
                    # 重新计算尺寸
                    char_width, char_height = get_text_dimensions(char, char_font)
                else:
                    char_font = font
                
                # 计算字符位置
                if layout == 'vertical':
                    axis_x = current_x + (column_width - char_width) // 2
                else:
                    axis_x = current_x
                
                if variation_range > 0:
                    offset_x = int(font_size_variation * variation_range / 250)
                    offset_y = int(font_size_variation * variation_range / 250)
                    axis_x = axis_x + (offset_x if random.random() > 0.5 else -offset_x)
                    axis_y = current_y + (offset_y if random.random() > 0.5 else -offset_y)
                else:
                    axis_y = current_y
                
                char_dict = {'char': char,
                            'axis': (axis_x, axis_y),
                            'font': char_font,
                            'size': char_size + font_size_variation}
                line_table.append(char_dict)
                
                # 更新下一个字符的位置
                if layout == 'vertical':
                    if j < len(line_text) - 1:
                        # 使用预先计算的字符高度
                        current_y += char_height + spacing
                else:
                    current_x += char_width + spacing
                    
            text_table.append(line_table)

        # 绘制字符
        _mask = Image.new('RGB', size=(width, height), color='black')
        draw = ImageDraw.Draw(_mask)
        for l in range(len(text_table)):
            for c in range(len(text_table[l])):
                char_dict = text_table[l][c]
                draw.text(char_dict.get('axis'), char_dict.get('char'), 
                         font=char_dict.get('font', font), fill='white')

        # 处理颜色
        try:
            if isinstance(font_color, str):
                font_color_rgb = ImageColor.getrgb(font_color)
            else:
                font_color_rgb = font_color
                
            if isinstance(background_color, str):
                bg_color_rgb = ImageColor.getrgb(background_color)
            else:
                bg_color_rgb = background_color
        except ValueError:
            font_color_rgb = (255, 160, 0)  # 默认橙色
            bg_color_rgb = (255, 255, 255)  # 默认白色

        # 创建最终图像
        _canvas = Image.new('RGB', size=(width, height), color=bg_color_rgb)
        _color = Image.new('RGB', size=(width, height), color=font_color_rgb)
        _canvas.paste(_color, mask=_mask.convert('L'))
        _canvas = self.convert_to_rgba(_canvas, _mask)
        
        # 转换为tensor格式
        image_tensor = torch.from_numpy(np.array(_canvas).astype(np.float32) / 255.0).unsqueeze(0)
        mask_tensor = torch.from_numpy(np.array(_mask.convert('L')).astype(np.float32) / 255.0).unsqueeze(0)
        
        print(f"[TextImage] 文本图像生成完成，X偏移={x_offset}，Y偏移={y_offset}")
        return (image_tensor, mask_tensor)

NODE_CLASS_MAPPINGS = {
    "文本图像": TextImage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "文本图像": "文本图像"
}
