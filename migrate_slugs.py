#!/usr/bin/env python3
"""将已有书籍的 slug 迁移为拼音格式

用法:
    python migrate_slugs.py --dry-run    # 预览迁移
    python migrate_slugs.py              # 执行迁移
"""

import os
import sys
import pickle
import shutil
import argparse
from pathlib import Path

from reader3 import Book, generate_slug


def scan_books(directory: str = "."):
    """扫描所有书籍"""
    books = []
    for item in os.listdir(directory):
        if item.endswith("_data") and os.path.isdir(os.path.join(directory, item)):
            pkl_path = os.path.join(directory, item, "book.pkl")
            if os.path.exists(pkl_path):
                try:
                    with open(pkl_path, "rb") as f:
                        book = pickle.load(f)
                    books.append((item, book))
                except Exception as e:
                    print(f"警告: 无法加载 {item}: {e}")
    return books


def main():
    parser = argparse.ArgumentParser(description="迁移书籍 slug 为拼音格式")
    parser.add_argument("--dry-run", action="store_true", help="预览迁移")
    parser.add_argument("--dir", default=".", help="书籍目录")
    args = parser.parse_args()

    books = scan_books(args.dir)
    if not books:
        print("未找到任何书籍")
        return

    print(f"找到 {len(books)} 本书籍\n")

    # 分析迁移计划
    migrations = []
    conflicts = []
    unchanged = []

    for old_folder, book in books:
        new_slug = generate_slug(book.metadata.title, "")
        new_folder = f"{new_slug}_data"

        if new_folder == old_folder:
            unchanged.append((old_folder, book.metadata.title))
        elif os.path.exists(os.path.join(args.dir, new_folder)):
            conflicts.append((old_folder, new_folder, book.metadata.title))
        else:
            migrations.append((old_folder, new_slug, book.metadata.title))

    # 显示结果
    if unchanged:
        print("无需迁移:")
        for folder, title in unchanged:
            print(f"  [{folder}] {title}")
        print()

    if conflicts:
        print("冲突（需手动处理）:")
        for old, new, title in conflicts:
            print(f"  [{old}] {title} -> {new}")
        print()

    if migrations:
        print("将迁移:")
        for old, new_slug, title in migrations:
            print(f"  [{old}] {title} -> {new_slug}_data")
        print()

    if args.dry_run:
        print("--- 预览模式 ---")
        return

    if conflicts:
        print("存在冲突，请先解决")
        sys.exit(1)

    if not migrations:
        print("无需迁移")
        return

    response = input(f"确认迁移 {len(migrations)} 本书籍? (y/N): ")
    if response.lower() != 'y':
        print("已取消")
        return

    # 执行迁移
    print("\n开始迁移...")
    success_count = 0
    for old_folder, new_slug, title in migrations:
        old_path = os.path.join(args.dir, old_folder)
        new_folder = f"{new_slug}_data"
        new_path = os.path.join(args.dir, new_folder)

        try:
            shutil.move(old_path, new_path)
            pkl_path = os.path.join(new_path, "book.pkl")
            with open(pkl_path, "rb") as f:
                book = pickle.load(f)
            book.slug = new_slug
            with open(pkl_path, "wb") as f:
                pickle.dump(book, f)
            print(f"  [{old_folder} -> {new_folder}] {title}")
            success_count += 1
        except Exception as e:
            print(f"  错误: {old_folder}: {e}")

    print(f"\n迁移完成: {success_count}/{len(migrations)}")


if __name__ == "__main__":
    main()
