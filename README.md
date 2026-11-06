# Glados自动签到

## 食用方式：

### 注册一个GLaDOS的账号([注册地址](https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG))

#### 我的邀请码：([0A58E-NV28S-6U3QV-33VMG](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

#### 我的优惠码（9折）：([DEVILSTORE](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

### **Fork**本仓库

![图片加载失败](imgs/1.png)

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Action`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值对应GLaDOS账号的cookie值中的有效部分（获取方式如下）

- 在GLaDOS的签到页面按`F12`

- 切换到`Network`页面下，刷新

![图片加载失败](imgs/2.png)

- 点击第一个选项卡后在`Request Headers`下找到`Cookie`，右键复制cookie的值即可

  > 参考格式：koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;

![图片加载失败](imgs/3.png)

- 多账号请在 `COOKIES` 中 添加多个 `cookies` 中间使用 `&`连接即可。（例如： `c1&c3&c3...`）

3. 配置积分兑换策略（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_PLAN`，配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 |

> 不配置时默认不进行自动兑换；如需兑换，设置 `GLADOS_EXCHANGE_PLAN` 为 `plan100` / `plan200` / `plan500`。

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key: ([获取地址](https://www.pushdeer.com/product.html))。

### **star**自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py	# 签到脚本
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
```

## 更新日志

- **2026-01**: 重构代码，添加log输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑，优化日志输出，支持[新版域名](https://railgun.info) ，在 GLADOS_COOKIES 中添加新版域名下的 cookies 即可使用。
- **2026-09**: 新增设备平台自适应重试（code 4 无需手动配置 UA 即可自动恢复）；默认关闭自动兑换，需显式配置 `GLADOS_EXCHANGE_PLAN` 才启用。
- **2026-09**: 新增网络层重试/退避：`requests.Session` 挂载 `HTTPAdapter` + `urllib3.Retry`（total=3、指数退避 1/2/4s、对 429/5xx 自动重试），降低 CI 网络抖动导致的误报失败；业务 200 响应不受影响。


## 2026-11 签到修复与配置

- 默认使用 Linux User-Agent；状态、积分、签到及兑换请求保持一致。设备不匹配时停止，不再切换平台重试。上述 2026-09 自适应重试说明已被本次修复替代。
- 默认只访问 `glados.cloud`，不再把同一个 Cookie 发往两个域名。
- 签到前后查询积分，使用十进制精度记录余额变化；接口返回成功但无法确认积分增长时，标记为未确认并让 Actions 失败，不自动重试。余额变化是核对依据，其他同时发生的积分操作可能影响它；应在网页复核异常。
- 修复汇总丢失签到返回积分的问题；缺少积分字段显示“未知”，不伪报为 0。日志区分接口积分与余额变化。
- 无效会话停止后续操作；签到失败或到账未确认时跳过兑换，余额不足也不调用兑换。
- 每天北京时间 09:18 触发一次定时任务，默认随机等待 0～1800 秒再签到。GitHub 排队可能使实际执行更晚；随机延迟不保证签到被接受。手动运行和 push 触发不等待。

在仓库 `Settings → Secrets and variables → Actions → Variables` 中可配置以下 **Repository variables**。已有 Cookie 和推送密钥仍保留在 Secrets，绝不要放进 Variables。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GLADOS_USER_AGENT` | Linux 浏览器 UA | 可填入你登录时浏览器请求的完整 `User-Agent`，不要填 Cookie；未配置即可按 Linux 使用 |
| `GLADOS_DOMAIN` | `glados.cloud` | 仅支持 `glados.cloud` 或 `railgun.info`；Cookie 必须属于所选站点 |
| `GLADOS_MAX_DELAY_SECONDS` | `1800` | 定时任务最大随机延迟秒数，允许 `0`～`1800`；设为 `0` 关闭随机延迟 |

同一次运行的多个 Cookie 必须属于所选域名并使用同一 UA 配置；不同域名或不同登录客户端应分别配置运行环境，不要混用凭据。以上默认值按 Linux 登录会话配置，并不保证平台允许自动签到。

离线回归测试（不会读取真实凭据或访问签到接口）：

```sh
python -m pip install requests pypushdeer
python -m unittest discover -s tests -v
```

## 问题排查与定位
- 大家可以通过查询 actions 中的 running checkin 日志快速定位问题，有其他问题提交issue。
- 若出现 `Automated check-in detected` 且 `reason=device-mismatch`：核对 Cookie 所属站点和登录浏览器的 User-Agent。脚本会停止，不切换平台重试。UA 一致也不能保证通过其他服务端检查；持续拒绝时先核实平台允许的签到方式。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份








