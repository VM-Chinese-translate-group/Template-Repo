import json
import os
import re
import shutil
from pathlib import Path
from typing import Tuple
from collections import OrderedDict
import requests
from LangSpliter import merge_all_to_snbt

TOKEN: str = os.getenv("API_TOKEN", "")
GH_TOKEN: str = os.getenv("GH_TOKEN", "")
PROJECT_ID: str = os.getenv("PROJECT_ID", "")
FILE_URL: str = f"https://paratranz.cn/api/projects/{PROJECT_ID}/files/"

if not TOKEN or not PROJECT_ID:
    raise EnvironmentError("环境变量 API_TOKEN 或 PROJECT_ID 未设置。")

# 初始化列表
file_id_list: list[int] = []
file_path_list: list[str] = []


def fetch_json(url: str, headers: dict[str, str]) -> list[dict[str, str]]:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def translate(file_id: int) -> Tuple[list[str], list[str]]:
    """
    获取指定文件的翻译内容并返回键值对列表

    :param file_id: 文件ID
    :return: 包含键和值的元组列表
    """
    url = f"https://paratranz.cn/api/projects/{PROJECT_ID}/files/{file_id}/translation"
    headers = {"Authorization": TOKEN, "accept": "*/*"}
    translations = fetch_json(url, headers)

    keys, values = [], []

    for item in translations:
        keys.append(item["key"])
        translation = item.get("translation", "")
        original = item.get("original", "")
        # 优先使用翻译内容，缺失时根据 stage 使用原文
        values.append(
            original if item["stage"] in [0, -1, 2] or not translation else translation
        )

    return keys, values


def get_files() -> None:
    """
    获取项目中的文件列表并提取文件ID和路径
    """
    headers = {"Authorization": TOKEN, "accept": "*/*"}
    files = fetch_json(FILE_URL, headers)

    for file in files:
        file_id_list.append(file["id"])
        file_path_list.append(file["name"])


def save_translation(zh_cn_dict: dict[str, str], path: Path) -> None:
    """
    保存翻译内容到指定的 JSON 文件。

    :param zh_cn_dict: 翻译内容的字典
    :param path: 原始文件路径
    """
    dir_path = Path("CNPack") / path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    zh_cn_filename = path.name.replace("en_us", "zh_cn")
    file_path = dir_path / zh_cn_filename
    source_path = Path("Source") / path

    with open(file_path, "w", encoding="UTF-8") as f:
        try:
            with open(source_path, "r", encoding="UTF-8") as f1:
                # 使用 OrderedDict 保留源文件的键顺序
                source_json: dict = json.load(f1, object_pairs_hook=OrderedDict)

            # 按源文件顺序更新值为翻译文本
            for key in source_json.keys():
                if key in zh_cn_dict:  # 仅更新存在的键
                    source_json[key] = zh_cn_dict[key]

            json.dump(source_json, f, ensure_ascii=False, indent=4, separators=(",", ":"))
        except (IOError, FileNotFoundError):
            print(f"{source_path}路径不存在，文件按首字母排序！")
            json.dump(zh_cn_dict, f, ensure_ascii=False, indent=4, separators=(",", ":"), sort_keys=True)


def process_translation(file_id: int, path: Path) -> dict[str, str]:
    """
    处理单个文件的翻译，返回翻译字典

    :param file_id: 文件ID
    :param path: 文件路径
    :return: 翻译内容字典
    """
    keys, values = translate(file_id)

    # 手动处理文本的替换，避免反斜杠被转义
    try:
        with open("Source/" + str(path), "r", encoding="UTF-8") as f:
            zh_cn_dict = json.load(f)
    except IOError:
        zh_cn_dict = {}

    # 检查路径是否包含quests
    is_quest_file = "quests" in str(path)

    for key, value in zip(keys, values):
        # 确保替换 \\u00A0 和 \\n
        value = re.sub(r'\\"', '\"', value)

        # 对quest文件进行特殊处理
        if is_quest_file and "image" not in value and not value.startswith("[\""):
            value = value.replace(" ", "\u00A0")

        # 保存替换后的值
        zh_cn_dict[key] = value

    return zh_cn_dict



def main() -> None:
    get_files()
    ftb_quests_lang_dir = None # 用于记录FTB Quests语言文件所在的目录

    for file_id, path_str in zip(file_id_list, file_path_list):
        if "TM" in path_str:  # 跳过 TM 文件
            continue

        path = Path(path_str)
        zh_cn_dict = process_translation(file_id, path)

        save_translation(zh_cn_dict, path)

        # 打印日志时，文件名也相应地从 en_us 变为 zh_cn
        log_path = re.sub('en_us', 'zh_cn', path_str)
        print(f"已从Paratranz下载到仓库：{log_path}")

        # 检查是否为 FTB Quests 的语言文件，并记录其输出目录
        if "kubejs/assets/quests/lang/" in path_str and os.path.exists("Source/config/ftbquests/quests/lang/en_us.snbt"):
            ftb_quests_lang_dir = Path("CNPack") / path.parent

    # 在所有文件处理完毕后，如果检测到了 FTB Quests 文件，则执行合并
    if ftb_quests_lang_dir and ftb_quests_lang_dir.exists():
        print(f"\n检测到 FTB Quests 翻译文件，开始调用 LangSpliter 合并 SNBT 文件...")

        # 定义输入和输出路径
        json_dir = str(ftb_quests_lang_dir)
        output_snbt_file = 'CNPack/config/ftbquests/quests/lang/zh_cn.snbt'

        # 直接调用从 LangSpliter 导入的函数
        merge_all_to_snbt(json_dir, output_snbt_file)

       # 合并完成后，清除已合并的临时JSON文件所在的父目录
        cleanup_dir = ftb_quests_lang_dir.parent

        if cleanup_dir.exists() and cleanup_dir.is_dir():
            try:
                shutil.rmtree(cleanup_dir)
                print(f"已成功清除临时文件夹及其内容：{cleanup_dir}")
            except OSError as e:
                print(f"错误：清除文件夹 {cleanup_dir} 时失败: {e}")
        else:
            print(f"警告：找不到要清理的目录 {cleanup_dir}。")

        print(f"SNBT 合并完成，文件已生成于: {output_snbt_file}")

if __name__ == "__main__":
    main()