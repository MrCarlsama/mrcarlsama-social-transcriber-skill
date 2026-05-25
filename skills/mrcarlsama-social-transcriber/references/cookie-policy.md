# Cookie 规则

这个 Skill 不能自动读取浏览器 Cookie。

provider 访问顺序：

```text
1. 裸跑 python -m yt_dlp
2. 如果提示 fresh cookies，生成公开访客态 cookie
3. 用临时 cookie 重试
4. 仍失败，要求用户显式提供 cookie 文件
```

公开访客态 cookie 只允许通过隔离临时浏览器上下文访问用户给出的公开页面生成。它不是用户浏览器 Cookie，也不是登录态 Cookie。

允许：

- 访问用户给出的公开页面，生成当前任务用的临时访客 cookie。
- 用户显式提供 `--cookie-file`。
- 用户手动导出 Cookie，并把文件路径交给 Skill。
- 用户手动下载视频或图文素材后，把本地文件交给 Skill 处理。

不允许：

- 自动读取 Chrome、Safari、Edge、Firefox 或系统钥匙串里的 Cookie。
- 在没有用户明确同意的情况下复制登录 Cookie。
- 使用 Cookie 绕过私密、付费、已删除或其他受限视频。

面向用户的话术：

```text
这个链接需要新鲜 Cookie。我已经尝试用公开访客态 cookie 重试，但仍然失败。
我不会自动读取你的浏览器 Cookie。请显式提供一个 Cookie 文件，或者手动下载视频后提供本地文件。
```
