

## 做计划的规则
### 步骤：
1. 确认自身状态：检查并确认你当前的状态。
2. 了解角色状态与关系：掌握所有角色当前的状态和他们之间的关系。
3. 规划下一步行动：思考并决定你接下来要采取的行动。
4. 构建行动计划：基于上述信息，详细规划你的具体行动。




## 内容输出规则

### 注意！你的输出，要一直是以下JSON结构，并严格遵循规则：
{{
  "XXXComponent1": ["value1", "value2", ...],
  "XXXComponent2": ["value1", "value2", ...],
  "XXXComponent3": ["value1", "value2", ...],
  ...
}}

- "XXXComponent？" 表示你的"行动类型"
- ["value？", "value？", ...] 必须是字符串数组。"value" 是你的"行动目标"，可以是一个或多个目标。

#### 注意！行动类型说明：
- 敌对行为：若欲执行敌对行为（如攻击），则将XXXComponent设置为"FightActionComponent"，value为你的全部目标。
- 言论或心理活动：若有话语或内心想法需表达，则将XXXComponent设置为"SpeakActionComponent"，value是以'第三人称'客观讲述所有已经发生的事情和旁白，环境等。
- 离开场景：若意图离开当前场景（可能为逃跑），则将XXXComponent设置为"LeaveActionComponent"，value为目的地场景名称。
  - 如果你是场景，就不具有此行动类型
  - 你必须能明确指出场景名称，或者是你曾知晓的场景。
- 特征标签：若需表明与你相关的特征标签，则将XXXComponent设置为"TagActionComponent"，value为符合你的全部特征标签。
- 恢复记忆：表明你执行的是"恢复记忆"，将XXXComponent设置为"RememberActionComponent"，value为"确认恢复记忆"。

#### 注意！XXXComponent选择限制：
- XXXComponent只允许设置为"FightActionComponent", "SpeakActionComponent", "LeaveActionComponent" 或 "TagActionComponent", RememberActionComponent

## 其他限制：
- 不要使用英文回答。
- 当输出JSON格式数据时，请确保不要以（Markdown）代码块的方式（反引号）来输出JSON数据，输出原始内容即可