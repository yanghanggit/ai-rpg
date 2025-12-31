"""
使用 LangChain 批量读取目录下所有 PDF 文件的脚本

功能：
- 扫描指定目录下的所有 PDF 文件
- 使用 PyPDFLoader 加载并提取内容
- 打印每个 PDF 的信息
- 将所有内容合并生成 Markdown 报告文件

运行方式:
    uv run python scripts/run_langchain_pdf_reader.py
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


def load_pdf_with_langchain(pdf_path: str) -> List[Document]:
    """
    使用 LangChain 的 PyPDFLoader 加载 PDF 文件

    Args:
        pdf_path: PDF 文件的路径

    Returns:
        文档列表，每个元素对应 PDF 的一页
    """
    logger.info(f"开始加载 PDF 文件: {pdf_path}")

    # 检查文件是否存在
    if not Path(pdf_path).exists():
        logger.error(f"PDF 文件不存在: {pdf_path}")
        raise FileNotFoundError(f"找不到文件: {pdf_path}")

    try:
        # 使用 PyPDFLoader 加载 PDF
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()

        logger.info(f"成功加载 PDF，共 {len(documents)} 页")
        return documents

    except Exception as e:
        logger.error(f"加载 PDF 时出错: {e}")
        raise


def clean_text(text: str) -> str:
    """
    清理从 PDF 提取的文本，去除多余的换行符

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    # 将单个字符的行（中文字符间的换行）合并
    text = text.replace("\n", "")
    # 保留空格作为分隔
    text = " ".join(text.split())
    return text


def display_document_info(documents: List[Document]) -> None:
    """
    显示文档信息和内容预览

    Args:
        documents: 文档列表
    """
    logger.info("=" * 80)
    logger.info("📄 文档信息")
    logger.info("=" * 80)

    total_pages = len(documents)
    total_chars = sum(len(doc.page_content) for doc in documents)

    logger.info(f"总页数: {total_pages}")
    logger.info(f"总字符数: {total_chars:,}")

    # 显示第一页的元数据
    if documents:
        first_doc = documents[0]
        logger.info(f"\n📑 第一页元数据:")
        for key, value in first_doc.metadata.items():
            logger.info(f"  {key}: {value}")

        # 显示第一页的内容预览（前300个字符）
        logger.info(f"\n📖 第一页内容预览:")
        cleaned_content = clean_text(first_doc.page_content)
        preview = cleaned_content[:300].strip()
        logger.info(f"{preview}...")

        # 显示最后一页的内容预览
        if total_pages > 1:
            last_doc = documents[-1]
            logger.info(f"\n📖 最后一页内容预览:")
            cleaned_content = clean_text(last_doc.page_content)
            preview = cleaned_content[:300].strip()
            logger.info(f"{preview}...")


def find_pdf_files(directory: str) -> List[Path]:
    """
    在指定目录下查找所有 PDF 文件

    Args:
        directory: 目录路径

    Returns:
        PDF 文件路径列表
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        logger.error(f"目录不存在: {directory}")
        raise FileNotFoundError(f"目录不存在: {directory}")

    if not dir_path.is_dir():
        logger.error(f"路径不是目录: {directory}")
        raise NotADirectoryError(f"路径不是目录: {directory}")

    # 查找所有 PDF 文件（不区分大小写）
    pdf_files = list(dir_path.glob("**/*.pdf")) + list(dir_path.glob("**/*.PDF"))
    pdf_files = sorted(set(pdf_files))  # 去重并排序

    logger.info(f"在目录 {directory} 中找到 {len(pdf_files)} 个 PDF 文件")
    return pdf_files


def process_single_pdf(pdf_path: Path) -> Dict[str, Any]:
    """
    处理单个 PDF 文件

    Args:
        pdf_path: PDF 文件路径

    Returns:
        包含文件信息和内容的字典
    """
    try:
        documents = load_pdf_with_langchain(str(pdf_path))
        display_document_info(documents)

        # 收集所有页面的文本内容
        full_text = ""
        for doc in documents:
            full_text += clean_text(doc.page_content) + "\n\n"

        return {
            "filename": pdf_path.name,
            "filepath": str(pdf_path),
            "pages": len(documents),
            "content": full_text.strip(),
            "metadata": documents[0].metadata if documents else {},
            "success": True,
        }

    except Exception as e:
        logger.error(f"处理 PDF {pdf_path.name} 时出错: {e}")
        return {
            "filename": pdf_path.name,
            "filepath": str(pdf_path),
            "pages": 0,
            "content": "",
            "metadata": {},
            "success": False,
            "error": str(e),
        }


def generate_markdown_report(
    pdf_results: List[Dict[str, Any]], output_path: Path
) -> None:
    """
    生成 Markdown 格式的报告文件

    Args:
        pdf_results: PDF 处理结果列表
        output_path: 输出文件路径
    """
    logger.info(f"开始生成 Markdown 报告: {output_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        # 写入标题和概要
        f.write("# PDF 文件提取报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**处理文件数**: {len(pdf_results)}\n\n")

        success_count = sum(1 for r in pdf_results if r["success"])
        f.write(
            f"**成功**: {success_count} | **失败**: {len(pdf_results) - success_count}\n\n"
        )
        f.write("---\n\n")

        # 写入目录
        f.write("## 目录\n\n")
        for i, result in enumerate(pdf_results, 1):
            status = "✅" if result["success"] else "❌"
            f.write(
                f"{i}. {status} [{result['filename']}](#{i}-{result['filename'].replace('.pdf', '').replace(' ', '-')})\n"
            )
        f.write("\n---\n\n")

        # 写入每个 PDF 的详细内容
        for i, result in enumerate(pdf_results, 1):
            f.write(f"## {i}. {result['filename']}\n\n")

            if result["success"]:
                f.write(f"**文件路径**: `{result['filepath']}`\n\n")
                f.write(f"**页数**: {result['pages']}\n\n")

                # 写入元数据
                if result["metadata"]:
                    f.write("**元数据**:\n\n")
                    for key, value in result["metadata"].items():
                        if key not in ["source"]:  # 跳过source，已经在文件路径中显示
                            f.write(f"- {key}: {value}\n")
                    f.write("\n")

                # 写入内容
                f.write("### 内容\n\n")
                f.write(f"{result['content']}\n\n")

            else:
                f.write(f"**状态**: ❌ 处理失败\n\n")
                f.write(f"**错误**: {result.get('error', '未知错误')}\n\n")

            f.write("---\n\n")

    logger.info(f"✅ Markdown 报告已生成: {output_path}")


def main() -> None:
    """主函数"""
    # 目标目录
    target_directory = "/Users/yanghang/Documents/GitHub/ai-rpg/logs/"

    try:
        logger.info("🚀 开始批量处理 PDF 文件")
        logger.info(f"目标目录: {target_directory}")

        # 1. 查找所有 PDF 文件
        pdf_files = find_pdf_files(target_directory)

        if not pdf_files:
            logger.warning("未找到任何 PDF 文件")
            return

        # 2. 处理每个 PDF 文件
        pdf_results = []
        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"处理文件 {i}/{len(pdf_files)}: {pdf_path.name}")
            logger.info(f"{'=' * 80}")

            result = process_single_pdf(pdf_path)
            pdf_results.append(result)

        # 3. 生成 Markdown 报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"pdf_extraction_report_{timestamp}.md"
        output_path = Path(target_directory) / output_filename

        generate_markdown_report(pdf_results, output_path)

        # 4. 输出统计信息
        logger.info("\n" + "=" * 80)
        logger.info("📊 处理统计")
        logger.info("=" * 80)
        logger.info(f"总文件数: {len(pdf_results)}")
        logger.info(f"成功: {sum(1 for r in pdf_results if r['success'])}")
        logger.info(f"失败: {sum(1 for r in pdf_results if not r['success'])}")
        logger.info(f"报告文件: {output_path}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 所有 PDF 处理完成")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ 程序执行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
