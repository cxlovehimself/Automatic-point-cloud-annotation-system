# PointCloud AI Backend

点云标注与 AI 语义分割系统后端，基于 FastAPI 提供用户认证、点云上传、异步 AI 推理、处理历史、数据集保存和支付宝会员支付等接口。

## 毕业设计论文写作参考

本项目是一个面向三维点云数据处理与智能标注场景的后端系统，主要用于支持前端完成点云文件上传、AI 语义分割、结果文件生成、处理历史管理、标注数据集保存以及会员支付等功能。系统以 FastAPI 作为 Web 服务框架，结合 SQLModel 进行数据库建模与持久化管理，使用 Celery 和 Redis 实现耗时 AI 推理任务的异步处理，并通过 Open3D、Open3D-ML、PyTorch 和 RandLA-Net 模型完成室内外点云场景的语义分割。

从毕业设计角度看，该系统可以描述为“基于深度学习的点云智能标注与管理平台后端”。它不仅提供普通业务系统所需的用户注册、登录、鉴权、历史记录等功能，还将点云语义分割模型集成到 Web 后端中，使用户可以通过浏览器上传点云文件，并异步获取 AI 处理结果。系统重点解决了点云文件体量较大、AI 推理耗时较长、前端请求不能长时间阻塞、处理结果需要长期保存和管理等问题。

## 系统总体设计

系统采用分层架构设计，主要分为接口层、业务服务层、数据访问层、AI 推理层和任务调度层。

- 接口层由 `routers/` 目录中的 FastAPI 路由组成，负责接收前端请求、参数校验、权限校验和统一响应。
- 业务服务层由 `services/` 目录组成，负责用户管理、历史记录、邮件验证码、支付订单和 AI 推理等核心业务逻辑。
- 数据访问层基于 SQLModel 和 SQLAlchemy，通过 `database.py` 管理数据库连接，通过 `models.py` 定义用户、订单、历史记录等数据表结构。
- AI 推理层封装在 `services/ai_engine.py` 中，负责加载室内和室外点云语义分割模型，并对上传的 `.ply`、`.txt`、`.bin` 等点云文件进行处理。
- 任务调度层由 Celery Worker 和 Redis 组成，用于把耗时的点云推理任务从主 Web 服务中拆分出来，避免接口长时间阻塞。

## 核心功能模块

- 用户认证模块：支持用户注册、登录、JWT Token 签发、当前用户信息获取、修改密码、邮箱验证码重置密码等功能。
- 点云处理模块：支持上传点云文件，选择室内、室外或自动识别场景类型，并提交 AI 语义分割任务。
- 异步任务模块：使用 Celery 将 AI 推理任务放入后台队列，前端可通过任务 ID 查询任务状态和处理结果。
- 历史记录模块：在 AI 处理完成后保存用户的处理历史，包括原始文件名、场景类型、结果文件访问地址和完成时间。
- 数据集管理模块：支持保存前端人工标注后的点云数据，为后续模型训练或数据管理提供基础。
- 支付模块：集成支付宝沙箱支付，支持创建会员订单、处理异步回调、更新用户会员状态和会员到期时间。
- 邮件服务模块：用于发送验证码和会员开通通知，提高系统完整性和用户体验。

## 点云 AI 推理流程

1. 用户登录后，通过前端上传点云文件，并选择 `indoor`、`outdoor` 或 `auto` 场景类型。
2. 后端接收文件后，将原始文件保存到 `data/uploads/` 目录，并生成唯一文件名避免冲突。
3. 后端创建 Celery 异步任务，立即向前端返回 `task_id`，避免请求阻塞。
4. Celery Worker 从 Redis 队列中取出任务，调用 `PointCloudAIEngine` 加载或复用 AI 模型。
5. AI 引擎读取点云数据，进行格式解析、场景判断、降采样、分块推理、标签还原和颜色映射。
6. 推理完成后，系统将结果点云保存到 `data/outputs/` 目录，并生成可访问的结果 URL。
7. 系统将本次处理记录写入数据库，前端可通过历史记录接口查看或删除记录。

## 可写入论文的技术特点

- 前后端分离：后端通过 RESTful API 为前端提供统一的数据接口，便于系统扩展和维护。
- 异步任务处理：通过 Celery 和 Redis 将 AI 推理任务后台化，解决深度学习推理耗时较长导致接口阻塞的问题。
- 双场景模型支持：系统同时预留室内 S3DIS 和室外 SemanticKITTI 两类点云场景配置，可根据用户选择或点云尺度自动判断场景。
- 大规模点云处理：针对点云数量较大的情况，系统设计了体素降采样、统计滤波、分块推理和标签还原流程。
- 统一数据建模：使用 SQLModel 同时承担数据库 ORM 模型和接口数据模型的职责，减少重复代码。
- 认证与权限控制：基于 JWT 实现用户登录态管理，并结合会员状态限制部分 AI 处理能力。
- 支付闭环：集成支付宝订单创建、异步回调验签、订单状态更新和会员有效期延长逻辑，形成较完整的商业化功能闭环。
- 结果可追溯：每次点云处理完成后都会保存历史记录，便于用户查看、下载和管理处理结果。

## 论文中可使用的系统描述

本系统设计并实现了一个点云智能标注平台的后端服务，主要面向三维点云数据的上传、处理、语义分割和结果管理需求。系统采用 FastAPI 构建 RESTful 接口，使用 SQLModel 完成用户、订单和历史记录等数据表建模，并结合 MySQL 数据库实现业务数据持久化。针对点云语义分割任务计算量大、执行时间长的特点，系统引入 Celery 异步任务队列和 Redis 消息中间件，将 AI 推理过程从主请求链路中拆分出来，提高了接口响应速度和系统稳定性。

在 AI 处理方面，系统基于 Open3D、Open3D-ML 和 PyTorch 集成 RandLA-Net 点云语义分割模型，支持室内和室外两类典型点云场景。系统能够读取多种点云文件格式，并通过自动场景判断、点云降采样、分块推理、标签投票和颜色映射等步骤生成可视化的语义分割结果。处理完成后，后端将结果文件保存为 `.ply` 格式，并向前端返回结果访问地址，同时将任务信息写入历史记录表，方便用户后续查看和下载。

此外，系统还实现了用户认证、密码加密、邮箱验证码、会员支付、订单回调和数据集保存等辅助功能，使平台不仅具备 AI 推理能力，还具有完整的用户管理和业务管理能力。整体上，该系统体现了 Web 后端开发、数据库设计、异步任务调度、深度学习模型集成和点云数据处理等多项技术的综合应用。

## 项目结构

```text
.
├── main.py                    # FastAPI 应用入口，注册路由、CORS、静态文件和 AI 引擎生命周期
├── worker.py                  # Celery Worker，执行点云 AI 推理任务
├── database.py                # 数据库连接、SQLModel 初始化和 Session 依赖
├── models.py                  # SQLModel 数据表模型与请求/响应模型
├── dependencies.py            # 登录用户鉴权依赖
├── security.py                # 密码加密、JWT 签发与 Token 解析
├── response.py                # 统一响应结构
├── routers/
│   ├── auth.py                # 注册、登录、用户信息、修改/重置密码
│   ├── task.py                # 点云上传、AI 任务提交、任务状态查询
│   ├── history.py             # 历史记录查询与删除
│   ├── dataset.py             # 标注数据集保存
│   └── payment.py             # 支付宝订单创建、回调、订单状态查询
├── services/
│   ├── ai_engine.py           # Open3D-ML / RandLA-Net 点云语义分割引擎
│   ├── crud_user.py           # 用户相关数据库操作
│   ├── crud_history.py        # 历史记录相关数据库操作
│   ├── email_service.py       # 邮件验证码发送与校验
│   ├── notification_service.py # VIP 通知邮件
│   └── payment_service.py     # 支付宝订单与回调处理
├── configs/
│   ├── indoor.yml             # 室内点云模型配置
│   └── outdoor.yml            # 室外点云模型配置
├── certs/                     # 支付宝公钥、应用私钥证书
├── data/
│   ├── uploads/               # 上传的原始点云文件
│   └── outputs/               # AI 处理后的点云结果文件
├── storage/datasets/          # 保存的标注数据集
├── test_main.http             # 接口测试请求示例
└── install-release-cpolar.sh  # cpolar 安装脚本
```

## 技术栈

- Web 框架：FastAPI
- 数据库 ORM：SQLModel / SQLAlchemy
- 数据库：通过 `DB_URL` 配置，当前代码适合连接 MySQL 等关系型数据库
- 认证：JWT、OAuth2 Bearer Token、Passlib bcrypt 密码哈希
- 异步任务：Celery
- 消息队列与结果后端：Redis
- 点云处理与 AI 推理：Open3D、Open3D-ML、PyTorch、NumPy、RandLA-Net
- 支付：支付宝开放平台 SDK
- 邮件：Python 标准库 `smtplib`
- 配置管理：`.env` 环境变量、YAML 模型配置文件

## 项目运行环境

- 操作系统：Windows + WSL2 Ubuntu
- Shell 环境：bash
- Python 运行环境：Linux / Ubuntu 子系统
- 项目路径示例：`/home/cx/Bishe_rear`
- Python 版本：建议 Python 3.9 及以上
- 数据库环境：MySQL 5.7 / 8.0
- 缓存与消息队列：Redis
- AI 推理环境：PyTorch、Open3D、Open3D-ML
- 开发工具：Cursor / VS Code / PyCharm

项目运行在 WSL2 Ubuntu 环境中，后端服务、Celery Worker、Redis 和 Python 依赖均在 Linux 子系统内启动。若使用 Windows 作为宿主系统，建议统一在 WSL2 终端中安装依赖、启动服务和运行项目，避免 Windows 与 Linux 路径差异导致文件访问异常。

## 需要安装的包

建议先创建虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
```

安装项目运行依赖：

```bash
pip install fastapi uvicorn sqlmodel sqlalchemy pymysql python-dotenv "pydantic[email]" python-multipart "passlib[bcrypt]" PyJWT python-jose celery redis numpy torch open3d alipay-sdk-python cryptography
```

依赖说明：

- `fastapi`、`uvicorn`：启动后端 HTTP 服务。
- `sqlmodel`、`sqlalchemy`、`pymysql`：数据库模型与 MySQL 连接。
- `python-dotenv`：读取 `.env` 中的数据库、支付宝、邮件等配置。
- `pydantic[email]`：支持邮箱字段校验。
- `python-multipart`：支持文件上传和表单解析。
- `passlib[bcrypt]`、`PyJWT`、`python-jose`：密码加密和 JWT 鉴权。
- `celery`、`redis`：后台 AI 推理任务队列。
- `numpy`、`torch`、`open3d`：点云读取、处理和深度学习推理。
- `alipay-sdk-python`、`cryptography`：支付宝支付和 RSA 签名验证。

## 运行前准备

1. 配置 `.env`：

```env
DB_URL=mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
JWT_SECRET_KEY=至少32位的随机JWT签名密钥
ALIPAY_APP_ID=你的支付宝应用ID
ALIPAY_RETURN_URL=支付完成后的同步跳转地址
ALIPAY_NOTIFY_URL=支付宝异步回调地址
ALIPAY_SELLER_ID=支付宝商户ID（可选，配置后回调会校验）
ALIPAY_SELLER_EMAIL=支付宝商户邮箱（可选，配置后回调会校验）
```

2. 启动 Redis：

```bash
redis-server
```

3. 准备模型文件：

```text
ckpt_00300.pth
randlanet_semantickitti_202201071330utc.pth
configs/indoor.yml
configs/outdoor.yml
```

4. 准备支付宝证书：

```text
certs/alipay_private_key.pem
certs/alipay_public_key.pem
```

## 启动方式

启动 FastAPI 服务：

```bash
uvicorn main:app --reload
```

启动 Celery Worker：

```bash
celery -A worker.celery_app worker --loglevel=info
```

服务启动后，接口文档默认可访问：

```text
http://127.0.0.1:8000/docs
```
