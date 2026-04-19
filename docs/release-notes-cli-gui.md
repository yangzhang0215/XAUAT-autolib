# XAUAT-autolib Release 说明

本次 Release 同时提供：

- `xauat-seminar-gui-portable.zip`
- `xauat-seminar-cli-mac.zip`

如果你主要想直接预约研讨室，推荐优先使用 GUI 版本。  
如果你在 macOS 终端环境里使用，或者更习惯命令行方式，可以使用 CLI 版本。

## 发布内容

### GUI 版本

文件：

- `xauat-seminar-gui-portable.zip`

适用场景：

- Windows 用户
- 不想自己安装 Python 环境
- 希望直接使用图形界面配置账号、成员、房间优先级和触发时间

使用方式：

1. 下载 `xauat-seminar-gui-portable.zip`
2. 解压后运行 `xauat-seminar-gui.exe`
3. 首次打开后填写账号、密码、手机号、成员学号、`roomId` 优先顺序等配置

### CLI 版本

文件：

- `xauat-seminar-cli-mac.zip`

适用场景：

- macOS 用户
- 习惯终端命令
- 需要自己编排脚本、定时任务或手动执行命令

使用方式：

1. 下载 `xauat-seminar-cli-mac.zip`
2. 解压后进入目录
3. 执行：

```bash
bash run.sh install
cp python/seminar.config.example.json python/seminar.config.local.json
```

4. 按需使用：

```bash
bash run.sh doctor
bash run.sh discover
bash run.sh reserve-now
bash run.sh reserve-wait
```

## 这次更新

- 修复了双段研讨室预约的逻辑错误
- 当预约时长超过 4 小时时，会自动按规则拆分为多段预约
- 每段预约时长不超过 `4 小时`，段与段之间保持固定 `15 分钟` 空档，最后一段至少 `60 分钟`
- 后续分段提交不再错误地真实等待 `15 分钟` 后再发起，而是会直接连续提交；`15 分钟` 只体现在预约时间窗里
- 修复了 GUI 重新打包时旧产物可能混入新包的问题
- 新增了服务器时间检查脚本，方便排查本地时间和图书馆服务器时间偏差
- 新增了预约加密与完整流程说明文档，方便查看接口加密和提交逻辑

## 使用建议

- 日常直接使用：优先选 GUI
- macOS 终端、脚本化、定时任务：使用 CLI
- 到点抢预约时，建议先确认本地时间和图书馆服务器时间是否有偏差

## 相关文档

- [GUI 使用说明](./seminar-gui.md)
- [独立研讨室工具说明](./seminar-standalone-tool.md)
- [预约加密与完整流程](./reservation-encryption-and-flow.md)
- [研讨室 roomId 对照表](./seminar-room-id-table.md)

## 说明

- GUI 与 CLI 的核心预约逻辑来自同一套 Python 代码
- GUI 更适合直接使用
- CLI 更适合终端和自动化场景
