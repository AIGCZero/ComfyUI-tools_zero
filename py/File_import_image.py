import hashlib
import os
import torch
import numpy as np
import re
from PIL import Image, ImageOps

class File_import_image:
    # Dictionary to store folder hashes
    folder_hashes = {}
    
    @staticmethod
    def natural_sort_key(s):
        """用于自然排序的键函数，正确处理文件名中的数字"""
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', os.path.basename(s))]

    @classmethod
    def IS_CHANGED(cls, folder, **kwargs):
        if not os.path.isdir(folder):
            return float("NaN")
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.tga']
        include_subfolders = kwargs.get('include_subfolders', False)
        
        file_data = []
        if include_subfolders:
            for root, _, files in os.walk(folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in valid_extensions):
                        path = os.path.join(root, file)
                        try:
                            mtime = os.path.getmtime(path)
                            file_data.append((path, mtime))
                        except OSError:
                            pass
        else:
            for file in os.listdir(folder):
                if any(file.lower().endswith(ext) for ext in valid_extensions):
                    path = os.path.join(folder, file)
                    try:
                        mtime = os.path.getmtime(path)
                        file_data.append((path, mtime))
                    except OSError:
                        pass
        
        file_data.sort()
        
        combined_hash = hashlib.md5()
        combined_hash.update(folder.encode('utf-8'))
        combined_hash.update(str(len(file_data)).encode('utf-8'))
        
        for path, mtime in file_data:
            combined_hash.update(f"{path}:{mtime}".encode('utf-8'))
        
        current_hash = combined_hash.hexdigest()
        
        old_hash = cls.folder_hashes.get(folder)
        cls.folder_hashes[folder] = current_hash
        
        if old_hash == current_hash:
            return old_hash
        
        return current_hash

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "folder": ("STRING", {"default": ""}),
                "width": ("INT", {"default": 1024, "min": -1, "step": 1}),
                "height": ("INT", {"default": 1024, "min": -1, "step": 1}),
                "keep_aspect_ratio": (["crop", "pad", "stretch", "keep proportion"],),
                "interpolation": (["nearest", "bilinear", "bicubic", "area", "lanczos"],{"default": "lanczos"}),
            },
            "optional": {
                "image_load_cap": ("INT", {"default": 0, "min": 0, "step": 1}),
                "start_index": ("INT", {"default": 0, "min": 0, "step": 1}),
                "include_subfolders": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "STRING",)
    RETURN_NAMES = ("image", "mask", "count", "image_path",)
    OUTPUT_IS_LIST = (True, True, False, True)
    FUNCTION = "load_images"
    CATEGORY = "tools_zero"
    DESCRIPTION = """Loads images from a folder into a batch, images are resized and loaded into a batch."""

    def load_images(self, folder, width, height, keep_aspect_ratio, interpolation="lanczos", image_load_cap=0, start_index=0, include_subfolders=False):
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Folder '{folder} cannot be found.'")
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.tga']
        image_paths = []
        if include_subfolders:
            for root, _, files in os.walk(folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in valid_extensions):
                        image_paths.append(os.path.join(root, file))
        else:
            for file in os.listdir(folder):
                if any(file.lower().endswith(ext) for ext in valid_extensions):
                    image_paths.append(os.path.join(folder, file))

        # 使用自然排序而不是简单的字典序排序
        dir_files = sorted(image_paths, key=self.natural_sort_key)

        if len(dir_files) == 0:
            raise FileNotFoundError(f"No files in directory '{folder}'.")

        # start at start_index
        dir_files = dir_files[start_index:]

        images = []
        masks = []
        image_path_list = []

        limit_images = False
        if image_load_cap > 0:
            limit_images = True
        image_count = 0

        for image_path in dir_files:
            if os.path.isdir(image_path):
                continue
            if limit_images and image_count >= image_load_cap:
                break
            i = Image.open(image_path)
            i = ImageOps.exif_transpose(i)
            
            # Resize image to maximum dimensions
            if width == -1 and height == -1:
                width = i.size[0]
                height = i.size[1]
            if i.size != (width, height):
                i = self.resize_with_aspect_ratio(i, width, height, keep_aspect_ratio, interpolation)
            
            
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
                if mask.shape != (height, width):
                    mask = torch.nn.functional.interpolate(mask.unsqueeze(0).unsqueeze(0), 
                                                         size=(height, width), 
                                                         mode='bilinear', 
                                                         align_corners=False).squeeze()
            else:
                mask = torch.zeros((height, width), dtype=torch.float32, device="cpu")
            
            images.append(image)
            masks.append(mask.unsqueeze(0))
            image_path_list.append(image_path)
            image_count += 1

        if len(images) == 0:
            return ([], [], 0, [])

        return (images, masks, len(images), image_path_list)

    def resize_with_aspect_ratio(self, img, width, height, mode, interpolation="lanczos"):
        # 转换插值方法名称为PIL的resampling方法
        pil_resampling = {
            "nearest": Image.Resampling.NEAREST,
            "bilinear": Image.Resampling.BILINEAR,
            "bicubic": Image.Resampling.BICUBIC,
            "area": Image.Resampling.BOX,
            "lanczos": Image.Resampling.LANCZOS
        }
        resampling_method = pil_resampling.get(interpolation, Image.Resampling.LANCZOS)
        
        if mode == "stretch":
            return img.resize((width, height), resampling_method)
        
        img_width, img_height = img.size
        
        if mode == "keep proportion":
            # 只指定了一个维度，计算另一个维度
            if width > 0 and height == 0:
                # 只指定了宽度，按比例计算高度
                height = round(img_height * (width / img_width))
            elif height > 0 and width == 0:
                # 只指定了高度，按比例计算宽度
                width = round(img_width * (height / img_height))
            elif width == 0 and height == 0:
                # 两个维度都未指定，保持原始尺寸
                width = img_width
                height = img_height
            else:
                # 两个维度都指定了，按比例缩放，选择较小的缩放比例
                ratio = min(width / img_width, height / img_height)
                width = round(img_width * ratio)
                height = round(img_height * ratio)
            
            # 调整图像大小，保持纵横比
            return img.resize((width, height), resampling_method)
        
        aspect_ratio = img_width / img_height
        target_ratio = width / height
            
        if mode == "crop":
            # Calculate dimensions for center crop
            if aspect_ratio > target_ratio:
                # Image is wider - crop width
                new_width = int(height * aspect_ratio)
                img = img.resize((new_width, height), resampling_method)
                left = (new_width - width) // 2
                return img.crop((left, 0, left + width, height))
            else:
                # Image is taller - crop height
                new_height = int(width / aspect_ratio)
                img = img.resize((width, new_height), resampling_method)
                top = (new_height - height) // 2
                return img.crop((0, top, width, top + height))

        elif mode == "pad":
            pad_color = self.get_edge_color(img)
            # Calculate dimensions for padding
            if aspect_ratio > target_ratio:
                # Image is wider - pad height
                new_height = int(width / aspect_ratio)
                img = img.resize((width, new_height), resampling_method)
                padding = (height - new_height) // 2
                padded = Image.new('RGBA', (width, height), pad_color)
                padded.paste(img, (0, padding))
                return padded
            else:
                # Image is taller - pad width
                new_width = int(height * aspect_ratio)
                img = img.resize((new_width, height), resampling_method)
                padding = (width - new_width) // 2
                padded = Image.new('RGBA', (width, height), pad_color)
                padded.paste(img, (padding, 0))
                return padded
    def get_edge_color(self, img):
        from PIL import ImageStat
        """Sample edges and return dominant color"""
        width, height = img.size
        img = img.convert('RGBA')
        
        # Create 1-pixel high/wide images from edges
        top = img.crop((0, 0, width, 1))
        bottom = img.crop((0, height-1, width, height))
        left = img.crop((0, 0, 1, height))
        right = img.crop((width-1, 0, width, height))
        
        # Combine edges into single image
        edges = Image.new('RGBA', (width*2 + height*2, 1))
        edges.paste(top, (0, 0))
        edges.paste(bottom, (width, 0))
        edges.paste(left.resize((height, 1)), (width*2, 0))
        edges.paste(right.resize((height, 1)), (width*2 + height, 0))
        
        # Get median color
        stat = ImageStat.Stat(edges)
        median = tuple(map(int, stat.median))
        return median

#此节点源自KJNodes/image/LoadImagesFromFolderKJ

# 注册节点
NODE_CLASS_MAPPINGS = {
    "文件导入图像": File_import_image
}