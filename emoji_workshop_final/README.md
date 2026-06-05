# 表情工坊 - 智能表情包管理系统

> 基于 PyQt6 + SQLite 构建的桌面端表情包管理工具，支持上下文智能推荐、性格画像分析、AI 文生图等功能。

---

## 核心功能

| 功能 | 说明 |
|:---|:---|
| 📁 库管理 | 批量导入文件夹，自动生成缩略图，支持删除 |
| 🏷️ 标签系统 | 自定义标签颜色，多标签交集筛选 |
| 🔍 搜索 | 按名称关键词快速搜索 |
| 📊 数据统计 | 格式分布、大小分布、标签频率、导入趋势图表 |
| 🎨 AI 生成 | 文字描述生成表情包（Pollinations.ai 免费 / 硅基流动） |
| 💡 网页导入提示 | 建议通过浏览器右键图片另存为后拖入程序 |
| 🎯 上下文推荐 | 粘贴聊天上下文，调用大模型（LLM）理解语义并匹配最合适标签，推荐相关表情 |
| 📝 性格画像 | 基于使用历史分析时段偏好、高频标签，生成个性化报告 |

---

## 技术栈

- **GUI 框架**：PyQt6
- **数据库**：SQLite 3（内置，无需额外安装）
- **图像处理**：Pillow
- **数据可视化**：matplotlib（嵌入 PyQt6）
- **网络请求**：requests
- **剪贴板**：pyperclip / Qt 原生剪贴板

---

## 项目结构

```
emoji_workshop_final/
├── main.py                        # 程序入口 & 主窗口
├── requirements.txt               # 依赖清单
├── .gitignore
│
├── models/                        # 数据实体层
│   ├── __init__.py
│   ├── image_model.py             # ImageModel dataclass
│   └── tag_model.py               # TagModel dataclass
│
├── views/                         # UI 展示层
│   ├── __init__.py
│   ├── gallery_view.py            # 缩略图画廊
│   ├── tag_panel.py               # 标签管理面板
│   ├── stats_panel.py             # 数据统计面板
│   ├── recommend_panel.py         # 智能推荐侧边栏 ★
│   ├── report_view.py             # 性格画像报告对话框 ★
│   ├── settings_dialog.py         # 设置对话框
│   └── ai_generate_dialog.py      # AI 生成对话框
│
├── controllers/                   # 业务控制层
│   ├── __init__.py
│   ├── ai_controller.py           # AI 生成控制器
│   ├── recommend_controller.py    # 上下文推荐控制器 ★
│   └── report_controller.py       # 性格画像报告控制器 ★
│
├── services/                      # 服务层（外部依赖封装）
│   ├── __init__.py
│   ├── database_service.py        # SQLite 数据库服务（单例模式）
│   ├── thumbnail_service.py       # 缩略图生成与缓存
│   ├── api_service.py             # 网络下载服务
│   ├── ai_service.py              # AI 图片生成服务（基类/Worker）
│   ├── vision_service.py          # 简易图像视觉分析（亮度/饱和度）
│   ├── llm_service.py             # 可选：与大模型交互的封装
│   ├── personality_service.py     # 性格画像核心逻辑（摘要、雷达图、证据）
│   ├── clipboard_monitor.py       # 剪贴板监听与导入
│   └── gif_generator.py           # GIF / 动图合成工具
│
├── utils/                         # 工具层
│   ├── __init__.py
│   ├── config_manager.py          # JSON 配置持久化
│   └── file_scanner.py            # 本地文件扫描
│
├── resources/                     # 资源与样式
│   ├── style.qss                   # 应用统一 QSS 主题
│   └── UI_GUIDE.md                 # UI 设计指引
│
├── tests/                         # 单元/集成测试（若存在）
│   ├── test_vision_service_parse.py
│   ├── test_vision_multi_message.py
│   └── ...
│
└── docs/
    └── architecture.md            # 架构说明文档
```

> ★ 标注为本版本新增功能

---

## 安装与运行

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 步骤

```bash
# 1. 进入项目目录
cd emoji_workshop_final

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动程序
python main.py
```

---

## 快捷键

| 快捷键 | 功能 |
|:---|:---|
| `Ctrl+G` | 打开 AI 生成对话框 |
| `Ctrl+T` | 切换数据统计面板 |
| `Ctrl+R` | 打开性格画像报告 |
| `Ctrl+,` | 打开设置 |
| `Ctrl+Q` | 退出程序 |

---

## 使用截图

> 运行后请将截图替换到此处。

---

## OOP 架构说明

本项目采用 **MVC + Service 分层**架构：

- **Model 层**：纯数据实体（`ImageModel`、`TagModel`），无业务逻辑，用 `dataclass` 声明字段。
- **View 层**：所有 PyQt6 Widget，只负责界面渲染和用户交互，通过 **pyqtSignal** 向上层传递事件。
- **Controller 层**：协调 View 和 Service，包含核心业务逻辑（推荐算法、报告生成）。
- **Service 层**：封装外部依赖（SQLite、网络、AI API、文件系统），对上层提供稳定接口。
- **Utils 层**：无状态工具函数（配置读写、文件扫描）。

详见 [docs/architecture.md](docs/architecture.md)。

---

发布说明（最终版本）

- 已统一现代化界面：resources/style.qss 与 views/* 已统一样式。
- 性格画像增强：services/personality_service.py，生成简短可读摘要、雷达图（嵌入 HTML）、关键标签证据。
- 依赖更新：新增 numpy（matplotlib 依赖），请使用 pip install -r requirements.txt 安装依赖。
- 注意事项：AI 生成提供商位于 services/providers；AIService 基类仅作为接口（子类实现 generate）。

运行与验证

1. 创建并激活虚拟环境，运行：pip install -r requirements.txt
2. 启动应用：python main.py
3. 打开“📝 性格画像报告”（Ctrl+R），生成报告并检查雷达图及摘要；测试 AI 生成对话并确保已配置提供商。

建议在提交前手动启动并生成一份报告，检查无异常截图并添加到 README 的“使用截图”部分。

