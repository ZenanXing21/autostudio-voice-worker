# AutoStudio Voice Worker

RunPod Pod 常驻 HTTP 配音服务。Agent 07 提交文本和已注册的声音 ID，服务使用 **Qwen3-TTS Base 的参考音频 ICL 克隆**生成中文、英文或混合语音。镜像默认运行 FastAPI；原有 Serverless handler 仍可通过 `WORKER_MODE=serverless` 启用。只注册本人或已明确授权的声音。

## 架构

```text
Agent 07 -> Pod HTTP /tts -> 规范化/分句 -> 同一 VoiceClonePrompt 逐段推理
                                      -> FFmpeg 调速/拼接/响度 -> WAV/MP3 + SRT/JSON
                                      -> 配置 S3/R2 时返回预签名 URL；否则保存到 OUTPUT_DIR 并返回鉴权下载 URL
注册音频 HTTPS -> 下载限制 -> FFmpeg 24 kHz 单声道 -> 质量检查 -> DATA_DIR 私有档案（配置 S3/R2 时再备份）
```

`api.py` 提供 HTTP 鉴权和下载，`app/handler.py` 复用原有推理流程，`app/voice_manager.py` 管理声音，`tts_engine.py` 仅调用 Base 克隆接口，`audio_processor.py` 处理媒体，`storage.py` 管理本地或私有对象存储。声音档案、模型缓存和本地输出分别位于 `$DATA_DIR/voices`、`$HF_HOME` 和 `$OUTPUT_DIR`。这些目录如需跨 Pod 重建保留，必须放在持久化卷。容器镜像不含录音或模型权重。

## 模型、许可证与硬件

- 官方 [Qwen3-TTS 仓库](https://github.com/QwenLM/Qwen3-TTS) 的 `Qwen3TTSModel.create_voice_clone_prompt(ref_audio, ref_text)` 和 `generate_voice_clone(text, language, voice_clone_prompt)` 是本项目使用的接口。
- 模型 ID 为 [`Qwen/Qwen3-TTS-12Hz-1.7B-Base`](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)。该模型卡及[上游许可证](https://github.com/QwenLM/Qwen3-TTS/blob/main/LICENSE)标注 Apache-2.0；部署前仍请复核所选模型版本与许可。
- CustomVoice 的预设说话人和 VoiceDesign 的指令接口不替代 Base 的参考音频克隆。Base 未公开可验证的 `style` 或 `speed` 生成参数：速度由 FFmpeg `atempo` 实现；风格需要分别注册**同一人**的 documentary / energetic / calm / conversational 参考录音，未注册的风格会报错。风格效果取决于参考录音，不能保证模型精确复现情绪。
- 建议从 **24 GB 显存**的 RunPod GPU 起步，`max_workers=1`，测试你的实际文本长度后调整。模型卡未给出本项目可保证的最低显存；24 GB 是保守的部署起点，不是官方硬性要求。Worker 启动时检查 CUDA，根据 GPU 架构选择 bf16/fp16，并使用 SDPA。OOM 时清空 CUDA 缓存并报告错误。
- 代码与接口按 2026-11-19 官方资料核对；本地 6 GB GPU 上已验证 0.6B Base 克隆，**1.7B Base 尚未在 RunPod 上验证**。

## 录音与声音注册

请录制安静环境中的本人声音，建议 5–15 秒，单人、无背景音乐，普通话或英语发音清晰。提交逐字准确的 `reference_text`。接受 WAV、MP3、M4A（FFmpeg 解码）；系统转为 24 kHz 单声道 WAV，裁剪首尾静音、做响度标准化，并检查 3–20 秒、峰值、静音比例和噪声估计。质量检查是启发式筛查，不能替代人工试听。默认声音名 `tech_narrator`，默认纪录片风格。性别、沉稳程度和低沉感由**你提供的声音**决定；系统不会凭空改变音色。其他风格以同一 `voice_name`、不同 `style` 注册。声音注册若已有同名风格会拒绝覆盖。

本地注册（在容器内或装有依赖的 Python 环境）：

```bash
export DATA_DIR=/workspace/autostudio
python -m scripts.register_voice /private/my_voice.m4a --voice-name tech_narrator --reference-text '这里填写录音对应的准确文本' --language Chinese
```

Serverless 注册使用存放在可信私有上传域名的**短期预签名 HTTPS 下载 URL**，将该域名加入 `REFERENCE_HOSTS`。不使用 URL 注册时可留空；但此时 `register_voice` API 会拒绝 URL。服务拒绝不在白名单内的域名、非公网地址、跳转和超大文件。RunPod API key 可调用端点，务必限制其持有者；音频 URL 本身可能暴露访问权，尽量缩短有效期。档案写入 `DATA_DIR`，配置 S3/R2 后另存私有备份；本地模式不自动备份。不要把声音文件放进 Git、Docker build context 或公开桶。

## 部署 RunPod Pod + HTTP API

1. 将镜像 `ghcr.io/zenanxing21/autostudio-voice-worker:sha-<已成功发布的提交前 12 位>` 填入 GPU Pod，给 Pod 配置持久化 `/workspace` 卷，并暴露 `8000/http`（如需 SSH，再保留 `22/tcp`）。RunPod 的 [Pod 代理 URL](https://docs.runpod.io/runpodctl/reference/runpodctl-remove-pods) 格式为 `https://<POD_ID>-8000.proxy.runpod.net`。镜像里的 Uvicorn 已监听 `0.0.0.0:8000`；不要让未设置 `API_TOKEN` 的 Pod 对公网服务。
2. 在 RunPod Secret/环境变量中设置一个**长随机** `API_TOKEN`；还可设置 `MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base`。镜像默认 `HF_HOME=/workspace/hf-cache`、`DATA_DIR=/workspace/autostudio`、`OUTPUT_DIR=/workspace/outputs`、`WORKER_MODE=pod`、`S3_BUCKET` 为空。若模型已在卷中，可设 `MODEL_ID=/workspace/models/Qwen3-TTS-12Hz-1.7B-Base`。私有录音只放在 `/workspace/autostudio/voices`，不要放进镜像或公开仓库。GPU 初始化完成后 `/health` 才会响应 `ready: true`。
3. 在 Pod 内用上面的 `python -m scripts.register_voice` 注册本人录音，并确保 `tech_narrator` 档案存在。随后从 Agent 07 调用：

   ```bash
   BASE_URL="https://<POD_ID>-8000.proxy.runpod.net"
   curl -fsS "$BASE_URL/health"
   curl -fsS -X POST "$BASE_URL/tts" \
     -H "Authorization: Bearer $API_TOKEN" -H 'Content-Type: application/json' \
     -d '{"text":"你好，这是一段测试语音。","voice":"tech_narrator","language":"Chinese","style":"documentary","speed":1.0,"format":"wav","job_id":"job-001"}'
   ```

   `/tts` 同步返回 `status`、`job_id`、`audio_url`、`wav_url`、`captions_url`、`segments_url`、时长等字段。`voice` 省略或写 `default` 时使用 `tech_narrator`。`job_id` 只供请求关联，实际文件目录由服务生成。下载也要带同一个 Bearer token，例如 `curl -fL -H "Authorization: Bearer $API_TOKEN" "$AUDIO_URL" -o audio.wav`。返回的 `audio_path` 是 Pod 内路径，供排查使用。`/health` 不要求 token；`/tts` 与下载要求 token。错误会使用 4xx/5xx 状态码；GPU 忙时返回 409。API 只允许一次 GPU 推理。

4. 无需 S3 即可通过受保护的 Pod 下载 URL 访问本地输出。Pod 停止期间 HTTP URL 不可用，持久化卷上的文件仍保留；若需 Pod 停止后持续下载，可配置私有 S3/R2。Pod 持续运行时按运行时长计费，低频使用应在任务完成后停止 Pod，并留意卷存储费用。

## 可选：RunPod Serverless 旧入口

1. 在 RunPod 创建 Network Volume，选择和 Serverless Endpoint 相同区域，挂载在 `/runpod-volume`。参考 [RunPod Serverless 文档](https://docs.runpod.io/serverless/overview) 和 [Network Volumes 文档](https://docs.runpod.io/storage/network-volumes)。卷持久保存声音及 Hugging Face 模型缓存；冷启动首次下载权重，之后复用缓存。
2. Agent 07 若从另一台服务读取输出，请创建私有 Cloudflare R2 或 S3 桶，生成仅限该桶的访问密钥。配置 `S3_BUCKET`、`S3_ENDPOINT_URL`（AWS S3 留空）、`S3_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`。输出以预签名 GET URL 返回。把密钥作为 RunPod 环境变量或 Secret 提供，不写入镜像或 Git。仅在同一持久化文件系统内处理输出时，可以留空 `S3_BUCKET`，使用 `OUTPUT_DIR` 本地模式。
3. `main` 分支更新后，GitHub Actions 的 `publish-image.yml` 会构建 Linux AMD64 镜像并发布到 GHCR：`ghcr.io/zenanxing21/autostudio-voice-worker:latest`，同时发布 `sha-<提交前 12 位>` 固定标签。在仓库 **Actions** 页确认发布任务成功后，再在 RunPod 填写该镜像地址。**本机的 `autostudio-voice-worker:local` 无法被 RunPod 拉取。**

   镜像默认使用官方 `python:3.12-slim`，再从 [PyTorch 官方 CUDA 12.6 wheel 索引](https://pytorch.org/get-started/previous-versions/)安装 `torch`/`torchaudio`。FFmpeg 由包含可执行文件的 `imageio-ffmpeg` wheel 提供，构建时检查 `libmp3lame` 编码器。如果本地 Docker Hub 代理返回不一致的镜像清单，可将 `PYTHON_BASE` 指向你信任的 Python 基础镜像镜像站。

   ```bash
   docker build -t autostudio-voice-worker:local .
   ```

4. 该 GHCR 包已设为 **Public**，RunPod 的 **Container Registry Credentials** 留空即可匿名拉取；公开镜像层包含 Worker 代码，但不包含录音或密钥。创建 RunPod **Custom Worker** Endpoint 时，镜像填写本次 Actions 发布的 `ghcr.io/zenanxing21/autostudio-voice-worker:sha-<提交前 12 位>`（或 `latest`），设置 `WORKER_MODE=serverless`、`HF_HOME=/runpod-volume/hf-cache`、`DATA_DIR=/runpod-volume/autostudio`，GPU 建议 24 GB 起，挂载 Network Volume。本地镜像解包后原约 10.8 GB，加入 HTTP 依赖和 SoX 后请按新镜像实际大小配置容器磁盘，建议先设 **30 GB**。建议先设 `max_workers=1`、`min_workers=0` 控制费用。Worker 启动时验证配置、初始化存储、扫描档案、检查 GPU、加载模型，随后调用 `runpod.serverless.start` 等待任务。
5. 首次启动下载模型可能较慢。可在挂载同一卷的 GPU Pod 中运行 `scripts/download_models.sh` 预热缓存。卷读写及区域配置以 RunPod 控制台当前界面为准。

### 在 Pod 上使用 `/workspace`（无 S3）

模型路径没有写死。`MODEL_ID` 可填 Hugging Face 模型 ID，模型文件会缓存在 `HF_HOME`；也可填已下载的**目录**，例如 `/workspace/models/Qwen3-TTS-12Hz-1.7B-Base`。目录名必须以 `-Base` 结尾。将持久化卷挂载到 `/workspace` 后，在 Pod 环境变量中设置：

```text
MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base
HF_HOME=/workspace/hf-cache
DATA_DIR=/workspace/autostudio
OUTPUT_DIR=/workspace/outputs
S3_BUCKET=
```

Worker 启动时会建立缓存、声音档案和输出目录；如需预先建立目录，可在 Pod 中执行 `mkdir -p /workspace/hf-cache /workspace/autostudio/voices /workspace/outputs`。私有声音文件位于 `/workspace/autostudio/voices`。`/workspace/outputs` 中的生成文件只在持有该卷的 Pod/进程可用，**不是可从互联网访问的 URL**。如果 Agent 07 在另一服务上通过 URL 获取音频，请配置 S3/R2。将这些目录放在持久化卷上，否则删除 Pod 或 Serverless worker 后可能丢失文件。

在接入 Agent 07 前，可在有足够显存的 GPU Pod 中使用已注册在卷上的本人声音进行**不上传对象存储**的试听：

```bash
python -m scripts.smoke_gpu --data-dir /runpod-volume/autostudio --output-dir /runpod-volume/autostudio/smoke --text '人工智能正在改变世界。' --format mp3
```

试听脚本生成 `audio.wav`、`audio_raw.wav`、`audio.mp3`、`captions.srt` 和 `segments.json`；字幕时间来自实际生成音频的片段采样数，只标记片段边界。6 GB GPU 可临时改用官方 `Qwen/Qwen3-TTS-12Hz-0.6B-Base` 验证克隆流程，生产默认仍为 1.7B Base。Windows Docker 绑定目录读取大权重可能很慢；RunPod 的 Linux Network Volume 或 Docker Linux 卷更适合模型缓存。

## 调用 API

将 `ENDPOINT_ID`、`RUNPOD_API_KEY` 设置在调用方私有环境中。异步作业建议使用 `/run` 并轮询 `/status/JOB_ID`；小任务可使用 `/runsync`。下方请求体与返回示例展示 Worker 的 `output` 内容：

```bash
curl -X POST "https://api.runpod.ai/v2/$ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d '{"input":{"task_type":"register_voice","voice_name":"tech_narrator","reference_audio_url":"https://your-private-upload-host.example.com/reference.wav?signature=...","reference_text":"这里填写录音对应的准确文本","language":"Chinese"}}'
```

成功时 `output` 为 `{"status":"completed","voice_id":"tech_narrator","style":"documentary","message":"Voice profile created","quality":{...}}`。

```bash
curl -X POST "https://api.runpod.ai/v2/$ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d '{"input":{"task_type":"tts_generate","voice_id":"tech_narrator","text":"人工智能正在改变整个世界。今天介绍 GitHub 上的 ComfyUI。","language":"Auto","style":"documentary","speed":1.0,"format":"mp3"}}'
```

中文配音传 `language: "Chinese"`，英文传 `"English"`，中英混合传 `"Auto"`。支持 `wav`、`mp3`；始终保留 WAV，MP3 为派生文件。`speed` 范围 0.75–1.5，默认为 1.0。配置 S3/R2 时，成功的 `output` 包括 `storage_mode: "s3"`、`audio_url`、`wav_url`、`raw_wav_url`、`captions_url`、`segments_url`、`duration`、`sample_rate: 24000`；URL 默认一小时过期，可配置 `PRESIGN_SECONDS`。未配置 `S3_BUCKET` 时，`storage_mode: "local"`，相应的 `*_url` 值为 `null`，使用 `audio_path`、`wav_path`、`raw_wav_path`、`captions_path`、`segments_path` 读取持久化卷上的文件。错误的 `output` 为 `{"status":"error","error_type":"...","message":"..."}`；Agent 07 应检查该状态并按需重试。

## 文本、字幕与质量边界

文本按中英文标点断句，每个普通句子单独生成，超长句再拆至 `CHUNK_CHARS`，各段复用同一 VoiceClonePrompt。`pronunciation.json` 是可编辑的英文技术词替换词典；内容应是模型可读的发音写法，修改后重新构建镜像或以 `PRONUNCIATION_DICTIONARY` 指向卷上文件。数字和百分比做保守处理，复杂版本号、缩写和项目名需人工检查发音。

`segments.json` 和 `captions.srt` 的时间范围来自**实际生成后每句音频的采样数**，包含句内的停顿；句间插入 120 ms 静音。普通长度的句子对应一个音频片段，因此字幕有句子级片段边界；超长句会拆成多个片段。它们**不是 WhisperX 强制对齐、词级或字级时间戳**。中英混合文本也按相同规则输出。若要求精确到句内实际发声起止点，应在真实中英混合测试集上验证 WhisperX 或其他中文对齐器后另行接入。原始拼接 WAV 和最终响度处理的 WAV 均保留；配置 S3/R2 时返回 `raw_wav_url` 和 `wav_url`，否则返回相应本地路径。可选降噪尚未启用，避免损伤参考音色。

## 成本、测试与故障

Pod 停机后不再支付 GPU 运行费，但持久化卷继续计费；持久化 HF 缓存减少重复下载。短文本、较小 `CHUNK_CHARS`、单 GPU 请求限制并发与显存峰值。清理过期输出对象可在桶生命周期规则中设置；本地输出需自行清理，但不要自动删除私有声音档案。视频**成片时长**不是 GPU 运行时长。当前声音 Worker 要求 CUDA GPU，未实现 CPU 推理。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app api.py handler.py scripts
docker build -t autostudio-voice-worker:local .
```

`CUDA GPU is required`：检查 RunPod GPU 类型和 Endpoint；`GPU out of memory`：减小 `CHUNK_CHARS` 或换更大 GPU；找不到声音：确认同一区域挂载同一 Network Volume、`DATA_DIR` 正确；注册失败：核对录音与逐字稿、白名单、私有 URL 有效期；S3 上传失败：核对密钥、桶、区域和 R2 endpoint。使用真实 GPU 与本人授权录音完成端到端试听后再接 Agent 07。

### 本地验证记录（2026-11-19）

在 Docker Hub 代理返回错误清单的环境中，使用已缓存的可信 Python 镜像构建：

```bash
docker build --build-arg PYTHON_BASE=docker.m.daocloud.io/library/python:3.12-slim -t autostudio-voice-worker:local .
```

旧 Serverless 构建成功；容器内 `qwen_tts`、RunPod、PyTorch 2.7.1+cu126 可导入，FFmpeg 提供 `libmp3lame`，CUDA 可见 6 GB 的 RTX 3060 Laptop GPU。使用授权参考音频与官方 0.6B Base 模型完成了中英两段真实 GPU 推理，输出 7.63 秒 WAV、MP3、SRT 和片段 JSON。**1.7B Base 尚未在 RunPod 实测；字幕也没有词级或字级强制对齐。** 新 Pod 镜像额外安装 SoX，消除 `sox: not found` 环境报错。
