# Python 目录说明

这个目录是当前仓库的主要实现。

## 入口

- [`cli.py`](cli.py)：统一 CLI
- [`seminar_cli.py`](seminar_cli.py)：独立研讨室 CLI
- [`seminar_gui.py`](seminar_gui.py)：独立研讨室 GUI 启动器

## 主要模块

- [`libspace_cli/authserver.py`](libspace_cli/authserver.py)：统一身份认证登录
- [`libspace_cli/api.py`](libspace_cli/api.py)：接口封装
- [`libspace_cli/commands.py`](libspace_cli/commands.py)：统一 CLI 命令逻辑
- [`libspace_cli/seminar_service.py`](libspace_cli/seminar_service.py)：研讨室校验与成员解析
- [`libspace_cli/seminar_standalone.py`](libspace_cli/seminar_standalone.py)：独立研讨室发现与预约
- [`libspace_cli/seminar_gui.py`](libspace_cli/seminar_gui.py)：GUI 主入口
- [`libspace_cli/seminar_desktop/models.py`](libspace_cli/seminar_desktop/models.py)：GUI 数据模型
- [`libspace_cli/seminar_desktop/service.py`](libspace_cli/seminar_desktop/service.py)：GUI 服务层
- [`libspace_cli/seminar_desktop/controller.py`](libspace_cli/seminar_desktop/controller.py)：MVC 控制器
- [`libspace_cli/seminar_desktop/views.py`](libspace_cli/seminar_desktop/views.py)：Fluent 视图组件
- [`libspace_cli/seminar_desktop/app.py`](libspace_cli/seminar_desktop/app.py)：桌面应用装配
- [`tests`](tests)：测试

## 配置和运行目录

- `config.local.json`：普通座位配置
- `seminar.config.local.json`：独立研讨室配置
- `runtime`：运行期状态、日志和 discover 导出结果

## GUI 这块补充一下

- 使用 `PySide6 + qfluentwidgets`
- 固定只支持预约当天
- 不再提供预约日期输入
- 获取今日空闲时会同时生成 `.json` 和 `.txt` 两份结果

## 测试

```powershell
py -3 -m unittest discover -s python\tests -v
```
