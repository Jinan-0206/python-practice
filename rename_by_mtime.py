# -*- coding: utf-8 -*-
"""
按修改时间给指定文件夹中的文件批量添加序号前缀。

功能：
1. 用 os.walk 递归遍历指定文件夹及其子文件夹中的所有文件
2. 读取每个文件的最后修改时间
3. 按修改时间从早到晚排序（时间相同则按相对路径排序）
4. 将文件重命名为：序号_原文件名（仍留在原来的子文件夹里）
   例如：test/报告.docx  ->  test/01_报告.docx

会跳过：
- 本脚本自身
- 名称以点开头的目录（例如 .idea），避免改到编辑器配置

默认只预览，不会真正改名。确认无误后加上 --apply 才会执行。
"""

import argparse  # 解析命令行参数
import os        # 按需求使用 os 模块处理路径、遍历文件、改名
import sys       # 用于出错时退出程序
import time      # 把修改时间戳格式化成可读的日期时间
import uuid      # 生成临时文件名，避免重命名时互相覆盖


def should_skip_dir(dir_name):
    """
    是否跳过某个子目录。

    以点开头的目录（.idea、.git 等）通常是工具自动生成的，不参与重命名。
    """
    return dir_name.startswith(".")


def list_files(folder):
    """
    递归列出文件夹中的普通文件。

    参数:
        folder: 目标文件夹的绝对路径
    返回:
        文件绝对路径列表
    """
    this_script = os.path.abspath(__file__)
    files = []

    # os.walk 会进入每一层子目录
    # dirpath: 当前走到的目录
    # dirnames: 该目录下的子文件夹名（可现场删掉，从而跳过某些目录）
    # filenames: 该目录下的文件名
    for dirpath, dirnames, filenames in os.walk(folder):
        # 原地修改 dirnames，os.walk 就不会再进入被删掉的子目录
        dirnames[:] = [name for name in dirnames if not should_skip_dir(name)]

        for name in filenames:
            full_path = os.path.join(dirpath, name)
            # 不要把自己也重命名掉
            if os.path.abspath(full_path) == this_script:
                continue
            if os.path.isfile(full_path):
                files.append(full_path)

    return files


def sort_by_mtime(paths):
    """
    按最后修改时间从早到晚排序。

    os.path.getmtime 返回时间戳（秒），数值越小表示越早。
    修改时间完全相同时，再按完整路径排序，保证结果稳定。
    """
    def sort_key(full_path):
        mtime = os.path.getmtime(full_path)
        return (mtime, full_path)

    return sorted(paths, key=sort_key)


def calc_digits(count, user_digits):
    """
    计算序号要补几位零。

    例如 12 个文件时自动用 2 位：01、02、...、12
    用户指定 --digits 时以用户的为准。
    """
    if user_digits > 0:
        return user_digits
    auto = len(str(count))
    return auto if auto >= 2 else 2


def strip_old_prefix(name):
    """
    去掉已经存在的「数字_」前缀，避免重复执行后变成 01_01_原名。

    例如：03_照片.jpg  ->  照片.jpg
          照片.jpg     ->  照片.jpg（没有前缀则原样返回）
    """
    underscore = name.find("_")
    if underscore <= 0:
        return name

    maybe_number = name[:underscore]
    if maybe_number.isdigit():
        return name[underscore + 1:]
    return name


def unique_name(directory, desired, reserved):
    """
    若目标文件名在该目录已经存在，则在扩展名前加 __1、__2，避免覆盖。

    reserved 记录的是「该目录下本轮已经占用的新文件名」。
    """
    name = desired
    stem, ext = os.path.splitext(desired)
    n = 1

    while True:
        full_path = os.path.join(directory, name)
        already_planned = (directory, name) in reserved
        if (not os.path.exists(full_path)) and (not already_planned):
            return name
        name = "%s__%d%s" % (stem, n, ext)
        n += 1


def build_plan(paths, digits):
    """
    生成「原路径 -> 新路径」对照表，还不真正改名。

    序号按全局修改时间统一编号，文件仍留在原来的子文件夹中。
    """
    plan = []
    reserved = set()  # (目录, 新文件名)

    for index, old_path in enumerate(paths, start=1):
        directory = os.path.dirname(old_path)
        old_name = os.path.basename(old_path)

        prefix = str(index).zfill(digits) + "_"
        base_name = strip_old_prefix(old_name)
        desired = prefix + base_name

        if desired == old_name:
            plan.append({
                "old_path": old_path,
                "new_path": old_path,
                "skip": True,
            })
            reserved.add((directory, desired))
            continue

        new_name = unique_name(directory, desired, reserved)
        reserved.add((directory, new_name))
        plan.append({
            "old_path": old_path,
            "new_path": os.path.join(directory, new_name),
            "skip": False,
        })

    return plan


def print_preview(root, paths, plan):
    """
    在终端打印预览表：修改时间、相对路径、新文件名。
    """
    print("")
    print("目录: %s" % root)
    print("文件数: %d（已递归进入子文件夹，已跳过 .idea 等隐藏目录）" % len(paths))
    print("-" * 100)
    print("%-20s  %-48s  %s" % ("修改时间", "原路径", "新文件名"))
    print("-" * 100)

    for item in plan:
        old_path = item["old_path"]
        mtime = os.path.getmtime(old_path)
        time_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))

        # 相对路径更直观，例如 test\照片.jpg
        rel_old = os.path.relpath(old_path, root)
        new_name = os.path.basename(item["new_path"])
        new_text = new_name if not item["skip"] else "(不变) " + new_name
        print("%-20s  %-48s  %s" % (time_text, rel_old, new_text))

    print("-" * 100)


def apply_rename(plan):
    """
    真正执行重命名。

    分两步：
    1. 先改成不会冲突的临时名
    2. 再从临时名改成最终的「序号_原文件名」

    这样即使同一目录里交叉改名，也不会互相覆盖。
    """
    to_rename = [item for item in plan if not item["skip"]]
    temps = []

    for item in to_rename:
        old_path = item["old_path"]
        directory = os.path.dirname(old_path)
        _stem, ext = os.path.splitext(old_path)
        temp_name = ".renaming_%s%s" % (uuid.uuid4().hex[:8], ext)
        temp_path = os.path.join(directory, temp_name)
        os.rename(old_path, temp_path)
        temps.append((temp_path, item["new_path"]))

    for temp_path, new_path in temps:
        os.rename(temp_path, new_path)


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="递归遍历子文件夹，按修改时间从早到晚排序，给文件名加上序号前缀。"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="目标文件夹路径，默认当前目录",
    )
    parser.add_argument(
        "--digits",
        type=int,
        default=0,
        help="序号位数，例如 3 表示 001、002。默认按文件数量自动决定",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正执行重命名。不加此参数时只打印预览",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    folder = os.path.abspath(args.folder)

    if not os.path.isdir(folder):
        print("错误：目录不存在 -> %s" % folder)
        sys.exit(1)

    paths = list_files(folder)
    if not paths:
        print("该文件夹及其子文件夹中没有可重命名的文件: %s" % folder)
        return

    paths = sort_by_mtime(paths)
    digits = calc_digits(len(paths), args.digits)
    plan = build_plan(paths, digits)

    print_preview(folder, paths, plan)

    if not args.apply:
        print("以上为预览，尚未改名。")
        print('确认无误后执行: python rename_by_mtime.py "%s" --apply' % folder)
        return

    apply_rename(plan)
    print("已按修改时间完成重命名。")


if __name__ == "__main__":
    main()
