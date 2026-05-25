---
name: mrcarlsama-social-transcriber
description: 当用户提供一条抖音或小红书链接，并希望下载公开内容、本地转写视频、校验产物、保存标题正文和互动数据、必要时用模型润色逐字稿时使用。仅支持单条链接，不支持作者批量抓取、搜索、评论内容采集、私密内容、付费内容或自动读取浏览器 Cookie。
---

# mrcarlsama 社交内容转写

当用户给出一条抖音或小红书链接，并要求生成逐字稿、字幕、词级时间戳、润色后的可读稿，或保存图文笔记正文与图片时，使用这个 Skill。

## 适用范围

支持：

- `douyin.com/video/...`
- `v.douyin.com/...`
- `xiaohongshu.com/...`
- `xhslink.com/...`
- 每次只处理一条链接
- 视频内容使用 `faster-whisper` 做本地 ASR
- 保存平台返回的标题、正文/描述、作者、发布时间、点赞数、评论数、收藏数、分享数、播放数等可用元数据
- 通过 `uv` 脚本依赖自动准备 `yt-dlp`、`faster-whisper`、`imageio-ffmpeg`、`playwright`
- Skill 目录自包含；不要依赖仓库根目录的 `pyproject.toml`
- provider 两级访问：裸跑 `python -m yt_dlp` 失败且提示 fresh cookies 时，生成公开访客态 cookie 后重试

不支持：

- 作者主页批量下载
- 搜索
- 评论内容采集
- 私密或付费内容
- 绕过登录或访问限制
- 自动读取浏览器 Cookie

## 执行流程

不要只把命令丢给用户。只要本地条件允许，就直接把任务跑完。

1. 从用户请求中提取一条 URL。如果出现多条不同 URL，要求用户选择一条，或明确说明将逐条处理。
2. 先检查 `uv`：

   ```bash
   uv --version
   ```

   如果缺少 `uv`，按系统安装：

   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows PowerShell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. 执行环境自检和缺失项补齐。默认用户机器只有 `uv`，不要假设已经全局安装 `yt-dlp`、ffmpeg、ASR 依赖或浏览器：

   ```bash
   uv run --script <skill_dir>/scripts/bootstrap.py --ensure
   uv run --script <skill_dir>/scripts/preflight.py --check
   ```

4. 执行单链接任务：

   ```bash
   uv run --script <skill_dir>/scripts/run_one.py "<URL>"
   ```

5. 视频内容校验以下输出文件存在且非空：

   - `【标题】原视频.<ext>`
   - `【标题】原音频.wav`
   - `【标题】正文.md`，仅在平台返回正文/描述时生成
   - `【标题】原始逐字稿.md`
   - `【标题】原始逐字稿.txt`
   - `【标题】字幕.srt`
   - `_meta/words.json`
   - `_meta/manifest.json`
   - `_meta/report.json`

6. 如果用户要求润色，读取 `【标题】原始逐字稿.md`，直接用模型能力生成 `【标题】逐字稿.md`。不要使用脚本润色。
7. 如果是图文笔记，保存 `【标题】正文.md` 和 `图片/`，不运行 ASR。
8. 最终回复中说明输出目录和主要文件路径。

## 自动试错协议

这个 Skill 的默认目标是“尽最大努力完成单链接任务”，不要在第一层失败处直接结束。

当前已接入的自动试错：

- provider 访问：裸跑 `python -m yt_dlp` -> fresh cookies 时生成公开访客态 cookie -> 用临时 cookie 重试 -> 仍失败才要求用户显式提供 Cookie 文件。
- 环境访问：入口脚本使用 `uv` 内联依赖声明；`yt-dlp` 来自官方项目 `https://github.com/yt-dlp/yt-dlp`，不要求用户全局安装。
- resume：如果输出目录里已有 `【标题】原视频.<ext>`，跳过下载。
- resume：如果已有 `【标题】原音频.wav`，跳过音频抽取。
- resume：如果已有 `【标题】原始逐字稿.md`、`【标题】原始逐字稿.txt`、`【标题】字幕.srt`、`_meta/words.json`，跳过 ASR。
- ASR 降级：从用户指定模型开始，失败或输出为空时按 `large-v3 -> medium -> small -> base -> tiny` 的顺序向下重试。
- 失败报告：仍失败时写入 `outputs/_failed/【日期】[【平台】][【失败原因】]/_meta/report.json`。

尚未接入脚本的 provider fallback 必须保留在 provider 层，不要塞进主流程：

- 抖音：`yt-dlp` 失败后可接 DouK / TikTokDownloader。
- 小红书：`yt-dlp` 失败后可接 XHS-Downloader。
- 图文：视频 ASR 主流程不处理图片下载，图文图片下载应由 xhs provider 输出 `图片/`。

需要完整策略时，读取 `references/auto-retry-policy.md`。

## Cookie 规则

禁止自动读取浏览器 Cookie。Provider 如果报告需要 Cookie，按这个顺序处理：

1. 先裸跑 `python -m yt_dlp`。
2. 如果提示 fresh cookies，生成公开访客态 cookie。这个动作只访问用户给出的公开页面，使用隔离临时浏览器上下文，不读取用户浏览器、不读取账号、不复用登录态。
3. 用这个临时 cookie 重试。
4. 仍失败时，才要求用户显式提供 Cookie 文件，或者手动下载内容后再交给本地处理流程。

只有当用户询问 Cookie，或访问失败信息明确提到 Cookie 时，才读取 `references/cookie-policy.md`。

## 失败处理

如果运行失败，先检查 `_meta/report.json` 和 provider 错误输出。把失败归类为：

- URL 错误
- 平台不支持
- 内容不可用
- 需要新鲜 Cookie
- 没有可下载媒体
- 音频抽取失败
- 本地 ASR 不可用
- ASR 输出为空
- 图文图片地址不可用

如果链接在探测阶段就失败，报告会写到：

```text
outputs/_failed/【日期】[【平台】][【失败原因】]/_meta/report.json
```

需要给用户准确处理建议时，读取 `references/failure-modes.md` 和 `references/auto-retry-policy.md`。

## 输出约定

默认输出目录：

```text
outputs/2026-3-24[douyin][示例视频标题]/
```

目录名规则是 `【日期】[【平台】][【标题】]`。日期优先使用平台返回的发布日期；没有发布日期时使用本地运行日期。

视频顶层文件面向用户，`_meta/` 面向机器复查：

- `【标题】逐字稿.md`：最终润色稿，由模型生成。
- `【标题】原视频.<ext>`：下载的视频。
- `【标题】原音频.wav`：ASR 使用的音频。
- `【标题】正文.md`：平台返回的正文/描述和互动数据，可能不存在。
- `【标题】原始逐字稿.md`：ASR 原始稿，带时间戳。
- `【标题】原始逐字稿.txt`：ASR 原始纯文本。
- `【标题】字幕.srt`：字幕文件。
- `_meta/manifest.json`：任务清单，含标题、正文、互动数据和文件清单。
- `_meta/report.json`：运行报告。
- `_meta/provider-info.json`：下载器原始元数据。
- `_meta/words.json`：词级时间戳。

图文笔记目标输出：

```text
outputs/2026-3-24[xiaohongshu][示例笔记标题]/
  示例笔记标题正文.md
  图片/
    01.jpg
    02.jpg
  _meta/
    manifest.json
    report.json
    provider-info.json
```

运行产物不要写进 Skill 目录。Skill 目录必须保持干净、可复用。
