# User Data Storage

此版本新增按用户名分隔的数据保存功能。

## 目录结构
```
backend/
  user_data/
    <username>/
      drafting_image_<timestamp>_<id>.png   # 进入 drafting 阶段时确认保存的最终图片（可能多份历史）
      revision_<timestamp>.txt              # 在 revision 阶段点击 Analyze Text 时保存的全文快照
```

## 触发时机
1. 用户在登录页输入任意用户名（非空即可）。
2. 规划 (planning) 阶段上传图片并点击 Next Stage 进入 drafting：
   - 前端调用 `/api/save-final-image` 持久化当前图片。
   - 之后会尝试自动执行 DePlot 提取。
3. 修订 (revision) 阶段点击 Analyze Text：
   - 先调用 `/api/save-revision-text` 保存当前全文，然后再执行原有分析逻辑。

## 新增后端接口
- `POST /api/save-final-image` (multipart/form-data)
  - 字段：`username`, `image`
  - 返回：`{"success": true, "path": "user_data/<username>/drafting_image_...png"}`

- `POST /api/save-revision-text` (application/json)
  - Body：`{"username": "xxx", "text": "当前全文"}`
  - 返回：`{"success": true, "path": "user_data/<username>/revision_<timestamp>.txt"}`

## 注意事项 / 后续可扩展
- 目前未做用户名合法性严格校验，只是简单替换路径中的 `..` 与分隔符。
- 若需要限制用户数量或清理历史，可增加定期清理脚本或设置最大文件数。
- 可在后端增加获取列表接口，允许前端展示历史版本。
- 如需支持“覆盖”模式，可在前端仅保留最后一次文件名并用固定命名。

## 简要前端改动
- `Login.jsx`：允许任意非空用户名登录，并通过 `onLogin(username)` 传递。
- `App.jsx`：
  - 保存 `username` state。
  - 在 planning -> drafting 阶段转换时调用 `saveFinalImage`。
  - 在 revision 阶段点击 Analyze Text 时调用 `saveRevisionText`。
- `api.js`：新增 `saveFinalImage` 与 `saveRevisionText` 方法。

---
若有进一步需求（如下载、展示历史、用户注销等），可以在此文件继续补充。