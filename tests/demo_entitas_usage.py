"""
Demo script showing how to use the entitas Entity and Context classes.
This demonstrates the basic usage patterns tested in our test suite.
"""

from src.multi_agents_game.entitas import Context, Matcher
from tests.unit.test_components import Position, Velocity, Health, Name, Score


def main() -> None:
    """Demo of entitas Entity and Context usage."""
    print("=== Entitas Entity-Context Demo ===\n")

    # Create a context (world)
    context = Context()
    print(f"Created context: {context}")

    # Create entities
    print("\n1. Creating entities...")
    player = context.create_entity()
    enemy1 = context.create_entity()
    enemy2 = context.create_entity()
    projectile = context.create_entity()

    print(f"Created {len(context.entities)} entities")

    # Add components to entities
    print("\n2. Adding components...")

    # Player: positioned, alive, named, has score
    player.add(Position, 0, 0)
    player.add(Health, 100, 100)
    player.add(Name, "Hero")
    player.add(Score, 0)
    print(f"Player: {player}")

    # Enemies: positioned and alive
    enemy1.add(Position, 10, 10)
    enemy1.add(Health, 50, 50)
    enemy1.add(Name, "Goblin")
    print(f"Enemy 1: {enemy1}")

    enemy2.add(Position, 20, 20)
    enemy2.add(Health, 30, 30)
    enemy2.add(Name, "Orc")
    print(f"Enemy 2: {enemy2}")

    # Projectile: positioned and moving
    projectile.add(Position, 5, 5)
    projectile.add(Velocity, 10, 0)
    print(f"Projectile: {projectile}")

    # Create groups to query entities
    print("\n3. Creating groups...")

    # All living entities (have health)
    living_entities = context.get_group(Matcher(Health))
    print(f"Living entities: {len(living_entities.entities)}")
    for entity in living_entities.entities:
        health = entity.get(Health)
        name = entity.get(Name) if entity.has(Name) else None
        print(
            f"  - {name.value if name else 'Unnamed'}: {health.value}/{health.max_value} HP"
        )

    # All moving entities (have velocity)
    moving_entities = context.get_group(Matcher(Velocity))
    print(f"\nMoving entities: {len(moving_entities.entities)}")
    for entity in moving_entities.entities:
        pos = entity.get(Position)
        vel = entity.get(Velocity)
        print(f"  - At ({pos.x}, {pos.y}) moving ({vel.dx}, {vel.dy})")

    # Entities with both position and health (living positioned entities)
    living_positioned = context.get_group(Matcher(Position, Health))
    print(f"\nLiving positioned entities: {len(living_positioned.entities)}")

    # Entities that are NOT moving (don't have velocity)
    stationary = context.get_group(Matcher(Position, none_of=(Velocity,)))
    print(f"Stationary entities: {len(stationary.entities)}")

    # Simulate some game events
    print("\n4. Simulating game events...")

    # Projectile hits enemy1
    print("Projectile hits enemy1!")

    # Move projectile
    old_pos = projectile.get(Position)
    projectile.replace(Position, old_pos.x + 5, old_pos.y)

    # Damage enemy1
    old_health = enemy1.get(Health)
    new_health_value = max(0, old_health.value - 20)
    enemy1.replace(Health, new_health_value, old_health.max_value)

    print(f"Enemy1 health: {old_health.value} -> {new_health_value}")

    # Check if enemy1 died
    if new_health_value <= 0:
        print("Enemy1 died! Removing from game...")
        context.destroy_entity(enemy1)

        # Player gets score
        old_score = player.get(Score)
        player.replace(Score, old_score.value + 100)
        print(f"Player score: {old_score.value} -> {player.get(Score).value}")

    # Destroy projectile after hit
    context.destroy_entity(projectile)

    # Show final state
    print("\n5. Final state...")
    print(f"Context: {context}")
    print(f"Living entities: {len(living_entities.entities)}")
    print(f"Moving entities: {len(moving_entities.entities)}")

    for entity in context.entities:
        components = []
        if entity.has(Name):
            components.append(f"Name: {entity.get(Name).value}")
        if entity.has(Position):
            pos = entity.get(Position)
            components.append(f"Pos: ({pos.x}, {pos.y})")
        if entity.has(Health):
            health = entity.get(Health)
            components.append(f"HP: {health.value}/{health.max_value}")
        if entity.has(Score):
            components.append(f"Score: {entity.get(Score).value}")
        if entity.has(Velocity):
            vel = entity.get(Velocity)
            components.append(f"Vel: ({vel.dx}, {vel.dy})")

        print(f"  {entity._creation_index}: {', '.join(components)}")


if __name__ == "__main__":
    main()
