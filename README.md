# 西建大图书馆预约工具

这个仓库是我自己一直在用、也一直在改的图书馆预约工具。现在主要分成三块：

- 普通座位预约 CLI
- 独立研讨室预约 CLI
- 独立研讨室预约 GUI

如果你主要是想约研讨室，我建议直接用 GUI，省得记命令，也更方便看当天空闲情况。

站点地址：[https://libspace.xauat.edu.cn](https://libspace.xauat.edu.cn)

## 现在有哪些入口

- `python/cli.py`：统一 CLI，主要还是普通座位那套
- `python/seminar_cli.py`：独立研讨室 CLI
- `python/seminar_gui.py`：独立研讨室 GUI

## 我建议怎么用

### 只想用研讨室

先装依赖：

```powershell
py -3 -m pip install -r python\requirements.txt
```

然后直接启动 GUI：

```powershell
py -3 python\seminar_gui.py
```

第一次打开后，把这些内容填好就行：

- 主账号学号和统一身份认证密码
- 手机号
- 触发时间
- 开始时间和结束时间
- 参与人学号
- `roomId` 优先顺序
- 主题、内容、是否公开

填完保存后，平时基本就是这几个按钮：

- `获取今日空闲`：拉今天的房间列表，同时导出 JSON 和 TXT
- `立即预约`：现在立刻提
- `到点预约`：一直等到你配置的触发时间再提

### 想走命令行

先复制配置模板：

```powershell
Copy-Item python\seminar.config.example.json python\seminar.config.local.json
```

然后常用命令就两个：

```powershell
py -3 python\seminar_cli.py discover
py -3 python\seminar_cli.py reserve --wait
```

如果你没在配置文件里写 `priorityRoomIds`，也可以临时指定房间：

```powershell
py -3 python\seminar_cli.py reserve --room-id 69 --participant 2504000001 --participant 2504000002 --wait
```

### 还在用普通座位

```powershell
Copy-Item python\config.example.json python\config.local.json
py -3 python\cli.py login
py -3 python\cli.py discover
py -3 python\cli.py reserve-once --force
```

## 研讨室这套工具现在的规则

- 只用主账号登录，其他参与人只填学号，不需要副账号登录
- 只能预约当天，不再输入预约日期
- 每天 `08:00:00` 开始预约
- 图书馆每天 `22:30` 关门，结束时间不能晚于 `22:30`
- 单次请求最多 4 小时
- 超过 4 小时会自动拆成两次请求，中间固定隔 15 分钟
- 总预约时长上限 8 小时
- 如果配置里写了 `priorityRoomIds`，就按顺序自动优先尝试
- 如果配置里没写 `priorityRoomIds`，再通过命令行传 `--room-id`

## GUI 里房间列表怎么看

现在列表是按楼层展开的，默认更适合直接看当天可用情况。

状态列的意思比较直接：

- `可自动尝试`：这间房今天至少还有一段满足最小时长要求的空档
- `无法预约`：今天剩下的空档已经不够用了，哪怕有零碎空隙也不算
- `当天不可约`：这天本来就不在它的可预约日期里
- `需上传材料`：这类房间不走自动预约

`获取今日空闲` 之后，会同时生成：

- `python/runtime/seminar-tool-discover-YYYYMMDD.json`
- `python/runtime/seminar-tool-discover-YYYYMMDD.txt`

如果你只是想快速看一眼当天空闲房间，直接打开 TXT 就够了。

## 配置文件

研讨室配置文件是：

- `python/seminar.config.local.json`

可以直接从模板复制：

- `python/seminar.config.example.json`

默认示例里已经把几个核心字段放好了：

- `auth.username`
- `auth.password`
- `seminar.triggerTime`
- `seminar.startTime`
- `seminar.endTime`
- `seminar.participants`
- `seminar.defaults`
- `seminar.priorityRoomIds`

## 文档

- [独立研讨室 GUI 说明](docs/seminar-gui.md)
- [独立研讨室工具说明](docs/seminar-standalone-tool.md)
- [研讨室 roomId 对照表](docs/seminar-room-id-table.md)
- [普通座位 seatId 对照表](docs/seat-id-table.md)
- [Python 目录说明](python/README.md)

## 测试

```powershell
py -3 -m unittest discover -s python\tests -v
```

## 最后说一句

这个仓库我还会继续改，尤其是研讨室 GUI 这块。如果你只是想赶紧用起来，优先看上面的“我建议怎么用”就行，不用先把整个项目看完。
