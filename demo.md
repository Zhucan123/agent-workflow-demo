# Demo script(40-50 秒沉默录屏)

> 无需语音,按镜头顺序操作,画面 → 动作。字体调大、深色主题。
> 主画面:**Agent Workbench 双栏产品壳**(左对话区 / 右业务面板)。
> 模型:真实 LLM(DeepSeek)。录前确认服务已以真实模式启动(MCP 已开启、notes.txt 已还原)。

## 推荐剧本:单任务点亮全部三个业务面板

任务一步三连:RAG 检索(点亮"Knowledge hits")→ MCP 读文件 → MCP 追加(进入"Approval queue"),轨迹栏全程滚动。

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

## 镜头 1(0-6s)打开产品壳
- 浏览器打开 `http://127.0.0.1:8000/playground`(Agent Workbench)
- 停顿 2 秒:观众看到左对话栏、右侧"Knowledge hits / Approval queue / Execution trail"三个空面板
- 标题栏显示 `llm: openai`

## 镜头 2(6-14s)输入任务
- 放慢粘贴:
  `Look up the refund window in the knowledge base, then read notes.txt from the MCP external workspace and append "refund window = 14 days" to it`
- 停顿 2 秒再点 **Run**

## 镜头 3(14-26s)左对话 + 右知识库,自动点亮
- 左侧:PLANNER 气泡(理由+步骤)、AI 气泡滚动
- 右侧:**Knowledge hits 卡片逐个弹出**(来源 refund-policy.md、命中百分比、片段预览)——画面最丰满的一段
- 轨迹栏同时滚动 tool.call/tool.result

## 镜头 4(26-34s)HITL 审批门(核心镜头)
- `mcp_workspace_append` 卡片出现在 **Approval queue**,状态 "awaiting approval"
- **故意等 3-5 秒**(让观众读懂"需要人决策")再点 **Approve**
- 卡片状态变绿 "approved",队列区换 "Action completed"

## 镜头 5(34-40s)结果落盘
- 切到终端,慢慢敲:
```bash
cat data/sandbox/notes.txt
```
- 展示追加成功,停 2 秒

## 镜头 6(40-48s)审计回放(收尾)
- 浏览器开 `http://127.0.0.1:8000/v1/agents/<session_id>/events`(session_id 在页面标题栏)
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
- 每个面板被点亮时留 1 秒静止,剪辑时才看得清
- 不配音,剪映加 3-4 行英文小字说明(planner / knowledge hits / approval / audit)
- 1080p MP4,YouTube unlisted → 链接挂 Upwork portfolio / README

## 录制前自查清单
- [ ] notes.txt 已还原(只含面板两行,无历史测试残留)
- [ ] 服务是真实 LLM 模式(`healthz` 显示 `llm_provider: openai`)且 `AGENT_MCP_MODE=demo`
- [ ] API key 不出现在任何画面(启动命令提前敲好)
- [ ] `/playground` 显示 Agent Workbench 双栏(不是旧单栏)
- [ ] 录完记得停服务/隧道,不留裸奔进程