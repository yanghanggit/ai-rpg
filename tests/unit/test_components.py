"""
Test components for entitas testing.
These are simple namedtuple-based components used in tests.
"""

from collections import namedtuple

# Basic components for testing
Position = namedtuple("Position", ["x", "y"])
Velocity = namedtuple("Velocity", ["dx", "dy"])
Health = namedtuple("Health", ["value", "max_value"])
Name = namedtuple("Name", ["value"])
Age = namedtuple("Age", ["value"])
Score = namedtuple("Score", ["value"])
Damage = namedtuple("Damage", ["value"])
Defense = namedtuple("Defense", ["value"])

# Component without fields for edge case testing
Marker = namedtuple("Marker", [])

# Multi-field component
Transform = namedtuple("Transform", ["x", "y", "rotation", "scale"])
