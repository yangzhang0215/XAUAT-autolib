# 西建大图书馆预约工具

这个仓库是我自己一直在用、也一直在维护的图书馆预约工具。

如果你主要是想预约研讨室，我现在最推荐直接用独立 GUI，不用记命令，也更方便看当天空闲房间和日志。

图书馆系统地址：[https://libspace.xauat.edu.cn](https://libspace.xauat.edu.cn)

## 如果你只是想用 GUI

GitHub Release 里我建议优先下载这个：

- `xauat-seminar-gui-portable.zip`

解压以后直接运行：

- `xauat-seminar-gui.exe`

这份是免 Python 环境的，正常情况下解压就能用。

如果你拿到的是目录版，也是在目录里直接双击：

- `xauat-seminar-gui\xauat-seminar-gui.exe`

## 如果你在 Mac 上用 CLI

GitHub Release 里对应的是：
- `xauat-seminar-cli-mac.zip`

这个包是给 macOS 终端用的，不包含 GUI。
解压后进入目录，先执行：

```bash
bash run.sh install
cp python/seminar.config.example.json python/seminar.config.local.json
```

然后按需执行：

```bash
bash run.sh doctor
bash run.sh discover
bash run.sh reserve-now
bash run.sh reserve-wait
```

## 这个 GUI 能做什么

- 独立预约研讨室，不走统一 CLI
- 只用主账号登录，其他成员只填学号
- 获取当天可预约房间，并按楼层展示
- 支持按 `roomId` 优先顺序自动尝试
- 支持到点自动预约
- 支持超过 4 小时自动拆成两段预约
- 自动导出当天房间列表 TXT，方便快速查看

## 第一次使用

第一次打开后，先去“偏好设置”把下面这些内容填好：

- 统一身份认证账号
- 统一身份认证密码
- 手机号
- 触发时间
- 开始时间
- 结束时间
- 参与人学号
- `roomId` 优先顺序
- 主题
- 内容
- 是否公开

填完后点保存就行。

程序会把配置保存在 exe 同目录下：

- `seminar.config.local.json`

运行过程中的状态、日志和导出文件会放在：

- `runtime\`

## 我平时是怎么用的

### 1. 先看今天有哪些房间

在主界面点：

- `获取今日空闲`

它会做两件事：

- 主界面按楼层展示房间列表
- 同时导出一份 JSON 和一份 TXT

导出文件位置：

- `runtime\seminar-tool-discover-YYYYMMDD.json`
- `runtime\seminar-tool-discover-YYYYMMDD.txt`

如果你只是想快速扫一眼当天哪些房间还能约，直接看 TXT 就够了。

### 2. 配置房间优先顺序

`roomId` 那一栏是按优先顺序填的，一行一个就行。

例如：

```text
69
70
71
```

程序会按这个顺序一个个尝试，命中第一个可预约房间就提交。

如果你只想固定某一间房，就只填一个 `roomId`。

房间对照表在这里：

- [研讨室 roomId 对照表](docs/seminar-room-id-table.md)

### 3. 立即预约

如果已经到了可预约时间，直接点：

- `立即预约`

程序会立刻用当前配置发起预约。

### 4. 到点预约

如果还没到开放时间，点：

- `到点预约`

程序会一直等到你配置的触发时间，然后自动提交预约。

这里有两个很重要的点：

- 可以锁屏，可以关显示器
- 不能让电脑睡眠、休眠、关机，也不能把 GUI 关掉

说直白一点：

- 锁屏没问题
- 睡着了就不会自动约

如果你点击“到点预约”的时候，今天已经过了设定触发时间，程序会自动顺延到第二天同一时间执行。

## 预约规则

- 只支持预约当天
- 每天 `08:00:00` 开始预约
- 图书馆 `22:30` 关门，结束时间不能晚于 `22:30`
- 单次请求最长 4 小时
- 超过 4 小时会自动拆成两段
- 两段之间固定间隔 15 分钟
- 总跨度不能超过 8 小时 15 分钟
- 两段预约请求之间会真实等待 15 分钟后再发送

比如你填：

- `08:00` 到 `16:15`

程序会自动拆成：

- `08:00-12:00`
- `12:15-16:15`

## 房间列表里的状态怎么理解

- `可自动尝试`：这间房今天至少还有一段满足条件的可用时间
- `无法预约`：今天剩余空档已经不够用了，碎片时间不算
- `当天不可约`：这一天本来就不在它的可预约日期里
- `需上传材料`：这类房间不走自动预约

## 常见问题

### 1. 为什么只需要主账号

因为真正登录的只有主账号，其他成员只是在提交预约前通过学号去解析成员信息，不需要再登录其他账号。

### 2. 为什么同一个房间看起来像有两个 id

真正提交预约时要用的是房间自己的 `roomId`。有些接口里还会出现申请配置 id、分组 id、子项 id，那些不是你预约时该传的房间 id。

### 3. 想指定固定房间怎么办

把 `roomId` 列表里只留一个就行。

### 4. 到点预约时我能离开电脑吗

可以离开，但前提是：

- GUI 不能关
- 电脑不能睡眠
- 网络不能断

### 5. 没有账号信息能不能用

可以。第一次打开 GUI 后，直接在界面里填账号、密码和成员信息，再保存即可。

## 文档

- [GUI 使用说明](docs/seminar-gui.md)
- [独立研讨室工具说明](docs/seminar-standalone-tool.md)
- [研讨室 roomId 对照表](docs/seminar-room-id-table.md)
- [普通座位 seatId 对照表](docs/seat-id-table.md)

## 还想自己跑源码的话

项目里现在还有这些入口：

- `python/cli.py`：统一 CLI
- `python/seminar_cli.py`：独立研讨室 CLI
- `python/seminar_gui.py`：独立研讨室 GUI 启动器

依赖安装：

```powershell
py -3 -m pip install -r python\requirements.txt
```

源码方式启动 GUI：

```powershell
py -3 python\seminar_gui.py
```

## 测试

```powershell
py -3 -m unittest discover -s python\tests -v
```
