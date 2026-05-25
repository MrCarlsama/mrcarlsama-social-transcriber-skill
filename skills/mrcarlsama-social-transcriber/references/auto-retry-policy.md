# 自动试错策略

这个 Skill 使用“单链接任务尽最大努力完成”的策略。

## 完成标准

视频链接完成标准：

- 有 `【标题】原视频.<ext>`。
- 有 `【标题】原音频.wav`。
- 有 `【标题】原始逐字稿.md`。
- 有 `【标题】原始逐字稿.txt`。
- 有 `【标题】字幕.srt`。
- 有 `_meta/words.json`。
- 有 `_meta/manifest.json`。
- 有 `_meta/report.json`。

图文链接完成标准：

- 有 `【标题】正文.md`。
- 如果 provider 返回图片地址，则有 `图片/`。
- 有 `_meta/manifest.json`。
- 有 `_meta/report.json`。
- 不运行 ASR。

## 当前已实现

provider 层：

```text
python -m yt_dlp
  -> fresh cookies 时生成公开访客态 cookie
  -> 用临时 cookie 重试
  -> 仍失败才要求用户显式提供 cookie 文件
```

本地媒体层：

```text
已有原视频 -> 跳过下载
已有原音频 -> 跳过音频抽取
已有逐字稿/字幕/words.json -> 跳过 ASR
```

ASR 层：

```text
large-v3 -> medium -> small -> base -> tiny
```

脚本会从用户指定的模型开始向下重试，不会反向升级到更大的模型。

## 还未接入的 provider fallback

这些 fallback 必须留在 provider 层：

- 抖音：`DouK` 或 `TikTokDownloader`。
- 小红书：`XHS-Downloader`。
- 图文笔记：xhs provider 下载图片并输出 `图片/`。

主流程不能写成 `if 抖音 then ... else 小红书 then ...` 的大分支。主流程只接收 provider 返回的标准结果。

## 失败报告

仍失败时写入：

```text
outputs/_failed/【日期】[【平台】][【失败原因】]/_meta/report.json
```

失败报告必须说明：

- 是否尝试过公开访客态 cookie。
- 是否读取过浏览器账号 Cookie，默认必须是 `false`。
- 下一步是否需要用户显式提供 Cookie 文件。
- 如果已有部分产物，下一次运行可以从哪里 resume。
