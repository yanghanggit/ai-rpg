# AWS 权限管理与服务架构指南

## 核心概念解析

### 1. Root 账号（根账号）

**定义**: AWS账户的最高权限持有者，拥有对所有AWS服务和资源的完全访问权限。

**特点**:

- 使用邮箱地址作为登录凭证
- 具有无限制的权限，包括账单和账户管理
- 无法被删除或限制权限
- 能够创建和管理所有其他用户和角色

**安全建议**:

- 仅用于初始设置和紧急情况
- 必须启用多因素认证(MFA)
- 日常操作不应使用Root账号

### 2. IAM用户（Identity and Access Management User）

**定义**: 在AWS账户内创建的具有特定权限的实体，代表真实的人员或应用程序。

**特点**:

- 拥有独立的登录凭证（用户名/密码或访问密钥）
- 权限通过IAM策略精确控制
- 可以分配到多个用户组
- 支持编程式访问和控制台访问

**权限管理**:

- 通过IAM策略附加权限
- 遵循最小权限原则
- 可以临时或永久授权

### 3. Role 角色

**定义**: 一组权限的集合，可以被临时假设（assume）来获得特定权限。

**特点**:

- 不与特定用户绑定
- 临时性权限授予
- 常用于跨账户访问或服务间调用
- 支持委托和信任关系

**使用场景**:

- EC2实例访问其他AWS服务
- 跨账户资源访问
- 联合身份验证
- 应用程序临时权限提升

## 三者关系图

```text
Root 账号 (最高权限)
    ├── 创建和管理 IAM用户
    ├── 创建和管理 Role角色
    └── 设置账户级别策略

IAM用户 (具体人员/应用)
    ├── 可以假设(assume) Role角色
    ├── 拥有长期凭证
    └── 权限通过策略控制

Role角色 (权限集合)
    ├── 被IAM用户假设
    ├── 被AWS服务使用
    └── 提供临时凭证
```

## 公司权限分配建议

### CEO 权限配置

**实现方式**: CEO直接控制Root账号，同时也可以拥有一个日常使用的IAM用户

**Root账号管理**:

- 持有Root账号的完全控制权
- 负责账户的最高级别决策
- 管理计费和账户设置

**CEO日常IAM用户权限** (推荐创建单独的IAM用户用于日常操作):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "iam:*",
                "organizations:*",
                "billing:*",
                "support:*",
                "trustedadvisor:*",
                "cloudtrail:*"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "s3:ListAllMyBuckets",
                "lambda:ListFunctions",
                "apigateway:GET",
                "cloudwatch:*"
            ],
            "Resource": "*"
        }
    ]
}
```

**权限特点**:

- ✅ 完全的IAM管理权限（创建/删除用户、角色）
- ✅ 组织和账单管理权限
- ✅ 所有服务的只读权限（监督用途）
- ⚠️ 限制对生产资源的直接操作权限（委托给CTO管理）

### CTO 权限配置

**实现方式**: Root账号为CTO创建一个IAM用户，并附加管理员级别的权限策略

**技术管理权限**:

- 完整的技术资源管理权限
- 开发和部署流程控制
- 基础设施架构决策

**具体实施步骤**:

1. **Root账号操作**: 登录Root账号创建CTO的IAM用户
2. **权限策略附加**: 为CTO用户附加预定义的管理员策略或自定义策略
3. **访问凭证**: 为CTO用户创建访问密钥和控制台密码
4. **MFA设置**: 强制启用多因素认证

**推荐的IAM策略配置**:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:*",
                "s3:*",
                "lambda:*",
                "apigateway:*",
                "cognito:*",
                "transcribe:*",
                "amplify:*",
                "cloudformation:*",
                "iam:ListRoles",
                "iam:PassRole",
                "iam:CreateRole",
                "iam:AttachRolePolicy",
                "logs:*",
                "monitoring:*"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Deny",
            "Action": [
                "iam:DeleteUser",
                "iam:CreateAccessKey",
                "organizations:*",
                "billing:*"
            ],
            "Resource": "*"
        }
    ]
}
```

**权限边界说明**:

- ✅ 允许: 管理所有技术资源和服务
- ✅ 允许: 创建和管理服务角色
- ❌ 禁止: 删除IAM用户（防止误删）
- ❌ 禁止: 管理组织和账单（保留给CEO）

**与Root账号的关系**:

- CTO是由Root账号创建的IAM用户，不是Root账号本身
- CTO无法修改Root账号的权限或删除Root账号
- CTO可以管理其他开发人员的IAM用户和权限
- 在紧急情况下，Root账号可以撤销或修改CTO的权限

### 组织架构建议

```text
Root账号 (CEO控制)
├── 管理员组 (CTO等高级技术人员)
├── 开发者组 (日常开发权限)
├── 只读组 (监控和审计人员)
└── 服务Role (各种AWS服务使用)
```

这种权限架构确保了安全性、可管理性和合规性的平衡，同时支持快速的业务发展和技术创新。
