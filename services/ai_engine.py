import os
import torch
import numpy as np
import open3d as o3d
import open3d.ml as _ml3d
import open3d.ml.torch as ml3d
import time

class PointCloudAIEngine:
    def __init__(self):
        self.pipelines = {"indoor": None, "outdoor": None}
        self.is_loaded = False
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # === 室内外配色表 ===
        self.color_maps = {
            "indoor": np.array([ [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 0.0], [1.0, 0.0, 1.0], [0.4, 0.4, 1.0], [0.8, 0.8, 0.4], [0.6, 0.4, 0.8], [1.0, 0.0, 0.0], [0.8, 0.4, 0.4], [0.0, 0.8, 0.4], [0.8, 0.8, 0.8], [0.2, 0.2, 0.2] ]),
            "outdoor": np.array([
                [0.39, 0.59, 0.92], # 0: 汽车 (Car) - 浅蓝色
                [0.39, 0.20, 0.59], # 1: 自行车 (Bicycle) - 深紫色
                [0.12, 0.22, 0.35], # 2: 摩托车 (Motorcycle) - 藏青色
                [0.31, 0.12, 0.31], # 3: 卡车 (Truck) - 紫褐色
                [0.39, 0.59, 0.59], # 4: 其他车辆 (Other Vehicle) - 蓝灰色
                [1.00, 0.12, 0.12], # 5: 行人 (Person) - 红色
                [1.00, 0.16, 0.78], # 6: 骑行者 (Bicyclist) - 艳粉色
                [0.59, 0.12, 0.35], # 7: 摩托骑手 (Motorcyclist) - 玫红色
                [1.00, 0.00, 1.00], # 8: 道路 (Road) - 粉紫色
                [1.00, 0.59, 1.00], # 9: 停车区 (Parking) - 浅粉色
                [0.29, 0.00, 0.29], # 10: 人行道 (Sidewalk) - 暗紫色
                [0.29, 0.00, 0.69], # 11: 其他地面 (Other Ground) - 蓝紫色
                [0.00, 0.78, 1.00], # 12: 建筑物 (Building) - 青色
                [0.20, 0.47, 0.20], # 13: 围栏 (Fence) - 深绿色
                [0.00, 0.69, 0.00], # 14: 植被 (Vegetation) - 亮绿色
                [0.53, 0.24, 0.00], # 15: 树干 (Trunk) - 棕色
                [0.59, 0.94, 0.31], # 16: 地形/草地 (Terrain) - 浅黄绿
                [1.00, 0.94, 0.59], # 17: 电线杆 (Pole) - 浅黄色
                [1.00, 0.00, 0.00]  # 18: 交通标志 (Traffic Sign) - 正红色
            ])
        }

    def initialize(self, indoor_yaml: str, indoor_ckpt: str, outdoor_yaml: str, outdoor_ckpt: str):
        if self.is_loaded: return
        print(f"🚀 [AI Engine Pro] 开始在 {self.device} 上加载双场景模型...")
        try:
            if os.path.exists(indoor_yaml) and os.path.exists(indoor_ckpt):
                cfg_in = _ml3d.utils.Config.load_from_file(indoor_yaml)
                self.pipelines['indoor'] = ml3d.pipelines.SemanticSegmentation(
                    model=ml3d.models.RandLANet(**cfg_in.model), dataset=ml3d.datasets.S3DIS(**cfg_in.dataset), device=self.device, **cfg_in.pipeline)
                self.pipelines['indoor'].load_ckpt(ckpt_path=indoor_ckpt)
                print("✅ 室内模型 (Indoor) 加载成功")

            if os.path.exists(outdoor_yaml) and os.path.exists(outdoor_ckpt):
                cfg_out = _ml3d.utils.Config.load_from_file(outdoor_yaml)
                self.pipelines['outdoor'] = ml3d.pipelines.SemanticSegmentation(
                    model=ml3d.models.RandLANet(**cfg_out.model), dataset=ml3d.datasets.SemanticKITTI(**cfg_out.dataset), device=self.device, **cfg_out.pipeline)
                self.pipelines['outdoor'].load_ckpt(ckpt_path=outdoor_ckpt)
                print("✅ 室外模型 (Outdoor) 加载成功")

            self.is_loaded = True
            print("🎉 AI Engine Pro 双引擎初始化完成.")
        except Exception as e:
            raise RuntimeError(f"模型初始化失败: {str(e)}")

    def process_pointcloud(self, input_path: str, output_path: str, scene_type: str = "auto") -> dict:
        if not self.is_loaded: raise RuntimeError("AI 引擎未初始化")

        try:
            # === 1. 解析点云 ===
            print(f"📂 正在读取文件: {input_path}")
            
            if input_path.lower().endswith('.bin'):
                # 🚀 依然支持 KITTI .bin，但只取 XYZ，抛弃反射率
                scan = np.fromfile(input_path, dtype=np.float32).reshape(-1, 4)
                points = scan[:, 0:3]
                colors = np.ones_like(points) * 0.5 # 占位颜色
                
            elif input_path.lower().endswith('.txt'):
                pc_data = np.loadtxt(input_path)
                points = pc_data[:, 0:3]
                if pc_data.shape[1] >= 6:
                    colors = pc_data[:, 3:6]
                    if colors.max() > 1.0: colors /= 255.0
                else:
                    colors = np.ones_like(points) * 0.5
            else:
                pcd = o3d.io.read_point_cloud(input_path)
                points = np.asarray(pcd.points)
                colors = np.asarray(pcd.colors) if pcd.has_colors() else np.ones_like(points) * 0.5

            if len(points) == 0: raise ValueError("点云为空")
            total_points = len(points)

            # === 2. 场景嗅探 (Pro Max版: 加入单位自校准与 Z 轴高度校验) ===
            if scene_type == "auto":
                x_span = np.max(points[:, 0]) - np.min(points[:, 0])
                y_span = np.max(points[:, 1]) - np.min(points[:, 1])
                z_span = np.max(points[:, 2]) - np.min(points[:, 2])
                max_span = max(x_span, y_span)

                if max_span > 1000.0:
                    print(f"📏 [数据清洗] 检测到极大跨度({max_span:.1f})，推测单位为毫米，自动换算为米...")
                    points = points / 1000.0
                    x_span, y_span, z_span = x_span / 1000.0, y_span / 1000.0, z_span / 1000.0
                    max_span = max(x_span, y_span)

                if z_span <= 6.0 and max_span <= 50.0:
                    scene_type = "indoor"
                elif max_span > 30.0:
                    scene_type = "outdoor"
                else:
                    scene_type = "indoor"

                print(f"🤖 [Auto-Detect] 修正后物理跨度: XY面 {max_span:.1f}米, 高度Z {z_span:.1f}米 -> 判定为: 【{scene_type.upper()}】")

            pipeline = self.pipelines.get(scene_type)
            colors_palette = self.color_maps[scene_type]
            
            if scene_type == "outdoor":
                BLOCK_SIZE, BLOCK_OVERLAP = 50.0, 5.0
                voxel_size = 0.2 if total_points > 1000000 else 0.1
            else:
                BLOCK_SIZE, BLOCK_OVERLAP = 10.0, 2.0
                voxel_size = 0.05
            
            start_total_time = time.time()
            final_predictions = np.zeros(total_points, dtype=np.int32)

            # === 3. 智能防御性降采样 ===
            if total_points > 200000:
                print(f"🛡️ 启动降采样防御 (体素 {voxel_size}m)...")
                temp_pcd = o3d.geometry.PointCloud()
                temp_pcd.points = o3d.utility.Vector3dVector(points)
                pcd_down = temp_pcd.voxel_down_sample(voxel_size=voxel_size)
                p_down = np.asarray(pcd_down.points)
                c_down = np.asarray(pcd_down.colors) if pcd_down.has_colors() else np.ones_like(p_down) * 0.5
                total_down = len(p_down)
                print(f"✅ 降采样完成！处理点数从 {total_points} 降至 {total_down}")
            else:
                print(f"⚡ 数据量安全 ({total_points}点)，跳过降采样，全量推理！")
                p_down, c_down = points, colors
                total_down = total_points

            down_vote_counter = np.zeros((total_down, len(colors_palette)), dtype=np.uint16)

            # === 4. 动态分块推理 (带防爆0保护) ===
            min_b, max_b = p_down.min(axis=0), p_down.max(axis=0)
            step_size = max(BLOCK_SIZE - BLOCK_OVERLAP, 1.0) 
            if max_b[0] == min_b[0]: max_b[0] += 0.1
            if max_b[1] == min_b[1]: max_b[1] += 0.1

            x_grids = np.arange(min_b[0], max_b[0], step_size)
            y_grids = np.arange(min_b[1], max_b[1], step_size)
            
            print(f"🧩 划分为 {len(x_grids) * len(y_grids)} 个区块进行推理...")
            for x in x_grids:
                for y in y_grids:
                    idx_in_block = np.where(
                        (p_down[:, 0] >= x) & (p_down[:, 0] < x + BLOCK_SIZE) & 
                        (p_down[:, 1] >= y) & (p_down[:, 1] < y + BLOCK_SIZE)
                    )[0]
                    if len(idx_in_block) < 10: continue
                        
                    p_block, c_block = p_down[idx_in_block], c_down[idx_in_block]
                    # 💡 核心改动：
                    # 室内模型 (in_channels=6) 需要吃 RGB 颜色，所以传入 c_block
                    # 室外模型 (in_channels=3) 只吃纯几何坐标 XYZ，所以特征必须是 None！
                    if scene_type == "outdoor":
                        f_block = None
                    else:
                        f_block = c_block
                        
                    results = pipeline.run_inference({ 
                        'point': p_block.astype(np.float32), 
                        'feat': f_block, 
                        'label': np.zeros((len(p_block),), dtype=np.int32) 
                    })
                    block_pred = np.clip(results['predict_labels'], 0, len(colors_palette) - 1)
                    
                    for i, real_idx in enumerate(idx_in_block):
                        down_vote_counter[real_idx, block_pred[i]] += 1

            # === 5. 标签还原 (匹配第 3 步的逻辑！) ===
            pcd_down_labels = np.argmax(down_vote_counter, axis=1)
            
            if total_points > 200000:
                print(f"📊 正在将推理结果无损还原给 {total_points} 个原始点...")
                kdtree = o3d.geometry.KDTreeFlann(pcd_down)
                BATCH = 2000000
                for i in range(0, total_points, BATCH):
                    batch_end = min(i + BATCH, total_points)
                    for j in range(i, batch_end):
                        _, idx, _ = kdtree.search_knn_vector_3d(points[j], 1)
                        final_predictions[j] = pcd_down_labels[idx[0]]
            else:
                print(f"📊 小点云直接映射标签，完成！")
                final_predictions = pcd_down_labels

            # === 6. 保存与计算指标 ===
            pcd_out = o3d.geometry.PointCloud()
            pcd_out.points = o3d.utility.Vector3dVector(points)
            pcd_out.colors = o3d.utility.Vector3dVector(colors_palette[final_predictions])
            o3d.io.write_point_cloud(output_path, pcd_out)

            unique_labels, counts = np.unique(final_predictions, return_counts=True)
            return {
                "point_count": total_points,
                "detected_classes": len(unique_labels),
                "total_process_time_sec": round(time.time() - start_total_time, 2),
                "class_distribution": {f"Class_{lbl}": f"{(cnt/total_points)*100:.2f}%" for lbl, cnt in zip(unique_labels, counts)},
                "scene_type_detected": scene_type
            }

        except Exception as e:
            raise RuntimeError(f"处理大点云过程中发生致命错误: {str(e)}")

ai_engine = PointCloudAIEngine()