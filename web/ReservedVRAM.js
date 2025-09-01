import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "ReservedVRAM",
    
    async setup() {
        // 初始化显存信息显示
        this.updateVRAMInfo();
        
        // 定期更新显存信息
        setInterval(() => {
            this.updateVRAMInfo();
        }, 5000); // 每5秒更新一次
        
        // 创建顶部控制栏
        this.createToolbarWidget();
    },
    
    createToolbarWidget() {
        // 等待DOM和ComfyUI完全加载
        setTimeout(() => {
            try {
                // 方法1: 使用新版ComfyUI按钮API
                if (window?.comfyAPI?.button?.ComfyButton && window?.comfyAPI?.buttonGroup?.ComfyButtonGroup) {
                    this.createComfyAPIWidget();
                } else {
                    // 方法2: 尝试直接在DOM中找到合适的位置
                    this.createDOMWidget();
                }
            } catch (e) {
                console.error("ReservedVRAM: 创建控件失败", e);
                // 方法3: 备用方案 - 在页面任意位置创建浮动控件
                this.createFloatingWidget();
            }
        }, 2000);
    },
    
// ... existing code ...
createComfyAPIWidget() {
    try {
        const ComfyButton = window.comfyAPI.button.ComfyButton;
        const ComfyButtonGroup = window.comfyAPI.buttonGroup.ComfyButtonGroup;
        
        // 创建显存信息显示容器
        const widgetContainer = document.createElement('div');
        widgetContainer.id = 'vram-widget-container';
        widgetContainer.style.cssText = `
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 8px;
            background: rgba(40, 40, 40, 0.8);
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 12px;
            color: #fff;
            position: relative;
            overflow: hidden;
        `;
        
        // 创建输入容器
        const inputContainer = document.createElement('div');
        inputContainer.style.cssText = `
            display: flex;
            align-items: center;
            gap: 4px;
            min-width: 120px;
        `;
        
        // 创建输入标签
        const inputLabel = document.createElement('span');
        inputLabel.textContent = '显存预留:';
        inputLabel.style.cssText = `
            font-size: 11px;
            color: #ccc;
            font-weight: 400;
            white-space: nowrap;
        `;
        
        // 创建输入框
        const input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.max = '48';
        input.step = '0.1';
        input.value = '0';
        input.placeholder = '0.0';
        input.style.cssText = `
            width: 45px;
            height: 22px;
            padding: 2px 4px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            background: rgba(30, 30, 30, 0.9);
            color: #fff;
            font-size: 11px;
            text-align: center;
            outline: none;
            transition: all 0.15s ease;
            font-family: 'Segoe UI', monospace;
        `;
        
        // 输入框焦点样式
        input.addEventListener('focus', () => {
            input.style.borderColor = 'rgba(100, 150, 255, 0.5)';
            input.style.background = 'rgba(35, 35, 35, 0.95)';
        });
        
        input.addEventListener('blur', () => {
            input.style.borderColor = 'rgba(255, 255, 255, 0.2)';
            input.style.background = 'rgba(30, 30, 30, 0.9)';
        });
        
        // 创建单位标签
        const unitLabel = document.createElement('span');
        unitLabel.textContent = 'GB';
        unitLabel.style.cssText = `
            font-size: 10px;
            color: #999;
            font-weight: 400;
        `;
        
        // 组装输入容器
        inputContainer.appendChild(inputLabel);
        inputContainer.appendChild(input);
        inputContainer.appendChild(unitLabel);
        
        // 组装主容器
        widgetContainer.appendChild(inputContainer);
        
        // 创建按钮组并添加到设置区域
        const group = new ComfyButtonGroup(widgetContainer);
        
        if (app.menu?.settingsGroup?.element) {
            app.menu.settingsGroup.element.before(group.element);
            console.log("ReservedVRAM: 使用ComfyAPI成功添加控件");
        } else if (app.menu?.element) {
            app.menu.element.appendChild(group.element);
            console.log("ReservedVRAM: 添加到menu element");
        }
        
        // 设置输入框事件
        this.setupInputEvents(input);
        
        // 获取当前设置
        this.getCurrentReservedVRAM().then(value => {
            input.value = value;
        });
        
    } catch (e) {
        console.error("ReservedVRAM: ComfyAPI控件创建失败", e);
        this.createDOMWidget();
    }
},

createDOMWidget() {
    try {
        // 查找可能的菜单位置
        const menuSelectors = [
            'header',
            '.comfy-menu', 
            '.menu-container',
            '.toolbar',
            '.comfy-toolbar',
            '[class*="menu"]',
            '[class*="toolbar"]',
            '.top-bar',
            '.nav'
        ];
        
        let targetContainer = null;
        for (const selector of menuSelectors) {
            targetContainer = document.querySelector(selector);
            if (targetContainer) {
                console.log(`ReservedVRAM: 找到容器 ${selector}`);
                break;
            }
        }
        
        if (!targetContainer) {
            // 如果找不到菜单，创建到body的顶部
            targetContainer = document.body;
            console.log("ReservedVRAM: 使用body作为容器");
        }
        
        // 创建控件容器
        const widgetContainer = document.createElement('div');
        widgetContainer.id = 'vram-widget-container';
        widgetContainer.style.cssText = `
            position: ${targetContainer === document.body ? 'fixed' : 'relative'};
            top: ${targetContainer === document.body ? '10px' : 'auto'};
            right: ${targetContainer === document.body ? '10px' : 'auto'};
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 8px;
            background: rgba(40, 40, 40, 0.8);
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 9999;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 12px;
            color: #fff;
            position: relative;
            overflow: hidden;
        `;
        
        // 创建输入容器
        const inputContainer = document.createElement('div');
        inputContainer.style.cssText = `
            display: flex;
            align-items: center;
            gap: 4px;
            min-width: 120px;
        `;
        
        // 创建输入标签
        const inputLabel = document.createElement('span');
        inputLabel.textContent = '显存预留:';
        inputLabel.style.cssText = `
            font-size: 11px;
            color: #ccc;
            font-weight: 400;
            white-space: nowrap;
        `;
        
        // 创建输入框
        const input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.max = '48';
        input.step = '0.1';
        input.value = '0';
        input.placeholder = '0.0';
        input.style.cssText = `
            width: 45px;
            height: 22px;
            padding: 2px 4px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            background: rgba(30, 30, 30, 0.9);
            color: #fff;
            font-size: 11px;
            text-align: center;
            outline: none;
            transition: all 0.15s ease;
            font-family: 'Segoe UI', monospace;
        `;
        
        // 输入框焦点样式
        input.addEventListener('focus', () => {
            input.style.borderColor = 'rgba(100, 150, 255, 0.5)';
            input.style.background = 'rgba(35, 35, 35, 0.95)';
        });
        
        input.addEventListener('blur', () => {
            input.style.borderColor = 'rgba(255, 255, 255, 0.2)';
            input.style.background = 'rgba(30, 30, 30, 0.9)';
        });
        
        // 创建单位标签
        const unitLabel = document.createElement('span');
        unitLabel.textContent = 'GB';
        unitLabel.style.cssText = `
            font-size: 10px;
            color: #999;
            font-weight: 400;
        `;
        
        // 组装输入容器
        inputContainer.appendChild(inputLabel);
        inputContainer.appendChild(input);
        inputContainer.appendChild(unitLabel);
        
        // 组装主容器
        widgetContainer.appendChild(inputContainer);
        
        targetContainer.appendChild(widgetContainer);
        
        // 设置输入框事件
        this.setupInputEvents(input);
        
        // 获取当前设置
        this.getCurrentReservedVRAM().then(value => {
            input.value = value;
        });
        
        console.log("ReservedVRAM: DOM控件创建成功");
        
    } catch (e) {
        console.error("ReservedVRAM: DOM控件创建失败", e);
        this.createFloatingWidget();
    }
},

createFloatingWidget() {
    // 创建浮动控件作为备用方案
    const floatingWidget = document.createElement('div');
    floatingWidget.id = 'vram-floating-widget';
    floatingWidget.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: rgba(40, 40, 40, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 10px;
        z-index: 10000;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 12px;
        color: #fff;
        cursor: move;
        min-width: 180px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        position: relative;
        overflow: hidden;
    `;
    
    const title = document.createElement('div');
    title.textContent = '显存预留';
    title.style.cssText = `
        font-weight: 500;
        margin-bottom: 8px;
        text-align: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding-bottom: 6px;
        font-size: 12px;
        color: #e0e0e0;
    `;
    
    const inputContainer = document.createElement('div');
    inputContainer.style.cssText = `
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 6px;
    `;
    
    const inputLabel = document.createElement('span');
    inputLabel.textContent = '预留:';
    inputLabel.style.cssText = `
        font-size: 11px;
        color: #ccc;
        font-weight: 400;
        min-width: 28px;
    `;
    
    const input = document.createElement('input');
    input.type = 'number';
    input.min = '0';
    input.max = '48';
    input.step = '0.1';
    input.value = '0';
    input.placeholder = '0.0';
    input.style.cssText = `
        width: 50px;
        height: 24px;
        padding: 3px 6px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        background: rgba(30, 30, 30, 0.9);
        color: #fff;
        font-size: 11px;
        text-align: center;
        outline: none;
        transition: all 0.15s ease;
        font-family: 'Segoe UI', monospace;
    `;
    
    // 输入框焦点样式
    input.addEventListener('focus', () => {
        input.style.borderColor = 'rgba(100, 150, 255, 0.5)';
        input.style.background = 'rgba(35, 35, 35, 0.95)';
    });
    
    input.addEventListener('blur', () => {
        input.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        input.style.background = 'rgba(30, 30, 30, 0.9)';
    });
    
    const unitLabel = document.createElement('span');
    unitLabel.textContent = 'GB';
    unitLabel.style.cssText = `
        font-size: 10px;
        color: #999;
        font-weight: 400;
    `;
    
    inputContainer.appendChild(inputLabel);
    inputContainer.appendChild(input);
    inputContainer.appendChild(unitLabel);
    
    floatingWidget.appendChild(title);
    floatingWidget.appendChild(inputContainer);
    
    document.body.appendChild(floatingWidget);
    
    // 设置输入框事件
    this.setupInputEvents(input);
    
    // 获取当前设置
    this.getCurrentReservedVRAM().then(value => {
        input.value = value;
    });
    
    // 添加拖拽功能
    this.makeDraggable(floatingWidget);
    
    console.log("ReservedVRAM: 浮动控件创建成功");
},
// ... existing code ...
    
    setupInputEvents(input) {
        // 输入框值变化事件
        input.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            if (value < 0) e.target.value = 0;
            if (value > 48) e.target.value = 48;
        });
        
        // 输入框失去焦点事件（设置显存预留）
        input.addEventListener('blur', (e) => {
            const value = parseFloat(e.target.value) || 0;
            this.setReservedVRAM(value);
        });
        
        // 回车键确认
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const value = parseFloat(e.target.value) || 0;
                this.setReservedVRAM(value);
                input.blur();
            }
        });
    },
    
    makeDraggable(element) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        element.onmousedown = dragMouseDown;
        
        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }
        
        function elementDrag(e) {
            e = e || window.event;
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            element.style.top = (element.offsetTop - pos2) + "px";
            element.style.left = (element.offsetLeft - pos1) + "px";
        }
        
        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    },
    
    async updateVRAMInfo() {
        try {
            const response = await fetch('/reserved_vram/info');
            const data = await response.json();
            
            const vramInfoElements = [
                document.getElementById('vram-info')
            ].filter(el => el);
            
            if (vramInfoElements.length > 0 && !data.error) {
                const freeGB = data.free_gb;
                const totalGB = data.total_gb;
                const reservedGB = data.reserved_vram_gb;
                
                const infoText = `显存: ${freeGB}GB/${totalGB}GB (预留: ${reservedGB}GB)`;
                
                vramInfoElements.forEach(element => {
                    element.innerHTML = infoText;
                    
                    // 根据可用显存设置颜色
                    if (freeGB < 2) {
                        element.style.color = '#ff6b6b'; // 红色警告
                    } else if (freeGB < 4) {
                        element.style.color = '#ffd93d'; // 黄色警告
                    } else {
                        element.style.color = '#6bcf7f'; // 绿色正常
                    }
                });
            }
        } catch (error) {
            console.error('更新显存信息失败:', error);
        }
    },
    
    async setReservedVRAM(gb) {
        try {
            const response = await fetch('/reserved_vram/set', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ gb: gb })
            });
            
            const data = await response.json();
            
            if (data.error) {
                console.error(`设置失败: ${data.error}`);
            } else {
                console.log(`显存预留设置成功: ${gb}GB`);
                this.updateVRAMInfo();
            }
        } catch (error) {
            console.error('设置显存预留失败:', error);
        }
    },
    
    async getCurrentReservedVRAM() {
        try {
            const response = await fetch('/reserved_vram/get');
            const data = await response.json();
            return data.reserved_vram_gb || 0;
        } catch (error) {
            console.error('获取显存预留设置失败:', error);
            return 0;
        }
    }
});
