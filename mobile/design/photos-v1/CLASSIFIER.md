# iOS Classifier 与人工复核

> 当前 `main`（2026-11-11）对 classifier API 的 iOS 客户端实现。后端仍是权威数据源；此文不表示已将后端部署到 NAS。

## 交互

- 图库左侧 Drawer 提供 Classifier Status（未分类、AI 已建议、待复核、人工已确认、处理中、失败）和 Classifier Rating（Safe、Sexy、Nudity、Explicit、Review）单选筛选。两项都进入 Library 列表和前后导航的同一 `GalleryScope`；组合筛选按服务端 AND 语义执行。
- 只在启用 classifier 筛选时，图片格显示紧凑等级徽标；显示 AI / 人工来源文字，不以颜色作为唯一状态线索。Classifier 筛选仅适用于照片。
- 图片查看器保持四个底部入口：收藏、内容分类、保存原件到相册、废纸篓。内容分类入口打开上划详情中的分类面板，放置在稳定的原生 sheet 中。
- 分类面板同时呈现生效结果、AI 建议、可折叠原始分数 / 区域证据和人工复核。四个人工分级与旧 SFW / NSFW 分栏显示；清除人工分级会恢复模型建议，不会写入旧内容标记。
- 在图库中只对明确选择的图片请求批量 AI 分类。自动分类不由浏览触发；状态 GET 只读、不启动推理。已排队、复用、跳过、失败项分别反馈。
- 更多菜单的“浏览未分类照片”临时进入图片 / 未分类范围并打开首张；“复核待复核照片”通过服务端快照建立有序 ID 队列，默认取 200 张。队列固定顺序保存在应用私有、文件保护的 Application Support 文件中，退出后可继续。快照有截断时显示本轮数量和总匹配量。
- 复核队列使用一套图片查看器分页和相邻预加载；点选人工分级只保存当前图片，不自动翻页。图片即使因复核离开 live “待复核”筛选，仍留在本机固定快照里，可继续前后浏览。到最后一张后，用户显式选择“完成复核”。

## 数据与安全边界

1. `media_safety_review` 人工评级优先于最近一次已完成的 `media_safety_assessment.suggested_rating`。
2. 原 `content_rating`（SFW / NSFW）仍独立可改；Classifier API 不更改它、Trash 或可见性。
3. 仅明确选中的图片可提交批量 AI 分类；视频不提交。默认不强制重跑，服务端可重用活动任务并跳过当前模型配置已完成项。
4. 人工评级 API 目前没有版本号 / ETag 冲突保护；客户端不将失败的评级请求离线静默重放。查看器提供状态重读；失败保持可见并允许用户决定是否重试。
5. 固定复核快照目前由服务端只对 `classifier_status=needs_review` 提供；未分类入口沿用 live Library scope，不伪称固定快照。快照最多按 App 当前请求上限取 200 个 ID；截断时可在完成本轮后重新建立快照。
6. 队列只持久化本机的 media ID、当前位置和来源截断数，不是跨设备同步工作流；文件写入使用 iOS 完整数据保护，不放进 `UserDefaults` / `@AppStorage`。
7. 选中 classifier 筛选后，如分页返回与筛选不符的媒体，客户端报后端兼容错误而不把未过滤结果展示出来。空结果仍按正常空状态处理。

## API 对应

- 列表与详情导航：`classifier_status`、`classifier_rating` query parameters。
- 状态详情：`GET /api/v1/media/{id}/nsfw-classification`。
- 单图 / 明确 ID 批量 AI 分类：`POST /api/v1/media/bulk/nsfw-classification`。
- 人工确认、覆盖和清除：`PUT` / `DELETE /api/v1/media/{id}/classifier-review`。
- 有序人工复核：`GET /api/v1/media/review-queue-snapshot`；请求时固定 `classifier_status=needs_review`、`kind=image`。
- SFW / NSFW 仍使用既有 `/content-rating`。

服务端 classifier API 和 `0024_media_safety_review` 数据库迁移必须存在；若设备所连服务器尚未更新，需先发布兼容后端，再使用相关功能。本次 iOS build / 安装不会改动服务器、数据库或生产媒体。

## 验证

契约及回归脚本：

```sh
zsh mobile/scripts/check-gallery-contracts.sh
zsh mobile/scripts/check-viewer-regressions.sh
```

真机触摸验收还应检查 Drawer 组合筛选、只读状态加载、启用/关闭 AI、人工覆盖与清除、断网后的显式重读、固定快照跨“待复核”过滤离开，以及 iPhone Dynamic Type / VoiceOver。成功编译和状态单测本身不证明真实手势视觉效果。
