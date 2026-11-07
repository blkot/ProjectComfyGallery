# 查看器手势与状态修复

本轮对应用户反馈的五项问题，仅修改 `mobile/`，不修改后端或 Web。以下内容覆盖 [UX 第二轮](UX-ITERATION-2.md) 中的分页实现和双击行为。

## 行为

- **同一条拖动只判定一次方向**：初始位移达到 14pt 后，只有横向位移至少是纵向的 1.6 倍才进入横滑；斜向 / 竖向优先锁定为竖向。锁定竖向后，即使后半段手指横移也不翻页。横向起手但最终明显上划时也不提交翻页。
- **跟手但一次最多一页**：用三页 SwiftUI film strip 替换独立横向 ScrollView 与上划手势的竞争。拖动位移最多一个容器宽度；预测终点只决定是否翻页，不用于计算跨几页。吸附动画结束后再一次性提交媒体 ID；等待服务端确认时不接受新的翻页或修改。
- **阈值集中配置**：`Features/Viewer/ViewerPagingPolicy.swift`。慢滑需达到 `max(64pt, width × 0.24)`；快甩需实际横移至少 40pt、同向预测位移达到屏宽 55%。上划详情 65pt，下划关闭 130pt。当前是代码参数，尚未增加用户设置界面。保留 Reduce Motion 和辅助功能的上一项 / 下一项入口。
- **成功静默、布局固定**：收藏、取消收藏、分级成功只更新控件状态，不再出现底部通知。失败和相册下载状态保留为工具栏上方 overlay，不参与 safe-area 高度计算，不改变媒体可用高度。
- **双击图片收藏 / 取消收藏**：复用底栏同一写入入口；切换中、已有写入或相册保存中不接受第二个操作。视频封面不触发图片双击收藏。双指放大 / 缩小及放大后拖动仍保留；不再双击放大。
- **移出范围立即同步**：服务端确认 Trash / 取消收藏 / 分级变更后，图库按当前 scope 立即移除不匹配项目、更新总数 / 已消费 offset / 选择 / 返回锚点，并使变更前的请求失效。当前全屏媒体仍保留直到用户主动离开，不自动跳页。之后查看器只按服务器 navigation 的“前一项 / 当前 / 后一项”重建页面，不保留已失效的历史页面。
- **不改变 Usage 语义**：词库的 Usage API 本来就包含 Trash；不能把普通图库的 Trash 排除规则套到词库。包含废纸篓 / 仅废纸篓范围也按各自 scope 处理。

## 诊断依据

将原来的页面追加逻辑原样提取为生产使用的 `ViewerPageWindow`，先执行：

```sh
zsh mobile/scripts/check-viewer-regressions.sh
```

修复前稳定失败：

```text
FAIL: trash B, seek C: expected [a, c], rendered ["a", "b", "c"]; stale B blocks reverse seek
```

原逻辑只插入新邻居、从不移除旧页面：B 被 Trash 后，C 的服务器前邻居已经是 A，而本地画面前一格仍是 B，访问 B 的范围校验失败后又回弹到 C。修复改为以服务器邻居 ID 重建有界页面窗口。

图库原先只替换 item 并等关闭后刷新，本轮在确认响应时同步投影，并用请求代次防止旧刷新 / 分页响应重新插回旧媒体。通知原先直接插入底部 `safeAreaInset`，因此改变图片高度；本轮移除成功通知并把剩余状态移到 overlay。

## 验证结果与边界

- `check-viewer-regressions.sh`：**1,030 项检查通过**，其中 30 项针对状态 / 阈值的断言，1,000 组确定性的双向快速甩动轨迹。运行的是 App 实际使用的 `ViewerPagingPolicy`、`ViewerPageWindow`、`LibraryMutationProjection` 与 scope / DTO 源码，不是复制一份测试算法。
- `check-gallery-contracts.sh`：原有 **43 项通过**。
- 全部 App / XCTest Swift 语法解析、工程重新生成、`git diff --check` 通过。
- 非宏的策略 / 投影 / DTO、`MediaActionBar` 与 `ViewerStatusOverlay` iOS 17 / Swift 6 类型检查通过。
- 新增 `ViewerMutationRegressionTests.swift` **6 项 XCTest**：删除后前后浏览、即时图库移除及 offset / 锚点、晚到旧刷新、Usage 保留 Trash、失败不移除、收藏与分级状态。首次因环境限制未运行；权限调整后的结果见下节。
- 首次访问模拟器和类型检查带宏的 SwiftUI / Observation 代码失败：`CoreSimulatorService connection invalid`、`sandbox-exec: sandbox_apply: Operation not permitted`。这是当时的执行权限限制，不是已确认的 App 编译错误。

### 2026-11-08：权限调整后的实际构建与无线安装

- 用户将权限改为 **Approve for me** 后，通过授权的 Xcode / CoreDevice 调用完成验证，无需改变签名身份或设备信任配置。
- 真机 Debug 完整构建成功，`codesign --verify --deep --strict` 通过。使用工程已有的本地开发团队配置，未新增或提交凭据。
- iOS 18.5 模拟器执行 `GalleryFeatureTests` 14 项及 `ViewerMutationRegressionTests` 6 项：**20 项全部通过、0 失败**。这不是 UI 手势自动化测试。
- 首次测试发现两个测试 target 缺少 Info.plist 配置，已在 `project.yml` 为其启用 `GENERATE_INFOPLIST_FILE` 并重新生成工程。旧分页测试的两条记录会被初次 reload 一次性读完，导致等待下一页的测试挂起；模拟数据改为真实的 48 条首屏及重叠第二页，并验证第二页确实可加载，未为测试修改生产分页算法。
- CoreDevice 确认连接为 `localNetwork`，设备已配对且开发者模式开启。通过 Wi-Fi 更新安装到 **iPhone 15 Pro Max / iOS 18.7.2**，随后启动 `com.comfygallery.mobile` 成功；未卸载 App、未清除应用数据。
- 已获取并检查真机 **1290 × 2796** 启动画面，确认图库和缩略图正常显示。截图仅保存在本机临时目录，不加入仓库。
- **仍需手动验收**：下列真实触摸方向仲裁、吸附动画、双击收藏和布局稳定性。构建、状态回归及启动截图不能替代这部分验收。未修改后端 / Web，也未提交或发布仓库变更。

## 真机验收

1. 从 A/B/C 中打开 B：缓慢斜上划、竖向起手再向左偏移，应只开详情 / 保持当前，不翻页。
2. 左右快速甩动、拖动超过一屏、拖回不足阈值后松开；每次至多一张，短拖回弹。等待吸附和网络确认后再开始下一次。
3. 连续收藏 / 取消 / N-R 切换，图片上下边界不动；双击图片切换心形而不改变缩放比例；双指缩放仍可用。
4. 正常图库 Trash B → 滑到 C → 向前应是 A，不再出现 B 或弹回 C；立即关闭图库应无 B。断网后再关闭，也不应把已确认删除的 B 重新显示。
5. 验证末张 / 唯一一张、Favorite-only 中取消收藏、SFW 范围改 NSFW、废纸篓中恢复、词库 Usage 中 Trash；各自遵循范围而不自动跳项。
6. iPhone / iPad、横竖屏、视频控制条、VoiceOver、减少动态效果与大字体。合成轨迹测试不等同系统手势仲裁或视觉验收。
