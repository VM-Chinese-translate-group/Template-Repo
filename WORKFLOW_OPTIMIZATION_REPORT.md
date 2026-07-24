# 工作流代码审阅与优化报告

## 1. 本次工作的范围

本次审阅覆盖了仓库内三条既有业务链路：

1. `GitHub → ParaTranz`：扫描 `Source` 中的英文 JSON，必要时拆分 FTB Quests SNBT，再创建或更新 ParaTranz 文件。
2. `ParaTranz → GitHub`：下载 ParaTranz 译文，按源文件格式生成 `CNPack` 内容，执行 FTB 颜色字符检查，提交译文并发布测试版压缩包。
3. `整合包上游更新`：检查 CurseForge 或 CurseTheBeast 的新版本，对比 `overrides`，更新 `Source` 和版本信息，创建更新 PR，并发布在线差异报告。

审阅时对照了 ParaTranz 当前的 [OpenAPI 0.5.1 文档](https://paratranz.cn/api-docs/?format=yml)，也检查了原工作流安装的 `ParaTranz-SDK-python`。该 SDK 仓库当前代码仍由 OpenAPI 0.3.4 生成，最后一次相关提交停留在 2023 年，已经落后于当前 0.5.1 接口文档。由于本仓库只使用四个文件接口，没有继续依赖整套旧 SDK，而是实现了一个小型、可审计的调用层。

按要求，本次没有新增自动测试工作流，也没有改变现有业务工作流的触发频率。回归测试只作为仓库内可选的本地验证代码保留。

## 2. 原实现中确认的问题

### 2.1 ParaTranz 上传可能“假成功”

原上传脚本存在三条会掩盖失败的路径：

- 获取远端文件列表失败后，脚本把远端项目当成空项目继续执行，随后可能对所有文件错误地调用“创建”。
- 捕获到 Pydantic `ValidationError` 后，无条件打印“上传成功”。这实际是在绕过旧 SDK 与新响应结构不一致的问题，不能证明服务端操作成功。
- 单个文件重试耗尽后只打印错误，不向上抛出；GitHub Action 最终仍可能显示绿色。

这三项的共同根因是：网络操作结果没有以 HTTP 状态和当前远端状态为准，而是依赖旧 SDK 的模型反序列化结果，并在异常时继续运行。

### 2.2 网络调用缺少明确的超时和瞬时故障处理

原 ParaTranz 和 CurseForge 的 `requests` 调用没有设置超时。服务端无响应时，任务可能长时间挂起。上传更新、获取列表等操作也没有区分 400/401 这类确定性错误与 429/5xx 这类可恢复错误。

### 2.3 multipart 重试可能发送空文件

multipart 文件上传第一次请求后，文件句柄通常位于 EOF。如果直接复用同一个句柄重试，第二次请求可能发送空内容。新的调用层在每次重试前恢复文件指针，并用回归测试覆盖“第一次 503、第二次仍上传完整文件”的场景。

### 2.4 上游更新的“空关注列表”行为与 README 不一致

README 说明：`attentionList` 为空时应比较整个 `sourceDir`。原代码只遍历 `filePatterns` 和 `folders`，两者都为空时会比较零个文件，因此永远报告“没有有效变化”。

### 2.5 排除规则没有覆盖删除操作

`exclusionPatterns` 原本只过滤新增和修改文件，删除文件没有经过同一套规则。结果是一个本应排除的本地汉化文件，仍可能因上游不存在而被删除。

此外，原目录对比会把整个新目录作为一个“新增项”复制。若排除规则只匹配该目录内部的某些文件，复制整个目录会绕过排除规则。

### 2.6 自动更新 PR 的 shell 参数和重复运行不够安全

原工作流把整合包名称、版本号和路径直接插入 shell 脚本，且分支名只替换空格和大小写。上游版本名如果包含 shell 特殊字符、Git 非法引用字符或换行，可能导致命令解释错误。

重复运行同一个版本时，原工作流使用无保护的 `git push --force`，随后再次执行 `gh pr create`。若同版本 PR 已存在，任务会失败；无保护强推也可能覆盖并发写入。

### 2.7 颜色检查报告可能被提交进仓库

颜色检查会生成未跟踪的 `error_report.html`。原提交步骤先用整个工作区的 `git status` 判断是否有变化，再执行 `git add .`，所以即使译文没有变化，报告文件本身也会触发提交，并被加入 Git 历史。

### 2.8 差异报告会吞掉损坏归档，并存在展示层注入风险

原 `compare_archives.py` 在解压失败时捕获所有异常并直接忽略，随后仍可能生成空报告或误导性报告。归档解压也没有显式限制成员路径。

报告把归档内的文件名和内容写入 GitHub Pages HTML。JSON 中出现 `</script>` 时可以提前关闭数据脚本标签；文件名又通过 `innerHTML` 渲染，缺少必要的 HTML 转义。目录树还使用普通 JavaScript 对象存储归档路径，`__proto__` 这类特殊路径段会干扰对象原型。

### 2.9 二进制大小差值显示错误

原单位循环在 1024 字节时会得到 `+1.0 B`，而不是 `+1.0 KB`；负数差值也会丢失负号。

### 2.10 模板配置不是合法 JSON

`.github/configs/modpack.json` 原本包含 `//` 注释，但工作流使用 `jq`、脚本使用 `json.load`，两者都要求严格 JSON。用户如果没有手工删除注释，工作流会在读取配置时立即失败。

## 3. 已实施的优化

### 3.1 新增轻量 ParaTranz API 调用层

新增 `.github/scripts/paratranz_api.py`，只实现当前工作流实际使用的端点：

- `GET /projects/{projectId}/files`
- `POST /projects/{projectId}/files`
- `POST /projects/{projectId}/files/{fileId}`
- `GET /projects/{projectId}/files/{fileId}/translation`

调用层现在具有以下行为：

- 用户仍可在 `API_KEY` 中直接填写原始 Token；代码按当前官方文档自动生成 `Authorization: Bearer <token>`。
- 所有请求使用连接超时和读取超时。
- GET 和文件更新会对网络异常、429、500、502、503、504 最多尝试三次，并使用指数退避或服务端 `Retry-After`。
- multipart 更新重试前恢复文件指针，避免空文件。
- 非 2xx 响应通过 `raise_for_status()` 让工作流失败。
- 文件列表和翻译列表必须是 JSON 数组，否则报告响应契约错误。

上传脚本已移除 `asyncio` 和旧 SDK。原代码虽然创建了异步任务，但信号量固定为 1，实际仍是串行上传；改为直接串行循环不会降低原有并发度，反而让失败位置和日志更清楚。

对于“创建请求已在服务端成功，但客户端没有收到响应”的情况，脚本会重新获取文件列表：若同路径文件已经存在，则确认创建成功；若不存在且错误可重试，才再次创建。这避免网络抖动造成同名文件冲突。

### 3.2 加强 ParaTranz 下载边界

下载脚本现在：

- 在运行时统一校验 `API_TOKEN`、`PROJECT_ID`，并要求项目 ID 是整数。
- 校验 ParaTranz 返回的文件条目结构。
- 拒绝绝对路径、`..` 和 Windows 盘符路径，防止远端文件名越过 `CNPack`/`Source` 范围。
- 只处理工作流支持的、文件名包含 `en_us` 的 JSON；其他远端文件会明确记录为“跳过”。
- 保留原有阶段语义：未翻译和隐藏词条使用原文；已翻译阶段即使译文为空，也保留空译文。
- 保留原有的源格式替换和 JSON 转义处理，回归测试覆盖了引号、反斜杠和换行转义。

### 3.3 修正上游版本差异收集

`update_checker.py` 将差异收集拆成可验证的纯函数，并统一按文件处理：

- `attentionList` 没有文件模式和目录时，比较整个 `sourceDir`。
- 新增、修改、删除全部经过 `exclusionPatterns`。
- 新增目录也展开成文件后再过滤，不再绕过目录内排除规则。
- `ignoreDeletions` 继续按每个关注项生效。
- 忽略 `.DS_Store`，但不再依赖 `filecmp.dircmp` 对新增目录进行整体复制。

配置中的仓库路径、关注目录和 glob 现在必须保持在各自根目录内。`sourceDir` 或 `infoFilePath` 写成 `../`、绝对路径或盘符路径会直接终止，避免误删/误写工作区外内容。

### 3.4 配置文件增加显式启用开关

`modpack.json` 已改为严格 JSON，并新增：

```json
"configured": false
```

模板维护者完成配置后需要将其改为 `true`。保留为 `false` 时更新检查会明确报出“仍是模板配置”，避免默认的 StoneBlock 示例值被误用。为兼容已经存在、没有该字段的派生仓库，脚本只在字段被显式设置为 `false` 时阻止运行；缺少字段仍按旧配置继续。

同时增加了 `packId`、`packName` 和 `updateMethod` 的类型/取值校验。

### 3.5 加固自动更新 PR 流程

工作流不再把步骤输出直接拼进 shell 源码，而是通过环境变量传递。分支名由安全化版本号和整合包名称/版本的短哈希构成，避免非法 Git 引用和 shell 解释问题。

同一整合包版本重复运行时：

- 如果远端分支已存在，使用带明确期望 SHA 的 `--force-with-lease` 更新；远端已被其他任务改写时会拒绝覆盖。
- 如果同一分支已有打开的 PR，更新其标题和正文；没有时才创建新 PR。

CurseTheBeast v0.7.1 下载增加了 HTTP 失败检测、瞬时错误重试和 SHA-256 校验。CurseForge 的归档下载也增加失败检测和重试。外部输出写入 `$GITHUB_OUTPUT` 时改用官方多行分隔符格式，避免换行破坏后续步骤输出。

### 3.6 修正译文提交范围

`ParaTranz → GitHub` 的提交步骤现在先执行：

```bash
git add -A -- CNPack
```

随后只检查暂存区。这样只有译文内容会触发提交，`error_report.html` 仍可上传为 Artifact/Release 附件，但不会进入仓库。

`.gitignore` 同时忽略颜色报告、差异报告、PR 正文和临时更新目录，防止本地运行产生无关工作树噪声。

### 3.7 修正 VMTU 版本匹配

Minecraft 版本号中的点号会先进行正则转义。例如 `1.20.1` 现在按字面版本匹配，不再把 `.` 当作“任意字符”；末尾数字边界仍会排除 `1.20.10`、`1.20.11` 等错误候选。loader 使用固定字符串、不区分大小写匹配，并加上 `--` 防止值被解释为 grep 选项。

### 3.8 加固归档解压和 HTML 报告

两个归档处理点都增加了成员路径检查，拒绝绝对路径、`..` 越界路径和目标目录外路径。差异报告还会拒绝 tar 符号链接/硬链接。损坏或不支持的归档不再生成假报告，而是让任务失败并保留真实错误。

差异报告现在：

- 将 JSON 数据中的 `<`、`>`、`&` 转为 Unicode 转义，不能提前关闭 `<script type="application/json">`。
- 文件名和路径在进入 `innerHTML` 前进行 HTML 转义。
- 目录节点使用无原型对象并以 `Object.hasOwn` 判断，特殊文件名不能影响对象原型。
- 正确显示 B、KB、MB、GB、TB，并保留正负号。

### 3.9 固定运行环境和依赖

三个既有工作流统一使用 Python 3.13，不再随 `python-version: "3"` 自动漂移到尚未验证的新大版本。

Python 依赖拆分为：

- `.github/requirements.txt`：ParaTranz/CurseForge HTTP 调用所需依赖及其精确版本。
- `.github/requirements-ftb.txt`：在上述依赖基础上，固定 `ftb-snbt-lib-fork` 的 Git 提交及其直接运行依赖。

旧的 `ParaTranz-SDK-python` 安装已经删除。Git 依赖固定到提交 `ce72db27291f2a32e9e1cbcbd9e92effc83804e0`，避免默认分支未来变化直接改变生产工作流。

## 4. 用户可见的功能行为变化

以下变化需要维护者知晓：

1. **首次配置多一步**：完成 `.github/configs/modpack.json` 后，需要把 `configured` 改成 `true`。
2. **API Token 配置名不变**：仍使用 `PARATRANZ_ENV` 中的 `API_KEY`；可以直接保存 ParaTranz 页面显示的原始 Token，代码会添加 Bearer 前缀。
3. **失败不再伪装成成功**：无法读取文件列表、上传重试耗尽、响应格式错误、没有找到任何英文 JSON 时，`GitHub → ParaTranz` 会失败并显示具体错误。
4. **不支持的远端文件会跳过**：`ParaTranz → GitHub` 只下载本工作流能安全处理的 `en_us` JSON；其他格式会写日志但不落盘。
5. **空关注列表真正比较整个 Source**：这与 README 的既有说明一致，但不同于旧代码的实际错误行为。
6. **排除规则也保护删除文件**：排除的本地文件不会再因上游缺失而被删除。
7. **同版本重复检查会更新已有自动 PR**：不再每次无保护强推并尝试重复创建 PR。
8. **自动更新分支名格式改变**：现在包含安全化版本号和 12 位哈希；旧格式分支不会被新逻辑复用。
9. **颜色报告不再成为提交内容**：报告只存在于 Artifact/Release。
10. **损坏或危险归档会让报告任务失败**：不再输出空白或误导性差异报告。
11. **运行时固定为 Python 3.13**：避免 GitHub Runner 默认 Python 大版本变化造成不可预期行为。
12. **没有新增测试工作流**：现有定时和手动触发范围保持不变。

## 5. 验证结果

当前本地验证包括：

- 全部 Python 脚本与测试通过 `compileall`。
- 关键静态错误规则通过 Ruff 检查。
- 三个现有 Actions YAML 均通过 YAML 解析和 actionlint 1.7.12。
- 25 个回归测试通过，覆盖：
  - 空关注列表全目录比较；
  - 删除项排除规则；
  - 配置路径越界和 Windows 盘符相对路径；
  - ZIP 路径穿越；
  - GitHub 多行输出；
  - 损坏归档失败；
  - 报告脚本标签注入；
  - 二进制大小单位和负号；
  - 远端文件创建确认与失败传播；
  - ParaTranz Bearer 鉴权、503 重试、multipart 文件指针恢复；
  - ParaTranz 路径越界和 Windows 盘符相对路径；
  - 空译文阶段语义；
  - 源 JSON 格式和转义保持。
- 使用 `.github/requirements-ftb.txt` 在独立临时目录安装了固定依赖，`requests`、`ftb_snbt_lib`、`LangSpliter`、上传脚本和下载脚本均成功导入。
- `git diff --check` 通过，没有新增尾随空格或补丁格式错误。

## 6. 无法在本地完成的验证边界

本地环境没有仓库的 `API_KEY`、ParaTranz 项目 ID 和 CurseForge 私有 API Key，因此没有执行真实的上传、下载或 PR 创建，避免对线上项目产生写入。HTTP 路径、鉴权格式、请求体和响应结构是依据当前 OpenAPI 0.5.1 文档及模拟响应验证的。

GitHub Pages 部署仍保持原有设计：在线地址显示最近一次部署的报告，而每次运行的 Artifact 与该次运行绑定。本次没有改变这一产品行为。

FTB SNBT 拆分/合并算法本身较大且已有独立历史，本次只验证其固定依赖可安装、模块可导入，并保留原转换逻辑；没有借工作流修复之名重写该算法。

## 7. 本地复核命令

维护者可在仓库根目录执行：

```powershell
python -m pip install -r .github/requirements-ftb.txt
python -m compileall -q .github/scripts .github/tests
python -m unittest discover -s .github/tests -v
```

若本机安装了 Ruff，可追加：

```powershell
ruff check --select E9,F63,F7,F82 .github/scripts .github/tests
```
