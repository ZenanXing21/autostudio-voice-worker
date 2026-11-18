# AutoStudio Voice Worker

RunPod Serverless 配音 Worker。Agent 07 提交文本和已注册的声音 ID，服务使用 **Qwen3-TTS Base 的参考音频 ICL 克隆**生成中文、英文或混合语音。只注册本人或已明确授权的声音。

## 架构

```text
Agent 07 -> RunPod job -> 规范化/分句 -> 同一 VoiceClonePrompt 逐段推理
                                      -> FFmpeg 调速/拼接/响度 -> WAV/MP3 + SRT/JSON
                                      -> 私有 S3/R2 -> 预签名 URL
注册音频 HTTPS -> 下载限制 -> FFmpeg 24 kHz 单声道 -> 质量检查 -> Network Volume 私有档案 + S3/R2 私有备份
```

`app/voice_manager.py` 管理声音，`tts_engine.py` 仅调用 Base 克隆接口，`audio_processor.py` 处理媒体，`storage.py` 管理私有对象存储。声音档案和模型缓存分别位于 `$DATA_DIR/voices` 与 `$HF_HOME`；必须把两者放在持久化卷。容器镜像不含录音或模型权重。

## 模型、许可证与硬件

- 官方 [Qwen3-TTS 仓库](https://github.com/QwenLM/Qwen3-TTS) 的 `Qwen3TTSModel.create_voice_clone_prompt(ref_audio, ref_text)` 和 `generate_voice_clone(text, language, voice_clone_prompt)` 是本项目使用的接口。
- 模型 ID 为 [`Qwen/Qwen3-TTS-12Hz-1.7B-Base`](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)。该模型卡及[上游许可证](https://github.com/QwenLM/Qwen3-TTS/blob/main/LICENSE)标注 Apache-2.0；部署前仍请复核所选模型版本与许可。
- CustomVoice 的预设说话人和 VoiceDesign 的指令接口不替代 Base 的参考音频克隆。Base 未公开可验证的 `style` 或 `speed` 生成参数：速度由 FFmpeg `atempo` 实现；风格需要分别注册**同一人**的 documentary / energetic / calm / conversational 参考录音，未注册的风格会报错。风格效果取决于参考录音，不能保证模型精确复现情绪。
- 建议从 **24 GB 显存**的 RunPod GPU 起步，`max_workers=1`，测试你的实际文本长度后调整。模型卡未给出本项目可保证的最低显存；24 GB 是保守的部署起点，不是官方硬性要求。Worker 启动时检查 CUDA，根据 GPU 架构选择 bf16/fp16，并使用 SDPA。OOM 时清空 CUDA 缓存并报告错误。
- 代码与接口按 2026-11-19 官方资料核对；**尚未在真实 GPU 上运行验证**。

## 录音与声音注册

请录制安静环境中的本人声音，建议 5–15 秒，单人、无背景音乐，普通话或英语发音清晰。提交逐字准确的 `reference_text`。接受 WAV、MP3、M4A（FFmpeg 解码）；系统转为 24 kHz 单声道 WAV，裁剪首尾静音、做响度标准化，并检查 3–20 秒、峰值、静音比例和噪声估计。质量检查是启发式筛查，不能替代人工试听。默认声音名 `tech_narrator`，默认纪录片风格。性别、沉稳程度和低沉感由**你提供的声音**决定；系统不会凭空改变音色。其他风格以同一 `voice_name`、不同 `style` 注册。声音注册若已有同名风格会拒绝覆盖。

本地注册（在容器内或装有依赖的 Python 环境）：

```bash
export DATA_DIR=/runpod-volume/autostudio
python -m scripts.register_voice /private/my_voice.m4a --voice-name tech_narrator --reference-text '这里填写录音对应的准确文本' --language Chinese
```

Serverless 注册使用存放在可信私有上传域名的**短期预签名 HTTPS 下载 URL**，将该域名加入 `REFERENCE_HOSTS`。服务拒绝不在白名单内的域名、非公网地址、跳转和超大文件。RunPod API key 可调用端点，务必限制其持有者；音频 URL 本身可能暴露访问权，尽量缩短有效期。档案写入 Network Volume，并上传到私有 S3/R2 桶备份；备份对象没有公开 ACL。不要把声音文件放进 Git、Docker build context 或公开桶。

## 部署 RunPod Serverless

1. 在 RunPod 创建 Network Volume，选择和 Serverless Endpoint 相同区域，挂载在 `/runpod-volume`。参考 [RunPod Serverless 文档](https://docs.runpod.io/serverless/overview) 和 [Network Volumes 文档](https://docs.runpod.io/storage/network-volumes)。卷持久保存声音及 Hugging Face 模型缓存；冷启动首次下载权重，之后复用缓存。
2. 创建私有 Cloudflare R2 或 S3 桶，生成仅限该桶的访问密钥。配置 `S3_BUCKET`、`S3_ENDPOINT_URL`（AWS S3 留空）、`S3_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`。输出以预签名 GET URL 返回。把密钥作为 RunPod 环境变量或 Secret 提供，不写入镜像或 Git。
3. 构建镜像并推送到你的私有或公开容器仓库：

   ```bash
   docker build -t YOUR_REGISTRY/autostudio-voice-worker:latest .
   docker push YOUR_REGISTRY/autostudio-voice-worker:latest
   ```

4. 创建 RunPod **Custom Worker** Endpoint，填入镜像、GPU（建议 24 GB 起）、Network Volume、环境变量。建议先设 `max_workers=1`、`min_workers=0` 控制费用。录音存放在卷和私有桶，不在镜像内。Worker 启动时验证配置、初始化存储、扫描档案、检查 GPU、加载模型，随后调用 `runpod.serverless.start` 等待任务。
5. 首次启动下载模型可能较慢。可在挂载同一卷的 GPU Pod 中运行 `scripts/download_models.sh` 预热缓存。卷读写及区域配置以 RunPod 控制台当前界面为准。

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

中文配音传 `language: "Chinese"`，英文传 `"English"`，中英混合传 `"Auto"`。支持 `wav`、`mp3`；始终保留并上传 WAV，MP3 为派生文件。`speed` 范围 0.75–1.5，默认为 1.0。成功的 `output` 包括 `audio_url`、`wav_url`、`raw_wav_url`、`captions_url`、`segments_url`、`duration`、`sample_rate: 24000`。URL 默认一小时过期，可配置 `PRESIGN_SECONDS`。错误的 `output` 为 `{"status":"error","error_type":"...","message":"..."}`；Agent 07 应检查该状态并按需重试。

## 文本、字幕与质量边界

文本按中英文标点断句，超长句再拆至 `CHUNK_CHARS`，各段复用同一 VoiceClonePrompt。`pronunciation.json` 是可编辑的英文技术词替换词典；内容应是模型可读的发音写法，修改后重新构建镜像或以 `PRONUNCIATION_DICTIONARY` 指向卷上文件。数字和百分比做保守处理，复杂版本号、缩写和项目名需人工检查发音。

`segments.json` 和 `captions.srt` 的时间范围来自**实际生成后每段音频的采样数**，包含每段音频内部的停顿；段间插入 120 ms 静音。它们是音频片段级时间边界，**不是 WhisperX 强制对齐、词级或字级时间戳**。混合语言可生成片段级字幕。若要求严格的句子内对齐，应在真实中英混合测试集上验证 WhisperX 或其他中文对齐器后另行接入。原始拼接 WAV 和最终响度处理的 WAV 均上传到私有对象存储，分别由 `raw_wav_url` 和 `wav_url` 返回。可选降噪尚未启用，避免损伤参考音色。

## 成本、测试与故障

`min_workers=0` 省闲置 GPU 费，但增加冷启动时间；持久化 HF 缓存减少重复下载。短文本、较小 `CHUNK_CHARS`、单 worker 限制并发与显存峰值。清理过期输出对象可在桶生命周期规则中设置；不要自动删除私有声音档案。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app handler.py scripts
docker build -t autostudio-voice-worker:local .
```

`CUDA GPU is required`：检查 RunPod GPU 类型和 Endpoint；`GPU out of memory`：减小 `CHUNK_CHARS` 或换更大 GPU；找不到声音：确认同一区域挂载同一 Network Volume、`DATA_DIR` 正确；注册失败：核对录音与逐字稿、白名单、私有 URL 有效期；S3 上传失败：核对密钥、桶、区域和 R2 endpoint。使用真实 GPU 与本人授权录音完成端到端试听后再接 Agent 07。
