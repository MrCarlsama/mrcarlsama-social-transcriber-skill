# MrcCarlsama 社交内容转写 Skill

把一条抖音或小红书链接整理成本地内容资产的 Skill，支持 Codex 和 Claude Code。

用户只需要丢一条链接，Skill 会尽量自动完成：

- 下载公开视频。
- 提取音频。
- 本地转写逐字稿。
- 生成字幕和词级时间戳。
- 保存标题、正文/描述、作者、发布时间、点赞数、评论数、收藏数、分享数、播放数等平台能返回的元数据。
- 需要时由 Codex 或 Claude Code 直接用模型能力润色逐字稿。

它不是平台爬虫，也不是批量采集器。当前只处理单条链接。

## 支持链接

- `douyin.com/video/...`
- `v.douyin.com/...`
- `xiaohongshu.com/...`
- `xhslink.com/...`

## 不支持

- 作者主页批量下载
- 搜索视频或笔记
- 评论内容采集
- 私密内容
- 付费内容
- 绕过访问控制
- 自动读取浏览器 Cookie

如果平台要求 Cookie，Skill 会先尝试生成公开访客态 cookie。这个过程只访问公开页面，不读取你的浏览器、不读取账号、不复用登录态。仍失败时，才需要你显式提供 Cookie 文件。

## 环境要求

最低要求：

- 系统：macOS、Windows 10/11 或常见 Linux 发行版。
- 终端：能运行 shell 命令。Windows 使用 PowerShell。
- 网络：第一次运行需要访问 GitHub、PyPI、模型下载源，以及用户提供的抖音/小红书公开页面。
- 磁盘：至少预留 5GB，建议 10GB 以上。视频、音频、ASR 模型缓存和 Playwright Chromium 都会占空间。
- 内存：建议 8GB 以上。默认用 CPU + int8 跑 `faster-whisper small`，配置低时会自动降级到更小模型。
- 权限：当前目录需要可写，用于保存 `outputs/`。安装 `uv` 时需要把 `uv` 加到 PATH。

不需要提前安装：

- 不需要全局 Python。入口脚本声明了 `requires-python = ">=3.12"`，`uv` 会自动准备可用的 Python。
- 不需要全局 `yt-dlp`。脚本会通过 `uv` 自动安装并用 `python -m yt_dlp` 调用。
- 不需要全局 ffmpeg。优先使用 `imageio-ffmpeg` 自带的 ffmpeg。
- 不需要 GPU。CPU 可以跑，只是长视频会慢。
- 不需要登录浏览器，也不会读取浏览器 Cookie。

可能会自动下载的内容：

- Python 3.12 或其他满足脚本要求的 Python 版本，由 `uv` 自动准备。
- `yt-dlp`、`faster-whisper`、`imageio-ffmpeg`、`playwright-python` 等 Python 依赖，由 `uv` 自动安装到隔离环境。
- Playwright Chromium，仅在本机没有可用 Chrome/Edge 且需要公开访客态 cookie 时安装。
- faster-whisper 模型文件。默认 `small`，如果你改用 `medium` 或 `large-v3`，首次下载会更大。

## 下载安装

先把这个仓库下载到本地：

- 不会用 Git：在 GitHub 页面点击 `Code` -> `Download ZIP`，解压后进入文件夹。
- 会用 Git：把仓库 clone 到本地后进入文件夹。

后续命令都在仓库根目录执行，也就是包含 `README.md`、`pyproject.toml`、`skills/` 的目录。

## 安装运行环境

这个 Skill 默认用户机器上什么都没有。你只需要先安装 `uv`。后面的 Python、`yt-dlp`、`faster-whisper`、`imageio-ffmpeg`、Playwright 都由 Skill 的脚本声明和自检流程处理。

macOS / Linux：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装后检查：

```bash
uv --version
```

然后直接运行自检。第一次运行时，`uv` 会按脚本头部声明自动准备 Python 和 Python 依赖：

```bash
uv run --script skills/mrcarlsama-social-transcriber/scripts/bootstrap.py --ensure
```

如果你的机器或网络环境导致 Python 自动准备失败，再手动执行：

```bash
uv python install 3.12
```

## 核心依赖来源

这些工具不是本仓库自己实现的，Skill 只是编排它们：

- `uv`：<https://github.com/astral-sh/uv>
- `yt-dlp`：<https://github.com/yt-dlp/yt-dlp>，官方安装说明：<https://github.com/yt-dlp/yt-dlp#installation>
- `faster-whisper`：<https://github.com/SYSTRAN/faster-whisper>
- `imageio-ffmpeg`：<https://github.com/imageio/imageio-ffmpeg>
- `playwright-python`：<https://github.com/microsoft/playwright-python>

不需要用户全局安装 `yt-dlp`。`yt-dlp` 已写进脚本依赖，第一次运行时由 `uv` 自动装到隔离环境里，脚本内部用 `python -m yt_dlp` 调用。

复制到 Codex 或 Claude Code 的只有 `skills/mrcarlsama-social-transcriber/` 目录也能运行；依赖声明写在入口脚本头部，不依赖仓库根目录的 `pyproject.toml`。

## 安装到 Codex

macOS / Linux：

```bash
mkdir -p ~/.codex/skills
rm -rf ~/.codex/skills/mrcarlsama-social-transcriber
cp -R skills/mrcarlsama-social-transcriber ~/.codex/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Remove-Item -Recurse -Force "$env:USERPROFILE\.codex\skills\mrcarlsama-social-transcriber" -ErrorAction SilentlyContinue
Copy-Item -Recurse ".\skills\mrcarlsama-social-transcriber" "$env:USERPROFILE\.codex\skills\"
```

然后重启 Codex。

在 Codex 里直接说：

```text
使用 mrcarlsama-social-transcriber 处理这个链接：https://v.douyin.com/example/
```

## 安装到 Claude Code

用户级安装，适合所有项目都能用。

macOS / Linux：

```bash
mkdir -p ~/.claude/skills
rm -rf ~/.claude/skills/mrcarlsama-social-transcriber
cp -R skills/mrcarlsama-social-transcriber ~/.claude/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\mrcarlsama-social-transcriber" -ErrorAction SilentlyContinue
Copy-Item -Recurse ".\skills\mrcarlsama-social-transcriber" "$env:USERPROFILE\.claude\skills\"
```

如果 Claude Code 当前会话已经在监听 `~/.claude/skills`，安装后会自动生效；如果没有识别到这个 Skill，重启 Claude Code。

在 Claude Code 里直接说：

```text
/mrcarlsama-social-transcriber https://v.douyin.com/example/
```

如果你只想让某个项目能用，也可以安装到项目内：

```bash
mkdir -p .claude/skills
rm -rf .claude/skills/mrcarlsama-social-transcriber
cp -R skills/mrcarlsama-social-transcriber .claude/skills/
```

## 检查是否安装成功

在仓库根目录执行：

```bash
uv run --script skills/mrcarlsama-social-transcriber/scripts/bootstrap.py --ensure
uv run --script skills/mrcarlsama-social-transcriber/scripts/preflight.py --check
```

看到类似结果就说明基础环境正常：

```json
{
  "ok": true,
  "checks": {
    "python_3_12_or_newer": true,
    "uv": true,
    "yt_dlp_python_module": true,
    "faster_whisper": true,
    "imageio_ffmpeg_or_ffmpeg": true,
    "playwright_python": true,
    "public_visitor_browser": true
  }
}
```

`bootstrap.py --ensure` 会检测公开访客态 cookie 所需的浏览器。如果机器没有 Chrome 或 Edge，它会安装 Playwright Chromium。你也可以手动运行：

```bash
uv run --script skills/mrcarlsama-social-transcriber/scripts/bootstrap.py --ensure
```

## 手动运行

正常情况下，你不需要手动运行脚本，Codex 或 Claude Code 会按 Skill 流程处理。

如果你想直接测试：

```bash
uv run --script skills/mrcarlsama-social-transcriber/scripts/run_one.py "https://v.douyin.com/example/"
```

如果平台仍要求 Cookie，并且你愿意显式提供 Cookie 文件：

```bash
uv run --script skills/mrcarlsama-social-transcriber/scripts/run_one.py \
  --cookie-file ./cookies.txt \
  "https://v.douyin.com/example/"
```

## 自动试错和续跑

Skill 的目标不是“跑一个命令就结束”，而是尽最大努力完成单链接任务。

当前脚本已接入：

- 环境试错：通过 `uv` 自动安装脚本依赖，不要求全局 `yt-dlp`。
- 下载试错：裸跑 `python -m yt_dlp`，fresh cookies 时生成公开访客态 cookie 重试。
- 断点续跑：已有原视频则跳过下载。
- 断点续跑：已有原音频则跳过音频抽取。
- 断点续跑：已有原始逐字稿、字幕和 `words.json` 则跳过 ASR。
- ASR 降级：从指定模型开始，失败或输出为空时向下切换到更小模型。
- 失败报告：无法完成时写入 `_failed/.../_meta/report.json`。

计划接入：

- 抖音 fallback：DouK / TikTokDownloader。
- 小红书 fallback：XHS-Downloader。
- 小红书图文图片下载：保存到 `图片/`。

## 输出目录

视频链接输出：

```text
outputs/
  2026-3-24[douyin][示例视频标题]/
    示例视频标题原视频.mp4
    示例视频标题原音频.wav
    示例视频标题正文.md
    示例视频标题原始逐字稿.md
    示例视频标题原始逐字稿.txt
    示例视频标题字幕.srt
    示例视频标题逐字稿.md
    _meta/
      manifest.json
      report.json
      provider-info.json
      words.json
```

图文笔记目标输出：

```text
outputs/
  2026-3-24[xiaohongshu][示例笔记标题]/
    示例笔记标题正文.md
    图片/
      01.jpg
      02.jpg
    _meta/
      manifest.json
      report.json
      provider-info.json
```

图文不运行 ASR，也不会生成音频和字幕。

## 文件说明

- `【标题】逐字稿.md`：最终润色后的逐字稿，由 Codex 或 Claude Code 用模型能力生成。
- `【标题】原视频.mp4`：下载到本地的原视频。
- `【标题】原音频.wav`：从视频中抽取的 16kHz 单声道音频，供 ASR 使用。
- `【标题】正文.md`：平台返回的正文/描述和互动数据；如果平台没有返回正文，则不会生成。
- `【标题】原始逐字稿.md`：ASR 原始识别稿，带时间戳，不做模型润色。
- `【标题】原始逐字稿.txt`：ASR 原始纯文本，方便复制或二次处理。
- `【标题】字幕.srt`：字幕文件，可导入剪辑软件。
- `_meta/manifest.json`：任务清单，记录链接、平台、标题、正文、作者、互动数据、模型、产物文件名。
- `_meta/report.json`：运行报告，记录是否成功、缺了什么文件、逐字稿字数。
- `_meta/provider-info.json`：下载器返回的原始元数据，只用于调试。
- `_meta/words.json`：词级时间戳数据，供后续字幕精修或程序处理使用。

## Cookie 策略

provider 访问顺序固定：

```text
1. 裸跑 python -m yt_dlp
2. 如果提示 fresh cookies，生成公开访客态 cookie
3. 用临时 cookie 重试
4. 仍失败，要求用户显式提供 cookie 文件
```

公开访客态 cookie 的生成方式：

- 使用隔离的临时浏览器上下文访问用户给出的公开链接。
- 不读取 Chrome、Safari、Edge、Firefox 的本地用户配置。
- 不读取账号登录态。
- 不保存到 Skill 目录；运行时文件临时写到 `outputs/_runtime/visitor-cookies/`，任务结束或重试失败后删除。
- 只用于当前下载/转写任务。

## 目录结构

```text
mrcarlsama-social-transcriber/
  README.md
  LICENSE
  .gitignore
  pyproject.toml

  skills/
    mrcarlsama-social-transcriber/
      SKILL.md
      agents/
        openai.yaml
      scripts/
        bootstrap.py
        run_one.py
        preflight.py
        verify.py
        media.py
        asr.py
        report.py
        providers/
          yt_dlp_provider.py
          douyin_provider.py
          xhs_provider.py
          visitor_cookies.py
      references/
        auto-retry-policy.md
        failure-modes.md
        cookie-policy.md

  examples/
    manifest.example.json
    示例视频标题原始逐字稿.example.md
    示例视频标题逐字稿.example.md
```
