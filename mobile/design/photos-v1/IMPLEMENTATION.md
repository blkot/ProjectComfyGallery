# iOS 相册式核心重构 · 实现记录

> 本文保留第一阶段的历史实现与当时验证结果。后续的相邻预加载、跟手分页、四组操作 / 相册保存、上划详情、Drawer、词库及精确角色后端扩展，请以 [UX 第二轮记录](UX-ITERATION-2.md) 为准；下方旧 Tab / 筛选 / 查看器限制已经被新实现覆盖。

2026-11-07。范围仅 `mobile/`。默认格子为 **宽:高 = 3:4**（portrait 4:3），未新增第三方依赖，仍兼容项目原有 iOS 17 最低版本。

## 已写入原生代码

- 原生 TabView：图库、收藏、搜索；设置改为工具栏 sheet。旧 Review 代码保留，暂不作为主导航入口。
- 默认三列竖向网格，2pt 间距；按当前排序日期分组。大字体缩为两列，iPad 随宽度增加列数。
- 类型切换、收藏 / 未收藏、SFW / NSFW、废纸篓范围和排序；筛选 sheet 用独立草稿，取消不提交。
- 搜索采用服务端 `q`，300ms 防抖；同一 `GalleryScope` 同时用于列表、分页和全屏导航。
- 筛选变更立即失效旧请求并清空旧选择；分页按服务端 offset 前进，按媒体 ID 去重，错误保留已加载内容并提供重试。
- 图片从认证的 `/original` 下载到临时文件后降采样；图库使用 `/preview`。全屏保留原始比例，支持缩放。
- 视频使用认证的 `/playback` 和现有有界本地缓存；仅当前页面创建 AVPlayer，不自动播放声音，离开 / 后台暂停。
- 查看器使用服务端 navigation 验证范围，提供前后按钮、横滑、缩略胶片条、显式隐藏控件和下滑关闭。
- 单项 / 多选收藏、可恢复废纸篓；提交明确媒体 IDs，不把已加载全选扩大成全库。根据 updated / skipped / errors 显示实际结果，并重新读取权威状态。
- 收藏或废纸篓变更不自动跳页；关闭后刷新并定位最后查看 ID，已离开范围时定位邻近剩余项。
- 临时网络失败不强制退出已连接图库；鉴权失败仍要求重新连接。重连更新正确的 Keychain profile，断开连接清理缓存；解码错误不再公开记录响应正文。

采用 SwiftUI Pro 的系统导航、可访问性标签、动态字体和减少动态效果建议。检查了 ShipSwift 组件目录；核心界面使用系统组件，无需引入装饰性组件或新包。

## 已执行的检查

| 检查 | 结果与边界 |
| --- | --- |
| `zsh mobile/scripts/check-gallery-contracts.sh` | **24 项通过**。直接编译实际 Foundation 模型、Endpoint、布局和日期分组源码；检查组合筛选、导航查询、分页、bulk 请求体、兼容解码、时长 / 日期、部分成功文案和 3:4 / 列数。 |
| 所有 App / XCTest Swift 文件 `swiftc -frontend -parse` | **通过**。仅语法解析，不等同完整类型检查或运行。 |
| `git diff --check` | **通过**。 |
| 交互设计稿 DOM 检查 | **12 项通过**：筛选组合、返回焦点、收藏、多选、搜索空态、取消草稿、废纸篓恢复、离线与主题等。未验证浏览器布局像素。 |
| `xcodegen generate` | **通过**，新源码与测试已登记到工程。 |
| 完整模拟器目标 `xcodebuild ... build` | **未通过，环境阻塞**：`sandbox-exec: sandbox_apply: Operation not permitted`，SwiftData / Observation / SwiftUI 宏插件不能启动；CoreSimulatorService 连接亦被拒绝。不能据此宣称代码已完整编译成功。 |
| 原生 XCTest / UI / 真实后端 | **未运行**。10 项新原生回归测试已写入 `GalleryFeatureTests.swift`；需要允许 Xcode 宏插件和模拟器运行的会话。 |

构建尝试的原始日志位于本机 `/tmp/comfy-gallery-photos-build.log`（临时诊断文件，不提交）。未生成模拟器截图，也未以设计图冒充运行截图。

## 在可运行 Xcode 的环境中验收

```sh
cd mobile
xcodegen generate
xcodebuild -project ComfyGalleryMobile.xcodeproj -scheme ComfyGalleryMobile \
  -destination 'platform=iOS Simulator,id=<available-simulator-uuid>' \
  -only-testing:ComfyGalleryMobileTests/GalleryFeatureTests test
```

随后连接专用测试图库，验证：图片完整显示、视频播放 / 暂停、横竖屏、跨分页导航、关闭返回定位、收藏跨 Tab 同步、取消筛选、部分失败、断网 / 重连、大字体与 VoiceOver。批量整理测试应使用可恢复的专用测试媒体，不触碰用户生产媒体。已有 `IntegrationTests` 默认依赖 localhost 服务，执行全套测试前需设置 `TEST_BASE_URL`。

## 本阶段尚未交付

- 模拟器 / 真机完整编译、运行截图及真实后端联调；没有声称已完成这些验证。
- 输入媒体、评价、空间视频生成、详情信息面板；此次先做浏览核心，没有添加不可用按钮。
- 原始图片磁盘离线库、离线写入队列、重启后的滚动位置持久化、iPad 专用侧栏。
- 全屏查看目前是单活动页面切换，不是跟手交互式分页动画；通过显式按钮隐藏控件，避免抢占 AVKit 点击。
- 浏览器设计稿中的离线开关 / 连接状态是演示，不代表原生端已有主动网络监测。原生请求失败会提示，未知写入状态要求刷新确认，不伪造成功。
- 日期分组沿用服务器返回时间的日历日期，不推断拍摄时间。

设计稿内壁纸示例只供本地评审，不在 Xcode 的应用资源路径下，不会被打包进 App。
