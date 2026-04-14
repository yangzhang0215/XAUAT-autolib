# 独立研讨室预约工具说明

仓库里现在有两套独立入口：

- `python/seminar_cli.py`
- `python/seminar_gui.py`

它们复用的是同一套主账号登录、房间发现、成员解析和预约提交逻辑。

## 配置文件

先复制模板：

```powershell
Copy-Item python\seminar.config.example.json python\seminar.config.local.json
```

主要字段：

- `auth.username`
- `auth.password`
- `seminar.triggerTime`
- `seminar.startTime`
- `seminar.endTime`
- `seminar.participants`
- `seminar.defaults`
- `seminar.priorityRoomIds`

## 规则总览

- 只需要主账号登录
- 其他参与人只填学号，不需要副账号登录
- 预约日期固定为当天
- 不再交互询问 `Reservation date (YYYY-MM-DD)`
- 图书馆每天 `22:30` 关门，结束时间不能晚于 `22:30`
- `priorityRoomIds` 有值时，按顺序自动选房
- 只有 `priorityRoomIds` 为空时，`--room-id` 才作为主要选房方式

## 长时预约规则

- 单次请求最多 4 小时
- 超过 4 小时时自动拆成两段
- 第二段从第一段结束 15 分钟后开始
- 第二段预约请求会在第一段提交成功后真实等待 15 分钟再发送
- 例如 `08:00 -> 16:15` 会拆成：
  - `08:00-12:00`
  - `12:15-16:15`
- 总预约时长最多 8 小时

## discover 用法

```powershell
py -3 python\seminar_cli.py discover
```

会同时生成：

- `python/runtime/seminar-tool-discover-YYYYMMDD.json`
- `python/runtime/seminar-tool-discover-YYYYMMDD.txt`

TXT 会把今天空闲研讨室、人数范围、禁用时段和 `roomId` 摘要出来。

## reserve 用法

### 按配置自动选房

```powershell
py -3 python\seminar_cli.py reserve --wait
```

### 配置为空时显式指定房间

```powershell
py -3 python\seminar_cli.py reserve --room-id 69 --participant 2504000001 --participant 2504000002 --wait
```

### 立即执行

```powershell
py -3 python\seminar_cli.py reserve --force
```

## GUI 建议

如果你主要是想直接用，不想记命令，优先走 GUI：

```powershell
py -3 python\seminar_gui.py
```

GUI 会自动读写 `python/seminar.config.local.json`，也更适合直接看按楼层整理后的今日房间列表。
