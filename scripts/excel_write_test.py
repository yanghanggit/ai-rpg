import pandas as pd
from pathlib import Path
from typing import Optional
from loguru import logger
from datetime import datetime
import shutil


def backup_file(file_path: str) -> bool:
    """创建文件备份"""
    try:
        if not Path(file_path).exists():
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.backup_{timestamp}"
        shutil.copy2(file_path, backup_path)
        logger.info(f"✅ 已创建备份: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 备份失败: {e}")
        return False


def read_csv_safe(file_path: str) -> Optional[pd.DataFrame]:
    """安全读取CSV文件"""
    try:
        if not Path(file_path).exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        # 尝试不同编码
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                logger.info(f"成功读取CSV: {file_path} (编码: {encoding})")
                logger.info(f"数据形状: {df.shape}")
                return df
            except UnicodeDecodeError:
                continue

        logger.error(f"无法读取CSV文件，尝试了所有编码: {file_path}")
        return None
    except Exception as e:
        logger.error(f"读取CSV失败: {e}")
        return None


def save_csv_safe(df: pd.DataFrame, file_path: str) -> bool:
    """安全保存CSV文件"""
    try:
        # 创建备份
        backup_file(file_path)

        # 保存新数据
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        logger.info(f"✅ 成功保存CSV: {file_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 保存CSV失败: {e}")
        return False


def update_excel_from_csv(excel_file: str, dungeons_csv: str, actors_csv: str) -> bool:
    """从CSV文件更新Excel表格"""
    try:
        logger.info(f"开始更新Excel文件: {excel_file}")

        # 创建Excel文件备份
        backup_file(excel_file)

        # 读取CSV数据
        dungeons_df = None
        actors_df = None

        if Path(dungeons_csv).exists():
            dungeons_df = read_csv_safe(dungeons_csv)
            if dungeons_df is not None:
                logger.info(f"读取地牢数据: {len(dungeons_df)} 条记录")

        if Path(actors_csv).exists():
            actors_df = read_csv_safe(actors_csv)
            if actors_df is not None:
                logger.info(f"读取角色数据: {len(actors_df)} 条记录")

        # 写入Excel文件
        with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
            if dungeons_df is not None:
                dungeons_df.to_excel(writer, sheet_name="dungeons", index=False)
                logger.info("✅ 地牢数据已写入Excel")

            if actors_df is not None:
                actors_df.to_excel(writer, sheet_name="actors", index=False)
                logger.info("✅ 角色数据已写入Excel")

        logger.info(f"✅ 成功更新Excel文件: {excel_file}")
        return True

    except Exception as e:
        logger.error(f"❌ 更新Excel文件失败: {e}")
        return False


def show_current_data(df: pd.DataFrame, data_type: str) -> None:
    """显示当前数据"""
    print(f"\n=== 当前{data_type}数据 ===")
    print(f"总共 {len(df)} 条记录")
    print("\n数据预览:")
    for idx, row in df.iterrows():
        row_num = int(idx) if isinstance(idx, (int, float)) else 0
        name = row.get("name", f"第{row_num+1}行")
        print(f"  {idx}: {name}")


def add_new_entry(df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """添加新条目"""
    print(f"\n=== 添加新{data_type} ===")

    new_data = {}
    for col in df.columns:
        while True:
            value = input(f"请输入 {col}: ").strip()
            if value or input(f"{col} 可以为空吗? (y/N): ").lower() in ["y", "yes"]:
                new_data[col] = value
                break
            print("此字段不能为空，请重新输入")

    # 显示预览
    print(f"\n新{data_type}预览:")
    for key, value in new_data.items():
        print(f"  {key}: {value}")

    if input("\n确认添加? (y/N): ").lower() in ["y", "yes"]:
        new_row = pd.DataFrame([new_data])
        df = pd.concat([df, new_row], ignore_index=True)
        print(f"✅ 成功添加新{data_type}")
    else:
        print("❌ 已取消添加")

    return df


def edit_entry(df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """编辑条目"""
    if df.empty:
        print(f"没有{data_type}可以编辑")
        return df

    show_current_data(df, data_type)

    try:
        idx = int(input(f"\n请输入要编辑的{data_type}编号: "))
        if idx < 0 or idx >= len(df):
            print("无效的编号")
            return df
    except ValueError:
        print("请输入有效数字")
        return df

    print(f"\n编辑 {data_type}: {df.iloc[idx].get('name', f'第{idx+1}行')}")
    print("直接回车保持原值")

    for col in df.columns:
        current_value = df.iloc[idx][col]
        new_value = input(f"{col} (当前: {current_value}): ").strip()
        if new_value:
            df.at[idx, col] = new_value

    print(f"✅ 成功编辑{data_type}")
    return df


def delete_entry(df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """删除条目"""
    if df.empty:
        print(f"没有{data_type}可以删除")
        return df

    show_current_data(df, data_type)

    try:
        idx = int(input(f"\n请输入要删除的{data_type}编号: "))
        if idx < 0 or idx >= len(df):
            print("无效的编号")
            return df
    except ValueError:
        print("请输入有效数字")
        return df

    name = df.iloc[idx].get("name", f"第{idx+1}行")
    if input(f"\n确认删除 '{name}'? (y/N): ").lower() in ["y", "yes"]:
        df = df.drop(idx).reset_index(drop=True)
        print(f"✅ 成功删除{data_type}")
    else:
        print("❌ 已取消删除")

    return df


def manage_data(file_path: str, data_type: str) -> None:
    """管理数据的主要函数"""
    # 读取数据
    df = read_csv_safe(file_path)
    if df is None:
        print(f"无法读取{data_type}数据，创建新的数据表")
        # 根据数据类型创建不同的列结构
        if data_type == "地牢":
            df = pd.DataFrame(columns=["name", "character_sheet_name", "stage_profile"])
        else:  # 角色
            df = pd.DataFrame(
                columns=["name", "character_sheet_name", "actor_profile", "appearance"]
            )

    modified = False

    while True:
        show_current_data(df, data_type)

        print(f"\n=== {data_type}管理菜单 ===")
        print("1. 添加新条目")
        print("2. 编辑条目")
        print("3. 删除条目")
        print("4. 保存并返回")
        print("5. 不保存返回")

        choice = input("\n请选择 (1-5): ").strip()

        if choice == "1":
            df = add_new_entry(df, data_type)
            modified = True
        elif choice == "2":
            df = edit_entry(df, data_type)
            modified = True
        elif choice == "3":
            df = delete_entry(df, data_type)
            modified = True
        elif choice == "4":
            if modified:
                if save_csv_safe(df, file_path):
                    print(f"✅ {data_type}数据已保存到原文件")
                else:
                    print(f"❌ 保存{data_type}数据失败")
            return
        elif choice == "5":
            if modified and input("有未保存的修改，确认放弃? (y/N): ").lower() not in [
                "y",
                "yes",
            ]:
                continue
            return
        else:
            print("请输入1-5")


def create_sample_files() -> None:
    """创建示例CSV文件"""
    print("创建示例CSV文件...")

    # 示例地牢数据
    dungeons_data = pd.DataFrame(
        [
            {
                "name": "测试洞窟",
                "character_sheet_name": "test_cave",
                "stage_profile": "一个用于测试的神秘洞窟，里面隐藏着未知的宝藏和危险。",
            },
            {
                "name": "暗影森林",
                "character_sheet_name": "shadow_forest",
                "stage_profile": "充满暗影生物的危险森林，树木高耸入云，阳光难以穿透。",
            },
        ]
    )

    # 示例角色数据
    actors_data = pd.DataFrame(
        [
            {
                "name": "测试哥布林",
                "character_sheet_name": "test_goblin",
                "actor_profile": "一个用于测试的哥布林战士，虽然弱小但十分狡猾。",
                "appearance": "绿色皮肤的小型人形生物，持有生锈的短剑。",
            },
            {
                "name": "暗影狼",
                "character_sheet_name": "shadow_wolf",
                "actor_profile": "森林中的暗影生物，速度极快且善于隐蔽。",
                "appearance": "黑色毛发的巨大狼类，眼中闪烁着红光。",
            },
        ]
    )

    # 保存为CSV文件
    dungeons_data.to_csv("dungeons_data.csv", index=False, encoding="utf-8-sig")
    actors_data.to_csv("actors_data.csv", index=False, encoding="utf-8-sig")

    print("✅ 示例文件已创建:")
    print("  - dungeons_data.csv")
    print("  - actors_data.csv")


def convert_excel_to_csv(excel_file: str, dungeons_csv: str, actors_csv: str) -> bool:
    """将Excel文件转换为CSV文件"""
    try:
        if not Path(excel_file).exists():
            logger.warning(f"Excel文件不存在: {excel_file}")
            return False

        logger.info(f"开始转换Excel文件为CSV: {excel_file}")

        # 读取Excel中的地牢数据
        try:
            dungeons_df = pd.read_excel(excel_file, sheet_name="dungeons")
            dungeons_df.to_csv(dungeons_csv, index=False, encoding="utf-8-sig")
            logger.info(f"✅ 地牢数据已转换为CSV: {dungeons_csv}")
        except Exception as e:
            logger.warning(f"无法读取地牢工作表: {e}")

        # 读取Excel中的角色数据
        try:
            actors_df = pd.read_excel(excel_file, sheet_name="actors")
            actors_df.to_csv(actors_csv, index=False, encoding="utf-8-sig")
            logger.info(f"✅ 角色数据已转换为CSV: {actors_csv}")
        except Exception as e:
            logger.warning(f"无法读取角色工作表: {e}")

        return True

    except Exception as e:
        logger.error(f"❌ Excel转CSV失败: {e}")
        return False


def main() -> None:
    """主函数"""
    print("🎮 游戏数据编辑工具 (CSV格式)")
    print("=" * 50)

    # 检查并处理原始Excel文件
    excel_file = "excel_test.xlsx"
    dungeons_csv = "dungeons_data.csv"
    actors_csv = "actors_data.csv"

    # 如果CSV文件不存在但Excel文件存在，先转换为CSV
    if not (Path(dungeons_csv).exists() or Path(actors_csv).exists()):
        if Path(excel_file).exists():
            print(f"📁 发现Excel文件: {excel_file}")
            if input("是否将Excel文件转换为CSV格式进行编辑？(y/n): ").lower() == "y":
                convert_excel_to_csv(excel_file, dungeons_csv, actors_csv)
        else:
            print("📁 未找到数据文件，创建示例文件...")
            create_sample_files()

    while True:
        print("\n📋 主菜单:")
        print("1. 编辑地牢数据")
        print("2. 编辑角色数据")
        print("3. 将CSV数据保存为Excel文件")
        print("4. 创建示例文件")
        print("5. 退出")

        choice = input("\n请选择操作 (1-5): ").strip()

        if choice == "1":
            manage_data(dungeons_csv, "地牢")
        elif choice == "2":
            manage_data(actors_csv, "角色")
        elif choice == "3":
            # 保存CSV数据为Excel文件
            print("\n💾 导出Excel文件...")
            excel_output = input("请输入Excel文件名 (默认: excel_test.xlsx): ").strip()
            if not excel_output:
                excel_output = "excel_test.xlsx"

            success = update_excel_from_csv(excel_output, dungeons_csv, actors_csv)
            if success:
                print(f"✅ 数据已成功保存为Excel文件: {excel_output}")
            else:
                print("❌ Excel文件保存失败")
        elif choice == "4":
            create_sample_files()
        elif choice == "5":
            print("👋 感谢使用游戏数据编辑工具!")
            break
        else:
            print("❌ 无效选择，请重试。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序被中断")
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
