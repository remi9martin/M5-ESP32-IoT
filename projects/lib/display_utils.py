# M5Stack Display Utilities
# Shared drawing functions for all M5Stack projects

# Color palette (RGB565 format for M5Stack displays)
COLORS = {
    'black': 0x0000,
    'white': 0xFFFF,
    'red': 0xF800,
    'green': 0x07E0,
    'blue': 0x001F,
    'cyan': 0x07FF,
    'magenta': 0xF81F,
    'yellow': 0xFFE0,
    'orange': 0xFD20,
    'purple': 0x8010,
    'gray': 0x8410,
    'dark_gray': 0x4208,
}

# Thermal color gradient (cold to hot)
THERMAL_GRADIENT = [
    0x001F,  # Blue (cold)
    0x07FF,  # Cyan
    0x07E0,  # Green
    0xFFE0,  # Yellow
    0xFD20,  # Orange
    0xF800,  # Red (hot)
]

def rgb_to_565(r, g, b):
    """Convert RGB888 to RGB565"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def interpolate_color(color1, color2, t):
    """Interpolate between two RGB565 colors (t: 0.0 to 1.0)"""
    # Extract RGB components
    r1 = (color1 >> 11) & 0x1F
    g1 = (color1 >> 5) & 0x3F
    b1 = color1 & 0x1F
    
    r2 = (color2 >> 11) & 0x1F
    g2 = (color2 >> 5) & 0x3F
    b2 = color2 & 0x1F
    
    # Interpolate
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    
    return (r << 11) | (g << 5) | b

def temp_to_color(temp, min_temp=15.0, max_temp=40.0):
    """Map temperature to thermal gradient color"""
    if temp <= min_temp:
        return THERMAL_GRADIENT[0]
    if temp >= max_temp:
        return THERMAL_GRADIENT[-1]
    
    # Normalize temperature to 0-1 range
    t = (temp - min_temp) / (max_temp - min_temp)
    
    # Find gradient segment
    segments = len(THERMAL_GRADIENT) - 1
    segment = int(t * segments)
    segment = min(segment, segments - 1)
    
    # Local interpolation within segment
    local_t = (t * segments) - segment
    
    return interpolate_color(
        THERMAL_GRADIENT[segment], 
        THERMAL_GRADIENT[segment + 1], 
        local_t
    )

def draw_progress_bar(display, x, y, width, height, value, max_value, 
                      fg_color=None, bg_color=None):
    """Draw a horizontal progress bar"""
    fg = fg_color or COLORS['green']
    bg = bg_color or COLORS['dark_gray']
    
    # Background
    display.rect(x, y, width, height, bg, True)
    
    # Foreground (filled portion)
    fill_width = int((value / max_value) * (width - 2))
    if fill_width > 0:
        display.rect(x + 1, y + 1, fill_width, height - 2, fg, True)
    
    # Border
    display.rect(x, y, width, height, COLORS['white'], False)

def draw_battery_icon(display, x, y, percent, charging=False):
    """Draw battery status icon"""
    # Battery body
    display.rect(x, y, 20, 10, COLORS['white'], False)
    # Battery tip
    display.rect(x + 20, y + 3, 3, 4, COLORS['white'], True)
    
    # Fill level
    fill_width = int((percent / 100) * 16)
    if percent > 60:
        color = COLORS['green']
    elif percent > 20:
        color = COLORS['yellow']
    else:
        color = COLORS['red']
    
    if fill_width > 0:
        display.rect(x + 2, y + 2, fill_width, 6, color, True)
    
    # Charging indicator
    if charging:
        display.text("⚡", x + 7, y + 1, COLORS['yellow'])

def draw_signal_bars(display, x, y, strength, max_strength=4):
    """Draw WiFi-style signal strength bars"""
    bar_width = 4
    gap = 2
    
    for i in range(max_strength):
        bar_height = 4 + (i * 3)
        bar_x = x + i * (bar_width + gap)
        bar_y = y + (max_strength * 3) - bar_height + 4
        
        if i < strength:
            color = COLORS['green'] if strength > 2 else COLORS['yellow']
        else:
            color = COLORS['dark_gray']
        
        display.rect(bar_x, bar_y, bar_width, bar_height, color, True)

def draw_status_dot(display, x, y, status):
    """Draw colored status indicator dot"""
    colors = {
        'online': COLORS['green'],
        'offline': COLORS['red'],
        'warning': COLORS['yellow'],
        'idle': COLORS['gray'],
    }
    color = colors.get(status, COLORS['gray'])
    display.circle(x, y, 4, color, True)

def center_text(display, text, y, color=None, font_size=1):
    """Draw centered text on display"""
    c = color or COLORS['white']
    # Approximate character width (varies by font)
    char_width = 8 * font_size
    text_width = len(text) * char_width
    x = (display.width() - text_width) // 2
    display.text(text, x, y, c)

def draw_header(display, title, bg_color=None):
    """Draw a header bar with title"""
    bg = bg_color or COLORS['blue']
    display.rect(0, 0, display.width(), 20, bg, True)
    center_text(display, title, 4, COLORS['white'])
