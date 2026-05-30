# 架构说明

## 为什么采用 MVC + Service 分层

传统 MVC 将代码分为 Model / View / Controller 三层，能有效降低耦合。但桌面应用还需要大量外部依赖（数据库、网络、文件系统），因此在 Controller 和 Model 之间额外引入 **Service 层**，专门封装这些依赖，让 Controller 只调用稳定接口，不直接操作 SQLite 或 requests。

这样带来的好处：
- View 只管渲染，不含 SQL；
- Controller 只含业务逻辑，不含 UI 代码；
- Service 可以单独测试，甚至替换底层实现（例如把 SQLite 换成 PostgreSQL）而不影响上层。

---

## 各层职责

| 层 | 目录 | 职责 |
|:---|:---|:---|
| Model | `models/` | 纯数据实体（`dataclass`），无副作用 |
| View | `views/` | PyQt6 Widget，发射信号，不含业务逻辑 |
| Controller | `controllers/` | 接收信号、调用 Service、处理业务规则 |
| Service | `services/` | 封装 SQLite / 网络 / AI API / 文件 IO |
| Utils | `utils/` | 无状态工具：配置读写、文件扫描 |

---

## 关键设计模式

### 单例 DatabaseService

`DatabaseService` 在 `MainWindow.__init__` 中创建唯一实例，并通过构造函数注入到所有需要数据库访问的组件。这避免了多处创建连接、事务冲突等问题。

### 信号槽通信

PyQt6 的 `pyqtSignal` 是观察者模式的语言级实现。View 层通过信号向外广播事件（如 `image_selected`、`tag_selected`），主窗口作为调度中心连接信号与对应槽函数，实现解耦。

### QThread 异步

缩略图生成、AI 图片下载、网络图片下载均在 `QThread` 子线程中执行，通过信号将进度回传到主线程更新 UI，避免界面卡顿。

---

## 上下文推荐算法说明（LLM）

```
用户输入聊天上下文
       ↓
LLMService（OpenAI 兼容接口）从已有标签中选择 Top-K 标签
       ↓
数据库按标签并集查询图片
       ↓
返回 Top-K 推荐结果
```

核心 SQL（并集）：

```sql
SELECT DISTINCT i.id, i.name, ...
FROM images i
JOIN image_tags it ON i.id = it.image_id
JOIN tags t       ON it.tag_id = t.id
WHERE t.name IN ('开心', '哈哈', ...)
ORDER BY i.created_at DESC
LIMIT top_k
```

当 LLM 未启用或调用失败时，会返回中文错误提示，不再回退 jieba。

---

## 性格画像算法说明

基于 `usage_history` 表中的使用时间和图片-标签关联，采用**简单规则引擎**推断特征：

1. 统计所有使用过的图片的标签，按频次累加；
2. 若"开心/快乐/笑"类标签占比 > 15% → **阳光开朗**；
3. 若"难过/哭/沮丧"类标签占比 > 15% → **感性细腻**；
4. 若"搞笑/沙雕/无语"类标签占比 > 15% → **幽默风趣**；
5. 若"猫/狗/可爱"类标签占比 > 15% → **温柔治愈**；
6. 若使用高峰在 22:00–5:00 → **夜猫子型**；
7. 若使用高峰在 5:00–9:00 → **早起鸟型**。

规则可在 `controllers/report_controller.py` 的 `_PERSONALITY_RULES` 中扩展，无需修改其他代码。
