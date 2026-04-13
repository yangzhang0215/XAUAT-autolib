# 研讨室预约 GUI 说明

这个 GUI 是独立入口，不走统一 CLI。

如果你只是想用研讨室预约，我建议直接用它。

## 启动方式

```powershell
py -3 python\seminar_gui.py
```

如果当前 `py -3` 指向的解释器没装好 GUI 依赖，启动器会自动尝试切到本机可用的 Python 解释器。

## 现在这版 GUI 的特点

- `PySide6 + qfluentwidgets`
- 独立研讨室入口
- 主界面按楼层展示今天的房间列表
- 右下角有日志控制台，点开后可以看实时日志
- 没有预约日期输入，只能预约当天

## 核心规则

- 只用主账号登录
- 其他参与人只填学号
- 每天 `08:00:00` 开始预约
- 图书馆 `22:30` 关门，结束时间不能晚于 `22:30`
- 超过 4 小时会自动拆成两次请求
- 第二次请求从第一次结束 15 分钟后开始
- 总时长上限 8 小时

## 设置页要填什么

- 账号
- 密码
- 手机号
- 触发时间
- 开始时间
- 结束时间
- `roomId` 优先顺序
- 参与人学号
- 主题
- 内容
- 是否公开

## 主界面几个按钮分别干什么

- `获取今日空闲`：拉今天的房间数据，并生成 JSON 和 TXT
- `立即预约`：现在马上提交
- `到点预约`：等到 `triggerTime` 再提交
- `打开 TXT 摘要`：直接看导出的文字版房间列表

## 房间列表里的状态说明

- `可自动尝试`：今天至少还有一段满足最小时长要求的空档
- `无法预约`：今天剩余空档已经不够，哪怕还有 15 分钟碎片也不会算可约
- `当天不可约`：今天不在它的可预约日期里
- `需上传材料`：这类房间不走自动预约

## 常见使用流程

### 第一次使用

1. 打开 GUI
2. 进“偏好设置”
3. 填账号、密码、手机号
4. 填开始时间、结束时间
5. 填 `roomId` 优先顺序
6. 填参与人、主题、内容
7. 保存配置

### 看今天空闲房间

1. 回到“仪表盘(预约)”
2. 点“获取今日空闲”
3. 在主界面直接看按楼层展开的列表
4. 需要留档的话，点“打开 TXT 摘要”

### 到点自动预约

1. 提前打开 GUI
2. 确认配置已经保存
3. 点“到点预约”
4. 保持 GUI 运行，程序会到点自动提交一次

## 输出文件

执行 `获取今日空闲` 后，会生成：

- `python/runtime/seminar-tool-discover-YYYYMMDD.json`
- `python/runtime/seminar-tool-discover-YYYYMMDD.txt`

## 注意事项

- 不支持提前挂着等第二天
- 如果已经错过触发窗口，会直接返回 `too_late`
- 参与人里不要再把主账号本人填进去
- 如果第一段成功、第二段失败，会记成 `partial_success`

## 相关文件

- [`../python/seminar_gui.py`](../python/seminar_gui.py)
- [`../python/seminar.config.example.json`](../python/seminar.config.example.json)
- [`seminar-room-id-table.md`](seminar-room-id-table.md)
- [`seminar-standalone-tool.md`](seminar-standalone-tool.md)
