# NSFW 本地测试集

主要测试流程独立于 CG：图片只需放在本地目录，以文件名和人工标签组成清单；不
需要上传到 CG、不需要数据库，也不需要记录媒体 ID。完整操作见
[`NSFW 图片分级手测指南`](../../doc/development/nsfw-classification-manual-test-zh.md)。

目录约定：

- `samples/`：私有样本图片，只在本地或目标 NAS 保留。
- `manifest.local.json`：本地 benchmark 清单，从
  `manifest.local.example.json` 复制后填写文件名、人工标签和备注。
- `results/`：每阶段的 JSON 数据和可视化 HTML 报告。
- `manifest.example.json`：仅供可选的 CG API 单张集成冒烟脚本使用；普通分级、
  性能和准确率测试不需要它。

所有图片、个人清单和结果文件都被 Git 忽略。提交前请确认没有把它们强制加入
仓库。
