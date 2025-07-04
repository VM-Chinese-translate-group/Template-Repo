<div align="center"> 
   <h1>某某项目简体中文翻译</h1>
</div>

| CurseForge     | 加载器     | 整合包版本         | 汉化维护状态 |
| :------------- | :--------- | :----------------- | :----------- |
| [链接](原链接) | 模组加载器 | MC 版本 整合包版本 | 翻译中       |

---

汉化项目：[Paratranz](https://paratranz.cn/projects/项目)

汉化发布：[VM 汉化组官网](https://vmct-cn.top/modpacks/项目)

译者：[查看贡献者排行榜](https://paratranz.cn/projects/项目/leaderboard)

# 整合包介绍

整合包介绍

# 自动化 Paratranz 同步教程

## 1. 设置环境变量

1. 到仓库顶部导航栏: `Settings -> Environments -> New environment` 新建 `PARATRANZ_ENV`
2. 添加加密变量（Environment secrets）:
   | 名称 | 值 |
   |-------------|-------------------------------------------------|
   | API_KEY | 你的 Paratranz token，须有上传文件权限 |
   token 可在 <https://paratranz.cn/users/my> 中的设置部分获取。
3. 添加环境变量（Environment variables）:

   | 名称 | 值                              |
   | ---- | ------------------------------- |
   | ID   | Paratranz 项目 ID，例如 `10719` |

## 2. 开始使用

我们的工作流有两种功能：从 Paratranz 同步到 github 仓库和从 github 仓库同步到 Paratranz。

它们全都可以手动运行，操作方法如下图所示：

![](.github/action.png)

其中，Paratranz 同步到 GitHub 仓库工作流会分别在北京时间每天早晚上 10 点左右自动运行一次。

下载译文至 Github 功能可自行修改`.github/workflows`文件夹中的`download_release.yml`自动执行时间，格式为[cron 表达式](https://blog.csdn.net/Stromboli/article/details/141962560)。

在有译文更改后，工作流会自动发布一次标记为预发布的 Release 供大家测试。此外，每次从上游同步还将运行一次 FTB 任务颜色字符检查程序，
当有颜色字符错误时，将会在 release 的说明页面中进行提示，并在工作流的构件（artifact）页和 release 页面上传错误报告的 html，相关人员可下载并通过浏览器打开该文件。

当没有检查到颜色错误时，工作流详情页内会出现警告，提示找不到错误报告文件，这一点无需担心，不会造成任何负面影响。

注：从 github 仓库同步到 Paratranz 的工作流很少使用，故仅支持手动触发。

如果项目已经完成，请在仓库设置（`Settings`）中禁用工作流运行。
