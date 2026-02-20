# 天气配置设计

## 方案：分层配置 + 智能识别

### 1. 默认城市（配置层）
用户通过 config 设置常住地，作为默认天气位置：

```bash
# 设置默认城市
munin config weather.location "Shanghai"

# 或使用中文
munin config weather.location "上海"
```

### 2. 日记中临时指定（消息层）
用户在日记消息中提及地点，自动识别并覆盖默认：

```
用户：今天在杭州西湖边散步，天气真好
系统：识别到"杭州" -> 获取杭州天气
标题：2026年2月20日 周四 🌤️ 正月廿三 杭州
```

### 3. 自动提取策略

```python
# 在日记消息中识别地点关键词
LOCATION_KEYWORDS = {
    '北京': 'Beijing',
    '上海': 'Shanghai', 
    '杭州': 'Hangzhou',
    '深圳': 'Shenzhen',
    '成都': 'Chengdu',
    '广州': 'Guangzhou',
    '普洱': 'Puer',
    '香港': 'Hong Kong',
    '东京': 'Tokyo',
    # ... 可扩展
}

def extract_location_from_message(message: str) -> Optional[str]:
    """从日记消息中提取地点"""
    for cn, en in LOCATION_KEYWORDS.items():
        if cn in message:
            return en
    return None  # 使用默认配置
```

### 4. 标题格式

```
# 默认城市
2026年2月20日 周四 🌤️ 正月廿三

# 指定城市（在标题末尾标注）
2026年2月20日 周四 🌤️ 正月廿三 · 杭州
```

### 5. 配置优先级

1. 消息中明确提到的地点（最高优先级）
2. 用户配置的默认城市
3. 系统默认（上海/Beijing）

### 6. 实现代码

```python
# bot/sync/weather_service.py

class WeatherConfig:
    """天气配置管理"""
    DEFAULT_LOCATION = "Shanghai"
    
    @classmethod
    def get_location(cls, user_id: int, message: str = None) -> str:
        """获取天气位置"""
        # 1. 尝试从消息提取
        if message:
            location = cls._extract_from_message(message)
            if location:
                return location
        
        # 2. 使用用户配置
        user_config = cls._get_user_config(user_id)
        if user_config.get('weather_location'):
            return user_config['weather_location']
        
        # 3. 使用系统默认
        return cls.DEFAULT_LOCATION
    
    @classmethod
    def _extract_from_message(cls, message: str) -> Optional[str]:
        """从消息中提取地点"""
        # 匹配 "在XX"、"去XX"、"到XX" 等模式
        import re
        patterns = [
            r'在(\w+)[市区县]?',
            r'去(\w+)[市区县]?',
            r'到(\w+)[市区县]?',
            r'(\w+)[市区县]?的?天气',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                city_cn = match.group(1)
                return CITY_MAP.get(city_cn)
        
        return None
```

### 7. 用户交互示例

```
用户：munin config weather.location 杭州
系统：✅ 已设置默认天气位置为：杭州

用户：今天在家休息
系统：📍 使用默认位置：杭州
标题：2026年2月20日 周四 🌧️ 正月廿三

用户：来北京出差了，天气好冷
系统：📍 识别到位置：北京
标题：2026年2月20日 周四 ❄️ 正月廿三 · 北京
```

## 优点

1. **智能**：自动识别消息中的地点
2. **灵活**：支持临时变更，不改配置
3. **可扩展**：地点词库可动态添加
4. **向后兼容**：没有地点信息时用默认配置

## 实现步骤

1. 添加城市映射表（中文->英文）
2. 实现消息地点提取函数
3. 修改标题生成逻辑，支持地点标注
4. 添加 config 命令支持
