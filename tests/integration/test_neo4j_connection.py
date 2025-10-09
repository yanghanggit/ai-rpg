#!/usr/bin/env python3
"""
Neo4j 连接和基本操作测试

测试 Neo4j 图数据库的基本连接和操作功能
包括：连接测试、CRUD 操作、AI RPG 数据模型测试

Author: yanghanggit
Date: 2025-10-09
"""

from typing import Generator, Any, Optional
import pytest
from loguru import logger

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


class TestNeo4jConnection:
    """Neo4j 连接和基本操作测试类"""

    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self) -> Generator[None, None, None]:
        """测试前后自动清理测试数据"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        # 测试前预清理
        self._cleanup_all_test_data()

        yield  # 运行测试

        # 测试后清理
        self._cleanup_all_test_data()

    def test_neo4j_connection(self) -> None:
        """测试 Neo4j 基本连接"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        logger.info("🔍 开始测试 Neo4j 连接...")

        driver = self._create_driver()
        if not driver:
            pytest.fail("无法建立 Neo4j 连接")

        try:
            # 测试连接
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                assert record is not None, "连接测试失败"
                assert record["test"] == 1, "连接测试返回值错误"

            logger.success("✅ Neo4j 连接测试成功")

        finally:
            driver.close()

    def test_basic_crud_operations(self) -> None:
        """测试基本的 CRUD 操作"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        logger.info("📝 开始测试基本 CRUD 操作...")

        driver = self._create_driver()
        if not driver:
            pytest.fail("无法建立 Neo4j 连接")

        try:
            with driver.session() as session:
                # 1. 创建测试节点
                result = session.run(
                    """
                    CREATE (p:Player {name: $name, level: $level, created_at: datetime()})
                    RETURN p.name as name, p.level as level
                    """,
                    name="测试玩家_pytest",
                    level=1,
                )

                record = result.single()
                assert record is not None, "创建节点失败"
                assert record["name"] == "测试玩家_pytest", "节点名称不匹配"
                assert record["level"] == 1, "节点等级不匹配"

                # 2. 查询节点
                result = session.run(
                    """
                    MATCH (p:Player {name: $name})
                    RETURN p.name as name, p.level as level, elementId(p) as node_id
                    """,
                    name="测试玩家_pytest",
                )

                records = list(result)
                assert (
                    len(records) == 1
                ), f"查询结果数量错误，期望1个，实际{len(records)}个"

                record = records[0]
                assert record["name"] == "测试玩家_pytest", "查询结果名称不匹配"
                assert record["level"] == 1, "查询结果等级不匹配"
                assert record["node_id"] is not None, "节点ID为空"

                # 3. 更新节点
                result = session.run(
                    """
                    MATCH (p:Player {name: $name})
                    SET p.level = p.level + 1, p.updated_at = datetime()
                    RETURN p.name as name, p.level as level
                    """,
                    name="测试玩家_pytest",
                )

                record = result.single()
                assert record is not None, "更新节点失败"
                assert record["level"] == 2, "节点等级更新错误"

                # 4. 验证更新结果
                result = session.run(
                    """
                    MATCH (p:Player {name: $name})
                    RETURN p.level as level
                    """,
                    name="测试玩家_pytest",
                )

                record = result.single()
                assert record is not None, "验证更新失败"
                assert record["level"] == 2, "更新后等级验证失败"

            logger.success("✅ 基本 CRUD 操作测试通过")

        finally:
            driver.close()

    def test_relationship_operations(self) -> None:
        """测试关系创建和查询"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        logger.info("🔗 开始测试关系操作...")

        driver = self._create_driver()
        if not driver:
            pytest.fail("无法建立 Neo4j 连接")

        try:
            with driver.session() as session:
                # 创建测试关系
                session.run(
                    """
                    MERGE (p:Player {name: $player_name, level: 1})
                    MERGE (g:Game {name: "AI RPG Test", type: "Roguelike TCG"})
                    MERGE (p)-[r:PLAYS]->(g)
                    SET r.started_at = datetime()
                    """,
                    player_name="测试玩家_pytest",
                )

                # 查询关系
                result = session.run(
                    """
                    MATCH (p:Player)-[r:PLAYS]->(g:Game)
                    WHERE p.name = $player_name
                    RETURN p.name as player, type(r) as relationship, g.name as game
                    """,
                    player_name="测试玩家_pytest",
                )

                relationships = list(result)
                assert (
                    len(relationships) == 1
                ), f"关系数量错误，期望1个，实际{len(relationships)}个"

                rel = relationships[0]
                assert rel["player"] == "测试玩家_pytest", "关系中玩家名称不匹配"
                assert rel["relationship"] == "PLAYS", "关系类型不匹配"
                assert rel["game"] == "AI RPG Test", "关系中游戏名称不匹配"

            logger.success("✅ 关系操作测试通过")

        finally:
            driver.close()

    def test_ai_rpg_schema(self) -> None:
        """测试 AI RPG 相关的图结构"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        logger.info("🎮 开始测试 AI RPG 数据模型...")

        driver = self._create_driver()
        if not driver:
            pytest.fail("无法建立 Neo4j 连接")

        try:
            with driver.session() as session:
                # 创建角色和技能
                session.run(
                    """
                    MERGE (c:Character {name: "勇者_pytest", class: "Warrior", hp: 100})
                    MERGE (s1:Skill {name: "剑击_pytest", damage: 25, mana_cost: 10})
                    MERGE (s2:Skill {name: "防御_pytest", defense_boost: 15, mana_cost: 5})
                    MERGE (c)-[:KNOWS]->(s1)
                    MERGE (c)-[:KNOWS]->(s2)
                    """
                )

                # 创建装备
                session.run(
                    """
                    MERGE (w:Weapon {name: "铁剑_pytest", attack: 20, durability: 100})
                    MERGE (a:Armor {name: "皮甲_pytest", defense: 10, durability: 80})
                    WITH w, a
                    MATCH (c:Character {name: "勇者_pytest"})
                    MERGE (c)-[:EQUIPS]->(w)
                    MERGE (c)-[:WEARS]->(a)
                    """
                )

                # 查询角色信息
                result = session.run(
                    """
                    MATCH (c:Character {name: "勇者_pytest"})
                    OPTIONAL MATCH (c)-[:KNOWS]->(s:Skill)
                    OPTIONAL MATCH (c)-[:EQUIPS]->(w:Weapon)
                    OPTIONAL MATCH (c)-[:WEARS]->(a:Armor)
                    RETURN c.name as character, 
                           c.class as class, 
                           c.hp as hp,
                           collect(DISTINCT s.name) as skills,
                           w.name as weapon,
                           a.name as armor
                    """
                )

                record = result.single()
                assert record is not None, "角色查询失败"
                assert record["character"] == "勇者_pytest", "角色名称不匹配"
                assert record["class"] == "Warrior", "角色职业不匹配"
                assert record["hp"] == 100, "角色生命值不匹配"
                assert record["weapon"] == "铁剑_pytest", "武器名称不匹配"
                assert record["armor"] == "皮甲_pytest", "防具名称不匹配"

                # 验证技能
                skills = record["skills"]
                assert len(skills) == 2, f"技能数量错误，期望2个，实际{len(skills)}个"
                assert "剑击_pytest" in skills, "剑击技能缺失"
                assert "防御_pytest" in skills, "防御技能缺失"

            logger.success("✅ AI RPG 数据模型测试通过")

        finally:
            driver.close()

    def test_neo4j_service_unavailable(self) -> None:
        """测试 Neo4j 服务不可用的情况"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        logger.info("⚠️ 测试服务不可用情况...")

        # 使用错误的端口测试连接失败
        try:
            driver = GraphDatabase.driver(
                "bolt://localhost:9999",  # 错误端口
                auth=("neo4j", "password123"),
                connection_timeout=1,
            )

            with driver.session() as session:
                session.run("RETURN 1")

            driver.close()
            pytest.fail("期望连接失败，但连接成功了")

        except ServiceUnavailable:
            logger.success("✅ 服务不可用测试通过")
        except Exception as e:
            logger.info(f"连接失败（其他原因）: {e}")
            # 其他类型的连接失败也是可接受的

    def test_authentication_error(self) -> None:
        """测试认证错误的情况"""
        if not NEO4J_AVAILABLE:
            pytest.skip("Neo4j Python驱动未安装")

        logger.info("🔒 测试认证错误情况...")

        try:
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("wrong_user", "wrong_password"),  # 错误凭据
                connection_timeout=3,
            )

            with driver.session() as session:
                session.run("RETURN 1")

            driver.close()
            pytest.fail("期望认证失败，但认证成功了")

        except AuthError:
            logger.success("✅ 认证错误测试通过")
        except ServiceUnavailable:
            logger.info("Neo4j 服务不可用，跳过认证测试")
            pytest.skip("Neo4j 服务不可用")
        except Exception as e:
            logger.info(f"认证失败（其他原因）: {e}")

    def _create_driver(self) -> Optional[Any]:
        """创建 Neo4j 驱动连接"""
        try:
            # 先尝试使用配置的密码
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("neo4j", "password123"),
                connection_timeout=3,
            )

            # 测试连接
            with driver.session() as session:
                session.run("RETURN 1")

            return driver

        except AuthError:
            # 尝试使用默认密码并重置
            try:
                logger.info("🔧 尝试使用默认密码连接...")
                temp_driver = GraphDatabase.driver(
                    "bolt://localhost:7687",
                    auth=("neo4j", "neo4j"),
                    connection_timeout=3,
                )

                with temp_driver.session(database="system") as session:
                    session.run(
                        "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO $new_password",
                        new_password="password123",
                    )

                temp_driver.close()

                # 使用新密码重新连接
                driver = GraphDatabase.driver(
                    "bolt://localhost:7687",
                    auth=("neo4j", "password123"),
                    connection_timeout=3,
                )

                with driver.session() as session:
                    session.run("RETURN 1")

                return driver

            except Exception as e:
                logger.error(f"❌ 连接失败: {e}")
                return None

        except ServiceUnavailable as e:
            logger.error(f"❌ Neo4j 服务不可用: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 连接异常: {e}")
            return None

    def _cleanup_all_test_data(self) -> None:
        """清理所有测试数据"""
        driver = self._create_driver()
        if not driver:
            return

        try:
            with driver.session() as session:
                # 删除所有测试节点和关系
                test_patterns = [
                    "测试玩家_pytest",
                    "勇者_pytest",
                    "剑击_pytest",
                    "防御_pytest",
                    "铁剑_pytest",
                    "皮甲_pytest",
                    "AI RPG Test",
                ]

                for pattern in test_patterns:
                    # 删除包含测试标识的节点
                    session.run(
                        """
                        MATCH (n) 
                        WHERE n.name CONTAINS $pattern
                        DETACH DELETE n
                        """,
                        pattern=pattern,
                    )

                # 额外清理可能的测试节点
                session.run(
                    """
                    MATCH (n) 
                    WHERE n.name =~ '.*pytest.*' OR n.name =~ '.*test.*'
                    DETACH DELETE n
                    """
                )

        except Exception as e:
            logger.warning(f"⚠️ 清理测试数据时出现问题: {e}")
        finally:
            driver.close()
