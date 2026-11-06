# iOS 图库体验优化 · 第二轮

2026-11-07。状态：已写入原生代码及获授权的最小后端扩展，尚未完成模拟器 / 真机验收。本文覆盖 V1 原型中的导航、筛选和查看器设计；`index.html` 保留为历史设计稿，没有同步本轮界面，不能作为运行截图。

## 当前交互

1. **图库 / 词库 / 搜索** 三个 Tab。保持默认宽:高 **3:4** 竖向网格、2pt 间距；图库按日期分组，词库 Usage 按服务端 Character LoRA 分组顺序展示。打开 / 关闭媒体详情保留媒体 ID 锚点。
2. **跟手分页滑动（interactive paging）与 snap**：水平 `ScrollView` + `LazyHStack`，每页使用容器宽度，原生 `.paging` 吸附。图片放大后暂停翻页手势；视频只在活动页持有播放器。快速切换采用请求代次保护，目标页面未确认前禁用修改操作。
3. **相邻预加载**：仅当前项与前后各一项保持重资源请求窗口；图片下载原件后按显示尺寸降采样，最长边上限 2,560px，图片内存缓存上限 96MiB。相邻视频仅在已知大小不超过 32MiB 时预载播放资源，否则只加载封面；选中视频后才正常加载播放内容。离开窗口取消无关请求。
4. **四组底部操作**：收藏、N / R 内容分级（SFW / NSFW）、保存到系统相册、废纸篓 / 恢复。保留服务端失败提示，不自动跳到下一项；移出当前筛选时继续显示当前媒体并标记。保存请求 Photos **add-only** 权限，下载 `/original` 后写入相册，不保存缩略图代替原件，不请求读取用户相册。权限拒绝提供设置入口，写入失败保留错误说明。
5. **上划详情**：系统中 / 大尺寸 sheet，显示文件日期、文件名、类型、分辨率、时长、大小，以及可信 `display_fields` 中的 Prompt ID、Character LoRA、LoRA 列表。Prompt 正文只从 Prompt Registry 读取；Prompt ID 可进入对应 Usage，关闭后返回原媒体。信息按钮提供非手势入口；下划关闭查看器。
6. **左侧覆盖式 Drawer**：左边缘右划或侧栏图标打开，点击遮罩 / 关闭 / 左划收起。只包含 Media Type、Favorite、Content Safety、Character LoRA 四类，前三类用图标选项，角色用可搜索勾选列表。修改立即生效并清空旧选择 / 过期结果；不再显示顶部媒体类型分段和筛选摘要。废纸篓入口保留在更多菜单用于恢复，不是第五类 Drawer 筛选。
7. **词库**：Prompt Direct lookup，或 Source + 数字 Index（保留前导零）；支持 Source 建议和 Character LoRA 筛选。没有 Heatmap / 注册写入功能。未注册 Prompt 定义仍可浏览 Usage。网格、查看器、上划详情和四组操作均复用图库组件。

## 路由与范围

| 入口 | 查询契约 | 范围约束 |
| --- | --- | --- |
| 图库列表 / 翻页 | `GET /api/v1/media`，`GET /api/v1/media/{id}/navigation` | 使用同一 `GalleryScope`；类型、收藏、分级、精确 `character_lora`、搜索及废纸篓范围一致 |
| 角色候选 | `GET /api/v1/prompt-registry/character-loras?q=...&limit=200` | 可搜索，超过 200 项提示继续输入名称；不以通用模型引用代替角色声明 |
| Source 建议 | `GET /api/v1/prompt-registry/sources?q=...&limit=50` | 建议失败仍可手动输入 |
| 词库定义 / Usage | `GET /api/v1/prompt-registry/lookup?prompt_id=...&character_lora=...&group_by_character=true` | 48 项分页，保留服务端分组 / 项目排序；零填充 Index 不转成客户端整数 |
| Usage 前后导航 | `GET /api/v1/prompt-registry/usage/navigation?prompt_id=...&character_lora=...&media_id=...` | 使用 Prompt Usage 范围，**不偷偷继承图库的收藏 / 分级 / 废纸篓排除规则** |
| 上划详情 | `GET /api/v1/media/{id}/workflow?node_limit=1&edge_limit=1` + Registry lookup | 只取可信展示字段与注册提示词；不把嵌入提示词当成词库定义 |
| 内容分级 | `PUT /api/v1/media/{id}/content-rating` | `content_rating: sfw / nsfw`，不是评价分数 |
| 保存原件 | `GET /api/v1/media/{id}/original` + Photos | 原始格式不受 Photos 支持时明确失败，不降级为缩略图成功 |

### 新后端能力与兼容性

用户明确授权扩展图库列表及导航接口。新增 `character_lora` 参数（最长 512 字符），对已有 `MediaPromptIndex.character_lora` 按去除首尾空白、大小写不敏感的完整值匹配，采用相关 `EXISTS`，不产生重复媒体。不进行通用 LoRA 引用匹配、子串匹配或无依据的角色推断。

列表响应增加可空 `character_lora` 回显（保留请求大小写，去除首尾空白）。App 在选中角色时验证回显；旧服务器忽略未知查询参数且缺少回显时，明确提示升级后端，拒绝展示未筛选结果。列表和导航复用同一过滤函数；未传角色参数的客户端行为保持不变。

本轮没有新迁移，使用已有 `0021_prompt_index_character_lora`；已有数据库需已完成该迁移及历史索引回填。该列表筛选不在请求时扫描工作流兜底。**未部署后端**，旧服务在升级前不能使用图库的新增精确角色筛选。未改 Web / XR / Quest UI。

## 实现依据

遵循 SwiftUI Pro 的状态隔离、系统导航与可访问性原则；检查 ShipSwift 目录后，本轮使用系统分页、sheet、Photos 和 SF Symbols，没有引入额外组件依赖。原生分页依据 Apple 的 [scrollTargetBehavior](https://developer.apple.com/documentation/swiftui/view/scrolltargetbehavior(_:))，相册写入采用 Photos 变更请求。

## 已验证与未验证

| 检查 | 本轮结果 |
| --- | --- |
| `zsh mobile/scripts/check-gallery-contracts.sh` | **43 项通过**：实际模型 / Endpoint / 分组 / 预加载策略源码编译并运行，含精确角色、Usage 路由、前导零、内容分级、混合 LoRA 元组、缓存窗口与视频大小限制 |
| 后端四组针对性回归 | **43 项通过**：`test_media_library.py`、`test_prompt_usage_navigation.py`、`test_prompt_registry.py`、`test_registry_contracts.py`；含角色大小写 / 空白、子串排除、组合筛选、分页与导航一致性 |
| API Ruff 与 OpenAPI | Ruff 检查通过，OpenAPI 从当前源码重新生成 |
| iOS 非宏核心源码 Swift 6 typecheck | **通过**：真实 API / 鉴权 / 模型 / 图片解码 / 媒体缓存 / 预加载策略 / Photos 权限与写入 helper；不包含依赖宏的 SwiftUI 视图或 Observable feature |
| App / XCTest Swift 语法解析、Info.plist、工程生成、diff whitespace | 通过；语法检查不等于 App 完整构建 |
| 原生 XCTest | `GalleryFeatureTests.swift` 已写入 **14 项**，**未运行** |
| 完整 `xcodebuild` / 模拟器 | **环境阻塞**：`sandbox-exec: sandbox_apply: Operation not permitted`，宏插件无法启动，CoreSimulatorService 连接被拒绝；没有真实运行截图 |
| Photos 保存、跟手手势、真实服务端、iPhone / iPad 视觉验收 | **未验证**，不可据上述静态 / 契约检查宣称已通过 |

构建诊断日志：`/tmp/comfy-gallery-ux-build.log`。代码保留在本地工作区，没有提交、推送或部署。

## 下一步设备验收清单

- 在可运行 Xcode 的环境生成工程，执行 `GalleryFeatureTests`，再在专用测试图库操作；不对生产媒体做破坏性测试。
- 连续左右拖动、半程取消、快速反向与跨 48 项边界；核对吸附、位置、返回网格锚点，检查图片放大不误翻页、视频离开不继续播放。
- 组合四类 Drawer 筛选，快速切换角色，确认旧请求不回填；用含同名普通 LoRA 但不同 Character 声明的媒体验证精确过滤。
- 收藏 / 分级 / 废纸篓操作不跳项，错误不伪装成功；同一媒体从词库入口可见收藏与 Trash 等状态，但不被图库筛选误排除。
- 相册首次授权、拒绝后设置恢复、图片 / 视频保存、失败格式、磁盘空间不足；核对保存的是原始媒体。
- 上划详情 → Prompt ID → Usage → 媒体 → 返回，核对各层原位置与视频暂停；验证未注册 ID、Source 建议失败和带前导零 Index。
- iPhone 紧凑宽度 / iPad、横竖屏、最大字体、VoiceOver、减少动态效果；断网与鉴权过期；观察连续浏览的缓存 / 内存峰值。
