import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";


app.registerExtension({
    name: "Zero_ColorAdjustment.Preview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "Zero_ColorAdjustment") {

            // 扩展节点的构造函数
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = onNodeCreated?.apply(this, arguments);
                
                // 设置组件起始位置，确保在端口下方
                this.widgets_start_y = 30; // 调整这个值以适应端口高度
                
                this.setupWebSocket();
                
                const sliderConfig = {
                    min: 0, 
                    max: 2, 
                    step: 0.01,
                    drag_start: () => this.isAdjusting = true,
                    drag_end: () => {
                        this.isAdjusting = false;
                        this.updatePreview(false);
                    }
                };

                const createSlider = (name, displayName) => {
                    this.addWidget("slider", displayName, 1.0, (value) => {
                        this[name] = value;
                        this.updatePreview(true);
                    }, sliderConfig);
                };

                // 基本调整
                createSlider("brightness", "亮度");
                createSlider("contrast", "对比度");
                createSlider("saturation", "饱和度");
                
                // 添加新的颜色控制选项
                // 色相调整 (0-2, 默认1.0表示无变化)
                createSlider("hue", "色相");
                
                // 色温调整 (0-2, 默认1.0表示中性)
                createSlider("temperature", "色温");
                
                // 色调调整 (0-2, 默认1.0表示中性)
                createSlider("tint", "色调");
                
                // 伽马调整 (0.1-3, 默认1.0表示无变化)
                this.addWidget("slider", "伽马", 1.0, (value) => {
                    this.gamma = value;
                    this.updatePreview(true);
                }, { min: 0.1, max: 3, step: 0.01, 
                     drag_start: () => this.isAdjusting = true,
                     drag_end: () => {
                        this.isAdjusting = false;
                        this.updatePreview(false);
                     }
                });
                
                // 自然饱和度调整 (0-2, 默认1.0表示无变化)
                createSlider("vibrance", "自然饱和度");
                
                // 添加重置按钮
                this.addWidget("button", "重置所有参数", null, () => {
                    // 重置所有滑块值为1.0
                    this.brightness = 1.0;
                    this.contrast = 1.0;
                    this.saturation = 1.0;
                    this.hue = 1.0;
                    this.temperature = 1.0;
                    this.tint = 1.0;
                    this.gamma = 1.0;
                    this.vibrance = 1.0;
                    
                    // 更新UI上的滑块显示
                    this.widgets.forEach(w => {
                        if (["亮度", "对比度", "饱和度", "色相", "色温", "色调", "伽马", "自然饱和度"].includes(w.name)) {
                            w.value = 1.0;
                        }
                    });
                    
                    // 更新预览
                    this.updatePreview(false);
                });
                
                return result;
            };

            // 添加WebSocket设置方法
            nodeType.prototype.setupWebSocket = function() {
                console.log(`[ColorAdjustment] 节点 ${this.id} 设置WebSocket监听`);
                api.addEventListener("zero_color_adjustment_update", async (event) => {
                    const data = event.detail;
                    
                    if (data && data.node_id && data.node_id === this.id.toString()) {
                        console.log(`[ColorAdjustment] 节点 ${this.id} 接收到更新数据`);
                        if (data.image_data) {
                            // 处理base64图像数据
                            console.log("[ColorAdjustment] 接收到base64数据:", {
                                nodeId: this.id,
                                dataLength: data.image_data.length,
                                dataPreview: data.image_data.substring(0, 50) + "...", // 只显示前50个字符
                                isBase64: data.image_data.startsWith("data:image"),
                                timestamp: new Date().toISOString()
                            });
                            
                            // 更新滑块值
                            if (data.brightness !== undefined) this.brightness = data.brightness;
                            if (data.contrast !== undefined) this.contrast = data.contrast;
                            if (data.saturation !== undefined) this.saturation = data.saturation;
                            if (data.hue !== undefined) this.hue = data.hue;
                            if (data.temperature !== undefined) this.temperature = data.temperature;
                            if (data.tint !== undefined) this.tint = data.tint;
                            if (data.gamma !== undefined) this.gamma = data.gamma;
                            if (data.vibrance !== undefined) this.vibrance = data.vibrance;
                            
                            // 更新UI滑块
                            this.widgets.forEach(w => {
                                if (w.name === "亮度" && data.brightness !== undefined) {
                                    w.value = data.brightness;
                                } else if (w.name === "对比度" && data.contrast !== undefined) {
                                    w.value = data.contrast;
                                } else if (w.name === "饱和度" && data.saturation !== undefined) {
                                    w.value = data.saturation;
                                } else if (w.name === "色相" && data.hue !== undefined) {
                                    w.value = data.hue;
                                } else if (w.name === "色温" && data.temperature !== undefined) {
                                    w.value = data.temperature;
                                } else if (w.name === "色调" && data.tint !== undefined) {
                                    w.value = data.tint;
                                } else if (w.name === "伽马" && data.gamma !== undefined) {
                                    w.value = data.gamma;
                                } else if (w.name === "自然饱和度" && data.vibrance !== undefined) {
                                    w.value = data.vibrance;
                                }
                            });
                            
                            this.loadImageFromBase64(data.image_data);
                        } else {
                            console.warn("[ColorAdjustment] 接收到空的图像数据");
                        }
                    }
                });
            };

            // 添加从base64加载图像的方法
            nodeType.prototype.loadImageFromBase64 = function(base64Data) {
                console.log(`[ColorAdjustment] 节点 ${this.id} 开始加载base64图像数据`);
                // 创建一个新的图像对象
                const img = new Image();
                
                // 当图像加载完成时
                img.onload = () => {
                    console.log(`[ColorAdjustment] 节点 ${this.id} 图像加载完成: ${img.width}x${img.height}`);
                    // 创建一个临时画布来获取像素数据
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = img.width;
                    tempCanvas.height = img.height;
                    const tempCtx = tempCanvas.getContext('2d');
                    
                    // 在临时画布上绘制图像
                    tempCtx.drawImage(img, 0, 0);
                    
                    // 获取像素数据
                    const imageData = tempCtx.getImageData(0, 0, img.width, img.height);
                    
                    // 创建二维数组存储像素数据
                    const pixelArray = [];
                    for (let y = 0; y < img.height; y++) {
                        const row = [];
                        for (let x = 0; x < img.width; x++) {
                            const idx = (y * img.width + x) * 4;
                            row.push([
                                imageData.data[idx],     // R
                                imageData.data[idx + 1], // G
                                imageData.data[idx + 2]  // B
                            ]);
                        }
                        pixelArray.push(row);
                    }
                    
                    // 存储像素数据并更新预览
                    this.originalImageData = pixelArray;
                    this.updatePreview();
                };
                
                // 设置图像源
                img.src = base64Data;
            };

            // 添加节点时的处理
            const onAdded = nodeType.prototype.onAdded;
            nodeType.prototype.onAdded = function() {
                const result = onAdded?.apply(this, arguments);
                
                if (!this.previewElement && this.id !== undefined && this.id !== -1) {
                    // 创建预览容器
                    const previewContainer = document.createElement("div");
                    previewContainer.style.position = "relative";
                    previewContainer.style.width = "100%";
                    previewContainer.style.height = "100%";
                    previewContainer.style.backgroundColor = "#333";
                    previewContainer.style.borderRadius = "8px";
                    previewContainer.style.overflow = "hidden";
                    
                    // 创建预览画布
                    const canvas = document.createElement("canvas");
                    canvas.style.width = "100%";
                    canvas.style.height = "100%";
                    canvas.style.objectFit = "contain";
                    
                    previewContainer.appendChild(canvas);
                    this.canvas = canvas;
                    this.previewElement = previewContainer;
                    
                    // 添加DOM部件
                    this.widgets ||= [];
                    this.widgets_up = true;
                    
                    requestAnimationFrame(() => {
                        if (this.widgets) {
                            this.previewWidget = this.addDOMWidget("preview", "preview", previewContainer);
                            this.setDirtyCanvas(true, true);
                        }
                    });
                }
                
                return result;
            };

            // 更新预览方法
            nodeType.prototype.updatePreview = function(onlyPreview = false) {
                if (!this.originalImageData || !this.canvas) {
                    return;
                }
                
                requestAnimationFrame(() => {
                    const ctx = this.canvas.getContext("2d");
                    const width = this.originalImageData[0].length;
                    const height = this.originalImageData.length;
                    
                    if (!onlyPreview && !this.isAdjusting) {
                        console.log(`[ColorAdjustment] 节点 ${this.id} 更新预览并准备发送数据 (${width}x${height})`);
                    } else {
                        console.log(`[ColorAdjustment] 节点 ${this.id} 仅更新预览 (${width}x${height})`);
                    }
                    
                    // 创建ImageData
                    const imgData = new ImageData(width, height);
                    
                    // 填充原始数据
                    for (let y = 0; y < height; y++) {
                        for (let x = 0; x < width; x++) {
                            const idx = (y * width + x) * 4;
                            imgData.data[idx] = this.originalImageData[y][x][0];     // R
                            imgData.data[idx + 1] = this.originalImageData[y][x][1]; // G
                            imgData.data[idx + 2] = this.originalImageData[y][x][2]; // B
                            imgData.data[idx + 3] = 255;                             // A
                        }
                    }
                    
                    // 应用颜色调整
                    const adjustedData = this.adjustColors(imgData);
                    
                    // 调整画布大小并显示
                    this.canvas.width = width;
                    this.canvas.height = height;
                    ctx.putImageData(adjustedData, 0, 0);
                    
                    // 只在拖动结束时发送数据
                    if (!onlyPreview && !this.isAdjusting) {
                        this.lastAdjustedData = adjustedData;
                        this.sendAdjustedData(adjustedData);
                    }
                });
            };

            // 优化颜色调整方法，提高性能
            nodeType.prototype.adjustColors = function(imageData) {
                const brightness = this.brightness || 1.0;
                const contrast = this.contrast || 1.0;
                const saturation = this.saturation || 1.0;
                const hue = this.hue || 1.0;
                const temperature = this.temperature || 1.0;
                const tint = this.tint || 1.0;
                const gamma = this.gamma || 1.0;
                const vibrance = this.vibrance || 1.0;
                
                const result = new Uint8ClampedArray(imageData.data);
                const len = result.length;
                
                // 使用查找表优化常用计算
                const contrastFactor = contrast;
                const contrastOffset = 128 * (1 - contrast);
                
                for (let i = 0; i < len; i += 4) {
                    // 获取原始RGB值
                    let r = result[i];
                    let g = result[i + 1];
                    let b = result[i + 2];
                    
                    // 应用色温调整 (温暖/冷色调)
                    if (temperature !== 1.0) {
                        // 温暖 (>1.0): 增加红色，减少蓝色
                        // 冷色 (<1.0): 增加蓝色，减少红色
                        const tempFactor = (temperature - 1.0) * 30;
                        r = Math.min(255, Math.max(0, r + tempFactor));
                        b = Math.min(255, Math.max(0, b - tempFactor));
                    }
                    
                    // 应用色调调整 (绿/洋红)
                    if (tint !== 1.0) {
                        // 绿色调 (>1.0): 增加绿色，减少洋红
                        // 洋红调 (<1.0): 增加洋红，减少绿色
                        const tintFactor = (tint - 1.0) * 30;
                        g = Math.min(255, Math.max(0, g + tintFactor));
                        r = Math.min(255, Math.max(0, r - tintFactor * 0.5));
                        b = Math.min(255, Math.max(0, b - tintFactor * 0.5));
                    }
                    
                    // 应用色相调整
                    if (hue !== 1.0) {
                        // 转换为HSL
                        const [h, s, l] = rgbToHsl(r, g, b);
                        // 调整色相 (0-2 映射到 -180 到 +180 度)
                        const hueShift = (hue - 1.0) * 180;
                        const newHue = (h + hueShift / 360) % 1;
                        // 转回RGB
                        const [nr, ng, nb] = hslToRgb(newHue, s, l);
                        r = nr;
                        g = ng;
                        b = nb;
                    }
                    
                    // 优化亮度和对比度调整
                    r = Math.min(255, r * brightness);
                    g = Math.min(255, g * brightness);
                    b = Math.min(255, b * brightness);
                    
                    r = r * contrastFactor + contrastOffset;
                    g = g * contrastFactor + contrastOffset;
                    b = b * contrastFactor + contrastOffset;
                    
                    // 应用伽马校正
                    if (gamma !== 1.0) {
                        const invGamma = 1.0 / gamma;
                        r = Math.pow(r / 255, invGamma) * 255;
                        g = Math.pow(g / 255, invGamma) * 255;
                        b = Math.pow(b / 255, invGamma) * 255;
                    }
                    
                    // 优化饱和度调整 - 使用更准确的亮度权重
                    if (saturation !== 1.0) {
                        const avg = r * 0.299 + g * 0.587 + b * 0.114;
                        r = avg + (r - avg) * saturation;
                        g = avg + (g - avg) * saturation;
                        b = avg + (b - avg) * saturation;
                    }
                    
                    // 应用自然饱和度 (vibrance) - 更智能的饱和度，保护已饱和的颜色和肤色
                    if (vibrance !== 1.0) {
                        const max = Math.max(r, g, b);
                        const avg = (r + g + b) / 3;
                        const amt = (max - avg) * 2 / 255; // 饱和度量
                        
                        // 计算肤色检测 (简单版本)
                        const isNeutral = Math.abs(r - g) < 20 && Math.abs(r - b) < 20 && Math.abs(g - b) < 20;
                        const skinLikeness = isNeutral ? 0.5 : 0; // 简单的肤色检测
                        
                        // 调整因子，饱和度越高，调整越少
                        const adjustFactor = (1 - amt) * (vibrance - 1) * (1 - skinLikeness);
                        
                        const vavg = r * 0.299 + g * 0.587 + b * 0.114;
                        r = vavg + (r - vavg) * (1 + adjustFactor);
                        g = vavg + (g - vavg) * (1 + adjustFactor);
                        b = vavg + (b - vavg) * (1 + adjustFactor);
                    }
                    
                    // 确保值在正确范围内
                    result[i] = Math.min(255, Math.max(0, r));
                    result[i + 1] = Math.min(255, Math.max(0, g));
                    result[i + 2] = Math.min(255, Math.max(0, b));
                }
                
                return new ImageData(result, imageData.width, imageData.height);
            };

            // 添加发送调整后数据的方法，优化为异步
            nodeType.prototype.sendAdjustedData = async function(adjustedData) {
                try {
                    const endpoint = '/color_adjustment/apply';
                    const nodeId = String(this.id);
                    
                    api.fetchApi(endpoint, {
                        method: 'POST',
                        body: JSON.stringify({
                            node_id: nodeId,
                            adjusted_data: Array.from(adjustedData.data),
                            width: adjustedData.width,
                            height: adjustedData.height
                        })
                    }).then(response => {
                        if (!response.ok) {
                            throw new Error(`服务器返回错误: ${response.status}`);
                        }
                        return response.json();
                    }).catch(error => {
                        console.error('数据发送失败:', error);
                    });
                } catch (error) {
                    console.error('发送数据时出错:', error);
                }
            };

            // 节点移除时的处理
            const onRemoved = nodeType.prototype.onRemoved;
            nodeType.prototype.onRemoved = function() {
                const result = onRemoved?.apply(this, arguments);
                
                if (this.canvas) {
                    const ctx = this.canvas.getContext("2d");
                    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                    this.canvas = null;
                }
                this.previewElement = null;
                
                return result;
            };

            // 添加RGB到HSL转换函数
            function rgbToHsl(r, g, b) {
                r /= 255;
                g /= 255;
                b /= 255;
                
                const max = Math.max(r, g, b);
                const min = Math.min(r, g, b);
                let h, s, l = (max + min) / 2;
                
                if (max === min) {
                    h = s = 0; // 灰色
                } else {
                    const d = max - min;
                    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
                    
                    switch (max) {
                        case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                        case g: h = (b - r) / d + 2; break;
                        case b: h = (r - g) / d + 4; break;
                    }
                    
                    h /= 6;
                }
                
                return [h, s, l];
            }
            
            // 添加HSL到RGB转换函数
            function hslToRgb(h, s, l) {
                let r, g, b;
                
                if (s === 0) {
                    r = g = b = l; // 灰色
                } else {
                    const hue2rgb = (p, q, t) => {
                        if (t < 0) t += 1;
                        if (t > 1) t -= 1;
                        if (t < 1/6) return p + (q - p) * 6 * t;
                        if (t < 1/2) return q;
                        if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                        return p;
                    };
                    
                    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                    const p = 2 * l - q;
                    
                    r = hue2rgb(p, q, h + 1/3);
                    g = hue2rgb(p, q, h);
                    b = hue2rgb(p, q, h - 1/3);
                }
                
                return [r * 255, g * 255, b * 255];
            }
        }
    }
}); 


