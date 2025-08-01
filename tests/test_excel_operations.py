"""
Excel 文件操作测试模块

包含CSV和Excel文件的读写、转换和验证功能测试
"""

import pytest
import pandas as pd
from pathlib import Path
from typing import Optional, Generator
from loguru import logger
from datetime import datetime
import shutil
import tempfile
import os


# ================================
# pytest fixtures
# ================================


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """创建临时目录进行测试"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_dungeons_data() -> pd.DataFrame:
    """提供示例地牢数据"""
    return pd.DataFrame(
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


@pytest.fixture
def sample_actors_data() -> pd.DataFrame:
    """提供示例角色数据"""
    return pd.DataFrame(
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


@pytest.fixture
def test_files(temp_dir: str) -> dict[str, str]:
    """提供测试文件路径"""
    return {
        "excel_file": os.path.join(temp_dir, "test_excel_output.xlsx"),
        "dungeons_csv": os.path.join(temp_dir, "test_dungeons_data.csv"),
        "actors_csv": os.path.join(temp_dir, "test_actors_data.csv"),
    }


# ================================
# 工具函数
# ================================


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
            has_data = False
            if dungeons_df is not None:
                dungeons_df.to_excel(writer, sheet_name="dungeons", index=False)
                logger.info("✅ 地牢数据已写入Excel")
                has_data = True

            if actors_df is not None:
                actors_df.to_excel(writer, sheet_name="actors", index=False)
                logger.info("✅ 角色数据已写入Excel")
                has_data = True

            # 如果没有任何数据，创建一个空的工作表
            if not has_data:
                empty_df = pd.DataFrame({"message": ["No data available"]})
                empty_df.to_excel(writer, sheet_name="empty", index=False)
                logger.info("ℹ️ 创建了空的Excel工作表")

        logger.info(f"✅ 成功更新Excel文件: {excel_file}")
        return True
    except Exception as e:
        logger.error(f"❌ 更新Excel文件失败: {e}")
        return False


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


def create_sample_csv_files(
    dungeons_csv: str,
    actors_csv: str,
    dungeons_data: pd.DataFrame,
    actors_data: pd.DataFrame,
) -> None:
    """创建示例CSV文件（自定义文件名）"""
    logger.info(f"创建示例CSV文件: {dungeons_csv}, {actors_csv}")

    # 保存为CSV文件
    dungeons_data.to_csv(dungeons_csv, index=False, encoding="utf-8-sig")
    actors_data.to_csv(actors_csv, index=False, encoding="utf-8-sig")


# ================================
# pytest 测试函数
# ================================


@pytest.mark.excel
def test_csv_file_creation(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """测试CSV文件创建"""
    logger.info("📝 测试CSV文件创建...")

    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    assert Path(test_files["dungeons_csv"]).exists(), "地牢CSV文件未创建"
    assert Path(test_files["actors_csv"]).exists(), "角色CSV文件未创建"
    logger.info("✅ CSV文件创建测试通过")


@pytest.mark.excel
def test_csv_file_reading(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """测试CSV文件读取"""
    logger.info("📖 测试CSV文件读取...")

    # 先创建文件
    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    # 读取文件
    dungeons_df = read_csv_safe(test_files["dungeons_csv"])
    actors_df = read_csv_safe(test_files["actors_csv"])

    assert dungeons_df is not None, "无法读取地牢CSV文件"
    assert actors_df is not None, "无法读取角色CSV文件"
    assert len(dungeons_df) == 2, f"地牢数据行数不正确: {len(dungeons_df)}"
    assert len(actors_df) == 2, f"角色数据行数不正确: {len(actors_df)}"

    logger.info(
        f"✅ CSV文件读取测试通过 - 地牢: {len(dungeons_df)}行, 角色: {len(actors_df)}行"
    )


@pytest.mark.excel
def test_data_content_validation(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """测试数据内容验证"""
    logger.info("🔍 测试数据内容验证...")

    # 创建文件
    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    # 读取并验证
    dungeons_df = read_csv_safe(test_files["dungeons_csv"])
    actors_df = read_csv_safe(test_files["actors_csv"])

    assert dungeons_df is not None
    assert actors_df is not None

    # 验证数据内容
    expected_dungeons = ["测试洞窟", "暗影森林"]
    expected_actors = ["测试哥布林", "暗影狼"]

    actual_dungeons = dungeons_df["name"].tolist()
    actual_actors = actors_df["name"].tolist()

    assert actual_dungeons == expected_dungeons, f"地牢名称不匹配: {actual_dungeons}"
    assert actual_actors == expected_actors, f"角色名称不匹配: {actual_actors}"

    logger.info("✅ 数据内容验证测试通过")
    logger.info(f"   地牢数据: {actual_dungeons}")
    logger.info(f"   角色数据: {actual_actors}")


@pytest.mark.excel
def test_csv_to_excel_conversion(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """测试CSV转Excel文件"""
    logger.info("💾 测试CSV转Excel文件...")

    # 创建CSV文件
    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    # 转换为Excel
    success = update_excel_from_csv(
        test_files["excel_file"], test_files["dungeons_csv"], test_files["actors_csv"]
    )

    assert success, "Excel文件创建失败"
    assert Path(test_files["excel_file"]).exists(), "Excel文件不存在"

    logger.info("✅ CSV转Excel文件测试通过")


@pytest.mark.excel
def test_excel_file_content_validation(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """测试Excel文件内容验证"""
    logger.info("🔄 测试Excel文件内容验证...")

    # 创建CSV文件并转换为Excel
    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    success = update_excel_from_csv(
        test_files["excel_file"], test_files["dungeons_csv"], test_files["actors_csv"]
    )
    assert success, "Excel文件创建失败"

    # 读取Excel文件并验证
    excel_dungeons = pd.read_excel(test_files["excel_file"], sheet_name="dungeons")
    excel_actors = pd.read_excel(test_files["excel_file"], sheet_name="actors")

    # 验证数据完整性
    assert len(excel_dungeons) == 2, f"Excel地牢数据行数不正确: {len(excel_dungeons)}"
    assert len(excel_actors) == 2, f"Excel角色数据行数不正确: {len(excel_actors)}"

    # 验证内容一致性
    expected_dungeons = ["测试洞窟", "暗影森林"]
    expected_actors = ["测试哥布林", "暗影狼"]

    actual_excel_dungeons = excel_dungeons["name"].tolist()
    actual_excel_actors = excel_actors["name"].tolist()

    assert (
        actual_excel_dungeons == expected_dungeons
    ), f"Excel地牢名称不匹配: {actual_excel_dungeons}"
    assert (
        actual_excel_actors == expected_actors
    ), f"Excel角色名称不匹配: {actual_excel_actors}"

    logger.info("✅ Excel文件内容验证测试通过")


@pytest.mark.excel
def test_excel_to_csv_conversion(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """测试Excel转CSV文件"""
    logger.info("🔄 测试Excel转CSV转换...")

    # 先创建Excel文件
    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    update_excel_from_csv(
        test_files["excel_file"], test_files["dungeons_csv"], test_files["actors_csv"]
    )

    # 删除原始CSV文件
    Path(test_files["dungeons_csv"]).unlink()
    Path(test_files["actors_csv"]).unlink()

    # 从Excel转换回CSV
    new_dungeons_csv = test_files["dungeons_csv"].replace(".csv", "_new.csv")
    new_actors_csv = test_files["actors_csv"].replace(".csv", "_new.csv")

    success = convert_excel_to_csv(
        test_files["excel_file"], new_dungeons_csv, new_actors_csv
    )
    assert success, "Excel转CSV失败"

    # 验证新生成的CSV文件
    assert Path(new_dungeons_csv).exists(), "转换后的地牢CSV文件不存在"
    assert Path(new_actors_csv).exists(), "转换后的角色CSV文件不存在"

    # 验证内容
    new_dungeons_df = read_csv_safe(new_dungeons_csv)
    new_actors_df = read_csv_safe(new_actors_csv)

    assert new_dungeons_df is not None and len(new_dungeons_df) == 2
    assert new_actors_df is not None and len(new_actors_df) == 2

    logger.info("✅ Excel转CSV转换测试通过")


@pytest.mark.excel
@pytest.mark.integration
def test_comprehensive_excel_workflow(
    test_files: dict[str, str],
    sample_dungeons_data: pd.DataFrame,
    sample_actors_data: pd.DataFrame,
) -> None:
    """综合测试：完整的Excel工作流程"""
    logger.info("🎯 综合测试：完整的Excel工作流程...")

    # 1. 创建CSV文件
    create_sample_csv_files(
        test_files["dungeons_csv"],
        test_files["actors_csv"],
        sample_dungeons_data,
        sample_actors_data,
    )

    # 2. 验证CSV文件
    dungeons_df = read_csv_safe(test_files["dungeons_csv"])
    actors_df = read_csv_safe(test_files["actors_csv"])
    assert dungeons_df is not None and actors_df is not None

    # 3. 转换为Excel
    success = update_excel_from_csv(
        test_files["excel_file"], test_files["dungeons_csv"], test_files["actors_csv"]
    )
    assert success

    # 4. 验证Excel内容
    excel_dungeons = pd.read_excel(test_files["excel_file"], sheet_name="dungeons")
    excel_actors = pd.read_excel(test_files["excel_file"], sheet_name="actors")
    assert len(excel_dungeons) == len(dungeons_df)
    assert len(excel_actors) == len(actors_df)

    # 5. 从Excel转换回CSV
    new_dungeons_csv = test_files["dungeons_csv"].replace(".csv", "_roundtrip.csv")
    new_actors_csv = test_files["actors_csv"].replace(".csv", "_roundtrip.csv")

    success = convert_excel_to_csv(
        test_files["excel_file"], new_dungeons_csv, new_actors_csv
    )
    assert success

    # 6. 验证往返转换的数据一致性
    roundtrip_dungeons = read_csv_safe(new_dungeons_csv)
    roundtrip_actors = read_csv_safe(new_actors_csv)

    assert roundtrip_dungeons is not None and roundtrip_actors is not None
    assert len(roundtrip_dungeons) == len(dungeons_df)
    assert len(roundtrip_actors) == len(actors_df)

    # 验证名称一致性
    original_dungeon_names = dungeons_df["name"].tolist()
    roundtrip_dungeon_names = roundtrip_dungeons["name"].tolist()
    assert original_dungeon_names == roundtrip_dungeon_names

    original_actor_names = actors_df["name"].tolist()
    roundtrip_actor_names = roundtrip_actors["name"].tolist()
    assert original_actor_names == roundtrip_actor_names

    logger.info("✅ 综合Excel工作流程测试通过")


# ================================
# 错误处理测试
# ================================


@pytest.mark.excel
@pytest.mark.error_handling
def test_read_nonexistent_csv() -> None:
    """测试读取不存在的CSV文件"""
    result = read_csv_safe("nonexistent_file.csv")
    assert result is None, "读取不存在文件应该返回None"


@pytest.mark.excel
@pytest.mark.error_handling
def test_excel_conversion_with_missing_csv(test_files: dict[str, str]) -> None:
    """测试当CSV文件不存在时的Excel转换"""
    # 确保文件不存在
    assert not Path(test_files["dungeons_csv"]).exists()
    assert not Path(test_files["actors_csv"]).exists()

    # 尝试转换不存在的CSV文件
    success = update_excel_from_csv(
        test_files["excel_file"], test_files["dungeons_csv"], test_files["actors_csv"]
    )

    # 应该创建一个空的Excel文件
    assert success, "即使CSV文件不存在，也应该能创建Excel文件"


# ================================
# 性能测试（可选）
# ================================


@pytest.mark.excel
@pytest.mark.slow
@pytest.mark.skip(reason="性能测试，通常不需要运行")
def test_large_dataset_performance(temp_dir: str) -> None:
    """测试大数据集的性能"""
    logger.info("🚀 性能测试：大数据集处理...")

    # 创建大量数据
    large_data = pd.DataFrame(
        {
            "name": [f"项目_{i}" for i in range(10000)],
            "character_sheet_name": [f"sheet_{i}" for i in range(10000)],
            "stage_profile": [f"描述_{i}" for i in range(10000)],
        }
    )

    csv_file = os.path.join(temp_dir, "large_test.csv")
    excel_file = os.path.join(temp_dir, "large_test.xlsx")

    # 测试大文件保存
    start_time = datetime.now()
    large_data.to_csv(csv_file, index=False, encoding="utf-8-sig")
    csv_time = (datetime.now() - start_time).total_seconds()

    # 测试Excel转换
    start_time = datetime.now()
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        large_data.to_excel(writer, sheet_name="large_data", index=False)
    excel_time = (datetime.now() - start_time).total_seconds()

    logger.info(f"CSV保存时间: {csv_time:.2f}秒")
    logger.info(f"Excel保存时间: {excel_time:.2f}秒")

    # 基本的性能断言
    assert csv_time < 10, f"CSV保存时间过长: {csv_time}秒"
    assert excel_time < 30, f"Excel保存时间过长: {excel_time}秒"


if __name__ == "__main__":
    # 可以直接运行pytest
    pytest.main([__file__, "-v"])
