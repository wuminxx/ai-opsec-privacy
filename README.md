# AI OPSEC & Privacy

**用 AI 时零身份暴露、零隐私泄漏的操作规程 + 可执行工具。**

覆盖三层：AI 客户端落盘取证面、提示词身份字段清洗、网络与提供商留存。
每一层都给**可直接跑的命令**，不是原则清单。

```
L1 会话层   AI 客户端在你机器上写什么、怎么清
L2 提示词层 你送进去的文本会留下什么
L3 网络层   出网时谁看得见、留存多久
```

任一层单独用都不够，三层叠加才是「任一场景都不被发现」。

---

## 为什么需要这个

AI 客户端把**完整对话明文写到磁盘**。这不是猜测，是默认行为。

典型落盘面（Claude Code 为例）：

```
~/.claude/projects/<cwd-slug>/    每次会话完整 transcript（明文 JSONL）
~/.claude/history.jsonl           你输入过的每一条 prompt
~/.claude/memory/                 memory 文件（跨会话持久）
~/.claude/shell-snapshots/        shell 环境快照 —— 含 env 变量、API key！
~/.claude/todos/                  任务清单
<project>/.claude/settings.json   项目级配置 —— 会被 git 提交
```

而送进 LLM 的文本，按**永久留存 + 可能被调取 + 可能进入训练**对待。

真实案例（2026-10 韩国银行 AI 攻击案）中，攻击方的破点正是这一层：

- 把工作目录开成**公网可读**（`http://38.244.50.120:18899/.claude/CLAUDE.md`）
- 在 Claude Code 会话里让 AI 写「安全研究员简历」，**顺手写进真实姓名、手机、Telegram、年龄、学校、居住地**

技术层伪装做得很好（12 国 IP、9 个代理、多模型栈），死在最基础的 OPSEC。

---

## 快速开始

```bash
git clone https://github.com/wuminxx/ai-opsec-privacy.git
cd ai-opsec-privacy

# 1. 先测绘：知道你的机器上 AI 痕迹在哪
./scripts/scan.sh          # Linux/macOS
.\scripts\scan.ps1         # Windows

# 2. 检查一份即将发给 AI 的文本
cat app.log | ./scripts/redact.sh          # 脱敏
./scripts/check-prompt.sh --file app.log   # 只检查不修改

# 3. 装 hook，自动拦截含身份字段的输入（Claude Code）
./scripts/install-hooks.sh

# 4. 用完清理
./scripts/shred.sh
```

---

## 目录

```
ai-opsec-privacy/
├── README.md
├── SKILL.md                      AI skill 版（给 Claude Code 用）
├── LICENSE                       MIT
├── scripts/
│   ├── scan.sh / scan.ps1        测绘：找出所有 AI 客户端落盘面
│   ├── redact.sh / redact.ps1    脱敏：剥离身份字段
│   ├── check-prompt.sh           检查：发送前扫描身份泄漏（不修改）
│   ├── shred.sh / shred.ps1      擦除：清 AI 会话痕迹
│   ├── local-model.sh            本地模型：三步起一个不出网的实例
│   └── install-hooks.sh          装 Claude Code PreToolUse hook
├── hooks/
│   ├── prompt-guard.py           PreToolUse hook：拦截含身份字段的输入
│   └── settings.snippet.json     要合并进 settings.json 的片段
├── docs/
│   ├── threat-model.md           威胁模型：先定清楚防谁
│   ├── forensics-surface.md      落盘取证面完整测绘
│   ├── prompt-hygiene.md         提示词卫生
│   ├── providers.md              各 AI 厂商留存政策对照
│   ├── local-models.md           Ollama / llama.cpp / vLLM 部署
│   ├── network.md                网络与元数据泄漏
│   └── checklist.md              上线前自查清单
└── examples/
    ├── pseudo-identity.txt       假身份模板
    └── gitignore.txt             AI 配置的 .gitignore 片段
```

---

## 三层速览

### L1 会话层

```bash
# 测绘
./scripts/scan.sh

# 关遥测（~/.claude/settings.json）
{ "env": { "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1" } }

# 会话目录挂 tmpfs（Linux）—— 重启即失
sudo mount -t tmpfs -o size=512m,mode=0700,uid=$(id -u) tmpfs ~/.claude/projects

# 擦除
./scripts/shred.sh
```

> **警告**：SSD + TRIM + 写时复制文件系统（btrfs/ZFS/APFS）下，原地覆写**不保证**擦除旧块。
> 真正需要时上全盘加密 + 一次性 VM。

### L2 提示词层

```bash
# 脱敏流水线：路径用户名 / 内网 IP / 邮箱 / 手机 / token / 内部主机名
cat app.log | ./scripts/redact.sh

# 只检查，不改（退出码非零 = 发现泄漏）
./scripts/check-prompt.sh --file app.log
```

### L3 网络层

```bash
# 本地模型，只绑 127.0.0.1，不出网
./scripts/local-model.sh ollama qwen2.5:14b

# 验证不泄漏真实 IP
curl -s https://api.ipify.org; echo
```

---

## 三个敏感度档位

| 档位 | 目标 | 做什么 | 成本 |
|---|---|---|---|
| **A 日常** | 防本地取证 | 测绘 + 关遥测 + 脱敏 + 清理脚本 | 低 |
| **B 敏感** | 防提供商 + 防关联 | A + 零留存渠道 + 假身份 + tmpfs + 无日志代理 | 中 |
| **C 高敏** | 防国家级 + 断网 | B + 本地模型 + 断网 + 一次性 VM + 全盘加密 | 高 |

决策树：

```
要处理敏感数据？
├─ 否 → A：测绘 + 关遥测 + 脱敏 + 清理脚本
└─ 是 → 数据必须离开本机？
        ├─ 否 → C：本地模型 + 断网
        └─ 是 → 必须给第三方？
                ├─ 否 → C（自托管在你的云）
                └─ 是 → B：零留存 + 假身份 + 脱敏 + 无日志代理
```

---

## 八个常见误区

| 你以为 | 实际 |
|---|---|
| 我删了会话记录 | SSD/CoW 下覆写不保证擦除旧块 → 真需要时上全盘加密 |
| 我用无痕模式 | 无痕只防本地历史，不防网络观测和服务端留存 |
| 我关了 memory | 服务端仍可能按账号聚合 → 高敏换账号或自托管 |
| 我用了代理 | 免费代理本身就是采集点 → 自建无日志 |
| 我脱敏了姓名 | 措辞习惯/时区/语言组合仍可指纹 → 全维度对齐 locale |
| 小模型本地跑就安全 | 模型文件、日志、缓存仍在磁盘 → 配全盘加密 + 关请求日志 |
| API key 存 env 就行 | env 会进 shell snapshot 和进程列表 → 用密钥库 / tmpfs |
| 换个说法问同样的事就没事 | 语义等价会被聚类 → 事本身不能问时，换说法也不能问 |

---

## 作为 Claude Code Skill 使用

```bash
cp -r . ~/.claude/skills/ai-opsec-privacy/
```

然后 `/ai-opsec-privacy`，或提到 AI 隐私 / OPSEC / 本地模型 / 会话清理 / prompt 脱敏时自动触发。

---

## 边界

- 本规程只处理**你自己**的隐私与你**有权处置**的数据。
- 涉及**第三方个人信息**时，向境外模型转发在《个人信息保护法》下属对外提供 + 出境行为，
  需单独同意 + 安全评估/认证/标准合同之一 + 事前影响评估。**技术脱敏不免除法律义务。**
- 本仓库不含任何绕过他人授权、伪造他人身份的内容 —— 目标是保护使用者自己。

---

## License

MIT
