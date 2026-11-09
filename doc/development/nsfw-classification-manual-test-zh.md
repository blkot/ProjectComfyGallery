# NSFW 图片分级：WSL 首次测试指南

先完成第一阶段：在 Windows WSL 中用 Mini/PyTorch 跑 5–10 张本地图片，并打开 HTML 报告。
这一步不连接 CG，不上传图片，也不需要记录媒体 ID。ONNX、NudeNet 和 NAS 性能测试放在后面。

## 1. 下载模型：它是什么、从哪里来

本项目第一阶段使用 **Viddexa NSFW Detection 2 Mini**。模型托管在 Hugging Face：

- 模型页面：[viddexa/nsfw-detection-2-mini](https://huggingface.co/viddexa/nsfw-detection-2-mini)
- 模型仓库 ID：`viddexa/nsfw-detection-2-mini`
- 下载到项目目录：`models/nsfw/mini/`

这里的“仓库”是 Hugging Face 上存放模型权重和配置文件的页面，不是 CG 的代码仓库。
网页标记为 **Not-For-All-Audiences**；首次查看时可能需要点页面上的 **View content**。

### 在 WSL 项目根目录执行

先确认当前目录是 ProjectComfyGallery 根目录，并确认下载和容器工具可用：

```bash
ls compose.nsfw-benchmark.yaml
uvx --version
docker compose version
```

下载整个模型仓库到项目要求的位置：

```bash
uvx --from huggingface_hub hf download \
  viddexa/nsfw-detection-2-mini \
  --revision main \
  --local-dir models/nsfw/mini
```

下载结束后检查目录：

```bash
ls -lh models/nsfw/mini
```

其中应包含 `config.json`、`preprocessor_config.json` 和模型权重文件（通常为
`model.safetensors`）。不要把权重改名或放到 `models/nsfw/` 的其他位置。模型由 WSL
中的命令下载；benchmark 容器运行时不联网，也不会自动下载模型。首次构建 Docker 镜像
需要网络来下载运行依赖。

如果提示找不到 `uvx`，先在 WSL 安装 uv，再重试这条下载命令。想重复得到完全相同的模型时，
把 `main` 换成模型页面对应的 commit SHA，并在运行命令中使用同一个 revision；第一次冒烟
测试先用 `main` 即可。

`hf download` 的官方用法见 [Hugging Face CLI 文档](https://huggingface.co/docs/huggingface_hub/guides/cli)。

## 2. 准备 5–10 张图片

把图片放到：

```text
testdata/nsfw/samples/
```

支持 JPG、PNG、WebP、BMP、TIFF。文件可以直接复制到 WSL 项目目录中；也可以通过下面的编辑器从
Windows 导入到 WSL，不需要导入 CG。

在 WSL 项目根目录启动编辑器服务：

```bash
python3 tools/nsfw-manifest-editor/server.py
```

保持这个终端运行，然后在 Windows 浏览器打开：

```text
http://127.0.0.1:8765
```

在页面中按需操作：

- 点 **从 WSL samples 加入图片**，把 WSL `testdata/nsfw/samples/` 里的图片加入清单。
- 点 **导入 Windows 图片文件夹**，选择 Windows 文件夹；图片会通过本机 localhost 复制到 WSL 的
  `testdata/nsfw/samples/`。也可以用 **添加 Windows 图片** 选择若干文件。
- 每张图片会显示预览卡片；选人工标签，备注可以留空。用 **从清单移除** 排除不想测的图片。
- 点 **重载 WSL 清单** 可继续编辑现有清单；也可以用 **导入 Windows 清单** 选择 JSON。
- 点 **保存到 WSL**，页面会直接写入 WSL 项目中的 `testdata/nsfw/manifest.local.json`，不会弹出
  Windows 保存对话框。

图片和 manifest 都保存在 WSL 项目目录。传输只经过本机回环地址，不连接 CG 或外网；服务只监听
`127.0.0.1`。完成后回到启动服务的终端按 Ctrl-C 停止。推荐 Chrome 或 Edge。

`file` 是相对于 `samples/` 的文件名，所以写 `case-001.jpg`，不要写 `samples/case-001.jpg`。
编辑器会自动写入相对文件名。标签含义如下：

| 标签 | 人工标注含义 |
| --- | --- |
| `safe` | 普通内容，无明显性暗示或裸露 |
| `sexy` | 性感或性暗示内容，无明确裸露 |
| `nudity` | 有裸露，但不属于明确色情内容 |
| `explicit` | 明确色情内容或性行为 |
| `review` | 人工也难以确定的边界图片 |

留空标签的图片仍会分类和显示，但不参与准确率统计。清单中不要写媒体 ID、姓名等个人信息。
图片、实际清单和结果目录都不会提交到 Git。

## 3. 跑第一阶段：Mini / PyTorch

在 WSL 的项目根目录执行这一条命令：

```bash
NSFW_INFERENCE_BACKEND=pytorch \
NSFW_NUDENET_ENABLED=false \
NSFW_BENCHMARK_PHASE=phase-1-pytorch-mini \
CG_NSFW_MODEL_REVISION=main \
docker compose -f compose.nsfw-benchmark.yaml run --build --rm nsfw-benchmark
```

第一次运行会构建 CPU 推理镜像，可能需要一些时间。容器只挂载本地模型和图片；图片目录为只读，
容器没有网络，也没有 CG、数据库或 API 依赖。

运行结束后会生成：

- `testdata/nsfw/results/phase-1-pytorch-mini.html`：可视化报告
- `testdata/nsfw/results/phase-1-pytorch-mini.json`：原始分数和计时数据

## 4. 在 Windows 中打开报告

从 WSL 执行：

```bash
explorer.exe "$(wslpath -w testdata/nsfw/results/phase-1-pytorch-mini.html)"
```

报告是自包含 HTML，可在浏览器离线查看。先检查人工标签、模型建议、置信度和类别分数，再展开图片
查看预览。报告还能按标签、文件名和复核状态筛选，并显示混淆矩阵及每类 Precision/Recall。
图片预览嵌在 HTML 中，所以报告应和原图片一样保存在私人位置。

如果单张图片解码或推理失败，工具仍会生成报告，但命令会返回非零状态；在报告的“错误”列查看原因。

### 常见问题

- **提示找不到模型文件：** 确认 `models/nsfw/mini/` 下有 `config.json`、
  `preprocessor_config.json` 和权重文件，再重新运行下载命令。
- **提示清单里的图片不存在：** 确认 `file` 文件名与 `testdata/nsfw/samples/` 完全一致，且不带
  `samples/` 前缀。
- **提示 Docker 命令不可用：** 确认 Docker Desktop 正在运行，并已开启当前 WSL 发行版的集成。

## 5. 第一阶段通过后再做

### 扩大测试集

- 5–10 张：确认模型和报告能正常运行。
- 100–200 张：比较耗时和内存；少于 1,000 张时 P99 只作观察值，主要看 P50/P95。
- 400–600 张：在时间允许时评估分类质量。样本比例尽量接近自己的图库。

### ONNX 对比

先在 WSL/PC 导出 ONNX，再用同一批图片做 PyTorch 与 ONNX 的数值对比：

```bash
bash scripts/export_nsfw_onnx.sh
uv run --with torch --with transformers --with pillow \
  --with numpy --with onnxruntime \
  python scripts/nsfw_onnx_parity.py testdata/nsfw/samples/*.jpg
```

通过对比后，把 `model.onnx` 放在 `models/nsfw/mini-onnx/model.onnx`，再运行：

```bash
NSFW_INFERENCE_BACKEND=onnx \
NSFW_NUDENET_ENABLED=false \
NSFW_BENCHMARK_PHASE=phase-2-onnx \
CG_NSFW_MODEL_REVISION=main \
docker compose -f compose.nsfw-benchmark.yaml run --rm nsfw-benchmark
```

如果样本不是 JPG，请把 PNG 等文件也传给 parity 命令。ONNX 不保证在 J4125 上更快，最终以 NAS
实测为准。

### NudeNet 裸露区域检测

在同一批图片上启用 NudeNet，观察报告中的检测框和部位标签：

```bash
NSFW_INFERENCE_BACKEND=pytorch \
NSFW_NUDENET_ENABLED=true \
NSFW_NUDENET_RUN_MODE=always \
NSFW_BENCHMARK_PHASE=phase-3-mini-nudenet \
CG_NSFW_MODEL_REVISION=main \
docker compose -f compose.nsfw-benchmark.yaml run --rm nsfw-benchmark
```

`always` 会对每张图片运行检测，便于先测召回率；它会增加推理时间。检测到身体部位不等于判断出色情
意图。模型判断与裸露检测冲突时，应查看单图证据并按你的分级标准复核。

### 在 J4125 NAS 上测性能

NAS 是最终性能验收设备。把相同的模型、`testdata/nsfw/` 和 Compose 文件复制到 NAS 测试目录，使用
构建机准备好的 benchmark 镜像。命令中**不要加 `--build`**：

```bash
NSFW_BENCHMARK_PHASE=phase-1-pytorch-mini \
docker compose -f compose.nsfw-benchmark.yaml run --rm nsfw-benchmark
```

用另一个 SSH 终端运行 `docker stats`，记录 benchmark 运行期间的 CPU 和内存。之后再分别测试 ONNX、
Mini + NudeNet。报告记录模型加载时间、首张推理、P50/P95/P99、串行吞吐量和进程 RSS；Docker Stats
用于补充容器资源数据。文档中的 `1536M` 内存上限和 P95 低于 2 秒是待验证目标，不是已测结果。

## 隐私与提交

不要把测试图片、`manifest.local.json`、JSON 结果或 HTML 报告提交到仓库。它们包含私人样本或嵌入的图片
预览；示例清单可以提交。
