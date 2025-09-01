import os
import csv
import json
import torch
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import folder_paths

# 日志函数
def log_node_warn(node_name, message):
    print(f"[警告] {node_name}: {message}")

def log_node_info(node_name, message):
    print(f"[信息] {node_name}: {message}")

class Batch_text_saving :      
    # 添加类变量保存当前编号
    current_number = 1

    def __init__(self):
        self.output_dir = folder_paths.output_directory
        self.type = 'output'

    @classmethod
    def INPUT_TYPES(s):
        input_types = {}
        input_types['required'] = {
            "output_file_path": ("STRING", {"multiline": False, "default": ""}),
            "file_name": ("STRING", {"multiline": False, "default": ""}),
            "file_extension": (["txt", "csv"],),
            "overwrite": ("BOOLEAN", {"default": True}),
            "name_number": ("INT", {"default": 1, "min": 0, "max": 99999}),
            "number_position": (["before", "after"], {"default": "before"}),
        }
        input_types['optional'] = {
            "text": ("STRING", {"default": "", "forceInput": True}),
            "image": ("IMAGE",),
        }
        return input_types

    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("text", 'image', 'next_number')

    FUNCTION = "save_text"
    OUTPUT_NODE = True
    CATEGORY = "tools_zero"

    def save_image(self, images, filename_prefix='', extension='png',quality=100, prompt=None,
                   extra_pnginfo=None, delimiter='_', filename_number_start='true', number_padding=4,
                   overwrite_mode='prefix_as_filename', output_path='', show_history='true', show_previews='true',
                   embed_workflow='true', lossless_webp=False, ):
        results = list()
        for image in images:
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            # Delegate metadata/pnginfo
            if extension == 'webp':
                img_exif = img.getexif()
                workflow_metadata = ''
                prompt_str = ''
                if prompt is not None:
                    prompt_str = json.dumps(prompt)
                    img_exif[0x010f] = "Prompt:" + prompt_str
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        workflow_metadata += json.dumps(extra_pnginfo[x])
                img_exif[0x010e] = "Workflow:" + workflow_metadata
                exif_data = img_exif.tobytes()
            else:
                metadata = PngInfo()
                if embed_workflow == 'true':
                    if prompt is not None:
                        metadata.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo is not None:
                        for x in extra_pnginfo:
                            metadata.add_text(x, json.dumps(extra_pnginfo[x]))
                exif_data = metadata

            file = f"{filename_prefix}.{extension}"

            # Save the images
            try:
                output_file = os.path.abspath(os.path.join(output_path, file))
                if extension in ["jpg", "jpeg"]:
                    img.save(output_file,
                             quality=quality, optimize=True)
                elif extension == 'webp':
                    img.save(output_file,
                             quality=quality, lossless=lossless_webp, exif=exif_data)
                elif extension == 'png':
                    img.save(output_file,
                             pnginfo=exif_data, optimize=True)
                elif extension == 'bmp':
                    img.save(output_file)
                elif extension == 'tiff':
                    img.save(output_file,
                             quality=quality, optimize=True)
                else:
                    img.save(output_file,
                             pnginfo=exif_data, optimize=True)

            except OSError as e:
                print(e)
            except Exception as e:
                print(e)

    def save_text(self, output_file_path, file_name, file_extension, overwrite, name_number=1, number_position="before", filename_number_start='true', text=None, image=None, prompt=None,
                  extra_pnginfo=None):
        if isinstance(file_name, list):
            file_name = file_name[0]
            
        # 更新类变量，始终记住最大的编号值
        if name_number > Batch_text_saving.current_number:
            Batch_text_saving.current_number = name_number
            
        # 使用类变量作为当前编号
        use_number = Batch_text_saving.current_number
            
        # 根据number_position设置文件名
        if number_position == "before":
            formatted_file_name = f"{use_number}_{file_name}"
        else:  # after
            formatted_file_name = f"{file_name}_{use_number}"
            
        filepath = str(os.path.join(output_file_path, formatted_file_name)) + "." + file_extension
        index = 1

        if (output_file_path == "" or file_name == ""):
            log_node_warn("Save Text", "No file details found. No file output.")
            return (text if text is not None else "", None, Batch_text_saving.current_number + 1)

        if not os.path.exists(output_file_path):
            os.makedirs(output_file_path)

        if overwrite:
            file_mode = "w"
        else:
            file_mode = "a"

        log_node_info("Save Text", f"Saving to {filepath}")

        # 只有当text不为None时才保存文本
        if text is not None:
            if file_extension == "csv":
                text_list = []
                for i in text.split("\n"):
                    text_list.append(i.strip())

                with open(filepath, file_mode, newline="", encoding='utf-8') as csv_file:
                    csv_writer = csv.writer(csv_file)
                    # Write each line as a separate row in the CSV file
                    for line in text_list:
                        csv_writer.writerow([line])
            else:
                with open(filepath, file_mode, newline="", encoding='utf-8') as text_file:
                    for line in text:
                        text_file.write(line)

        result = {"result": (text if text is not None else "", None)}

        if image is not None:
            imagepath = os.path.join(output_file_path, formatted_file_name)
            image_index = 1
            if not overwrite:
                while os.path.exists(filepath):
                    if os.path.exists(filepath):
                        imagepath = str(os.path.join(output_file_path, formatted_file_name)) + "_" + str(index)
                        index = index + 1
                    else:
                        break
            # result = self.save_images(image, imagepath, prompt, extra_pnginfo)

            delimiter = '_'
            number_padding = 4
            lossless_webp = (False,)

            original_output = self.output_dir

            # Setup output path
            if output_file_path in [None, '', "none", "."]:
                output_path = self.output_dir
            else:
                output_path = ''
            if not os.path.isabs(output_file_path):
                output_path = os.path.join(self.output_dir, output_path)
            base_output = os.path.basename(output_path)
            if output_path.endswith("ComfyUI/output") or output_path.endswith(r"ComfyUI\output"):
                base_output = ""

            # Check output destination
            if output_path.strip() != '':
                if not os.path.isabs(output_path):
                    output_path = os.path.join(folder_paths.output_directory, output_path)
                if not os.path.exists(output_path.strip()):
                    print(
                        f'The path `{output_path.strip()}` specified doesn\'t exist! Creating directory.')
                    os.makedirs(output_path, exist_ok=True)

            images = []
            images.append(image)
            images = torch.cat(images, dim=0)
            self.save_image(images, imagepath, 'png', 100, prompt, extra_pnginfo, filename_number_start=filename_number_start, output_path=output_path, delimiter=delimiter,
                             number_padding=number_padding, lossless_webp=lossless_webp)

            log_node_info("Save Text", f"Saving Image to {imagepath}")
            result['result'] = (text if text is not None else "", image)
        
        # 更新并返回next_number
        next_number = use_number + 1
        Batch_text_saving.current_number = next_number
        
        return (text if text is not None else "", image, next_number)

# 节点注册
NODE_CLASS_MAPPINGS = {
    "Batch_text_saving": Batch_text_saving
}

# 节点类别对应的显示名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "Batch_text_saving": "批量文本保存"
}