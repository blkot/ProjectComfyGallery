# NSFW 图片分级：本地测试集与可视化测试指南

**状态：** 独立测试工具和报告已准备；模型准确率、ONNX 性能和 J4125 实测尚待手动验证。

## 测试方式

分级、性能和准确率测试直接读取本地样本目录，用图片文件名和人工标签生成结果。
这条测试路径不连接 CG API、数据库或媒体 ID；不需要先把整套样本上传到 CG。

测试容器使用与 `nsfw-runtime` 相同的推理模块和环境变量，网络模式为 `none`，
样本以只读方式挂载，报告写到本地 `results/` 目录。每个阶段会输出 JSON 数据和
一个可离线打开的 HTML 报告，报告里可以按标签筛选、看混淆矩阵、展开单张图片、
查看 NudeNet 检测框和分数。

最后可以额外用一张图片在 CG 里做集成冒烟测试，确认 UI 和上传自动触发。那一步
不需要把整个测试集上传，也不需要手工记录媒体 ID。

AI 建议不会修改人工 `content_rating`（`sfw` / `nsfw`），不会隐藏、移动或删除
媒体。

## 1. 准备本地图片集

### 1.1 人工标签约定

先按你自己的图库和使用习惯确定参考标签。PyTorch、ONNX 和 NudeNet 各阶段都复用
同一清单，避免阶段间更换样本。

| 人工参考标签 | 含义 | 样本边界举例 |
| --- | --- | --- |
| `safe` | 没有明显性暗示或裸露 | 普通照片、风景、日常插画、穿着完整的角色图 |
| `sexy` | 有明显性暗示，但没有明确裸露或性行为 | 性感姿势、暴露穿着、擦边写真 |
| `nudity` | 有可见裸露部位，但画面不属于明确色情内容 | 非明确色情的真人、插画或 3D 裸露图 |
| `explicit` | 明确色情内容、性行为或成人漫画 | 依照你对图库的管理标准标注 |
| `review` | 人工也难以确定，或需要结合语境判断 | 模糊、遮挡、低清晰度或模型容易冲突的边界图 |

`nudity` 是业务标签，不是 Mini 的原生类别。Mini 输出 Normal、Drawing、Sexy、
Porn、Hentai 五类；启用 NudeNet 后，系统才会根据裸露部位证据建议 `nudity`。
裸露检测本身不表示色情意图。

### 1.2 样本规模与覆盖

- **冒烟样本：** 5–10 张，先验证模型能否加载、报告能否生成、类别与裸露证据能否查看。
- **性能样本：** 100–200 张，覆盖不同分辨率、纵横比和来源，用于比较 PyTorch、ONNX、NudeNet。
- **准确性样本：** 条件允许时扩展到 400–600 张人工标注图片，覆盖真人照片、AI 图、
  3D 渲染和插画。

主测试集的类别比例尽量接近实际图库。如果为了检查少见类别而额外增加样本，把它们
标为“挑战样本”并单独解读，不要把人为均衡的分布当作图库真实准确率。

建议准备这些控制样本：

- 普通人像、运动或海滩照片等可能造成误报的 Safe 图。
- 性感穿着但无明显裸露的 Sexy 图。
- 真人、插画和 3D 中的非明确色情裸露图。
- 明确成人内容和成人插画。
- 遮挡、远景、裁切、低清晰度和复杂背景等边界图。
- 裸露部位明显但语境非色情的图，用来检查模型有没有把“检测到部位”直接当成 Explicit。

重复图片只保留一份。边界样本和普通负样本都要保留，不要只挑容易分类的图片。

### 1.3 目录与清单

把图片放在 `testdata/nsfw/samples/`。支持 JPEG、PNG、WebP、BMP、TIFF 等常见静态
格式。图片不需要导入 CG。

复制本地清单示例：

```bash
cp testdata/nsfw/manifest.local.example.json \
  testdata/nsfw/manifest.local.json
```

把示例中的文件名换成 `samples/` 下的真实文件名，并填写人工标签和备注：

```json
{
  "images": [
    {
      "file": "case-001.jpg",
      "expected_rating": "nudity",
      "notes": "illustration | vertical | non-explicit"
    },
    {
      "file": "case-002.png",
      "expected_rating": "safe",
      "notes": "photo | beach | negative-control"
    }
  ]
}
```

`expected_rating` 可用 `safe`、`sexy`、`nudity`、`explicit`、`review`；不想把图片纳入
准确率统计时可以省略该字段。`notes` 用来记录来源类型和边界特征，不要填姓名、地址
等个人信息。清单按文件名匹配图片，不包含 CG ID。

图片、`manifest.local.json` 和结果目录都被 Git 忽略；只提交示例清单，不要提交私人样本。

### 1.4 下载并固定 Mini 模型

在 Mac/PC 上下载模型，再按现有文件传输方式复制到测试环境的
`models/nsfw/mini/`。固定 Hugging Face commit SHA，并在 `.env` 的
`CG_NSFW_MODEL_REVISION` 使用同一个 SHA：

```bash
MODEL_COMMIT="填入实际使用的 Hugging Face commit SHA"
uvx --from huggingface_hub hf download \
  viddexa/nsfw-detection-2-mini \
  --revision "$MODEL_COMMIT" \
  --local-dir ./models/nsfw/mini
```

ONNX 阶段再把导出的 `model.onnx` 放到 `models/nsfw/mini-onnx/`。NudeNet 由固定版本
的 benchmark 镜像提供。测试样本与报告包含私人媒体数据，请按与原图片相同的标准
保管。许可证说明见 [ADR-0016](../decisions/0016-nsfw-onnx-and-nudity-evidence.md)。

## 2. 配置独立 benchmark

在项目根目录 `.env` 设置当前测试阶段的配置。Mini/PyTorch 基线示例：

```dotenv
CG_NSFW_MODEL_REVISION=<Mini 的 commit SHA>
NSFW_INFERENCE_BACKEND=pytorch
NSFW_NUDENET_ENABLED=false
NSFW_CPU_THREADS=2
NSFW_CPU_LIMIT=2.0
NSFW_MEMORY_LIMIT=1536M
NSFW_BENCHMARK_DATA_DIR=./testdata/nsfw
NSFW_BENCHMARK_RESULTS_DIR=./testdata/nsfw/results
NSFW_BENCHMARK_PHASE=phase-1-pytorch-mini
```

独立 benchmark 不读取 `CG_NSFW_CLASSIFIER_ENABLED`、`CG_NSFW_AUTO_CLASSIFY`、API
Token 或数据库配置。其 Compose 文件只启动一次性 `nsfw-benchmark` 容器；没有 CG
依赖、端口、外部网络或可写样本挂载。

### 在 Mac/PC 上试跑

在有模型文件和测试图片的项目目录执行：

```bash
docker compose -f compose.nsfw-benchmark.yaml \
  run --build --rm nsfw-benchmark
```

这会在本机构建/运行 `linux/amd64` benchmark 镜像。Mac 上的容器结果用于核对报告和
分类输出；它不代表 J4125 的速度。

### 在 J4125 NAS 上测性能

不要在 J4125 上构建 PyTorch 镜像。先通过项目发布流程在构建机生成并部署带有本分支
benchmark 程序的 `nsfw-runtime` 镜像，再把 `samples/`、`manifest.local.json`、模型文件
和独立 Compose 文件放到 NAS 测试目录。确保 `.env` 的镜像标签指向该镜像，随后运行：

```bash
docker compose -f compose.nsfw-benchmark.yaml \
  run --rm nsfw-benchmark
```

NAS benchmark 不启动 CG 服务，也不访问 CG 数据库。报告写入
`NSFW_BENCHMARK_RESULTS_DIR` 指定的目录。生成的 HTML 可从共享目录复制到电脑，用浏览器
打开；它是自包含文件，不需要联网。

## 3. 分阶段测试

每阶段只改变后端或 NudeNet 配置之一。每次运行都产生独立的 `.json` 和 `.html`，不要
覆盖上一阶段结果。

第 2 节在 Mac/PC 首次运行时会构建镜像；后续阶段复用该镜像。只有推理代码改变时才在
Mac/PC 重新加 `--build`。NAS 上始终使用构建机准备好的镜像，不要在 J4125 上构建。

### 阶段 1：Mini / PyTorch

确认 `NSFW_INFERENCE_BACKEND=pytorch`、`NSFW_NUDENET_ENABLED=false`，先用 5–10 张图：

```bash
NSFW_BENCHMARK_PHASE=phase-1-pytorch-mini \
docker compose -f compose.nsfw-benchmark.yaml \
  run --rm nsfw-benchmark
```

会生成：

- `testdata/nsfw/results/phase-1-pytorch-mini.json`
- `testdata/nsfw/results/phase-1-pytorch-mini.html`

用浏览器打开 HTML，检查每张图的人工标签、Mini 标签、建议评级、置信度、类别分数和
复核状态。展开图片查看预览；如果启用了 NudeNet，还能查看检测框。先核对样本和标注，
再扩大到性能集。

如果个别图片无法解码或推理失败，工具仍会先写出报告并以非零状态结束；在报告错误列
查看失败原因，修正清单或样本后再重跑该阶段。

### 阶段 2：本机 ONNX 一致性

先在 Mac/PC 上导出 ONNX，再用本地图片比对 PyTorch 和 ONNX logits，不上传图片：

```bash
bash scripts/export_nsfw_onnx.sh
uv run --with torch --with transformers --with pillow \
  --with numpy --with onnxruntime \
  python scripts/nsfw_onnx_parity.py \
  testdata/nsfw/samples/*.jpg
```

每张图的 Top label 应一致，最大 logit 差异不超过 `1e-4`。任何一张失败，都先不要
切换 NAS 后端；保存命令输出并查明原因。parity 脚本直接读取本地图片文件，不需要
清单里的 ID。

### 阶段 3：ONNX / NAS 对比

把 ONNX 模型复制到 NAS 的 `models/nsfw/mini-onnx/model.onnx`，设置
`NSFW_INFERENCE_BACKEND=onnx`，复用同一目录和同一清单：

```bash
NSFW_BENCHMARK_PHASE=phase-2-onnx \
docker compose -f compose.nsfw-benchmark.yaml \
  run --rm nsfw-benchmark
```

对比 PyTorch 与 ONNX 报告中的类别建议、Review 数、置信度、P50/P95、串行吞吐量和
峰值内存。ONNX 不保证在 J4125 上更快；若输出异常或资源表现更差，继续使用 PyTorch。

### 阶段 4：NudeNet 融合

保持阶段 3 选定的 Mini 后端，设置：

```dotenv
NSFW_NUDENET_ENABLED=true
NSFW_NUDENET_RUN_MODE=always
NSFW_NUDENET_SCORE_THRESHOLD=0.25
NSFW_BENCHMARK_PHASE=phase-3-nudenet
```

运行：

```bash
docker compose -f compose.nsfw-benchmark.yaml \
  run --rm nsfw-benchmark
```

在 HTML 中逐张检查检测框、部位标签和分数，重点比较非色情裸露、覆盖部位、照片/插画/3D
以及普通负样本。Mini 低置信度时应建议 Review；Mini 判断 Explicit 时 NudeNet 不应把
结果降成 Nudity。

可再单独设置 `NSFW_NUDENET_RUN_MODE=risk_or_review` 运行挑战阶段，检查安全图和
Drawing 图是否被跳过。此模式更省 CPU，但可能漏掉 Mini 判成 Safe/Drawing 的裸露图，
结果应与 `always` 分开保存。

### 阶段 5：可选的 CG 单图集成检查

只有独立模型测试通过后才做这一小步：在 CG 里选一张图片，用详情页的 AI 分级按钮验证
Job、UI 和人工评级保持正常。若要测上传自动触发，再短暂打开
`CG_NSFW_AUTO_CLASSIFY=true`，只上传一张 ComfyUI 图片，确认完成后立即关闭。这里不需要
重传整个测试集，也不需要手工维护 ID 清单。

## 4. 可视化报告怎么看

HTML 报告包括：

- 成功/失败数量、模型加载时间、首张成功推理时间、分类耗时 P50/P95/P99、预热 P95 和 RSS 峰值。
- 真实标签 × 模型建议的混淆矩阵。
- 每类 Precision、Recall、总体准确率和 Review 比例。
- 可搜索文件名和备注，并按人工标签、模型建议或复核状态过滤。
- 单图缩略图；展开后显示全部类别分数和 NudeNet 检测框。

图片预览被嵌入 HTML，所以报告可能较大且包含测试图片内容。不要通过公共网站托管或
上传报告。准确率只对有人工标签且推理成功的图片计算；失败任务单独看，Review 比例为
完成分类中建议 `review` 的数量占比。

样本只有 100–200 张时，P99 受单张偶发延迟影响很大，只作观察值；主要用 P50/P95 和
连续运行期间的 NAS 资源表现判断是否可用。

## 5. J4125 CPU、内存记录

独立 benchmark 会记录推理进程 RSS 和单张推理时间；Docker 资源限制会独立限制
`nsfw-benchmark` 容器。要采集容器 CPU/RAM，在 NAS 开两个 SSH 终端：一个运行 benchmark，
另一个运行：

```bash
docker stats
```

在 `docker stats` 中找到项目名前缀为 `nsfw-local-benchmark` 的一次性容器，记录模型加载、
批量推理和报告生成期间的内存/CPU。benchmark 结束后容器会退出，按 `Ctrl-C` 停止
`docker stats`。`network_mode: none` 的容器不连接 CG，也无法访问 NAS 网络服务。

| 配置 | 模型加载秒数 | 首张推理 ms | P50 ms | P95 ms | 张/分钟 | RSS 峰值 MB | Docker 峰值 MB | CPU 峰值 | 结果 / 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PyTorch Mini |  |  |  |  |  |  |  |  |  |
| ONNX Mini |  |  |  |  |  |  |  |  |  |
| Mini + NudeNet |  |  |  |  |  |  |  |  |  |

初始参考目标是容器不超过 `1536M`、连续运行无 OOM、J4125 上每张 P95 尽量低于 2 秒。
这些是待实测的工程目标，不是已确认结果。独立 benchmark 测量直接推理和批处理，不包含
CG 队列、API 或上传传输延迟；要测 CG 集成体验，使用阶段 5 的单图检查。

## 6. 结果归档

每个阶段保留自己的 JSON 和 HTML。建议再记下：测试日期、Git revision、Mini commit SHA、
ONNX/NudeNet 版本、CPU 线程、阈值和运行设备。这样以后更改模型或规则时可用同一套私有
图片集复测。

测试图片、实际 `manifest.local.json`、JSON 结果和 HTML 报告都属于本地私有数据，请勿
提交到仓库。
