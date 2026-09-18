# Demo script(30-40 秒沉默录屏)

> 无需语音。按镜头顺序录,每条给出"画面 → 终端命令"。字体调大、深色背景。
> 录前:`export OPENAI_BASE_URL=...; export OPENAI_API_KEY=...`(别录进画面)

## 镜头 1(5s)启动
```bash
cd server
uv run uvicorn app.main:app --port 8000
curl -s http://localhost:8000/healthz   # → {"status":"ok"}
```

## 镜头 2(5s)发任务
```bash
curl -N -X POST http://localhost:8000/v1/agents/workflow/run \
  -H 'Content-Type: application/json' \
  -d '{"task": "Calculate 3 items at 129.9 each plus 15% tax, then write a receipt file named receipt-2026.txt"}'
```

## 镜头 3(10s)事件流
让终端滚动展示:
```
event: agent.plan    steps=[calculator, file_store(write)]
event: tool.call     calculator args={"expression": "3*129.9*1.15"}
event: tool.result   ok=true output=448.255
event: approval.request  summary="Write receipt-2026.txt to sandbox"  ← 在这里停 2 秒
```

## 镜头 4(10s)HITL 审批 + 续跑
第二个终端:
```bash
curl -X POST http://localhost:8000/v1/agents/<session_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"action_id": "<上一条事件里的 action_id>", "decision": "allow"}'
```
回到第一个终端:继续滚动 tool.result / token.usage / agent.done,打开生成的
`server/data/sandbox/receipt-2026.txt` 展示内容。

## 镜头 5(5s)Java 集成(可选加分项)
```bash
cd integration/java-client
mvn -q spring-boot:run -Dspring-boot.run.arguments="Calculate 2 items at 59.9 each"
```
展示同样的事件流从 Java 客户端里打出来。

## 镜头 6(5s)RAG(可选)
```bash
uv run python ../scripts/seed.py
curl -s 'http://localhost:8000/v1/rag/search?q=refund+policy&k=3'
```

## 录制要点
- 终端背景深色,字号 16pt+,行高拉开
- 每个镜头之间留 0.5s 黑屏或静止,方便剪辑
- 不配音;剪映加 3-4 行英文字幕(可选)
- 输出 1080p MP4,上传 YouTube(unlisted)→ 链接挂 Upwork portfolio / README

## 录制前自查清单
- [ ] 服务在 stub 模式下也能跑(无 key 观众可复现)
- [ ] API key 不出现在画面
- [ ] 沙箱目录干净(删掉演示产物)
- [ ] /healthz 返回 200(镜头 1 有东西可拍)