# Proxy Troubleshooter

版本：0.1.0

Proxy Troubleshooter 是一个 Codex 插件，用来根据本机证据排查代理、Clash/Mihomo、路由规则、DNS、TUN、应用绕过代理、地区跳转等问题。

它面向不会用专业术语描述网络问题的用户。插件会指导 Codex 读取本机代理状态、判断可能原因，并在执行小范围可回滚修复前请求明确授权。

## 包含内容

- Codex 插件：`plugins/proxy-troubleshooter`
- 内置技能：`proxy-troubleshooter`
- 只读本机代理诊断脚本
- Clash/Mihomo 小范围规则修复脚本，写入前会备份配置
- 反馈记录脚本，用于记录修复是否有效，不会把本机案例上传到仓库
- 测试：`tests/`

## 从 GitHub marketplace 仓库安装

公开仓库发布后，把它添加为 Codex 插件 marketplace：

```powershell
codex plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
```

然后在 Codex 插件目录里安装并启用 **Proxy Troubleshooter**，再开启一个新线程使用。

## 从本地目录安装

在仓库根目录执行：

```powershell
codex plugin marketplace add .
```

如果当前 Codex 线程里看不到插件，开启新线程或重启 Codex App。

## 安全边界

这个插件把“诊断”和“改动”分开：

- 只读初始化可以查看代理端口、系统代理状态、DNS/TUN 线索、可能的代理客户端、非敏感配置结构。
- 低风险写操作也必须先获得小范围授权。
- 规则修复只做窄范围改动，并在写入前备份。
- 插件不得打印或保存订阅链接、节点凭据、控制器密钥、token、cookie、密码、完整账户标识或完整配置。
- DNS、TUN、系统代理、路由、证书、MITM、重启代理应用、订阅改动，都必须单独确认，并给出断联后的恢复方法。

本机 profile、运行记录、案例、备份都是运行时状态，已被 git 忽略。数据边界见 `PRIVACY.md`。

## 开发

运行测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

如果本机有 Codex 内置校验器，可以校验 skill 和 plugin：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\plugins\proxy-troubleshooter\skills\proxy-troubleshooter"
python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" ".\plugins\proxy-troubleshooter"
```

## 官方 Codex 插件目录

OpenAI 当前公开文档把 Codex App 的插件目录描述为：OpenAI curated 插件、工作区共享插件、用户创建或添加的插件；同时也说明 repo marketplace 可以用来分享插件。

文档目前没有说明第三方插件进入官方 curated 目录的自助提交流程。所以，在 OpenAI 发布正式提交入口前，这个 GitHub marketplace 仓库就是公开分发路径。
