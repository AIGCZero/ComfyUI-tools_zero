/**
 * parse-css.js
 * 简单的CSS颜色值解析库，用于解析CSS颜色值（如RGB、十六进制等）
 */

// 将十六进制颜色值转换为RGB数组
function hexToRgb(hex) {
  // 移除#前缀（如果有）
  hex = hex.replace(/^#/, '');
  
  // 处理简写形式（#RGB）
  if (hex.length === 3) {
    hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
  }
  
  const bigint = parseInt(hex, 16);
  return [
    (bigint >> 16) & 255,
    (bigint >> 8) & 255,
    bigint & 255
  ];
}

// 解析rgba()和rgb()格式
function parseRgb(color) {
  const match = color.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (!match) return null;
  
  return {
    type: match[4] !== undefined ? 'rgba' : 'rgb',
    values: [
      parseInt(match[1], 10),
      parseInt(match[2], 10),
      parseInt(match[3], 10),
      match[4] !== undefined ? parseFloat(match[4]) : 1
    ]
  };
}

// 解析hsla()和hsl()格式
function parseHsl(color) {
  const match = color.match(/hsla?\(\s*(\d+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (!match) return null;
  
  // 将HSL转换为RGB
  const h = parseInt(match[1], 10) / 360;
  const s = parseInt(match[2], 10) / 100;
  const l = parseInt(match[3], 10) / 100;
  const a = match[4] !== undefined ? parseFloat(match[4]) : 1;
  
  let r, g, b;
  
  if (s === 0) {
    r = g = b = l;
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
  
  return {
    type: match[4] !== undefined ? 'hsla' : 'hsl',
    values: [
      Math.round(r * 255),
      Math.round(g * 255),
      Math.round(b * 255),
      a
    ]
  };
}

// 颜色名称映射
const COLOR_NAMES = {
  black: '#000000',
  silver: '#c0c0c0',
  gray: '#808080',
  white: '#ffffff',
  maroon: '#800000',
  red: '#ff0000',
  purple: '#800080',
  fuchsia: '#ff00ff',
  green: '#008000',
  lime: '#00ff00',
  olive: '#808000',
  yellow: '#ffff00',
  navy: '#000080',
  blue: '#0000ff',
  teal: '#008080',
  aqua: '#00ffff'
};

// 解析CSS颜色值
function parseCss(color) {
  if (!color) return null;
  
  // 处理颜色名称
  if (COLOR_NAMES[color.toLowerCase()]) {
    color = COLOR_NAMES[color.toLowerCase()];
  }
  
  // 处理十六进制
  if (color.startsWith('#')) {
    const values = hexToRgb(color);
    return {
      type: 'hex',
      values: values,
      original: color
    };
  }
  
  // 处理RGB/RGBA
  if (color.startsWith('rgb')) {
    return parseRgb(color);
  }
  
  // 处理HSL/HSLA
  if (color.startsWith('hsl')) {
    return parseHsl(color);
  }
  
  return null;
}

export default parseCss; 