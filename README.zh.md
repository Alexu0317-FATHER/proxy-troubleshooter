# Proxy Troubleshooter

版本：0.2.0

简体中文 | [English](README.md)

如果你明明能打开 YouTube，Gmail 却死活加载不出来；如果 Google 都能打开，LinkedIn 却莫名其妙打不开；甚至 Claude Code 可以正常使用，但 Codex 却一直重连……

如果这些疑似和网络代理有关的问题，你跟我一样都得反复问 AI，AI 又一次次把用量花在收集系统代理、Clash/Mihomo 配置、DNS、TUN、路由规则这些本机信息上……

试试 Proxy Troubleshooter。它会根据你的本机证据排查各种和代理/梯子相关的问题，并把已排查的问题记录成本地脱敏案例。下次类似问题复现时，不需要再浪费用量从零排查；如果需要改动配置，它也会从安全角度给出备份和回滚操作指导。

## 包含内容

- 共享插件：`plugins/proxy-troubleshooter`
- Codex manifest：`plugins/proxy-troubleshooter/.codex-plugin/plugin.json`
- Claude Code manifest：`plugins/proxy-troubleshooter/.claude-plugin/plugin.json`
- Codex marketplace catalog：`.agents/plugins/marketplace.json`
- Claude Code marketplace catalog：`.claude-plugin/marketplace.json`
- 内置技能：`proxy-troubleshooter`
- 只读本机代理诊断脚本
- Clash/Mihomo 小范围规则修复脚本，写入前会备份配置
- 反馈记录脚本，用于记录修复是否有效，不会把本机案例上传到仓库
- 测试：`tests/`

## 在 Codex 中安装

把这个仓库添加为 Codex 插件 marketplace：

```powershell
codex plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
```

然后在 Codex 插件目录里安装并启用 **Proxy Troubleshooter**，再开启一个新线程使用。

本地开发时，在仓库根目录执行：

```powershell
codex plugin marketplace add .
```

如果当前 Codex 线程里看不到插件，开启新线程或重启 Codex App。

## 在 Claude Code 或 Claude Code Desktop 中安装

这是 Claude Code 插件。Claude Code 官方文档覆盖 terminal、IDE、desktop app 和 browser，所以同一个插件也适用于 Claude Code Desktop。

在 Claude Code 或 Claude Code Desktop 里执行：

```text
/plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
/plugin install proxy-troubleshooter@proxy-troubleshooter
/reload-plugins
```

之后可以直接调用技能：

```text
/proxy-troubleshooter:proxy-troubleshooter
```

如果要用命令行非交互安装：

```powershell
claude plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
claude plugin install proxy-troubleshooter@proxy-troubleshooter
```

本地开发时，在仓库根目录执行：

```powershell
claude plugin validate .
claude plugin marketplace add .
claude plugin install proxy-troubleshooter@proxy-troubleshooter
```

如果只想在一次 Claude Code 会话里直接加载本地插件：

```powershell
claude --plugin-dir .\plugins\proxy-troubleshooter
```

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

如果本机有 Codex 内置校验器，可以校验 Codex skill 和 plugin：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\plugins\proxy-troubleshooter\skills\proxy-troubleshooter"
python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" ".\plugins\proxy-troubleshooter"
```

如果本机装了 Claude Code，可以校验 Claude marketplace 和 plugin：

```powershell
claude plugin validate .
claude plugin validate .\plugins\proxy-troubleshooter
```

## 官方 Codex 插件目录

OpenAI 当前公开文档把 Codex App 的插件目录描述为：OpenAI curated 插件、工作区共享插件、用户创建或添加的插件；同时也说明 repo marketplace 可以用来分享插件。

文档目前没有说明第三方插件进入官方 curated 目录的自助提交流程。所以，在 OpenAI 发布正式提交入口前，这个 GitHub marketplace 仓库就是公开分发路径。

## 官方 Claude 插件市场

Anthropic 的 Claude Code 文档说明了两个公开 marketplace：

- `claude-plugins-official`：Anthropic 自己维护的 curated marketplace，没有申请流程。
- `claude-community`：第三方插件通过审核后进入的社区 marketplace。提交前需要先运行 `claude plugin validate`。

在这个插件被 `claude-community` 接收之前，直接从这个 GitHub marketplace 仓库安装。
