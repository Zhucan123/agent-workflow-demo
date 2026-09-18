# Demo script(40-50 秒沉默录屏)

> 无需语音,按镜头顺序操作,画面 → 动作。字体调大、深色主题。
> 推荐走 **playground 页面**操作(视觉效果好);需要终端流时看文末备选方案。
> 模型:真实 LLM(DeepSeek)。录前确认服务已以真实模式启动(MCP 已开启、notes.txt 已还原)。

## 准备(录前一次,别录进画面)

```bash
cd /home/ubuntu/freelancer/agent-workflow-demo/server
# 还原 MCP 演示文件(保证 read 输出干净)
printf 'meeting notes:\n- refund window is 14 days\n' > data/sandbox/notes.txt
# 服务启动参数(真实 LLM + MCP demo 模式):
#   env AGENT_LLM_MODE=openai OPENAI_BASE_URL=... OPENAI_API_KEY=... \
#       AGENT_MODEL=deepseek-flash AGENT_MCP_MODE=demo \
#       .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 确认 http://127.0.0.1:8000/healthz 返回 {"status":"ok","llm_provider":"openai"}
```

## 镜头 1(0-6s)打开页面
- 浏览器打开 `http://127.0.0.1:8000/playground`,两次"Run"字样隐约可见
- 停顿 2 秒,让观众看清页面标题栏("LLM: openai")

## 镜头 2(6-14s)输入任务
- 粘贴任务文本到输入框,放慢、不要瞬间粘贴完成:
  `Use the MCP external workspace to read notes.txt, then append the line "computed total = 448.155" to it`
- 光标停在按钮上,停 2 秒,再点 **Run**

## 镜头 3(14-26s)事件流滚动
- `agent.start` / `agent.plan`(LLM 的理由文本逐行出现,画面最丰满的一段)
- `tool.call` → `mcp_workspace_read` → `tool.result`(能看到 notes.txt 内容)
- 不要移动鼠标,让画面自然滚动

## 镜头 4(26-34s)HITL 审批门(核心镜头)
- `approval.request` 出现,**Approve 按钮亮起后故意等 3-5 秒再点**
- 点击 Approve → `tool.result ok=true`

## 镜头 5(34-40s)结果落盘
- 切到终端,慢慢敲:
```bash
cat data/sandbox/notes.txt
```
- 展示追加成功的两行内容,停 2 秒

## 镜头 6(40-48s)审计回放(收尾)
- 从 playground 事件里找到 session_id(agent.start 里),敲:
```bash
curl -s http://127.0.0.1:8000/v1/agents/<session_id>/events | python3 -m json.tool
```
- 画面定格在完整时间线,淡出

## 备选:纯终端流(不拍页面)
用 `curl -N` 跑同一任务,事件在终端滚动;审批改第二个终端发 approve 请求:
```bash
curl -X POST http://localhost:8000/v1/agents/<session_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"action_id": "<approval.request 里的 action_id>", "decision": "allow"}'
```

## 录制要点
- 关键节奏:**审批门等待 3-5 秒**是本片叙事点,别剪掉
- 每段之间留 0.5s 静止,方便剪辑
- 不配音,剪映加 3-4 行英文小字说明(plan/approval/audit)
- 1080p MP4,YouTube unlisted → 链接挂 Upwork portfolio / README

## 录制前自查清单
- [ ] notes.txt 已还原(只含面板两行,无历史测试残留)
- [ ] 服务是真实 LLM 模式(`healthz` 显示 `llm_provider: openai`)且 `AGENT_MCP_MODE=demo`
- [ ] API key 不出现在任何画面(启动命令提前敲好)
- [ ] playground 能打开(`/playground` 200)
- [ ] 录完记得停服务/隧道,不留裸奔进程