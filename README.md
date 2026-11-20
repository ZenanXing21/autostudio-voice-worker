# AutoStudio Voice Worker

RunPod Serverless 固定音色配音 Worker。默认加载**你本人训练的 GPT-SoVITS v2Pro GPT + SoVITS 权重**。首次在私有卷注册一段 3–10 秒参考录音与逐字稿，之后 Agent 07 每次只提交文本：

```json
{"input":{"text":"你好，今天我们开始工作。"}}
```

这是“固定参考条件”的服务：请求中不需要参考音频，但上游模型启动时仍需要私有参考录音。它**没有改造 Decoder，也没有声称两份权重本身能够无条件合成**。只使用本人或明确授权的声音。

## 架构与模型

```text
RunPod job(text) -> normalize/chunk -> 固定 tech_narrator 档案
                                -> GPT-SoVITS v2Pro GPT 预测语义 token
                                -> 原版 SoVITS + 参考频谱/说话人嵌入
                                -> FFmpeg 拼接/调速/响度 -> WAV/MP3 + SRT/JSON
                                -> 私有卷路径或 S3/R2 预签名 URL
```

镜像包含 [GPT-SoVITS 官方源码](https://github.com/RVC-Boss/GPT-SoVITS)的固定提交 `6d51ffceafbf240145619af4c92408a6e54b7924`，原版 `TTS.run` 和 Decoder 均未修改。你的 `.ckpt` 是 GPT Text2Semantic 权重；`.pth` 的 `05` 文件头是[上游规定的 v2Pro 标记](https://github.com/RVC-Boss/GPT-SoVITS/blob/6d51ffceafbf240145619af4c92408a6e54b7924/GPT_SoVITS/process_ckpt.py)，**不是损坏**。v2Pro SoVITS 配置为 32 kHz。上游 `set_ref_audio` 在加载后缓存参考语义和频谱；推理时由说话人验证网络从缓存的参考音频求嵌入。新代码只负责固定私有路径和传入文本，不改动模型参数或结构。详见[设计说明](docs/gpt-sovits-v2pro-design.md)。上游代码为 [MIT 许可](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/LICENSE)。

模型除你训练的两份权重外，还需要公共的 Chinese RoBERTa、CNHuBERT、ERes2NetV2 和 G2PW。它们以及私人文件都放在持久化卷，**不进入 Git 或公开 Docker 镜像**。镜像使用 [PyTorch 官方 CUDA 12.6 wheel](https://pytorch.org/get-started/previous-versions/) 安装 `torch/torchaudio 2.7.1+cu126`，构建时验证版本。Worker 启动时打印 PyTorch/CUDA/GPU 信息并执行 CUDA kernel 自检，失败直接退出。建议先用 24 GB GPU、`min_workers=0`、`max_workers=1`；16 GB 与截图中其他 GPU 的真实 v2Pro 显存需求仍需实测。CUDA 自检通过仅证明基本运算可用，不证明整套模型能装入显存。

## 声音录制与一次性注册

选择自己清晰的 **3–10 秒**录音，单人、无音乐，提供与片段逐字一致的文本。支持 WAV/MP3/M4A，注册时转为单声道 WAV 并做质量筛查。`10min.m4a` 可作为训练素材，**不能整段直接作 v2Pro 推理参考**；应从中或从已提供的录音中挑 3–10 秒。已有本地 `tech_narrator` 候选片段约 8.8 秒，其逐字稿是根据原稿与停顿推断，尚未经 ASR/人工逐字核对。部署前应试听核对。

在挂载同一 RunPod Network Volume 的 GPU Pod 中，先将自己的 `.ckpt`、`.pth` 和短参考音频**私下传入 Pod**，再执行：

```bash
python -m scripts.download_gpt_sovits_models --model-dir /runpod-volume/gpt-sovits
python -m scripts.setup_fixed_voice \
  --gpt /private/zenan_voice_v1-e15.ckpt \
  --sovits /private/zenan_voice_v1_e8_s160.pth \
  --reference /private/reference_8s.wav \
  --reference-text '这段八秒录音实际说出的逐字文本' \
  --model-dir /runpod-volume/gpt-sovits \
  --data-dir /runpod-volume/autostudio
```

`download_gpt_sovits_models` 只下载公共辅助模型到卷；`setup_fixed_voice` 校验 v2Pro 文件头、参考时长，并将权重和参考录音存入私有卷。已有同名档案会拒绝覆盖。`register_voice` API 也能注册参考录音，但不会上传权重；权重必须先位于 `GPT_SOVITS_MODEL_DIR`。不要把私人文件复制进本仓库或镜像构建目录。卷目录约定：

```text
/runpod-volume/gpt-sovits/zenan_voice_v1-e15.ckpt
/runpod-volume/gpt-sovits/zenan_voice_v1_e8_s160.pth
/runpod-volume/gpt-sovits/pretrained_models/{chinese-roberta-wwm-ext-large,chinese-hubert-base,sv/...}
/runpod-volume/gpt-sovits/G2PWModel/
/runpod-volume/autostudio/voices/tech_narrator/documentary/{profile.json,reference.wav}
```

如已在别处注册声音档案，可把 `voices/tech_narrator/documentary/` 整个目录私下复制到卷上的 `DATA_DIR`；仅复制本机的 `profile.json` 而没有 `reference.wav` 不够。

## RunPod Serverless 部署

1. 建立 [Network Volume](https://docs.runpod.io/storage/network-volumes)，在相同数据中心创建 Custom Worker Endpoint，挂载到 `/runpod-volume`。先在卷上准备上述全部文件。
2. GitHub Actions 的 `publish-image.yml` 在 `main` 更新后构建并推送 `ghcr.io/zenanxing21/autostudio-voice-worker:latest` 和 `sha-<提交前12位>`。在 [Actions](https://github.com/ZenanXing21/autostudio-voice-worker/actions) 确认成功，再将固定 `sha-...` 标签填入 Endpoint。该 GHCR 包公开可匿名拉取，录音/权重不在镜像内。
3. Endpoint 环境变量参考 `.env.example`：`TTS_BACKEND=gpt_sovits`、`GPT_SOVITS_MODEL_DIR=/runpod-volume/gpt-sovits`、`DATA_DIR=/runpod-volume/autostudio`、`OUTPUT_DIR=/runpod-volume/autostudio/outputs`。无需设置 `API_TOKEN` 或暴露 `8000/http`；主进程是 `python -u /app/handler.py`。
4. `S3_BUCKET` 留空时输出只给持久化卷上的 `*_path`；Agent 07 在另一服务时，设置私有 R2/S3 桶及 `S3_ENDPOINT_URL`、`S3_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`，才能得到可下载的预签名 `*_url`。密钥放 RunPod Secret/环境变量，不提交到 Git。

模型在首个有效 TTS 作业时加载并复用，避免无效输入和注册请求触发昂贵的模型冷启动。HF 公开辅助权重预先下载到卷，避免每次新 Worker 下载。

## API 与 Agent 07

RunPod Requests 直接提交上面的 JSON。`task_type` 省略时默认 `tts_generate`；`text` 可用 `prompt` 代替，`voice_id` 省略时默认 `tech_narrator`，风格默认 `documentary`，语言默认 `Auto`。`{"input":"你好。"}` 也可用。不能提交空的 `input`：RunPod SDK 会在进入 handler 前拒绝它，日志为 `Job has missing field(s): id or input`，见 [RunPod 官方案例](https://github.com/runpod/runpod-plugins-official/blob/main/plugins/runpod/skills/runpod/golden-paths/07-network-volume-handoff.md)。

```bash
curl -X POST "https://api.runpod.ai/v2/$ENDPOINT_ID/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d '{"input":{"text":"人工智能正在改变世界。今天介绍 GitHub 上的 ComfyUI。","language":"Chinese","speed":1.0,"format":"mp3"}}'
```

首次加载可能较久；`/run` 返回作业 ID 后，用 `GET https://api.runpod.ai/v2/$ENDPOINT_ID/status/$JOB_ID` 查询结果。暖机且确定在同步时限内时才使用 `/runsync`。

中文 `language: "Chinese"`，英文 `"English"`，中英混合 `"Auto"`；它们映射至上游 `zh`、`en`、`auto`。语速 0.75–1.5 由 FFmpeg 调整。`style` 可选 `documentary`、`energetic`、`calm`、`conversational`，但必须为该风格另外注册本人参考录音；上游 v2Pro 没有本服务可验证的通用情绪参数。输出始终保留原始 WAV、处理后 WAV，按请求另产 MP3，并提供 `captions.srt`、`segments.json`。字幕时间从实际生成的音频片段长度计算，是**片段级**，未做词级/字级强制对齐。成功的 `output.status` 为 `completed`；失败为 `error` 与明确 `message`。Agent 07 必须检查内部 `output.status`，不能只看 RunPod 外层的 `COMPLETED`。

声音注册 API 保持兼容：

```json
{"input":{"task_type":"register_voice","voice_name":"tech_narrator","reference_audio_url":"https://private-host.example.com/ref.wav?signature=...","reference_text":"准确逐字稿","language":"Chinese"}}
```

URL 注册需要把私有 HTTPS 域名加入 `REFERENCE_HOSTS`。服务拒绝非白名单/非公网地址、跳转和过大的文件。不要提供公开永久链接。

## 本地验证、成本与故障

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app handler.py scripts
docker build -t autostudio-voice-worker:local .
```

有完整资产的 GPU Pod 可离线试听：

```bash
python -m scripts.smoke_gpu --data-dir /runpod-volume/autostudio \
  --output-dir /runpod-volume/autostudio/smoke --text '你好，这是一段测试语音。' --format mp3
```

`GPT-SoVITS assets missing` 表示卷缺少私人权重或公共辅助模型；`no registered ... reference in DATA_DIR` 表示声音档案未在 Endpoint 的卷上；CUDA 自检失败先检查 GPU 分配和驱动；显存不足则缩短 `CHUNK_CHARS` 或换大卡；`flash-attn is not installed` 仅为可选加速警告。当前尚未用这两份 v2Pro 权重在 RunPod 上完成真实试听；不能据单元测试推断音色相似度、自然度或发音准确率。每日低频调用可设 `min_workers=0`、`max_workers=1`，接受冷启动来节省闲置 GPU 费；保留卷缓存减少模型下载时间。

`evaluation/cases.json` 给出中文、英文、混合、数字和长段落的试听文本。完整资产就绪后运行 `python -m scripts.evaluate_voice --data-dir /runpod-volume/autostudio --output-dir /runpod-volume/autostudio/evaluation`，逐条听生成结果并在 `evaluation/review_template.csv` 填写音色相似度、自然度和发音评分。没有改造上游 Decoder，因此不存在需要伪造分数的“改造版 vs 原版 Decoder”对照；可用上游 API 对相同权重、参考片段和文本做人工对照。
