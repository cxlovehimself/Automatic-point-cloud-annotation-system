# 系统详细设计相关模块

本文档整理后端系统中异步任务调度模块、点云 AI 推理模块、支付与会员管理模块、邮件验证码与通知模块的详细设计内容，可作为毕业设计论文“系统详细设计”章节的参考材料。

## 5.5 异步任务调度模块

### 5.5.1 实现详解

异步任务调度模块主要用于处理点云 AI 推理这类耗时较长的任务。由于点云数据通常体量较大，若直接在 HTTP 请求中完成模型推理，会导致接口响应时间过长，影响用户体验。因此系统采用 Celery 作为异步任务框架，Redis 作为消息队列和任务结果存储后端。

当用户上传点云文件后，后端不会立即在接口中执行完整推理流程，而是将任务提交到 Celery 队列中，并立即返回任务编号。Celery Worker 在后台监听任务队列，取出任务后调用 AI 推理模块完成点云处理。处理结束后，任务结果会被写入 Redis，前端可以通过任务编号查询任务状态和处理结果。

该模块对应代码文件为 `worker.py`。其中 Redis 的 0 号数据库作为消息代理，Redis 的 1 号数据库作为结果后端。

### 5.5.2 操作说明

用户上传点云文件后，系统会生成一个异步任务。前端收到任务编号后，可以进入任务等待页面，并定时请求任务状态接口。当任务处于等待状态时，页面显示排队提示；当任务处于处理中时，页面显示 AI 正在处理；当任务成功完成时，前端获取结果文件地址并进入点云结果展示页面。

### 5.5.3 关键代码

```python
celery_app = Celery(
    "ai_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)
celery_app.conf.update(task_track_started=True)
```

该代码用于创建 Celery 应用，并配置 Redis 作为任务队列和结果存储后端。`task_track_started=True` 用于记录任务是否已经开始执行，便于前端根据任务状态进行进度展示。

```python
@celery_app.task(name="run_ai_segmentation")
def run_ai_segmentation_task(
    input_path: str,
    output_path: str,
    scene_type: str,
    user_id: int,
    safe_filename: str,
    result_url: str
):
    start_time = time.time()

    if not ai_engine.is_loaded:
        ai_engine.initialize(
            indoor_yaml="./configs/indoor.yml",
            indoor_ckpt="./ckpt_00300.pth",
            outdoor_yaml="./configs/outdoor.yml",
            outdoor_ckpt="./randlanet_semantickitti_202201071330utc.pth"
        )

    metrics = ai_engine.process_pointcloud(input_path, output_path, scene_type)
    actual_scene = metrics.get("scene_type_detected", scene_type)
    total_time = metrics.get(
        "total_process_time_sec",
        round(time.time() - start_time, 2)
    )

    with Session(engine) as db:
        crud_history.create_history_record(
            db=db,
            user_id=user_id,
            original_filename=safe_filename,
            scene_type=actual_scene,
            result_url=result_url
        )

    return {
        "result_url": result_url,
        "scene_type": actual_scene,
        "total_process_time_sec": total_time,
        "metrics": metrics
    }
```

该代码是异步任务调度模块的核心逻辑。Worker 首先判断 AI 引擎是否加载，若未加载则初始化模型；随后调用点云处理函数完成推理；最后将结果写入历史记录，并返回结果地址、场景类型、处理耗时和统计指标。

### 5.5.4 前端对接说明

该模块与前端任务状态页面对应。前端需要保存后端返回的 `task_id`，并通过轮询方式查询任务状态。该设计使用户在等待 AI 处理时能够获得明确反馈，避免页面长时间无响应。

## 5.6 点云 AI 推理模块

### 5.6.1 实现详解

点云 AI 推理模块是系统的核心功能模块，主要负责完成点云语义分割任务。该模块基于 Open3D、Open3D-ML、PyTorch 和 RandLA-Net 模型实现，支持室内和室外两类点云场景。

系统在初始化阶段分别加载室内模型配置和室外模型配置。其中室内场景使用 S3DIS 数据集配置，室外场景使用 SemanticKITTI 数据集配置。推理过程中，系统会读取上传的点云文件，解析点坐标和颜色信息，并根据用户选择或自动判断结果确定点云场景类型。

对于大规模点云，系统采用降采样、统计滤波、分块推理和标签还原等方式降低计算压力。推理完成后，系统根据预测出的语义类别为点云赋予不同颜色，并保存为 `.ply` 格式结果文件，供前端进行三维可视化展示。

### 5.6.2 操作说明

用户上传点云文件后，AI 推理模块由后台 Worker 自动调用。用户无需直接操作该模块，只需要在上传时选择场景类型，例如室内、室外或自动识别。系统处理完成后会返回点云结果文件地址，前端根据该地址加载并展示语义分割后的点云。

### 5.6.3 关键代码

```python
def initialize(self, indoor_yaml, indoor_ckpt, outdoor_yaml, outdoor_ckpt):
    if self.is_loaded:
        return

    if os.path.exists(indoor_yaml) and os.path.exists(indoor_ckpt):
        cfg_in = _ml3d.utils.Config.load_from_file(indoor_yaml)
        self.pipelines["indoor"] = ml3d.pipelines.SemanticSegmentation(
            model=ml3d.models.RandLANet(**cfg_in.model),
            dataset=ml3d.datasets.S3DIS(**cfg_in.dataset),
            device=self.device,
            **cfg_in.pipeline
        )
        self.pipelines["indoor"].load_ckpt(ckpt_path=indoor_ckpt)

    if os.path.exists(outdoor_yaml) and os.path.exists(outdoor_ckpt):
        cfg_out = _ml3d.utils.Config.load_from_file(outdoor_yaml)
        self.pipelines["outdoor"] = ml3d.pipelines.SemanticSegmentation(
            model=ml3d.models.RandLANet(**cfg_out.model),
            dataset=ml3d.datasets.SemanticKITTI(**cfg_out.dataset),
            device=self.device,
            **cfg_out.pipeline
        )
        self.pipelines["outdoor"].load_ckpt(ckpt_path=outdoor_ckpt)

    self.is_loaded = True
```

该代码完成室内和室外两类模型的加载。系统根据配置文件创建 RandLA-Net 语义分割管线，并加载对应权重文件。

```python
if input_path.lower().endswith(".bin"):
    scan = np.fromfile(input_path, dtype=np.float32).reshape(-1, 4)
    points = scan[:, 0:3]
    colors = np.ones_like(points) * 0.5
elif input_path.lower().endswith(".txt"):
    pc_data = np.loadtxt(input_path)
    points = pc_data[:, 0:3]
    if pc_data.shape[1] >= 6:
        colors = pc_data[:, 3:6]
        if colors.max() > 1.0:
            colors /= 255.0
    else:
        colors = np.ones_like(points) * 0.5
else:
    pcd = o3d.io.read_point_cloud(input_path)
    points = np.asarray(pcd.points)
    colors = np.asarray(pcd.colors) if pcd.has_colors() else np.ones_like(points) * 0.5
```

该代码用于解析不同格式的点云文件，支持 `.bin`、`.txt` 和 Open3D 可读取的点云格式，并从文件中提取点坐标和颜色信息。

```python
if scene_type == "auto":
    x_span = np.max(points[:, 0]) - np.min(points[:, 0])
    y_span = np.max(points[:, 1]) - np.min(points[:, 1])
    z_span = np.max(points[:, 2]) - np.min(points[:, 2])
    max_span = max(x_span, y_span)

    if max_span > 1000.0:
        points = points / 1000.0
        x_span, y_span, z_span = x_span / 1000.0, y_span / 1000.0, z_span / 1000.0
        max_span = max(x_span, y_span)

    if z_span <= 6.0 and max_span <= 50.0:
        scene_type = "indoor"
    elif max_span > 30.0:
        scene_type = "outdoor"
    else:
        scene_type = "indoor"
```

该代码用于自动判断点云场景类型。系统根据点云在 X、Y、Z 方向的空间范围判断其更接近室内场景还是室外场景，并选择对应的推理模型。

```python
if total_points > 200000:
    temp_pcd = o3d.geometry.PointCloud()
    temp_pcd.points = o3d.utility.Vector3dVector(points)
    temp_pcd, _ = temp_pcd.remove_statistical_outlier(
        nb_neighbors=20,
        std_ratio=2.0
    )
    pcd_down = temp_pcd.voxel_down_sample(voxel_size=voxel_size)
    p_down = np.asarray(pcd_down.points)
else:
    p_down = points
```

该代码用于大规模点云降采样。通过统计滤波去除离群点，再使用体素降采样减少点数量，从而降低模型推理压力。

```python
for x in x_grids:
    for y in y_grids:
        idx_in_block = np.where(
            (p_down[:, 0] >= x) & (p_down[:, 0] < x + BLOCK_SIZE) &
            (p_down[:, 1] >= y) & (p_down[:, 1] < y + BLOCK_SIZE)
        )[0]
        if len(idx_in_block) < 10:
            continue

        p_block, c_block = p_down[idx_in_block], c_down[idx_in_block]
        f_block = None if scene_type == "outdoor" else c_block

        results = pipeline.run_inference({
            "point": p_block.astype(np.float32),
            "feat": f_block,
            "label": np.zeros((len(p_block),), dtype=np.int32)
        })
        block_pred = np.clip(results["predict_labels"], 0, len(colors_palette) - 1)

        for i, real_idx in enumerate(idx_in_block):
            down_vote_counter[real_idx, block_pred[i]] += 1
```

该代码是分块推理的核心。系统根据点云空间范围划分多个局部块，对每个点云块调用模型进行语义分割，并通过投票方式统计每个点的预测类别，提高分块推理结果的稳定性。

```python
pcd_down_labels = np.argmax(down_vote_counter, axis=1)

if total_points > 200000:
    kdtree = o3d.geometry.KDTreeFlann(pcd_down)
    for i in range(0, total_points, BATCH):
        batch_end = min(i + BATCH, total_points)
        for j in range(i, batch_end):
            _, idx, _ = kdtree.search_knn_vector_3d(points[j], 1)
            final_predictions[j] = pcd_down_labels[idx[0]]
else:
    final_predictions = pcd_down_labels

pcd_out = o3d.geometry.PointCloud()
pcd_out.points = o3d.utility.Vector3dVector(points)
pcd_out.colors = o3d.utility.Vector3dVector(colors_palette[final_predictions])
o3d.io.write_point_cloud(output_path, pcd_out)
```

该代码负责标签还原和结果保存。对于经过降采样的点云，系统使用 KDTree 最近邻搜索将降采样点的预测标签映射回原始点云；随后根据预测类别从颜色表中取出对应颜色，生成带有语义颜色的 `.ply` 点云文件。

### 5.6.4 前端对接说明

该模块对应前端的点云结果展示页面。后端生成结果文件后返回 `result_url`，前端通过该地址加载 `.ply` 文件，并在三维视图中展示语义分割结果。不同类别通过不同颜色区分，用户可以直观查看 AI 分割效果。

## 5.9 支付与会员管理模块

### 5.9.1 实现详解

支付与会员管理模块用于实现系统会员功能。系统集成支付宝沙箱支付，支持创建支付订单、生成支付链接、接收支付宝异步回调、验证支付结果、更新订单状态以及延长用户会员时间。

用户在前端点击开通会员后，后端会生成唯一订单号，并在数据库中创建待支付订单。随后系统调用支付宝 SDK 生成支付链接并返回给前端。用户完成支付后，支付宝会向系统回调接口发送支付结果，后端通过验签确认数据真实性，并更新订单和用户会员状态。

### 5.9.2 操作说明

用户进入会员页面后，点击开通会员按钮，系统生成支付链接。用户跳转到支付宝沙箱页面完成支付。支付成功后，后端收到支付宝回调并更新用户会员状态。前端再次查询用户信息或订单状态时，即可显示用户已开通会员。

### 5.9.3 关键代码

```python
alipay = AliPay(
    appid=APP_ID,
    app_notify_url=None,
    app_private_key_string=APP_PRIVATE_KEY,
    alipay_public_key_string=ALIPAY_PUBLIC_KEY,
    sign_type="RSA2",
    debug=True
)
```

该代码用于初始化支付宝 SDK，配置应用 ID、应用私钥、支付宝公钥和签名方式。

```python
def create_payment_order(db: Session, user_id: int, amount: str = "9.90", base_url: str = ""):
    random_str = uuid.uuid4().hex[:6]
    out_trade_no = f"ORDER_{int(time.time())}_{user_id}_{random_str}"

    new_order = Order(
        user_id=user_id,
        out_trade_no=out_trade_no,
        total_amount=amount,
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    order_string = alipay.api_alipay_trade_page_pay(
        out_trade_no=out_trade_no,
        total_amount=amount,
        subject="PointCloud Annotator Pro 包月会员",
        return_url=RETURN_URL,
        notify_url=NOTIFY_URL
    )

    payurl = f"https://openapi-sandbox.dl.alipaydev.com/gateway.do?{order_string}"
    return payurl, out_trade_no
```

该代码负责创建本地订单并生成支付宝支付链接。订单初始状态为 `pending`，表示等待支付。前端拿到支付链接后，可以引导用户跳转到支付宝页面完成付款。

```python
def process_callback(db: Session, data: dict):
    signature = data.pop("sign", None)
    if not alipay.verify(data, signature):
        return False

    if data.get("trade_status") in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        out_trade_no = data.get("out_trade_no")
        alipay_trade_no = data.get("trade_no")

        statement_order = select(Order).where(Order.out_trade_no == out_trade_no)
        order = db.exec(statement_order).first()

        if order and order.status == "pending":
            if float(data.get("total_amount", 0)) != float(order.total_amount):
                return False

            order.status = "paid"
            order.alipay_trade_no = alipay_trade_no
            db.add(order)

            statement_user = select(User).where(User.id == order.user_id)
            user = db.exec(statement_user).first()

            if user:
                user.is_subscribed = True
                now = datetime.now()
                if not user.vip_expire_time or user.vip_expire_time < now:
                    user.vip_expire_time = now + timedelta(days=30)
                else:
                    user.vip_expire_time = user.vip_expire_time + timedelta(days=30)
                db.add(user)

            db.commit()
        return True, user.email if user else None

    return False, None
```

该代码是支付回调处理的核心。系统先验证支付宝签名，再校验订单金额，最后更新订单状态和用户会员到期时间。该设计能够防止伪造回调和金额篡改，提高支付流程的安全性。

```python
@router.post("/callback")
async def alipay_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    body = await request.form()
    data = dict(body)

    is_success, user_email = payment_service.process_callback(db=db, data=data)

    if is_success:
        if user_email:
            background_tasks.add_task(send_vip_welcome_email, user_email)
        return "success"
    else:
        return "fail"
```

该代码是支付宝异步回调接口。支付成功后，系统不仅会更新订单和会员状态，还会通过 `BackgroundTasks` 添加后台通知任务，避免通知逻辑阻塞支付回调。

### 5.9.4 前端对接说明

该模块对应前端个人中心或会员开通页面。前端调用创建订单接口获取支付链接，引导用户完成支付，并通过订单状态接口查询支付结果。支付成功后，前端可刷新用户信息，展示会员状态和到期时间。

## 5.10 邮件验证码与通知模块

### 5.10.1 实现详解

邮件验证码与通知模块主要用于密码重置和会员通知。系统通过 SMTP 服务发送验证码邮件，并在内存中临时保存验证码和过期时间。用户提交验证码后，系统校验验证码是否存在、是否过期以及是否匹配。

此外，在会员支付成功后，系统会通过后台任务触发通知逻辑，避免通知过程阻塞支付回调接口。

### 5.10.2 操作说明

当用户忘记密码时，可以在前端输入邮箱并请求发送验证码。后端生成 6 位随机验证码并发送到用户邮箱。用户输入验证码和新密码后，后端校验验证码，校验通过后完成密码重置。

当用户支付会员成功后，系统会触发后台通知任务，用于提示会员开通成功。

### 5.10.3 关键代码

```python
def generate_and_store_code(email: str) -> str:
    code = str(random.randint(100000, 999999))
    OTP_STORE[email] = {
        "code": code,
        "expire": time.time() + 300
    }
    return code
```

该代码生成 6 位随机验证码，并设置 5 分钟有效期。

```python
def verify_code(email: str, code: str):
    record = OTP_STORE.get(email)
    if not record:
        return False, "验证码无效或未发送"
    if time.time() > record["expire"]:
        return False, "验证码已过期，请重新获取"
    if record["code"] != code:
        return False, "验证码错误"

    del OTP_STORE[email]
    return True, "校验通过"
```

该代码用于验证码校验。校验通过后立即删除验证码，避免同一验证码被重复使用。

```python
def send_real_email(receiver_email: str, code: str):
    sender = os.getenv("SMTP_SENDER")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = "smtp.qq.com"

    if not sender or not password:
        return False

    mail_msg = f"""
    <h3>CloudLabel Pro 安全中心</h3>
    <p>您正在尝试修改/重置密码。您的验证码是：
    <strong style="color: #58a6ff; font-size: 20px;">{code}</strong></p>
    <p>验证码在 5 分钟内有效。如果不是您本人的操作，请忽略此邮件。</p>
    """

    message = MIMEText(mail_msg, "html", "utf-8")
    message["From"] = formataddr(("CloudLabel Pro", sender))
    message["To"] = receiver_email
    message["Subject"] = Header("【验证码】密码重置验证", "utf-8")

    server = smtplib.SMTP_SSL(smtp_server, 465)
    server.login(sender, password)
    server.sendmail(sender, [receiver_email], message.as_string())
    server.quit()
    return True
```

该代码通过 SMTP SSL 协议发送 HTML 格式验证码邮件。系统从环境变量中读取邮箱账号和授权码，从而避免在代码中硬编码敏感信息。

```python
def send_vip_welcome_email(user_email: str):
    print(f"正在为 Pro 用户 {user_email} 分配独立 3D 渲染容器...")
    time.sleep(5)
    print(f"容器分配成功！已向 {user_email} 发送欢迎邮件！")
```

该代码表示会员开通后的后台通知逻辑。当前实现为模拟通知流程，主要用于展示支付成功后的异步处理机制。

### 5.10.4 前端对接说明

该模块对应前端忘记密码页面和会员通知功能。忘记密码页面需要调用发送验证码接口和重置密码接口；会员支付成功后，前端可在个人中心展示会员开通状态。该模块提高了系统账户安全性和用户体验。
