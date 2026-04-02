# 西安建大图书馆预约 CLI

一个基于 Python 的西安建筑科技大学图书馆预约命令行工具，面向 `https://libspace.xauat.edu.cn` 当前线上系统，实现统一身份认证登录、座位发现、单次预约、取消预约和接口清单导出。

这个仓库现在只维护 Python 版本，旧的 Node 版本已经移除。

## 项目特性

- 统一身份认证直连登录，不依赖浏览器自动化
- `discover`、`reserve-once`、`cancel-seat` 自动检测并刷新失效 token
- 支持“指定房间 + 指定座位号顺序回退”
- 支持“按区域匹配 + 座位偏好”的自助选区
- 支持取消当前账号下的有效预约，并轮询确认取消结果
- 支持导出 124 个已整理接口的 Markdown/JSON 清单
- 附带座位号与 `seatId` 的 Markdown 对照表，方便直接抄配置

## 仓库结构

- [python/cli.py](python/cli.py)：CLI 入口
- [python/libspace_cli](python/libspace_cli)：核心实现
- [python/tests](python/tests)：单元测试
- [python/config.json](python/config.json)：安全模板配置
- [docs/seat-id-table.md](docs/seat-id-table.md)：座位号与 `seatId` 对照表
- [scripts/register-python-task.ps1](scripts/register-python-task.ps1)：Windows 计划任务注册脚本
- [scripts/python-run-reserve-once.cmd](scripts/python-run-reserve-once.cmd)：Windows 一键运行脚本

## 环境要求

- Windows
- Python 3.11 及以上
- 能访问学校统一身份认证和图书馆预约站点

安装依赖：

```powershell
py -3 -m pip install -r python\requirements.txt
```

## 快速开始

### 1. 配置账号密码

仓库里跟踪的是安全模板 [python/config.json](python/config.json)，建议你实际使用时新建 `python/config.local.json`，把真实账号密码写进去。

推荐做法：

1. 复制 `python/config.json` 为 `python/config.local.json`
2. 在 `python/config.local.json` 里填写自己的统一身份认证账号和密码
3. 不要把 `python/config.local.json` 提交到 GitHub

示例：

```json
{
  "baseUrl": "https://libspace.xauat.edu.cn",
  "triggerTime": "07:00:00",
  "lang": "zh",
  "auth": {
    "username": "你的学号",
    "password": "你的统一身份认证密码"
  },
  "selectionMode": "candidate_seats",
  "candidateSeats": [],
  "areaPreferences": []
}
```

如果 `python/config.local.json` 存在，程序会优先读取它；否则才回退到 `python/config.json`。

### 2. 登录并缓存 token

```powershell
py -3 python\cli.py login
```

如果你只是临时想覆盖配置文件里的账号密码，也可以直接传参数：

```powershell
py -3 python\cli.py login --username 你的学号 --password 你的密码
```

### 3. 拉取当天可预约房间和座位

```powershell
py -3 python\cli.py discover
```

指定日期：

```powershell
py -3 python\cli.py discover --date 2026-04-01
```

输出文件会写到：

- `python/runtime/discover-YYYYMMDD.json`

里面包含：

- `candidateTemplate`
- `areaPreferenceTemplate`
- `rooms`

你可以先跑一次 `discover`，再从输出里挑自己想要的 `roomId` 和 `seatId`。

### 4. 配置选座策略

#### 方案 A：`candidate_seats`

适合你已经明确知道要抢哪个房间、哪些座位号。

```json
{
  "selectionMode": "candidate_seats",
  "candidateSeats": [
    {
      "roomId": 3,
      "seatIds": [3064, 3065, 3066]
    }
  ],
  "areaPreferences": []
}
```

含义是：

- 先尝试 `roomId=3`
- 在这个房间里按 `3064 -> 3065 -> 3066` 的顺序找空位
- 找到第一个可用座位就只发一次确认请求

#### 方案 B：`area_preferences`

适合你想优先某个区域，但不想手工维护大量 `roomId`。

```json
{
  "selectionMode": "area_preferences",
  "candidateSeats": [],
  "areaPreferences": [
    {
      "label": "南自修区优先",
      "roomId": 3,
      "seatIds": [3064, 3065]
    },
    {
      "label": "北自修区兜底",
      "match": {
        "areaName": "雁塔图书馆",
        "floorName": "二楼",
        "roomName": "北自修区"
      },
      "seatIds": []
    }
  ]
}
```

规则说明：

- `roomId` 和 `match` 二选一，若同时写了以 `roomId` 为准
- `match.areaName`、`match.floorName`、`match.roomName` 都是去掉首尾空格后的精确匹配
- `seatIds` 为空时，表示该区域内任意空位都可以
- `seatIds` 非空时，按顺序挑选

### 5. 单次预约

正常运行：

```powershell
py -3 python\cli.py reserve-once
```

手动测试时跳过时间窗口检查：

```powershell
py -3 python\cli.py reserve-once --force
```

当前策略保持“单次确认，不做重试风暴”：

- 会先检查缓存 token
- token 缺失或过期时自动重新登录
- 找到目标座位后只发送一次 `/api/Seat/confirm`

### 6. 取消当前账号的预约

```powershell
py -3 python\cli.py cancel-seat
```

如果当前账号有多条有效预约，必须显式指定要取消的预约 ID：

```powershell
py -3 python\cli.py cancel-seat --id 5962079
```

取消逻辑：

- 先查 `/api/Member/seat`
- 自动识别状态为 `1 / 2 / 9` 的有效预约
- 若只有一条，直接取消
- 若有多条，要求传 `--id`
- 调用 `/api/Space/cancel` 成功后，短轮询列表验证状态是否已刷新

### 7. 导出接口清单

终端查看：

```powershell
py -3 python\cli.py interfaces
```

导出 Markdown：

```powershell
py -3 python\cli.py interfaces --output python\runtime\interfaces.md
```

导出 JSON：

```powershell
py -3 python\cli.py interfaces --format json --output python\runtime\interfaces.json
```

## 配置说明

### 凭据优先级

程序按下面的顺序选择登录凭据：

1. CLI 参数 `--username` 和 `--password`
2. 环境变量 `LIBSPACE_USERNAME` 和 `LIBSPACE_PASSWORD`
3. `python/config.local.json`
4. `python/config.json`

### 关键配置项

- `baseUrl`：图书馆预约系统地址
- `triggerTime`：预约触发时间，格式固定 `HH:MM:SS`
- `lang`：请求头语言，通常为 `zh`
- `auth.username`：统一身份认证账号
- `auth.password`：统一身份认证密码
- `selectionMode`：`candidate_seats` 或 `area_preferences`
- `candidateSeats`：精确选座模式的候选列表
- `areaPreferences`：自助选区模式的候选列表

## 座位号与 seatId 对照表

已经拆成 Markdown 文档，见 [docs/seat-id-table.md](docs/seat-id-table.md)。

这个表按房间分节，适合直接复制到自己的配置过程里。  
如果你要填 `area_preferences.match`，建议先看 `discover-YYYYMMDD.json` 里的房间名称，再把对应标签原样写进去。

## 自动登录机制

以下命令会在 token 缺失或失效时自动重新登录：

- `discover`
- `reserve-once`
- `cancel-seat`

所以实际使用时，很多场景并不需要先手工执行 `login`。

例如：

```powershell
py -3 python\cli.py discover
py -3 python\cli.py reserve-once --force
```

## Windows 计划任务

注册每天定时执行的任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-python-task.ps1
```

自定义任务名和触发时间：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-python-task.ps1 -TaskName "XAUAT-Libspace" -TriggerTime "07:00"
```

这个计划任务最终执行的是：

```powershell
scripts\python-run-reserve-once.cmd
```

它内部会调用：

```powershell
py -3 python\cli.py reserve-once
```

## 运行时文件

运行过程中会在 `python/runtime/` 下生成：

- `state.json`
- `discover-*.json`
- `logs/*.jsonl`
- 你手工导出的接口清单

`state.json` 里最重要的字段有：

- `token`
- `userInfo`
- `tokenSavedAt`
- `lastLogin`
- `lastReserve`
- `lastCancel`

## 2026-04-01 实测结论

- 统一身份认证直连登录可用
- 全局 `/api/Seat/date` 当前返回 `500`，所以主流程已经不再依赖它
- 房间级 `/api/Seat/date` 正常
- `/api/Seat/tree` 对未来某些日期可能返回空数组
- `/api/Space/cancel` 正常
- 取消预约后，列表状态可能延迟几秒刷新

## 已知限制

- 当前只覆盖正常的账号密码登录
- 如果统一身份认证要求验证码或滑块，本次命令会返回 `captcha_required`
- 不做验证码识别或绕过
- 不支持多账号轮换、代占等场景

## 测试

运行全部单元测试：

```powershell
py -3 -m unittest discover -s python\tests -v
```

## 开源发布前建议

- 真实账号密码只放在 `python/config.local.json`
- 不要把 `python/runtime/` 下的状态文件和日志公开出去
- 若你准备正式开源，建议补一个明确的 `LICENSE`
