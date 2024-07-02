# Description: 游戏构建器数据的JSON Schema
GAME_BUILDER_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "players": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "actor": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        },
                        "required": ["name"]
                    },
                    "props": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "count": {
                                    "type": "string",
                                    "pattern": "^\d+$"  # 确保count是数字字符串
                                }
                            },
                            "required": ["name", "count"]
                        }
                    }
                },
                "required": ["actor", "props"]
            }
        },
        "actors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "actor": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        },
                        "required": ["name"]
                    },
                    "props": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "count": {
                                    "type": "string",
                                    "pattern": "^\d+$"
                                }
                            },
                            "required": ["name", "count"]
                        }
                    }
                },
                "required": ["actor", "props"]
            }
        },
        "stages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "props": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "count": {
                                            "type": "string",
                                            "pattern": "^\d+$"
                                        }
                                    },
                                    "required": ["name", "count"]
                                }
                            },
                            "actors": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"}
                                    },
                                    "required": ["name"]
                                }
                            }
                        },
                        "required": ["name", "props", "actors"]
                    }
                },
                "required": ["stage"]
            }
        },
        "world_systems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "world_system": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        },
                        "required": ["name"]
                    }
                },
                "required": ["world_system"]
            }
        },
        "database": {
            "type": "object",
            "properties": {
                "actors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "actor": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "codename": {"type": "string"},
                                    "url": {"type": "string"}
                                    # 添加更多属性
                                },
                                "required": ["name", "codename", "url"]
                            }
                        },
                        "required": ["actor"]
                    }
                },
                # 定义stages, props, systems等
            },
            "required": ["actors"]  # 根据需要添加更多
        },
        "about_game": {"type": "string"},
        "version": {"type": "string"}
    },
    "required": ["players", "actors", "stages", "world_systems", "database", "about_game", "version"]
}