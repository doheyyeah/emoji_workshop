# UI 改造指南（外包同学）

## 1) 文件说明
- 只改：`emoji_workshop_final/resources/style.qss`
- 不需要改 Python 文件即可调整大部分界面样式

## 2) 快速调色板（当前默认）
- 主色：`#4a9eff`
- 主色悬停：`#6ab3ff`
- 深色背景：`#1e1e1e`
- 深色面板：`#252526`
- 深色边框：`#3e3e42`
- 文字（dark 主题）：`#e0e0e0`

> **注意：本项目已固定为 dark 主题**，不再支持 light（亮色）主题切换。
> `style.qss` 中已移除所有 `#mainWindow[theme="light"]` 相关样式。

## 3) 关键控件（可精准定位）
| 控件 | objectName |
|---|---|
| 主窗口 | `mainWindow` |
| 左侧标签面板 | `tagPanel` |
| 中间画廊 | `galleryView` |
| 右侧推荐面板 | `recommendPanel` |
| 顶部 KPI 卡片 | `statsCard` |
| 主要按钮 | `primaryButton` |
| 次要按钮 | `secondaryButton` |
| 危险按钮 | `dangerButton` |
| 网络状态标签 | `networkStatusLabel` |

## 4) 如何测试改动
1. 修改 `resources/style.qss`
2. 重启程序：`python main.py`
3. 打开统计页、AI 生成页、设置页，检查样式是否一致

## 5) 常见任务示例
- 换主色调：统一替换主色 `#4a9eff`
- 调整圆角：修改 `border-radius`
- 加阴影：可在关键控件上增加边框层次（QSS 对阴影支持有限，建议温和处理）

## 6) 可参考主题
- PyDracula
- BreezeStyleSheets
- QSS Stock

## 7) 不要碰的内容
- 不要改 `.py` 业务代码
- 不要修改现有 objectName（避免样式失效）
- 打包发布不在本轮范围（PR #6 再做）
