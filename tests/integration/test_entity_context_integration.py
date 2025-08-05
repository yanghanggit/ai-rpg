"""
Integration tests for Entity and Context working together.
"""

import pytest

from src.multi_agents_game.entitas import Context, Entity, Matcher
from tests.unit.test_components import Position, Velocity, Health, Name, Age, Score


class TestEntityContextIntegration:
    """Integration tests for Entity and Context interaction."""

    def test_entity_context_basic_workflow(self):
        """Test basic workflow of entities in context."""
        context = Context()
        
        # Create entities
        player = context.create_entity()
        enemy = context.create_entity()
        
        # Add components
        player.add(Position, 0, 0)
        player.add(Health, 100, 100)
        player.add(Name, "Hero")
        
        enemy.add(Position, 10, 10)
        enemy.add(Health, 50, 50)
        
        # Verify entities exist in context
        assert context.has_entity(player)
        assert context.has_entity(enemy)
        
        # Create groups and verify entity membership
        living_entities = context.get_group(Matcher(Health))
        positioned_entities = context.get_group(Matcher(Position))
        named_entities = context.get_group(Matcher(Name))
        
        assert len(living_entities.entities) == 2
        assert len(positioned_entities.entities) == 2
        assert len(named_entities.entities) == 1
        
        assert player in living_entities.entities
        assert enemy in living_entities.entities
        assert player in named_entities.entities
        assert enemy not in named_entities.entities

    def test_component_changes_affect_groups(self):
        """Test that component changes properly affect group membership."""
        context = Context()
        entity = context.create_entity()
        
        # Create groups
        health_group = context.get_group(Matcher(Health))
        position_group = context.get_group(Matcher(Position))
        mobile_group = context.get_group(Matcher(Position, Velocity))
        
        # Initially entity is in no groups
        assert len(health_group.entities) == 0
        assert len(position_group.entities) == 0
        assert len(mobile_group.entities) == 0
        
        # Add position component
        entity.add(Position, 5, 5)
        assert len(position_group.entities) == 1
        assert len(mobile_group.entities) == 0  # needs both Position and Velocity
        
        # Add velocity component
        entity.add(Velocity, 1, 1)
        assert len(mobile_group.entities) == 1  # now has both
        
        # Add health component
        entity.add(Health, 100, 100)
        assert len(health_group.entities) == 1
        
        # Remove velocity component
        entity.remove(Velocity)
        assert len(mobile_group.entities) == 0  # no longer mobile
        assert len(position_group.entities) == 1  # still positioned
        assert len(health_group.entities) == 1  # still alive

    def test_entity_destruction_removes_from_groups(self):
        """Test that destroying entities removes them from all groups."""
        context = Context()
        
        entity1 = context.create_entity()
        entity1.add(Position, 0, 0)
        entity1.add(Health, 100, 100)
        
        entity2 = context.create_entity()
        entity2.add(Position, 10, 10)
        entity2.add(Health, 50, 50)
        
        # Create groups
        all_group = context.get_group(Matcher(any_of=(Position, Health)))
        position_group = context.get_group(Matcher(Position))
        health_group = context.get_group(Matcher(Health))
        
        # Verify initial state
        assert len(all_group.entities) == 2
        assert len(position_group.entities) == 2
        assert len(health_group.entities) == 2
        
        # Destroy one entity
        context.destroy_entity(entity1)
        
        # Verify groups are updated
        assert len(all_group.entities) == 1
        assert len(position_group.entities) == 1
        assert len(health_group.entities) == 1
        assert entity2 in all_group.entities
        assert entity1 not in all_group.entities

    def test_complex_game_scenario(self):
        """Test a complex game scenario with multiple entity types."""
        context = Context()
        
        # Create player
        player = context.create_entity()
        player.add(Position, 0, 0)
        player.add(Health, 100, 100)
        player.add(Name, "Player")
        player.add(Score, 0)
        
        # Create enemies
        enemies = []
        for i in range(3):
            enemy = context.create_entity()
            enemy.add(Position, i * 10, i * 10)
            enemy.add(Health, 30, 30)
            enemy.add(Name, f"Enemy_{i}")
            enemies.append(enemy)
        
        # Create projectiles
        projectiles = []
        for i in range(2):
            projectile = context.create_entity()
            projectile.add(Position, i * 5, 0)
            projectile.add(Velocity, 10, 0)
            projectiles.append(projectile)
        
        # Create groups for game logic
        living_entities = context.get_group(Matcher(Health))
        moving_entities = context.get_group(Matcher(Velocity))
        player_group = context.get_group(Matcher(Name, Score))
        enemy_group = context.get_group(Matcher(Health, none_of=(Score,)))
        
        # Verify initial setup
        assert len(living_entities.entities) == 4  # player + 3 enemies
        assert len(moving_entities.entities) == 2  # 2 projectiles
        assert len(player_group.entities) == 1  # just player
        assert len(enemy_group.entities) == 3  # 3 enemies (have health but no score)
        
        # Simulate combat: projectile hits enemy
        hit_enemy = enemies[0]
        hit_projectile = projectiles[0]
        
        # Damage enemy
        old_health = hit_enemy.get(Health)
        new_health = Health(old_health.value - 20, old_health.max_value)
        hit_enemy.replace(Health, new_health.value, new_health.max_value)
        
        # Remove projectile
        context.destroy_entity(hit_projectile)
        
        # Verify state changes
        assert len(moving_entities.entities) == 1  # one projectile left
        assert hit_enemy.get(Health).value == 10  # enemy damaged
        
        # Enemy dies
        hit_enemy.remove(Health)
        assert len(living_entities.entities) == 3  # one less living entity
        assert len(enemy_group.entities) == 2  # one less enemy
        
        # Player gets score
        player.replace(Score, 100)
        assert player.get(Score).value == 100

    def test_group_events_integration(self):
        """Test that group events work correctly with entity operations."""
        context = Context()
        
        # Track events
        added_entities = []
        removed_entities = []
        updated_entities = []
        
        def on_entity_added(entity, component):
            added_entities.append((entity, component))
        
        def on_entity_removed(entity, component):
            removed_entities.append((entity, component))
        
        def on_entity_updated(entity, prev_comp, new_comp):
            updated_entities.append((entity, prev_comp, new_comp))
        
        # Create group and register events
        health_group = context.get_group(Matcher(Health))
        health_group.on_entity_added += on_entity_added
        health_group.on_entity_removed += on_entity_removed
        health_group.on_entity_updated += on_entity_updated
        
        # Create entity with health
        entity = context.create_entity()
        entity.add(Health, 100, 100)
        
        # Verify add event
        assert len(added_entities) == 1
        assert added_entities[0][0] == entity
        
        # Replace health component
        entity.replace(Health, 80, 100)
        
        # Verify update event - replacement triggers both remove and add internally
        assert len(updated_entities) == 1
        assert updated_entities[0][0] == entity
        # Note: replace operation internally triggers remove and add events
        # So we expect 2 removed events: one for replace, one for actual remove
        
        # Remove health component
        entity.remove(Health)
        
        # Verify remove events - should have 2: one from replace, one from remove
        assert len(removed_entities) == 2
        assert removed_entities[0][0] == entity
        assert removed_entities[1][0] == entity

    def test_multiple_contexts_isolation(self):
        """Test that multiple contexts are properly isolated."""
        context1 = Context()
        context2 = Context()
        
        # Create entities in different contexts
        entity1 = context1.create_entity()
        entity1.add(Position, 0, 0)
        
        entity2 = context2.create_entity()
        entity2.add(Position, 10, 10)
        
        # Verify isolation
        assert context1.has_entity(entity1)
        assert not context1.has_entity(entity2)
        assert context2.has_entity(entity2)
        assert not context2.has_entity(entity1)
        
        # Groups should be separate
        group1 = context1.get_group(Matcher(Position))
        group2 = context2.get_group(Matcher(Position))
        
        assert len(group1.entities) == 1
        assert len(group2.entities) == 1
        assert entity1 in group1.entities
        assert entity2 in group2.entities
        assert entity1 not in group2.entities
        assert entity2 not in group1.entities

    def test_entity_reuse_maintains_group_consistency(self):
        """Test that entity reuse maintains group consistency."""
        context = Context()
        
        # Create and destroy entity
        entity = context.create_entity()
        entity.add(Health, 100, 100)
        
        health_group = context.get_group(Matcher(Health))
        assert len(health_group.entities) == 1
        
        context.destroy_entity(entity)
        assert len(health_group.entities) == 0
        
        # Reuse entity with different components
        reused_entity = context.create_entity()
        assert reused_entity is entity  # Same object
        
        # Add different component
        reused_entity.add(Position, 5, 5)
        
        position_group = context.get_group(Matcher(Position))
        
        # Health group should still be empty
        assert len(health_group.entities) == 0
        # Position group should have the reused entity
        assert len(position_group.entities) == 1
        assert reused_entity in position_group.entities

    def test_performance_scenario(self):
        """Test performance scenario with many entities and operations."""
        context = Context()
        entities = []
        
        # Create many entities
        for i in range(100):
            entity = context.create_entity()
            entity.add(Position, i, i)
            if i % 2 == 0:
                entity.add(Health, 100, 100)
            if i % 3 == 0:
                entity.add(Velocity, 1, 1)
            entities.append(entity)
        
        # Create groups
        all_entities = context.get_group(Matcher(Position))
        living_entities = context.get_group(Matcher(Health))
        moving_entities = context.get_group(Matcher(Velocity))
        mobile_living = context.get_group(Matcher(Health, Velocity))
        
        # Verify counts
        assert len(all_entities.entities) == 100
        assert len(living_entities.entities) == 50  # every other entity
        assert len(moving_entities.entities) == 34  # every third entity (0, 3, 6, ..., 99)
        assert len(mobile_living.entities) == 17  # entities divisible by both 2 and 3 (i.e., by 6)
        
        # Perform bulk operations
        for i, entity in enumerate(entities[:50]):
            if entity.has(Health):
                entity.replace(Health, 50, 100)  # Damage half health
        
        # Destroy some entities
        for entity in entities[90:]:
            context.destroy_entity(entity)
        
        # Verify final state
        assert len(all_entities.entities) == 90
        assert len(context.entities) == 90
