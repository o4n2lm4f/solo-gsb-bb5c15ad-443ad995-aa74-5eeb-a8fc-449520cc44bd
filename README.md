# Archive Path Precheck API

跨平台压缩包路径预检服务。接收待解包条目的原始路径与类型（file/directory），
按 **Windows 目标规则**在内存中完成规范化与安全检查，返回规范路径、同名碰撞组
和层级冲突。全程**不访问文件系统**，结果与宿主平台无关。

## 快速开始

单条启动命令（自动完成依赖安装、镜像构建并启动服务）：

```bash
docker compose up --build
```

服务监听 **8000** 端口：

- 交互式文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

不使用 Docker 时也可本地运行（Python 3.11+）：

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API

### `GET /health`

健康检查，返回 `{"status": "ok"}`。

### `POST /precheck`

请求体：

```json
{
  "entries": [
    {"path": "docs/README.md", "type": "file"},
    {"path": "DOCS\\readme.md", "type": "file"},
    {"path": "C:\\evil\\abs.txt", "type": "file"},
    {"path": "../escape.txt", "type": "file"},
    {"path": "dir", "type": "file"},
    {"path": "dir/child.txt", "type": "file"},
    {"path": "CON.txt", "type": "file"}
  ]
}
```

`type` 仅接受 `file` 或 `directory`。

响应示例：

```json
{
  "results": [
    {"index": 0, "path": "docs/README.md", "type": "file",
     "canonical_path": "docs\\readme.md", "safe": true, "issues": []},
    {"index": 1, "path": "DOCS\\readme.md", "type": "file",
     "canonical_path": "docs\\readme.md", "safe": true, "issues": []},
    {"index": 2, "path": "C:\\evil\\abs.txt", "type": "file",
     "canonical_path": "evil\\abs.txt", "safe": false,
     "issues": ["drive_letter_path"]},
    {"index": 3, "path": "../escape.txt", "type": "file",
     "canonical_path": null, "safe": false, "issues": ["parent_escape"]},
    {"index": 4, "path": "dir", "type": "file",
     "canonical_path": "dir", "safe": true, "issues": []},
    {"index": 5, "path": "dir/child.txt", "type": "file",
     "canonical_path": "dir\\child.txt", "safe": true, "issues": []},
    {"index": 6, "path": "CON.txt", "type": "file",
     "canonical_path": "con.txt", "safe": true,
     "issues": ["reserved_device_name"]}
  ],
  "collisions": [
    {"canonical_path": "docs\\readme.md", "indices": [0, 1]}
  ],
  "hierarchy_conflicts": [
    {"file_index": 4, "canonical_path": "dir", "blocked_indices": [5]}
  ]
}
```

- **`results`**：逐条结果，严格保持输入顺序，含原始路径回显。
- **`collisions`**：规范路径相同的条目组（按 Windows 大小写不敏感语义），
  组内与组间均按输入顺序。
- **`hierarchy_conflicts`**：`file` 类型条目占据其他条目的祖先路径
  （如文件 `dir` 挡住了 `dir/child.txt`）。

## 规范化规则（Windows 目标）

1. **Unicode NFC**：先行归一，使等价字符序列可比较。
2. **分隔符统一**：`/` 与 `\` 都视为分隔符，规范路径以 `\` 连接。
3. **大小写统一**：规范路径做大小写折叠（casefold），碰撞判定不区分大小写。
4. **段尾空格/句点**：每段末尾的空格与句点被剥离（`"dir ."` → `dir`）。
5. **点段解析**：`.` 丢弃；`..` 弹出上一段；越界（超出压缩包根）的 `..`
   标记 `parent_escape`，该条目 `canonical_path` 为 `null`。
6. **保留设备名**：任意路径段的基名（首个句点之前、忽略尾随空格）命中
   `CON`、`PRN`、`AUX`、`NUL`、`COM1`–`COM9`、`LPT1`–`LPT9`（不区分大小写，
   含 `con.txt`、`nul .dat` 等形式）时，在 `issues` 中标记
   `reserved_device_name`。

## 安全判定

出现以下任一情况时 `safe = false`：

| issue 代码 | 含义 |
| --- | --- |
| `absolute_path` | 绝对路径（`/...`、`\\...`、UNC `\\server\share`） |
| `drive_letter_path` | 盘符路径（`C:\...`、`C:...`） |
| `parent_escape` | `..` 越出压缩包根目录 |

其余 issue 代码（`reserved_device_name`、`empty_segment`）仅作提示，不影响
`safe`。绝对路径与盘符路径仍会给出剥离根前缀后的规范路径；越界 `..`
的路径规范结果为 `null`，且不参与碰撞与层级冲突计算。

## 项目结构

```
app/
  main.py        # FastAPI 路由（/health、/precheck）
  models.py      # Pydantic 请求/响应模型
  normalizer.py  # 单路径规范化（纯内存、零依赖）
  analysis.py    # 碰撞分组与层级冲突（纯内存、零依赖）
tests/           # unittest/pytest 兼容测试
Dockerfile       # 构建时安装依赖
docker-compose.yml
requirements.txt
requirements-dev.txt
```

## 测试

```bash
pip install -r requirements-dev.txt
python -m pytest tests/          # 或 python -m unittest discover -s tests
```

核心逻辑（`normalizer`、`analysis`）不依赖第三方库，仅用标准库即可运行
对应测试；API 测试需要 fastapi/httpx，缺失时自动跳过。
