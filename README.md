<div align="center"> 
   <h1>某某项目简体中文翻译</h1>
</div>

| CurseForge     | 加载器     | 整合包版本         | 汉化维护状态 |
| :------------- | :--------- | :----------------- | :----------- |
| [链接](原链接) | 模组加载器 | MC 版本 整合包版本 | 翻译中       |

### 📌 汉化相关

- **汉化项目**：[Paratranz](https://paratranz.cn/projects/项目)
- **汉化发布**：[VM 汉化组官网](https://vmct-cn.top/modpacks/项目)
- **译者名单**：[贡献者排行榜](https://paratranz.cn/projects/项目/leaderboard)

# 📖 整合包介绍

（在这里填写整合包介绍内容……）

# ⚙️ 自动化 Paratranz 同步教程

## 1. 设置环境变量

1. 在仓库顶部导航栏依次进入：
   `Settings -> Environments -> New environment`，新建环境 `PARATRANZ_ENV`。

2. 在该环境中添加 **加密变量（Environment secrets）**：

   | 名称    | 值                                       |
   | ------- | ---------------------------------------- |
   | API_KEY | 你的 Paratranz token，需具备上传文件权限 |
   | CF_API_KEY| 如果采用CurseForge源检查更新须填此项|

   🔑 Token 可在 [Paratranz 用户设置页](https://paratranz.cn/users/my) 获取。

3. 在该环境中添加 **环境变量（Environment variables）**：

   | 名称 | 值                              |
   | ---- | ------------------------------- |
   | ID   | Paratranz 项目 ID，例如 `10719` |

## 2. 使用说明

我们目前有两个 GitHub Actions 工作流：

- **Paratranz → GitHub**：从 Paratranz 拉取译文至 GitHub 仓库。
- **GitHub → Paratranz**：将原文内容推送到 Paratranz。

> ✅ 两者均支持手动运行，操作如下图所示：

![](.github/action.png)

### 自动运行规则

- **Paratranz → GitHub** 会在北京时间 **每天早上与晚上 10 点左右** 自动执行。
- 下载译文至 GitHub 的功能可通过修改 `.github/workflows/download_release.yml` 内的 `cron 表达式` 自行设定执行时间。

📎 参考：[Cron 表达式教程](https://blog.csdn.net/Stromboli/article/details/141962560)

### 发布与检查机制

- 当有译文更改时，工作流会自动发布一个 **预发布 Release** 供测试。
- 每次同步上游后，会运行一次 **FTB 任务颜色字符检查程序**：

  - **发现错误**：在 Release 说明页面提示，并上传 HTML 报告至 **Artifacts** 和 **Release 页面**。
  - **未发现错误**：工作流详情页会提示找不到报告文件，此属正常情况，无需担心。

⚠️ 注意：

- **GitHub → Paratranz** 的同步任务使用频率较低，仅支持手动触发。
- 若项目已完成，请至仓库 **Settings** 中禁用工作流运行。

# ⚙️ 自动化整合包更新教程

本教程介绍如何配置 Actions 以实现自动检测 CurseForge 上的整合包更新，并创建包含更新文件的拉取请求（Pull Request）。

## 1. 首次配置

### 配置 `modpack.json`

在仓库的 `.github/configs/modpack.json` 文件中进行详细配置。此文件是自动化更新脚本的核心。

```jsonc
// .github/configs/modpack.json
{
  // [必需] 整合包在 CurseForge 上的数字 ID。
  "packId": 130,

  // [必需] 整合包的名称，用于生成 PR 标题等。
  "packName": "FTB StoneBlock 4",

  // [必需] 存储当前版本信息的文件路径。脚本会读写此文件。
  "infoFilePath": "CNPack/modpackinfo.json",

  // [必需] 存放整合包 `overrides` 目录内容的文件夹路径。
  "sourceDir": "Source",
  
  // [必需] 指定检查更新和下载文件的方法。
  // 可选值: "api" (默认) 或 "cursethebeast"。
  // "api" 方法需要配置 CF_API_KEY。
  "updateMethod": "cursethebeast",
  
  // [可选, 仅用于 'api' 方法] 版本号解析模板。
  // 用于从 CurseForge API 返回的完整文件名中提取干净的版本号。
  "versionPattern": "FTB StoneBlock 4 {version}",

  // [可选] "关注列表"，指定脚本只检查特定文件或文件夹的变更，可提高效率。
  // 如果此项为空，则默认对比整个 `sourceDir` 目录。
  "attentionList": {
    "folders": [
      {
        "path": "config/ftbquests/quests", // 检查此文件夹
        "ignoreDeletions": false // 不忽略删除操作
      }
    ],
    "filePatterns": [
      {
        "pattern": "kubejs/assets/*/lang/en_us.json", // 检查匹配此模式的文件
        "ignoreDeletions": true // 忽略删除操作（例如不删除我们自己创建的语言文件）
      }
    ]
  },

  // [可选] "排除模式列表"，用于从变更中排除特定文件。
  "exclusionPatterns": [
    "**/lang/*.*",       // 排除所有语言文件
    "!**/lang/en_us.*"   // 但保留 en_us 语言文件
  ]
}
```

## 2. 工作流说明

-   **工作流文件**：`.github/workflows/check_update.yml`
-   **触发方式**：默认在北京时间 **每天早上 6 点** 自动运行，也支持在 Actions 页面手动触发。

### 自动化流程

1.  工作流按计划或手动启动。
2.  脚本根据 `modpack.json` 的配置，检查 CurseForge 是否有新版本发布。
3.  **如果检测到新版本**：
    -   下载新旧两个版本的整合包存档。
    -   对比 `overrides` 目录中的文件差异。
    -   将文件的 **新增、修改、删除** 应用到 `sourceDir` 目录。
    -   更新 `infoFilePath` 中指定的版本号。
    -   创建一个新的分支，并提交所有变更。
    -   **自动创建一个拉取请求（Pull Request）**，其中包含清晰的变更摘要。
    -   生成一份详细的 HTML 差异报告，并将其链接评论到该 PR 中，供人工审查。
4.  **如果未检测到新版本**，工作流正常结束，不执行任何操作。

> ✅ **您的工作**：当机器人创建 PR 后，您需要做的就是 **审查 PR 中的文件变更**，确认无误后 **手动合并** 它，即可完成整合包的更新。