# 西安建大图书馆预约 CLI

一个基于 Python 的西安建筑科技大学图书馆预约命令行工具，面向 `https://libspace.xauat.edu.cn` 当前线上系统，覆盖统一身份认证登录、座位发现、单次预约、取消预约和接口清单导出。

当前仓库只维护 Python 实现，旧的 Node 版本已经移除。

## 项目概览

- 统一身份认证直连登录，不依赖浏览器自动化
- `discover`、`reserve-once`、`cancel-seat` 会自动检查并刷新失效 token
- 支持“指定房间 + 指定座位号顺序回退”的精确抢座
- 支持“按区域匹配 + 座位偏好”的自助选区
- 支持取消当前账号下的有效预约，并轮询确认取消结果
- 支持导出已整理的接口清单，便于二次分析
- 提供 [docs/seat-id-table.md](docs/seat-id-table.md) 作为 `seatId` 对照表，方便整理自己的配置

## 仓库结构

- [python/cli.py](python/cli.py)：CLI 入口
- [python/libspace_cli](python/libspace_cli)：核心实现
- [python/tests](python/tests)：单元测试
- [python/config.example.json](python/config.example.json)：示例配置模板
- [docs/seat-id-table.md](docs/seat-id-table.md)：座位号与 `seatId` 对照表
- [scripts/register-python-task.ps1](scripts/register-python-task.ps1)：Windows 计划任务注册脚本
- [scripts/python-run-reserve-once.cmd](scripts/python-run-reserve-once.cmd)：Windows 一键执行脚本

## 环境要求

- Windows
- Python 3.11 及以上
- 能正常访问学校统一身份认证站点和图书馆预约站点

安装依赖：

```powershell
py -3 -m pip install -r python\requirements.txt
```

查看命令帮助：

```powershell
py -3 python\cli.py --help
py -3 python\cli.py login --help
```

## 快速开始

### 1. 准备本地配置文件

程序默认读取 `python/config.local.json`。仓库中保留的 [python/config.example.json](python/config.example.json) 只是模板，不会被自动加载。

推荐先复制模板：

```powershell
Copy-Item python\config.example.json python\config.local.json
```

然后编辑 `python/config.local.json`。当前这个文件仍然是运行入口配置，即使你打算用命令行参数或环境变量覆盖账号密码，也建议保留它，因为里面还包含：

- `baseUrl`
- `triggerTime`
- `lang`
- 选座策略配置

一个常见的配置示例如下：

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
  "candidateSeats": [
    {
      "roomId": 3,
      "seatIds": [3064, 3065, 3066]
    }
  ],
  "areaPreferences": []
}
```

注意事项：

- `python/config.local.json` 不要提交到 GitHub
- 如果你不想把账号密码放进文件，可以省略 `auth`，改用环境变量或 CLI 参数传入
- `selectionMode` 为 `candidate_seats` 时，`candidateSeats[*].seatIds` 必须是非空数组

### 2. 登录并缓存 token

默认登录：

```powershell
py -3 python\cli.py login
```

临时覆盖账号密码：

```powershell
py -3 python\cli.py login --username 你的学号 --password 你的密码
```

用环境变量覆盖：

```powershell
$env:LIBSPACE_USERNAME = "你的学号"
$env:LIBSPACE_PASSWORD = "你的密码"
py -3 python\cli.py login
```

如果你已经从浏览器或别的流程拿到了回调参数，也可以手动传入：

```powershell
py -3 python\cli.py login --cas "回调里的 cas 值"
py -3 python\cli.py login --url "包含 cas 参数的完整回调 URL"
```

凭据优先级如下：

1. CLI 参数 `--username` 和 `--password`
2. 环境变量 `LIBSPACE_USERNAME` 和 `LIBSPACE_PASSWORD`
3. `python/config.local.json` 里的 `auth`

这里的“优先级”只针对登录凭据，不会替代整个配置文件。

### 3. 发现当天可预约的房间和座位

拉取当天数据：

```powershell
py -3 python\cli.py discover
```

指定日期：

```powershell
py -3 python\cli.py discover --date 2026-04-01
```

运行后会生成：

- `python/runtime/discover-YYYYMMDD.json`

输出里主要包含三部分：

- `candidateTemplate`：适合直接粘进 `candidate_seats`
- `areaPreferenceTemplate`：适合直接粘进 `area_preferences`
- `rooms`：当天可预约房间、时段和可用座位明细

推荐流程是先跑一次 `discover`，再根据输出结果填写自己的目标 `roomId` 和 `seatId`。

### 4. 配置选座策略

当前支持两种模式。

#### 方案 A：`candidate_seats`

适合已经明确知道目标房间和目标座位号的情况。

```json
{
  "selectionMode": "candidate_seats",
  "candidateSeats": [
    {
      "roomId": 3,
      "seatIds": [3064, 3065, 3066]
    },
    {
      "roomId": 8,
      "seatIds": [8121, 8122]
    }
  ],
  "areaPreferences": []
}
```

执行语义：

- 先按 `candidateSeats` 的顺序遍历房间
- 进入某个房间后，按 `seatIds` 的顺序查找可用座位
- 找到第一个可用目标座位后立即发起确认

#### 方案 B：`area_preferences`

适合你更关心区域，而不是维护一长串固定 `roomId` 的情况。

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

- `roomId` 和 `match` 二选一，如果同时填写则以 `roomId` 为准
- `match.areaName`、`match.floorName`、`match.roomName` 都是去掉首尾空格后的精确匹配
- `seatIds` 为空时，表示该区域里任意空位都可以
- `seatIds` 非空时，程序会按顺序优先挑选

### 5. 执行单次预约

正常运行：

```powershell
py -3 python\cli.py reserve-once
```

调试时跳过时间窗口检查：

```powershell
py -3 python\cli.py reserve-once --force
```

当前实现的预约行为：

- 会先校验缓存 token 是否仍可用
- token 缺失或过期时会自动重新登录
- 默认要求在 `triggerTime` 前后 60 秒窗口内执行
- 如果当前时间早于触发时间但仍在窗口内，程序会等待到目标秒点
- 找到目标座位后只发送一次确认请求，不做“重试风暴”

### 6. 取消当前账号预约

取消当前账号下唯一的一条有效预约：

```powershell
py -3 python\cli.py cancel-seat
```

如果当前账号存在多条有效预约，需要显式指定预约 ID：

```powershell
py -3 python\cli.py cancel-seat --id 5962079
```

取消逻辑：

- 先调用 `/api/Member/seat`
- 自动筛出状态为 `1 / 2 / 9` 的有效预约
- 若只有一条有效预约则直接取消
- 若有多条有效预约则要求传 `--id`
- 调用 `/api/Space/cancel` 后，会短轮询列表确认状态是否已刷新

### 7. 导出接口清单

终端查看摘要：

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

## 命令参考

- `login`：执行登录并缓存 token，支持 `--username`、`--password`、`--url`、`--cas`
- `discover`：拉取当天或指定日期可预约的房间与座位，支持 `--date YYYY-MM-DD`
- `reserve-once`：按配置执行一次预约，支持 `--force`
- `cancel-seat`：取消当前账号的一条有效预约，支持 `--id`
- `interfaces`：查看或导出接口清单，支持 `--format` 和 `--output`

## 配置字段说明

- `baseUrl`：图书馆预约系统地址，当前一般为 `https://libspace.xauat.edu.cn`
- `triggerTime`：预约触发时间，格式固定为 `HH:MM:SS`
- `lang`：请求语言，通常填 `zh`
- `auth.username`：统一身份认证账号
- `auth.password`：统一身份认证密码
- `selectionMode`：选座模式，可选 `candidate_seats` 或 `area_preferences`
- `candidateSeats`：精确选座模式使用的候选房间列表
- `areaPreferences`：区域偏好模式使用的候选规则列表

补充说明：

- `auth` 可以省略，但如果保留该字段，`username` 和 `password` 都必须填写
- `candidateSeats[*].roomId` 为必填
- `candidateSeats[*].seatIds` 必须是非空数组
- `areaPreferences[*].label` 为必填
- `areaPreferences[*]` 必须至少提供 `roomId` 或 `match`

## 运行机制

### 登录流程

默认登录路径如下：

1. 从 CLI 参数、环境变量或配置文件中解析凭据
2. 请求 `/api/index/config`
3. 确认当前站点使用统一身份认证登录
4. 进入统一认证页，解析 `execution` 和 `pwdEncryptSalt`
5. 按前端规则加密密码并提交认证表单
6. 提取最终 `cas`
7. 调用 `/api/cas/user` 换取 libspace token
8. 将 token 与登录结果写入 `python/runtime/state.json`

如果认证端要求验证码或滑块，当前命令会直接返回 `captcha_required`，不会尝试识别或绕过。

### 自动登录兜底

以下命令会在发现 token 缺失或失效时自动重新登录：

- `discover`
- `reserve-once`
- `cancel-seat`

所以很多场景下不必先手动执行一次 `login`。

### 预约主流程

当前预约实现不依赖全局 `/api/Seat/date`。主流程是：

1. 请求 `POST /api/Seat/tree`
2. 展平可用房间
3. 逐房间请求 `POST /api/Seat/date`
4. 选出第一个可预约时段
5. 请求 `POST /api/Seat/seat`
6. 找到符合策略的空位后调用 `POST /api/Seat/confirm`

## 运行时文件

运行过程中会在 `python/runtime/` 下生成：

- `state.json`
- `discover-*.json`
- `logs/*.jsonl`
- 手动导出的接口清单

`state.json` 里常见的关键字段包括：

- `token`
- `userInfo`
- `tokenSavedAt`
- `lastLogin`
- `lastReserve`
- `lastCancel`

## 座位号与 `seatId` 对照表

项目已经把整理后的座位数据拆到 [docs/seat-id-table.md](docs/seat-id-table.md)。

使用建议：

- 想配 `candidate_seats` 时，可以直接从表里抄 `seatId`
- 想配 `area_preferences.match` 时，建议先看 `discover-YYYYMMDD.json` 里的实际房间标签，再把名称原样写进配置

## Windows 计划任务

注册一个每天执行的计划任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-python-task.ps1
```

自定义任务名和触发时间：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-python-task.ps1 -TaskName "XAUAT-Libspace" -TriggerTime "07:00"
```

默认脚本内部最终执行的是：

```powershell
py -3 python\cli.py reserve-once
```

如果你只是想在当前终端快速跑一次，也可以直接执行：

```powershell
scripts\python-run-reserve-once.cmd
```

## 当前站点适配情况

截至 2026-04-01 的实测结果：

- 统一身份认证直连登录可用
- 全局 `/api/Seat/date` 返回 `500`，所以当前主流程已不依赖它
- 房间级 `/api/Seat/date` 正常
- `/api/Seat/tree` 对未来某些日期可能返回空数组
- `/api/Space/cancel` 可正常工作
- 取消预约后，列表状态可能延迟几秒刷新

## 已知限制

- 当前只覆盖常规账号密码登录流程
- 如果统一身份认证要求验证码或滑块，命令会返回 `captcha_required`
- 当前没有实现多账号轮换
- 当前策略是单次确认，不做高频重试

## TODO

- [ ] 支持储存不同账号配置，并为每个账号隔离 token 和运行状态
- [ ] 实现多账号自动切换，在主账号登录失败、token 失效或预约失败时按优先级兜底

## 测试

运行全部单元测试：

```powershell
py -3 -m unittest discover -s python\tests -v
```

当前测试覆盖的主要内容：

- 配置解析与 `config.local.json` 加载逻辑
- 统一身份认证密码加密
- `cas` 提取逻辑
- 自动登录兜底
- 取消预约后的验证逻辑
- 接口清单导出
- 候选座位与区域偏好解析
