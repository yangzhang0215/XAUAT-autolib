# Python 实现说明

这个目录是当前仓库唯一维护的实现版本。

如果你是第一次使用这个项目，先看仓库根文档：

- [../README.md](../README.md)

## 目录结构

- [cli.py](cli.py)：根入口，负责调用包内 CLI
- [libspace_cli/cli.py](libspace_cli/cli.py)：参数解析
- [libspace_cli/commands.py](libspace_cli/commands.py)：命令编排
- [libspace_cli/authserver.py](libspace_cli/authserver.py)：统一身份认证登录链路
- [libspace_cli/api.py](libspace_cli/api.py)：图书馆接口封装
- [libspace_cli/http.py](libspace_cli/http.py)：请求会话与公共请求头
- [libspace_cli/crypto.py](libspace_cli/crypto.py)：AES-CBC 加解密
- [libspace_cli/interfaces_catalog.py](libspace_cli/interfaces_catalog.py)：接口清单
- [tests](tests)：单元测试

## 登录流程

默认登录路径：

1. 从 CLI 参数、环境变量或配置文件读取账号密码
2. 请求 `/api/index/config`
3. 确认当前站点处于统一身份认证模式
4. 打开统一认证登录页
5. 解析 `execution` 和 `pwdEncryptSalt`
6. 调用 `checkNeedCaptcha.htl`
7. 按前端规则加密 `randomString(64) + password`
8. 提交认证表单并提取最终 `cas`
9. 调用 `/api/cas/user` 换取图书馆 token
10. 把 token 写入 `python/runtime/state.json`

如果统一认证返回 `isNeed=true`，命令会直接记录 `captcha_required`。

## 配置加载规则

当前仓库提供示例模板，实际运行使用本地配置：

- 跟踪到仓库的模板文件：[config.example.json](config.example.json)
- 本地覆盖文件：`config.local.json`

程序默认读取 `config.local.json`；`config.example.json` 仅作为示例模板，不会被自动加载。

命令运行时的凭据优先级：

1. CLI 参数
2. `LIBSPACE_USERNAME` / `LIBSPACE_PASSWORD`
3. `config.local.json`

## 自动登录兜底

`discover`、`reserve-once` 和 `cancel-seat` 都会先检查当前缓存 token：

- token 可用：直接继续
- token 缺失：自动登录
- token 过期：清理旧 token 后自动登录一次
- 自动登录失败：当前命令直接停止，并把结果写入状态文件

## 预约主流程

当前预约实现不依赖全局 `/api/Seat/date`，因为实测该接口会返回 `500`。

实际流程是：

1. `POST /api/Seat/tree`
2. 展平有效房间
3. 对每个房间调用 `POST /api/Seat/date {build_id}`
4. 选中第一个可用时间段
5. `POST /api/Seat/seat`
6. `POST /api/Seat/confirm`

## 命令列表

- `login`
- `discover`
- `reserve-once`
- `cancel-seat`
- `interfaces`

查看帮助：

```powershell
py -3 python\cli.py --help
py -3 python\cli.py login --help
```

## 测试

运行全部单元测试：

```powershell
py -3 -m unittest discover -s python\tests -v
```

当前测试覆盖：

- 配置解析和 `config.local.json` 覆盖逻辑
- 统一身份认证密码加密
- `cas` 提取逻辑
- 自动登录兜底
- 取消预约后的状态验证
- 接口清单导出
- 候选座位和自助选区解析

## 开发注意事项

- 真实凭据只放本地 `config.local.json`
- `python/runtime/` 是运行期目录，不要提交状态和日志
- 当前环境下包入口会自动补齐真实 `site-packages` 路径，避免依赖仓库根目录的 `Lib/`
