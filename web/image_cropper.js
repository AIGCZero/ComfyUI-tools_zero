import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// 创建裁剪模态窗口的HTML结构
function createCropperModal() {
    const modal = document.createElement("dialog");
    modal.id = "image-cropper-modal";
    modal.innerHTML = `
        <div class="cropper-container">
            <div class="cropper-header">
                <h3>图像裁剪</h3>
                <button class="close-button">×</button>
            </div>
            <div class="cropper-content">
                <div class="cropper-wrapper">
                    <canvas id="crop-canvas"></canvas>
                    <div class="crop-selection"></div>
                </div>
                <div class="cropper-controls">
                    <button id="apply-crop">应用裁剪</button>
                    <button id="cancel-crop">取消</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    return modal;
}

// 修改样式
const style = document.createElement("style");
style.textContent = `
    #image-cropper-modal {
        border: none;
        border-radius: 8px;
        padding: 0;
        background: #2a2a2a;
        max-width: 90vw;  /* 限制最大宽度 */
        max-height: 90vh; /* 限制最大高度 */
    }
    
    .cropper-container {
        width: fit-content;  /* 根据内容自适应 */
        height: fit-content;
        min-width: 400px;   /* 减小最小尺寸 */
        min-height: 300px;
        display: flex;
        flex-direction: column;
    }
    
    .cropper-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 20px;
        background: #333;
        border-bottom: 1px solid #444;
    }
    
    .cropper-header h3 {
        margin: 0;
        color: #fff;
    }
    
    .close-button {
        background: none;
        border: none;
        color: #fff;
        font-size: 24px;
        cursor: pointer;
    }
    
    .cropper-content {
        padding: 20px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        overflow: auto;    /* 添加滚动条 */
    }
    
    .cropper-wrapper {
        position: relative;
        overflow: hidden;
        background: #1a1a1a;
        display: flex;     /* 使用flex布局 */
        justify-content: center;
        align-items: center;
    }
    
    #crop-canvas {
        max-width: 100%;
        max-height: 70vh;
        object-fit: contain; /* 保持比例 */
    }
    
    .crop-selection {
        position: absolute;
        border: 2px solid #00ff00;
        background: rgba(0, 255, 0, 0.1);
        pointer-events: none;
        transform-origin: 0 0; /* 添加变换原点 */
    }
    
    .cropper-controls {
        display: flex;
        gap: 10px;
        justify-content: flex-end;
    }
    
    .cropper-controls button {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    
    #apply-crop {
        background: #2a8af6;
        color: white;
    }
    
    #cancel-crop {
        background: #666;
        color: white;
    }
`;
document.head.appendChild(style);

// 裁剪功能类
class ImageCropper {
    constructor() {
        this.modal = createCropperModal();
        this.canvas = this.modal.querySelector("#crop-canvas");
        this.ctx = this.canvas.getContext("2d");
        this.selection = this.modal.querySelector(".crop-selection");
        
        this.isDrawing = false;
        this.startX = 0;
        this.startY = 0;
        
        this.hasFixedSeed = false;
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // 关闭按钮事件
        const closeButton = this.modal.querySelector(".close-button");
        if (closeButton) {
            closeButton.addEventListener("click", () => {
                this.cleanupAndClose(true);  // true 表示是取消操作
            });
        }
        
        // 取消按钮事件
        const cancelButton = this.modal.querySelector("#cancel-crop");
        if (cancelButton) {
            cancelButton.addEventListener("click", () => {
                this.cleanupAndClose(true);  // true 表示是取消操作
            });
        }
        
        // 应用裁剪按钮事件
        const applyButton = this.modal.querySelector("#apply-crop");
        if (applyButton) {
            applyButton.addEventListener("click", () => this.applyCrop());
        }
        
        // ESC键关闭
        this.modal.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                this.cleanupAndClose(true);  // true 表示是取消操作
            }
        });
        
        // 画布鼠标事件
        this.canvas.addEventListener("mousedown", (e) => this.startDrawing(e));
        this.canvas.addEventListener("mousemove", (e) => this.draw(e));
        this.canvas.addEventListener("mouseup", () => this.endDrawing());
        
        // 添加调试日志
        console.log("事件监听器已设置:", {
            closeButton: !!closeButton,
            cancelButton: !!cancelButton,
            applyButton: !!applyButton
        });
    }
    
    async cleanupAndClose(cancelled = false) {
        // 如果是取消操作，通知后端
        if (cancelled && this.currentNodeId) {
            try {
                await api.fetchApi("/zero_image_cropper/cancel", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        node_id: this.currentNodeId
                    })
                });
            } catch (error) {
                console.error("发送取消信号失败:", error);
            }
        }
        
        // 清理选择框
        if (this.selection) {
            this.selection.style.display = 'none';
            this.selection.style.width = '0';
            this.selection.style.height = '0';
        }
        
        // 清理画布
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        
        // 重置状态
        this.isDrawing = false;
        this.startX = 0;
        this.startY = 0;
        
        // 关闭窗口
        this.modal.close();
    }
    
    startDrawing(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.isDrawing = true;
        this.startX = e.clientX - rect.left;
        this.startY = e.clientY - rect.top;
        
        this.selection.style.left = `${this.startX}px`;
        this.selection.style.top = `${this.startY}px`;
        this.selection.style.width = "0px";
        this.selection.style.height = "0px";
        this.selection.style.display = "block";
    }
    
    draw(e) {
        if (!this.isDrawing) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        const width = currentX - this.startX;
        const height = currentY - this.startY;
        
        this.selection.style.width = `${Math.abs(width)}px`;
        this.selection.style.height = `${Math.abs(height)}px`;
        this.selection.style.left = `${width < 0 ? currentX : this.startX}px`;
        this.selection.style.top = `${height < 0 ? currentY : this.startY}px`;
    }
    
    endDrawing() {
        this.isDrawing = false;
    }
    
    calculateScale() {
        const canvas = this.canvas;
        const wrapper = canvas.parentElement;
        
        // 获取实际显示尺寸
        const displayRect = canvas.getBoundingClientRect();
        
        // 计算缩放比例
        this.scaleX = canvas.width / displayRect.width;
        this.scaleY = canvas.height / displayRect.height;
        
        console.log("缩放比例:", {
            scaleX: this.scaleX,
            scaleY: this.scaleY,
            canvasWidth: canvas.width,
            canvasHeight: canvas.height,
            displayWidth: displayRect.width,
            displayHeight: displayRect.height
        });
    }
    
    async applyCrop() {
        // 检查是否有选择区域
        if (!this.selection || 
            !this.selection.style.width || 
            !this.selection.style.height ||
            parseInt(this.selection.style.width) <= 0 ||
            parseInt(this.selection.style.height) <= 0) {
            console.warn("未选择有效的裁剪区域");
            this.cleanupAndClose();
            return;
        }

        const rect = this.selection.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();
        
        // 计算实际坐标（考虑缩放）
        let x = (rect.left - canvasRect.left) * this.scaleX;
        let y = (rect.top - canvasRect.top) * this.scaleY;
        let width = rect.width * this.scaleX;
        let height = rect.height * this.scaleY;

        console.log("裁剪参数:", {
            x, y, width, height,
            originalRect: rect,
            canvasRect: canvasRect
        });

        // 确保坐标和尺寸在有效范围内
        x = Math.max(0, Math.min(x, this.canvas.width));
        y = Math.max(0, Math.min(y, this.canvas.height));
        width = Math.min(width, this.canvas.width - x);
        height = Math.min(height, this.canvas.height - y);

        // 检查最终尺寸是否有效
        if (width <= 0 || height <= 0) {
            console.error("裁剪区域无效");
            this.cleanupAndClose();
            return;
        }
        
        try {
            // 创建临时画布进行裁剪
            const tempCanvas = document.createElement("canvas");
            tempCanvas.width = width;
            tempCanvas.height = height;
            const tempCtx = tempCanvas.getContext("2d");
            
            // 添加错误处理
            try {
                tempCtx.drawImage(this.canvas, 
                    x, y, width, height,
                    0, 0, width, height
                );
            } catch (drawError) {
                console.error("裁剪绘制失败:", drawError);
                this.cleanupAndClose();
                return;
            }
            
            // 转换为base64
            let croppedImage;
            try {
                croppedImage = tempCanvas.toDataURL("image/png");
            } catch (dataUrlError) {
                console.error("图像转换失败:", dataUrlError);
                this.cleanupAndClose();
                return;
            }
            
            console.log("准备发送请求，参数:", {
                node_id: this.currentNodeId,
                width: Math.round(width),
                height: Math.round(height),
                x: Math.round(x),
                y: Math.round(y),
                imageLength: croppedImage.length
            });

            // 简化请求处理
            await api.fetchApi("/zero_image_cropper/apply", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    node_id: this.currentNodeId,
                    width: Math.round(width),
                    height: Math.round(height),
                    x: Math.round(x),
                    y: Math.round(y),
                    cropped_data_base64: croppedImage,
                })
            });
            
            // 简单关闭窗口
            this.cleanupAndClose();
            
        } catch (error) {
            console.error("裁剪操作失败:", error);
            this.cleanupAndClose();
        }
    }
    
    show(nodeId, imageData, node) {
        this.currentNodeId = nodeId;
        this.currentNode = node;
        
        const img = new Image();
        img.onload = () => {
            this.canvas.width = img.width;
            this.canvas.height = img.height;
            this.ctx.drawImage(img, 0, 0);
            this.modal.showModal();
            
            // 计算初始缩放比例
            this.calculateScale();
        };
        img.src = imageData;
    }
}

// 注册节点
app.registerExtension({
    name: "Zero_ImageCropper",
    async setup() {
        const cropper = new ImageCropper();
        
        // 监听裁剪更新事件
        api.addEventListener("zero_image_cropper_update", ({ detail }) => {
            const { node_id, image_data } = detail;
            const node = app.graph.getNodeById(node_id);
            cropper.show(node_id, image_data, node);
        });
    },
    
    async beforeRegisterNodeDef(nodeType, nodeData) {
        // 只处理 ImageCropper 节点
        if (nodeData.name === "Zero_ImageCropper") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            
            // 重写节点创建方法
            nodeType.prototype.onNodeCreated = function() {
                if (onNodeCreated) {
                    onNodeCreated.apply(this, arguments);
                }
                
                // 创建种子值组件
                const seedWidget = this.addWidget(
                    "number",
                    "seed",
                    0,
                    (value) => {
                        this.seed = value;
                    },
                    {
                        min: 0,
                        max: Number.MAX_SAFE_INTEGER,
                        step: 1,
                        precision: 0
                    }
                );
                
                // 创建裁剪按钮
                const cropButton = this.addWidget("button", "裁剪图像", null, () => {
                    // 使用随机种子
                    let newValue = Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
                    seedWidget.value = newValue;
                    seedWidget.callback(newValue);
                    
                    // 使用rgthree的队列输出节点方法
                    if (window.rgthree && window.rgthree.queueOutputNodes) {
                        window.rgthree.queueOutputNodes([this.id]);
                    }
                });
            };
        }
    }
});
