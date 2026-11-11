# Xanta Utils custom prompt registry handoff

这份文档交给负责修改 `ComfyUI-Xanta-Utils` 的 agent。目标是在
`XantaPromptLibrary.use_custom_prompt` 打开时，把实际自定义 prompt 注册到
ComfyGallery Prompt Registry，并让保存图片使用 CG 分配的
`custom - 00001` Prompt ID。

ComfyGallery 仓库不包含已安装的 `ComfyUI-Xanta-Utils` 源码。该 agent 需要在
用户实际运行的 Xanta Utils checkout 修改节点，并按本文接口联调。
CG 端点目前位于 `codex/custom-prompt-registry` 实现分支；在该分支发布到 NAS
之前，NAS 上的 API 尚不能处理此请求。

## 现有节点连线

目前 `XantaPromptLibrary` 输出的正向 prompt 与 Prompt ID 分别连接到
`XantaSaveAndUpload` 的 `cg_prompt` 和 `cg_prompt_id`。在自定义模式下，正向
prompt 来自手动文本框，但 Prompt ID 输出仍可能是当前选中的库条目 ID；把
这个旧 ID 当成实际 prompt 的 ID 会让媒体错误地归到原条目。

ComfyGallery 的保存节点显式写入 `comfy_gallery_display_v1`，并以该字段优先
解析媒体 Prompt ID。参考仓库中的
[`xanta_save_display_fields/nodes.patch`](../../integrations/comfyui/xanta_save_display_fields/nodes.patch)
和 [Prompt Registry 设计](../design/prompt-registry.md)。

## 节点改动

### `XantaPromptLibrary`

- 从当前 `use_custom_prompt` widget 状态输出一个布尔值，例如
  `is_custom_prompt`。
- 将该输出追加到现有输出列表末尾，不重排或更改现有输出索引，以保持已保存
  工作流兼容。
- `prompt_id` 输出可以继续表示用户当前选中的基础库条目 ID。custom 模式下，
  它仅是来源线索，不能作为最终 Prompt ID。
- custom 模式输出的 prompt 应与当前送入正向 conditioning 的文本相同。

### `XantaSaveAndUpload`

给现有节点增加可选输入：

| 输入 | 类型 | 用途 |
| --- | --- | --- |
| `cg_prompt_is_custom` | `BOOLEAN` | 连接 `XantaPromptLibrary.is_custom_prompt` |
| `cg_negative_prompt` | `STRING` | 当前实际使用的负向 prompt；没有时可省略 |

继续使用现有 `cg_prompt` 和 `cg_prompt_id`：

- `cg_prompt`：实际送入 prompt conditioning 的正向文本。
- `cg_prompt_id`：普通模式下是有效 Prompt ID；custom 模式下保留为基础库 ID，
  仅用于原始工作流 provenance。
- `cg_prompt_is_custom=false`：保持现有行为，不调用新接口，继续使用
  `cg_prompt_id`。
- `cg_prompt_is_custom=true`：先调用下方 CG 注册接口，再保存图片。将接口返回的
  `prompt_id` 写入 saver 的 `comfy_gallery_display_v1.fields.prompt_id`；将实际
  正向文本写入 `fields.prompt`。不要把基础库 ID 写成媒体的有效 Prompt ID。

如果正负向 prompt 后面还经过文本拼接或处理，请将实际生效的文本接入 saver，
而不是只接 Prompt Library 的原始输出。若自定义开关只替换正向 prompt、负向
prompt 仍沿用库条目，也要把该有效负向文本一并注册。

对同一 saver 执行中的一批图片只需注册一次，再将同一个有效 Prompt ID 写入该批
每张图片的显示字段。

## CG 注册接口

请求使用现有 `config/api_config.json` 中的 Gallery URL 和 Bearer token。不要把
token 写进工作流、PNG metadata、请求日志或节点输出。

```http
POST /api/v1/prompt-registry/custom
Authorization: Bearer <configured-api-token>
Content-Type: application/json
```

```json
{
  "prompt": "portrait, soft studio lighting",
  "negative_prompt": "blurry, low quality",
  "origin": "xanta-utils"
}
```

`negative_prompt` 没有生效内容时传 `null` 或省略。接口固定写入 `custom` source，
由 CG 分配数字索引；客户端不得自行计算或递增索引。首次注册示例响应：

```json
{
  "prompt_id": "custom - 00001",
  "created": true,
  "entry": {
    "id": "018f47f2-3e44-7bdc-99c2-000000000001",
    "source": "custom",
    "index": "00001",
    "prompt": "portrait, soft studio lighting",
    "negative_prompt": "blurry, low quality",
    "metadata": {},
    "origin": "xanta-utils",
    "media_count": 0,
    "created_at": "2026-11-11T00:00:00Z",
    "updated_at": "2026-11-11T00:00:00Z"
  }
}
```

`entry` 其余字段与现有 Prompt Registry entry response 一致。相同正向和负向文本
再次注册时，接口返回同一个 `prompt_id`、`created=false`，不创建重复条目。正向
文本不能为空；文本按收到的内容保存。负向文本为空或全空白时按不存在处理。

## 保存与失败行为

注册成功后，将返回的 `prompt_id` 写入 saver 的显式显示字段，然后按现有
ComfyUI 保存路径写入完整 `PROMPT` / `EXTRA_PNGINFO` 元数据并上传最终文件。原始
工作流继续保留用户选中的基础 Prompt ID、`use_custom_prompt` 状态和自定义文本；
显式显示字段中的 ID 表示这张媒体实际使用的 custom registry entry。

如果注册接口不可用或认证失败：

1. 仍把图像保存到本地。
2. 不要回退到基础库 Prompt ID，也不要以错误 ID 上传到 Gallery。
3. 在节点结果中报告注册失败和本地文件路径，供用户稍后重试。

ComfyUI 的队列执行 UUID（ComfyUI `prompt_id`）与 Prompt Library 的
`source - index` ID 是两套不同标识；新接口只返回后者。

## 手工验收

1. 普通模式运行一次，确认不请求 custom 接口，ID 和原流程不变。
2. 打开自定义开关运行一次，确认 API 返回 `custom - 00001` 一类 ID，Gallery
   Detail 和 Prompt Registry lookup 显示该 ID 及注册的文本。
3. 使用相同正负向文本再次运行，确认复用同一 ID，usage 聚合到同一 Registry
   entry。
4. 修改 prompt 文本后运行，确认获得新 ID，旧记录和旧媒体关系不变。
5. 暂时让 Gallery API 不可达，确认本地图片仍保存、节点显示错误，并且没有错误
   上传或把图片归到基础 Prompt ID。
6. 检查上传 PNG：正常 ComfyUI workflow metadata 保留；显式
   `comfy_gallery_display_v1.fields.prompt_id` 是 CG 返回的 custom ID；工作流仍保留
   基础 Prompt ID 和 custom 开关/文本；没有 Bearer token。
7. 在 CG Prompt Registry 的 source lookup / heatmap 选择 `custom`，确认该 source
   可见，且 prompt ID 可以直接 lookup。
