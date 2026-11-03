# GLORIA Prompt Archive 设计分析（初步）

**状态：** 参考分析，用于前端重构的视觉与交互取舍
**对象：** <https://seasnakes.github.io/gloria-prompt-archive/>
**源码：** <https://github.com/seasnakes/gloria-prompt-archive>（分析快照 `629c039`，2026-10-31）
**分析时间：** 2026-11-04
**方法：** 阅读站点源码与线上构建产物，并在 1440×900 桌面（横屏 / 竖屏作品）和 430×932 移动视口下截取详情页。未做真实点赞、手势与动效体感测试。

本文只记录设计判断，不复制其实现代码，也不建议整站照搬。

## 1. 产品结构

单页两段式，没有独立路由页面：

1. **Hero**：品牌、诗、进入按钮、海洋流体背景；
2. **Archive**：搜索、筛选、排序、瀑布流卡片、加载更多；
3. Footer。

内容模型是核心：每条 work 要么是 **prompt**（作者给出了原始提示词），要么是 **reference**（只有效果参考、没有原始提示词）。模型、生成方式、来源未确认时标「待确认」，作者未复现时标「待测试」。这种“不假装知道”的标注贯穿列表与详情。

站点同时为 agent 提供 `llms.txt`、`prompts.json`、单作品 Markdown 和 MCP/Skill。**数据是结构化的，网页只是其中一种视图**——这一点和我们的 media/workflow 证据模型很接近。

## 2. 视觉语言

### 2.1 色彩与主题

- 深色是默认：深海蓝背景（`#060b15` / `#051637` 一带），玻璃面板，冷蓝强调色 `#91bbff`。
- 语义 token 数量很少：`--surface`、`--raised`、`--ink`、`--muted`、`--line`、`--accent`、`--chip`、`--shadow`，再叠加一层 glass token（`--glass`、`--glass-nav`、`--glass-line`、`--glass-ink`、`--glass-muted`、`--glass-control`）。
- 通过 `data-theme="light"` 整体换一套 token；深浅两套不是两套样式表。
- 强调色只用于交互态、选中态与少量标签，不用于大面积装饰。

### 2.2 字体

- 展示标题/作品标题用**宋体**（Songti SC / Noto Serif CJK），字距偏大（0.07–0.2em），形成“画册/展览”气质。
- 品牌用 Georgia；大标题另有自定义字体 `Gloria Title`。
- 正文、控件、数字用系统无衬线；位置计数用等宽感呈现（`07 / 8962`）。
- 中文标题 + 英文提示词混排时，靠字号与字重区分层级，而不是靠颜色。

### 2.3 材质：液态玻璃

- 卡片是多层壳体：半透明底 + 1px 亮边 + 内阴影高光 + `backdrop-filter: blur(16px) saturate(145%)`，再叠加一层渐变高光。
- 桌面精细指针下再加 **3D 倾斜（±7°）与光斑跟随**；通过 SVG `feTurbulence + feDisplacementMap` 给玻璃边缘做折射。
- 这些效果只在 `hover:hover and pointer:fine and prefers-reduced-motion:no-preference` 下启用，并只对进入视口的卡片生效。
- Hero 的海洋是 Three.js 流体 canvas；进入 Archive 后同一背景被降饱和、降亮度，避免干扰阅读。

### 2.4 形态与节奏

- 大圆角：卡片 21–25px，按钮/胶囊 13–24px，详情 23px。
- 图片 `object-fit: contain`，不裁切作品构图；卡片比例来自作品真实宽高（`--ratio: width/height`）。
- 瀑布流 4 列（≥1100px）/ 3 列（≥780px）/ 2 列；列距 16px，窄屏 12px。
- 卡片 hover 只抬升、不缩放图片（早期版本有 scale，后来移除，避免作品被裁切）。

## 3. Archive 卡片

结构（自上而下）：

1. 玻璃壳（7px padding）；
2. 媒体区：真实比例，封面懒加载；无封面时显示标题占位 + 骨架线；
3. 信息区：两行标题、单行摘要（原始提示词或效果描述）；
4. 悬浮控件：左上 like（心形+计数）、右上 copy（复制提示词或作品链接）；
5. 生成封面时另有角标。

值得注意的取舍：

- **角标很少**：没有“已解析/Warning/评分”等状态堆叠，画面干净；状态信息留在详情与筛选里。
- **复制与打开分离**：copy 按钮独立，点击不会打开详情。
- **图片不裁切**：宁可留白，也保留构图；用 `--ratio` 先占位，避免加载抖动。
- **性能有代价**：玻璃 + blur 对大量卡片很重，因此用 IntersectionObserver 控制 `glass-visible`、MutationObserver 管理新增卡片、rAF 节流指针、reduced-motion 直接降级；不支持的浏览器回退为实色。

## 4. 独立的卡片详情（重点）

### 4.1 形态：`<dialog>` 覆盖层，不是独立路由

- 使用原生 `<dialog>` + `showModal()`，进入 top layer。
- URL 仍可深链：`#work/{id}`；打开时 `history.pushState`，关闭时若来自详情则 `history.back()`，否则 replace 回 `#archive`。
- 监听 `popstate`，浏览器前进/后退能正确开合。
- 关闭后焦点回到打开前的元素（`lastFocus.focus({preventScroll:true})`）。
- `body:has(dialog[open]) { overflow:hidden }` 锁滚动。
- Toast 在详情打开时被 **append 进 dialog** 并用 popover 显示——因为 top layer 无法用 z-index 覆盖。

**为什么用覆盖层**：保留画廊上下文与滚动位置，开合快，桌面/移动同一套结构。
**代价**：SEO 无、历史/焦点/滚动都要手写、媒体尺寸要 JS 计算、长内容只能在层内滚动。

### 4.2 尺寸与响应式

- 基础宽度 `min(1160px, 94vw)`，高度 `92dvh`；顶部 toolbar 57px，sticky。
- 打开时根据作品宽高计算三个 CSS 变量：`--dialog-width`、`--media-width`、`--video-ratio`，并设置 `data-orientation`。
- 竖屏作品（ratio < 0.85）且桌面 ≥780px：两列布局，媒体列 ≤420px，信息列独立滚动（`max-height: calc(92dvh - 57px)`）。
- 横屏作品：单列，媒体全宽在上、信息在下，整个 dialog 滚动；第一屏几乎被媒体占满。
- 移动：单列，媒体高 ≤52svh，信息跟随滚动；dialog 96vw / 94svh。
- 视频 `aspect-ratio: var(--video-ratio)` 先占位，等 `loadedmetadata` 再修正，避免 CLS。

### 4.3 顶部与媒体区

- 左：`07 / 8962` 位置（模态内当前筛选结果集，不是全库）。
- 右：“左右滑动切换”提示 + 圆形关闭。
- 媒体：原生 `<video controls playsinline preload="metadata">`，poster 用封面；点击 surface 播放/暂停。
- 图片作品支持多图：`1 / N` 上一张/下一张，按钮在媒体下方。
- 视频加载失败：错误文案 + “重新加载”；重试时会重新拉取 catalog 以刷新会过期的媒体链接。
- 关闭时移除 `src` 并 `load()`，避免后台继续播放。

### 4.4 信息列顺序

1. 类型标签：**有提示词** / **效果参考**；
2. 标题（宋体，28px，可换行）；
3. 作者 · 来源；
4. 标签 chips；
5. 三列事实：模型 / 生成方式 / 模型版本（未确认就写“未确认”）；
6. **提示词**：标题 + 右侧“复制提示词”按钮，正文 `pre-wrap`、行高 1.9、可选中；
7. 负面提示词（有才显示，带复制）；
8. 视频信息与参数 `<details>`（尺寸、时长、参数文本）；
9. 来源证据图（可选，多图外链）；
10. 操作：查看原始来源 / 复制作品链接。

效果参考类作品没有 prompt：标题改为「效果说明」，复制按钮隐藏，正文说明效果与用法，不伪造提示词。

### 4.5 交互细节

| 行为 | 实现 |
| --- | --- |
| 关闭 | X / Esc（拦截 `cancel` 后自行关闭）/ 点击 dialog 外的 backdrop（用 `getBoundingClientRect` 判断，因为点击 backdrop 的 target 仍是 dialog） |
| 上一条 / 下一条 | ← → 键；手机上左右 swipe；trackpad 横向 wheel |
| 手势阈值 | 水平位移 ≥60px、横向占优 1.6 倍、时长 <1.6s；忽略按钮/链接/输入/视频底部 64px 控制条 |
| 滚轮切换 | 横向累计 ≥80px 才触发，280ms 锁，防止惯性连跳 |
| 切换动画 | 旧内容 180ms 退出（rotateY 9° + 位移 + 缩放），新内容 360ms 进入；媒体与信息列 35ms 错峰 |
| 动效降级 | `prefers-reduced-motion` 或页面隐藏时直接换内容 |
| 加载 | 打开时 dialog 与信息列滚动位置归零；视频只预载 metadata |
| 复制失败 | 回退到手动复制弹层 |

### 4.6 可访问性

- `dialog` 有 `aria-labelledby`，工具栏按钮有明确 `aria-label`。
- 焦点归还、键盘切换、`focus-visible` 描边、skip link。
- 点赞按钮有 `aria-pressed` / `aria-busy`；结果计数与 toast 是 live region。
- 语言切换会持久化并 reload，保证整页只按一种语言渲染。
- 动效全部尊重 reduced-motion。

## 5. 列表与筛选交互

- **搜索**：250ms debounce；NFKC 归一化 + 小写 + 多词 AND；覆盖标题、提示词、描述、作者、模型、标签、英文别名。
- **筛选**：收录类型 tabs + 来源/模型/方式下拉 + 风格标签，全部收进独立 filter dialog（各视口一致）；采用“草稿 → 应用/重置”，避免每次点选都重排。
- **筛选摘要**：结果数、已选条件、清除按钮；触发按钮带数量 badge。
- **排序**：默认“最受欢迎”（点赞排名，4s 超时回退最新），可切“最近收录”；listbox 支持方向键。
- **加载更多**：每批 24 条，按钮 + 350px 预取 sentinel，避免无限滚动失控。
- **sticky filter**：滚动到顶部后固定；向下滚隐藏、向上滚出现（阈值 32px / 12px）；输入聚焦时不隐藏；ResizeObserver 维持占位高度。
- **状态**：catalog 加载失败可重试；空结果有“查看全部”；封面失败显示占位与“打开看视频”。

## 6. 性能与工程取舍

- 瀑布流用绝对定位 + `ResizeObserver` + rAF 重排，而不是 CSS columns，避免列内重排与动画冲突。
- 封面自定义懒加载（IntersectionObserver），加载完成淡入。
- 玻璃效果只对可视卡片启用；Three.js 背景异步 import，失败则回退纯色。
- 页面首屏等点赞排名最多 4s，失败自动回退“最新”，不让排序阻塞内容。
- 详情内所有媒体尺寸在打开时一次算好，避免逐帧布局。

## 7. 对 ComfyGallery 的启示

### 7.1 值得借鉴

1. **详情的位置感**：`当前 / 总数` + 键盘/手势切换，浏览连续性强。
2. **媒体按作品比例**：详情不用固定 2:3 stage，避免裁切构图；用 CSS 变量先占位。
3. **信息层级**：类型 → 标题 → 作者/来源 → 事实 → prompt → negative → 参数 → 证据 → 操作，比我们当前 inspector 更“先读内容、后读技术”。
4. **复制动作就近**：prompt 区右上角复制，与打开/选择解耦。
5. **“有提示词 / 效果参考”**：缺失信息明确成一种类型，而不是空白。
6. **少角标**：卡片只保留 like/copy/生成标记，状态移到详情与筛选。
7. **筛选草稿 + 应用**：移动端不会边点边抖。

### 7.2 不建议照搬

1. **整页 Three.js 海洋**：我们运行在 NAS/局域网浏览器，收益低、成本高。
2. **大面积 backdrop-filter**：低端设备/远程桌面上会掉帧；可以作为少量层级的高光，不做全局材质。
3. **覆盖层替代详情路由**：我们已有 `/library/:mediaId`、返回锚点、`panel=evaluation` 等 URL 契约；直接改成 dialog 会破坏这些契约。可借鉴其**节奏**，而不是换路由模型。
4. **无限滚动**：我们保持服务端分页与 48 条/页的确定性。
5. **横屏单列详情**：长 prompt 时第一屏被媒体占满；我们的证据优先场景更适合固定工作表（左媒体、右 inspector）。

### 7.3 可落地的候选

- 详情顶部加 `n / total` 与 ← → 切换（已有键盘逻辑，可扩展到详情）。
- 媒体 stage 使用记录的真实宽高比，而不是固定框。
- inspector 顶部先放“类型/标题/来源”，技术证据折叠在后。
- prompt 区增加就地复制与来源链接；negative 默认折叠。
- 卡片角标进一步收敛（我们刚完成 warning/WF 移除与单字母分级，方向一致）。
- 移动端筛选改为草稿式面板（如果后续做窄屏）。

## 8. 待确认

- 是否引入“覆盖层快速预览”，与现有详情路由并存？
- 玻璃质感是否值得引入，预算多少帧？
- 是否支持 trackpad 横向手势切换，还是只保留键盘？
- 详情信息顺序是否按“内容优先”重排，还是维持“证据优先”？

## 9. 代码索引（外部仓库）

- 详情逻辑：`src/main.js`（`openWork` / `closeWork` / `moveWork` / `readHash` / toast / 键盘）
- 尺寸计算：`src/video-layout.js`
- 手势：`src/work-swipe.js`
- 卡片倾斜与详情转场：`src/glass-motion.js`
- 视觉：`src/style.css`、`src/liquid-glass.css`、`src/compact-ui.css`
- 详情结构：`index.html` 的 `#work-dialog`
- 搜索/筛选：`src/catalog.js`、`src/compact-filters.js`、`src/sticky-filters.js`
