/**
 * text_image.js
 * 用于 ComfyUI 的文本图像节点前端
 */

import { app } from '../../scripts/app.js';
import parseCss from '../extern/parse-css.js';

// 注册颜色选择器部件
app.registerExtension({
    name: "Zero_TextImage.ColorPicker",
    
    async beforeRegisterNodeDef(nodeType, nodeData) {
        // 检查是否是我们的节点类型
        if (nodeData.name === "文本图像") {
            // 初始化共享变量
            if (!window.MTB) {
                window.MTB = {};
            }
            
            // 导入mtb_widgets中的共享函数
            const isColorBright = (colorValues, threshold = 125) => {
                if (!colorValues || colorValues.length < 3) return false;
                // 计算亮度 (0.299*R + 0.587*G + 0.114*B)
                const brightness = 0.299 * colorValues[0] + 0.587 * colorValues[1] + 0.114 * colorValues[2];
                return brightness > threshold;
            };
            
            // 获取原始的 getExtraMenuOptions 函数
            const originalGetExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;

            // 添加颜色交换选项到右键菜单
            nodeType.prototype.getExtraMenuOptions = function(_, options) {
                const result = originalGetExtraMenuOptions ? originalGetExtraMenuOptions.apply(this, arguments) : undefined;

                options.push(
                    {
                        content: "交换前景/背景颜色",
                        callback: () => {
                            // 找到颜色部件
                            const fontColorWidget = this.widgets.find(w => w.name === "font_color");
                            const bgColorWidget = this.widgets.find(w => w.name === "background_color");
                            
                            if (fontColorWidget && bgColorWidget) {
                                // 交换颜色值
                                const tempColor = fontColorWidget.value;
                                fontColorWidget.value = bgColorWidget.value;
                                bgColorWidget.value = tempColor;
                                
                                // 更新画布
                                app.canvas.setDirty(true);
                            }
                        }
                    }
                );

                return result;
            };
            
            // 添加自定义部件处理
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // 找到并增强颜色部件
                setTimeout(() => {
                    for (let i = 0; i < this.widgets.length; i++) {
                        const widget = this.widgets[i];
                        if (widget.type === "COLOR" || (widget.name === "font_color" || widget.name === "background_color")) {
                            this.enhanceColorWidget(widget);
                        }
                    }
                }, 100);
                
                return result;
            };

            // 创建颜色选择器面板
            const createColorPickerPanel = (node, widget, x, y) => {
                // 检查是否已经存在颜色选择器
                if (document.getElementById('text-image-color-picker-panel')) {
                    document.getElementById('text-image-color-picker-panel').remove();
                }
                
                // 创建颜色选择器面板
                const panel = document.createElement('div');
                panel.id = 'text-image-color-picker-panel';
                panel.style.cssText = `
                    position: absolute;
                    left: ${x}px;
                    top: ${y}px;
                    z-index: 10000;
                    background-color: #2a2a2a;
                    border: 1px solid #444;
                    border-radius: 5px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
                    padding: 10px;
                    min-width: 300px;
                    user-select: none;
                `;
                
                // 创建标题
                const titleDiv = document.createElement('div');
                titleDiv.style.cssText = `
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                    font-weight: bold;
                    color: #fff;
                    font-size: 14px;
                    padding-bottom: 5px;
                    border-bottom: 1px solid #444;
                `;
                titleDiv.innerHTML = `
                    <span>${widget.name === 'font_color' ? '文本颜色' : '背景颜色'}</span>
                    <span style="cursor:pointer" id="close-color-picker">×</span>
                `;
                panel.appendChild(titleDiv);
                
                // 创建颜色选择器容器
                const pickerContainer = document.createElement('div');
                pickerContainer.style.cssText = `
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                `;
                
                // 创建渐变色选择区域
                const gradientArea = document.createElement('div');
                gradientArea.style.cssText = `
                    width: 100%;
                    height: 200px;
                    background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
                    background-position: center;
                    position: relative;
                    cursor: crosshair;
                    border-radius: 4px;
                    margin-bottom: 10px;
                    position: relative;
                `;
                
                // 创建亮度/饱和度选择区域
                const shadesArea = document.createElement('div');
                shadesArea.style.cssText = `
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,1)), 
                               linear-gradient(to right, rgba(0,0,0,1), rgba(0,0,0,0));
                    border-radius: 4px;
                `;
                gradientArea.appendChild(shadesArea);
                
                // 创建颜色选择光标
                const cursor = document.createElement('div');
                cursor.style.cssText = `
                    position: absolute;
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    border: 2px solid #fff;
                    transform: translate(-50%, -50%);
                    pointer-events: none;
                    box-shadow: 0 0 3px rgba(0,0,0,0.5);
                `;
                gradientArea.appendChild(cursor);
                
                // 颜色条
                const colorStrip = document.createElement('div');
                colorStrip.style.cssText = `
                    width: 100%;
                    height: 20px;
                    background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
                    border-radius: 4px;
                    position: relative;
                    cursor: pointer;
                `;
                
                // 颜色条选择器
                const stripCursor = document.createElement('div');
                stripCursor.style.cssText = `
                    position: absolute;
                    top: -3px;
                    width: 6px;
                    height: 26px;
                    border-radius: 3px;
                    border: 2px solid #fff;
                    transform: translateX(-3px);
                    pointer-events: none;
                    box-shadow: 0 0 3px rgba(0,0,0,0.5);
                `;
                colorStrip.appendChild(stripCursor);
                
                // RGB输入区域
                const rgbInputs = document.createElement('div');
                rgbInputs.style.cssText = `
                    display: flex;
                    justify-content: space-between;
                    margin-top: 15px;
                `;
                
                // 创建RGB输入框
                ['R', 'G', 'B'].forEach(channel => {
                    const inputGroup = document.createElement('div');
                    inputGroup.style.cssText = `
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        width: 30%;
                    `;
                    
                    const label = document.createElement('label');
                    label.textContent = channel;
                    label.style.cssText = `
                        color: #fff;
                        font-size: 14px;
                        margin-bottom: 5px;
                    `;
                    
                    const input = document.createElement('input');
                    input.type = 'number';
                    input.min = 0;
                    input.max = 255;
                    input.id = `text-image-${channel.toLowerCase()}-input`;
                    input.style.cssText = `
                        width: 100%;
                        padding: 5px;
                        background: #333;
                        color: #fff;
                        border: 1px solid #555;
                        border-radius: 4px;
                        text-align: center;
                    `;
                    
                    inputGroup.appendChild(label);
                    inputGroup.appendChild(input);
                    rgbInputs.appendChild(inputGroup);
                });
                
                // 颜色预览和十六进制值
                const previewContainer = document.createElement('div');
                previewContainer.style.cssText = `
                    display: flex;
                    margin-top: 15px;
                    margin-bottom: 5px;
                    gap: 10px;
                    align-items: center;
                `;
                
                // 预览色块
                const colorPreview = document.createElement('div');
                colorPreview.id = 'text-image-color-preview';
                colorPreview.style.cssText = `
                    width: 40px;
                    height: 40px;
                    border-radius: 4px;
                    border: 1px solid #555;
                    background-color: ${widget.value || '#ff0000'};
                `;
                
                // 十六进制输入框
                const hexInput = document.createElement('input');
                hexInput.type = 'text';
                hexInput.id = 'text-image-hex-input';
                hexInput.value = widget.value || '#ff0000';
                hexInput.style.cssText = `
                    flex-grow: 1;
                    padding: 8px;
                    background: #333;
                    color: #fff;
                    border: 1px solid #555;
                    border-radius: 4px;
                    font-family: monospace;
                `;
                
                previewContainer.appendChild(colorPreview);
                previewContainer.appendChild(hexInput);
                
                // 预设颜色
                const presets = document.createElement('div');
                presets.style.cssText = `
                    display: flex;
                    flex-wrap: wrap;
                    margin-top: 15px;
                    gap: 5px;
                `;
                
                // 常用颜色
                const commonColors = [
                    '#ff0000', '#ff8000', '#ffff00', '#80ff00', '#00ff00',
                    '#00ff80', '#00ffff', '#0080ff', '#0000ff', '#8000ff',
                    '#ff00ff', '#ff0080', '#ffffff', '#c0c0c0', '#808080',
                    '#404040', '#202020', '#000000'
                ];
                
                commonColors.forEach(color => {
                    const preset = document.createElement('div');
                    preset.style.cssText = `
                        width: 20px;
                        height: 20px;
                        border-radius: 3px;
                        background-color: ${color};
                        border: 1px solid ${color === '#ffffff' ? '#555' : color};
                        cursor: pointer;
                    `;
                    preset.onclick = () => {
                        setSelectedColor(color);
                    };
                    presets.appendChild(preset);
                });
                
                // 添加所有元素到容器
                pickerContainer.appendChild(gradientArea);
                pickerContainer.appendChild(colorStrip);
                pickerContainer.appendChild(rgbInputs);
                pickerContainer.appendChild(previewContainer);
                pickerContainer.appendChild(presets);
                panel.appendChild(pickerContainer);
                document.body.appendChild(panel);
                
                // 设置初始颜色
                const setSelectedColor = (color) => {
                    try {
                        // 更新十六进制输入框
                        document.getElementById('text-image-hex-input').value = color;
                        
                        // 更新预览
                        document.getElementById('text-image-color-preview').style.backgroundColor = color;
                        
                        // 解析RGB值并更新输入框
                        const rgb = parseCss(color)?.values || [0, 0, 0];
                        document.getElementById('text-image-r-input').value = rgb[0];
                        document.getElementById('text-image-g-input').value = rgb[1];
                        document.getElementById('text-image-b-input').value = rgb[2];
                        
                        // 更新widget值
                        widget.value = color;
                        app.canvas.setDirty(true);
                    } catch (e) {
                        console.error("设置颜色出错:", e);
                    }
                };
                
                // 注册事件
                document.getElementById('close-color-picker').onclick = () => {
                    panel.remove();
                };
                
                // 处理渐变区域点击和拖动
                let isGradientDragging = false;
                gradientArea.onmousedown = (e) => {
                    isGradientDragging = true;
                    updateGradientCursor(e);
                };
                
                document.addEventListener('mousemove', (e) => {
                    if (isGradientDragging) {
                        updateGradientCursor(e);
                    }
                });
                
                document.addEventListener('mouseup', () => {
                    isGradientDragging = false;
                });
                
                function updateGradientCursor(e) {
                    // 获取相对位置
                    const rect = gradientArea.getBoundingClientRect();
                    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
                    const y = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
                    
                    // 更新光标位置
                    cursor.style.left = `${x}px`;
                    cursor.style.top = `${y}px`;
                    
                    // 计算颜色
                    const hue = (x / rect.width) * 360;
                    const saturation = (rect.width - x) / rect.width;
                    const value = 1 - (y / rect.height);
                    
                    // 将HSV转换为RGB
                    const rgb = hsvToRgb(hue, saturation, value);
                    
                    // 转换为十六进制
                    const hex = rgbToHex(rgb[0], rgb[1], rgb[2]);
                    setSelectedColor(hex);
                }
                
                // 处理颜色条点击和拖动
                let isStripDragging = false;
                colorStrip.onmousedown = (e) => {
                    isStripDragging = true;
                    updateStripCursor(e);
                };
                
                document.addEventListener('mousemove', (e) => {
                    if (isStripDragging) {
                        updateStripCursor(e);
                    }
                });
                
                document.addEventListener('mouseup', () => {
                    isStripDragging = false;
                });
                
                function updateStripCursor(e) {
                    const rect = colorStrip.getBoundingClientRect();
                    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
                    
                    stripCursor.style.left = `${x}px`;
                    
                    // 更新色相
                    const hue = (x / rect.width) * 360;
                    const rgb = hsvToRgb(hue, 1, 1);
                    const hex = rgbToHex(rgb[0], rgb[1], rgb[2]);
                    
                    // 更新渐变区域的背景
                    gradientArea.style.backgroundColor = hex;
                }
                
                // 处理RGB输入框
                ['r', 'g', 'b'].forEach(channel => {
                    const input = document.getElementById(`text-image-${channel}-input`);
                    input.addEventListener('input', () => {
                        const r = parseInt(document.getElementById('text-image-r-input').value) || 0;
                        const g = parseInt(document.getElementById('text-image-g-input').value) || 0;
                        const b = parseInt(document.getElementById('text-image-b-input').value) || 0;
                        
                        const hex = rgbToHex(r, g, b);
                        setSelectedColor(hex);
                    });
                });
                
                // 处理十六进制输入
                hexInput.addEventListener('input', () => {
                    let hex = hexInput.value;
                    if (hex.length > 0 && !hex.startsWith('#')) {
                        hex = '#' + hex;
                        hexInput.value = hex;
                    }
                    
                    // 验证十六进制格式
                    if (/^#([0-9A-F]{3}){1,2}$/i.test(hex)) {
                        setSelectedColor(hex);
                    }
                });
                
                // 设置初始颜色值
                setSelectedColor(widget.value || '#ff0000');
                
                // 辅助函数：HSV转RGB
                function hsvToRgb(h, s, v) {
                    h /= 360;
                    let r, g, b;
                    
                    const i = Math.floor(h * 6);
                    const f = h * 6 - i;
                    const p = v * (1 - s);
                    const q = v * (1 - f * s);
                    const t = v * (1 - (1 - f) * s);
                    
                    switch (i % 6) {
                        case 0: r = v; g = t; b = p; break;
                        case 1: r = q; g = v; b = p; break;
                        case 2: r = p; g = v; b = t; break;
                        case 3: r = p; g = q; b = v; break;
                        case 4: r = t; g = p; b = v; break;
                        case 5: r = v; g = p; b = q; break;
                    }
                    
                    return [
                        Math.round(r * 255),
                        Math.round(g * 255),
                        Math.round(b * 255)
                    ];
                }
                
                // 辅助函数：RGB转十六进制
                function rgbToHex(r, g, b) {
                    return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
                }
                
                // 点击外部关闭面板
                document.addEventListener('mousedown', function(e) {
                    if (panel && !panel.contains(e.target) && e.target !== widget) {
                        panel.remove();
                    }
                });
                
                return panel;
            };
            
            // 增强颜色选择器部件
            nodeType.prototype.enhanceColorWidget = function(widget) {
                // 保存原始的draw函数
                const origDraw = widget.draw;
                
                // 创建颜色选择器UI
                widget.draw = function(ctx, node, widgetWidth, widgetY, height) {
                    if (origDraw && this.type !== "COLOR") {
                        origDraw.call(this, ctx, node, widgetWidth, widgetY, height);
                        return;
                    }
                    
                    // 如果没有value，使用默认值
                    if (!this.value) {
                        this.value = this.name === "font_color" ? "#FFA000" : "#FFFFFF";
                    }
                    
                    // 修改：使用整个宽度作为颜色块，减少间距
                    const margin = 0; // 减少边距
                    const boxHeight = height * 0.85; // 增加高度占比
                    const boxWidth = widgetWidth; // 使用全宽
                    const boxX = margin;
                    const boxY = widgetY + (height - boxHeight) / 2;
                    
                    // 背景颜色
                    ctx.fillStyle = "#333";
                    ctx.fillRect(boxX, widgetY, boxWidth, height);
                    
                    // 绘制颜色块
                    ctx.fillStyle = this.value;
                    ctx.fillRect(boxX, boxY, boxWidth, boxHeight);
                    
                    // 显示名称和十六进制值
                    const color = parseCss ? parseCss(this.value) : null;
                    if (color) {
                        ctx.fillStyle = isColorBright(color.values, 125) ? "#000" : "#fff";
                        ctx.font = "12px Arial";
                        ctx.textAlign = "center";
                        
                        // 在颜色块中央显示名称
                        const displayName = this.name === "font_color" ? "文本颜色" : "背景颜色";
                        ctx.fillText(displayName, boxWidth / 2, boxY + boxHeight / 3);
                        
                        // 在颜色块下方显示十六进制值
                        ctx.fillText(this.value, boxWidth / 2, boxY + boxHeight * 2/3);
                    }
                    
                    // 保存位置信息用于鼠标事件
                    this._color_picker = {
                        x: boxX,
                        y: boxY,
                        width: boxWidth,
                        height: boxHeight
                    };
                };
                
                // 处理鼠标事件
                const origMouse = widget.mouse || function() {};
                widget.mouse = function(e, pos, node) {
                    const result = origMouse.call(this, e, pos, node);
                    
                    if (e.type === "pointerdown" && this._color_picker) {
                        const { x, y, width, height } = this._color_picker;
                        const [mouseX, mouseY] = pos;
                        
                        if (mouseX >= x && mouseX <= x + width && 
                            mouseY >= y && mouseY <= y + height) {
                            // 计算颜色选择器的位置（固定在节点边缘）
                            const canvasRect = app.canvas.canvas.getBoundingClientRect();
                            const nodePos = node.pos;
                            const nodeSize = node.size;
                            
                            // 计算节点在canvas上的位置
                            const scale = app.canvas.ds.scale;
                            const offset = app.canvas.ds.offset;
                            
                            // 计算节点在屏幕上的实际位置
                            const nodeScreenX = (nodePos[0] * scale) + offset[0] + canvasRect.left;
                            const nodeScreenY = (nodePos[1] * scale) + offset[1] + canvasRect.top;
                            
                            // 节点右侧边缘的位置
                            const nodeRightX = nodeScreenX + (nodeSize[0] * scale);
                            
                            // 创建颜色选择器，并固定在节点右侧
                            createColorPickerPanel(
                                node, 
                                widget, 
                                nodeRightX + 5, 
                                nodeScreenY
                            );
                            
                            return true;
                        }
                    }
                    
                    return result;
                };
                
                // 设置原始类型为COLOR
                widget.type = "COLOR";
            };
        }
    }
});
