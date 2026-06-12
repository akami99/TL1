import bpy
import gpu
import math
import mathutils
from gpu_extras.batch import batch_for_shader

# グローバル変数保持用
_draw_handler = None
_updating_godeye = False

# カーブ幾何データのキャッシュ（GPU描画時のコンテキストエラーを回避するため）
_curve_cache = {
    "name": "",
    "points": [],
    "distances": [],
    "total_dist": 0.0
}

# 前回位置・距離キャッシュ用
_prev_locations = {}
_prev_distances = {}


def get_curve_points_via_mesh(curve_obj):
    """カーブオブジェクトをポリゴンメッシュに一時変換してサンプル点群をワールド座標で取得する"""
    if not curve_obj or curve_obj.type != 'CURVE':
        return []
    
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(depsgraph)
    
    try:
        mesh = bpy.data.meshes.new_from_object(eval_obj)
    except Exception as e:
        print(f"Failed to convert curve to mesh: {e}")
        return []
        
    matrix = curve_obj.matrix_world
    points = [matrix @ vertex.co for vertex in mesh.vertices]
    
    bpy.data.meshes.remove(mesh)
    return points


def get_curve_geometry(curve_obj):
    """サンプル点群、各点の累積距離、総距離を計算して返す"""
    points = get_curve_points_via_mesh(curve_obj)
    if not points:
        return [], [], 0.0
        
    distances = [0.0]
    total_dist = 0.0
    for i in range(1, len(points)):
        dist = (points[i] - points[i-1]).length
        total_dist += dist
        distances.append(total_dist)
        
    return points, distances, total_dist


def get_closest_distance_on_curve(target_co, points, distances):
    """3D座標からカーブ上の最寄りの進行距離を計算して返す"""
    if not points:
        return 0.0
        
    min_dist = float('inf')
    closest_distance = 0.0
    
    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i+1]
        d0 = distances[i]
        d1 = distances[i+1]
        
        v = p1 - p0
        w = target_co - p0
        v_len_sq = v.length_squared
        if v_len_sq == 0.0:
            t = 0.0
        else:
            t = w.dot(v) / v_len_sq
            t = max(0.0, min(1.0, t))
            
        closest_point = p0 + t * v
        dist = (target_co - closest_point).length
        if dist < min_dist:
            min_dist = dist
            closest_distance = d0 + t * (d1 - d0)
            
    return closest_distance


def distance_to_co(dist, points, distances):
    """進行距離からカーブ上の3D座標を補間して返す"""
    if not points:
        return mathutils.Vector((0.0, 0.0, 0.0))
        
    if dist <= 0.0:
        return points[0]
    if dist >= distances[-1]:
        return points[-1]
        
    for i in range(len(distances) - 1):
        d0 = distances[i]
        d1 = distances[i+1]
        if d0 <= dist <= d1:
            t = (dist - d0) / (d1 - d0) if (d1 - d0) != 0.0 else 0.0
            return points[i] + t * (points[i+1] - points[i])
            
    return points[-1]


def update_curve_cache(rail_obj):
    """メモリ上のカーブ幾何データキャッシュを再計算して更新する"""
    global _curve_cache
    if not rail_obj:
        _curve_cache = {"name": "", "points": [], "distances": [], "total_dist": 0.0}
        return
        
    points, distances, total_dist = get_curve_geometry(rail_obj)
    _curve_cache = {
        "name": rail_obj.name,
        "points": points,
        "distances": distances,
        "total_dist": total_dist
    }
    print(f"[God Eye] Curve cache updated: {rail_obj.name} ({total_dist:.2f}m)")


# 再評価無限ループやDepsgraph競合を防ぐためのタイマー遅延実行フラグ
_timer_pending = False

def trigger_cache_update(rail_obj):
    """1フレーム後に安全にキャッシュを再構築するタイマーを登録"""
    global _timer_pending
    if _timer_pending:
        return
    _timer_pending = True
    
    def timer_callback():
        global _timer_pending
        try:
            # 基準レールが有効であればキャッシュを再構築
            if bpy.context.scene.godeye_rail_curve == rail_obj:
                update_curve_cache(rail_obj)
                # ビューポートを描画更新させる
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception as e:
            print(f"Delayed cache update failed: {e}")
        finally:
            _timer_pending = False
        return None  # 1回のみ実行
        
    bpy.app.timers.register(timer_callback)


_autosave_timer_pending = False

def trigger_auto_export(scene):
    """デバウンスを挟んで自動的にJSONをエクスポートする"""
    global _autosave_timer_pending
    if _autosave_timer_pending:
        return
    _autosave_timer_pending = True
    
    def autosave_callback():
        global _autosave_timer_pending
        try:
            path = scene.get("godeye_last_export_path")
            if path:
                global _updating_godeye
                if not _updating_godeye:
                    _updating_godeye = True
                    try:
                        import os
                        if os.path.exists(os.path.dirname(path)):
                            bpy.ops.myaddon.myaddon_ot_export_scene('EXEC_DEFAULT', filepath=path)
                            print(f"[God Eye] Hot-reload: Auto-exported to {path}")
                    finally:
                        _updating_godeye = False
        except Exception as e:
            print(f"Auto-export failed: {e}")
        finally:
            _autosave_timer_pending = False
        return None  # 1回のみ実行
        
    bpy.app.timers.register(autosave_callback, first_interval=0.5)


def godeye_depsgraph_update_handler(scene, depsgraph):
    """同期およびキャッシュ管理ハンドラ"""
    global _updating_godeye, _prev_locations, _prev_distances, _curve_cache
    if _updating_godeye:
        return
        
    # 1. 基準レールが未設定の場合は、シーン内の最初のカーブオブジェクトを自動バインディング
    if not scene.godeye_rail_curve:
        curves = [obj for obj in scene.objects if obj.type == 'CURVE']
        if curves:
            scene.godeye_rail_curve = curves[0]
            trigger_cache_update(curves[0])
            
    rail_obj = scene.godeye_rail_curve
    if not rail_obj:
        return
        
    # 2. 基準レールの変形や移動（ID更新、およびカーブデータ自体の変形）を検知してキャッシュを更新
    rail_updated = False
    for update in depsgraph.updates:
        if update.id == rail_obj or update.id == rail_obj.data:
            rail_updated = True
            break
            
    if rail_updated or not _curve_cache["points"] or _curve_cache["name"] != rail_obj.name:
        # デプスグラフの評価中ループから外れて安全に更新するため、タイマー遅延でキャッシュを更新
        trigger_cache_update(rail_obj)
        
    # 3. 選択中の出現ポイントオブジェクトの同期
    active_objs = [obj for obj in bpy.context.selected_objects if "spawn" in obj]
    if not active_objs:
        return
        
    points = _curve_cache["points"]
    distances = _curve_cache["distances"]
    if not points:
        return
        
    _updating_godeye = True
    try:
        for obj in active_objs:
            # PLAYERのみ位置とdistanceを同期し、ENEMYなどは同期しない
            if obj.get("spawn") != "PLAYER":
                continue

            curr_loc = tuple(obj.location)
            prev_loc = _prev_locations.get(obj.name)
            
            if "distance" not in obj:
                obj["distance"] = 0.0
                
            curr_dist = obj["distance"]
            prev_dist = _prev_distances.get(obj.name)
            
            if prev_loc is not None and curr_loc != prev_loc:
                # 3D座標の移動を検知 ➔ 距離の更新
                new_dist = get_closest_distance_on_curve(obj.location, points, distances)
                obj["distance"] = new_dist
                _prev_distances[obj.name] = new_dist
                _prev_locations[obj.name] = tuple(obj.location)
                
            elif prev_dist is not None and not math.isclose(curr_dist, prev_dist, abs_tol=1e-4):
                # distanceプロパティの変更を検知 ➔ 3D座標をスライド移動（オフセット維持）
                old_rail_co = distance_to_co(prev_dist, points, distances)
                offset = obj.location - old_rail_co
                
                new_rail_co = distance_to_co(curr_dist, points, distances)
                obj.location = new_rail_co + offset
                
                _prev_locations[obj.name] = tuple(obj.location)
                _prev_distances[obj.name] = curr_dist
                
            else:
                _prev_locations[obj.name] = curr_loc
                _prev_distances[obj.name] = curr_dist
    except Exception as e:
        print(f"Error in godeye sync: {e}")
    finally:
        _updating_godeye = False

    # 4. 自動エクスポート（ホットリロード）の判定
    if not _updating_godeye and scene.get("godeye_last_export_path"):
        should_autosave = False
        for update in depsgraph.updates:
            if isinstance(update.id, bpy.types.Object):
                obj = update.id
                if "spawn" in obj or obj == scene.godeye_rail_curve:
                    should_autosave = True
                    break
        if should_autosave:
            trigger_auto_export(scene)


def draw_heatmap_callback():
    """3Dビューポートへのヒートマップおよび生存ラインの描画処理 (キャッシュを参照し安全に描画)"""
    global _curve_cache
    scene = bpy.context.scene
    
    # 描画表示のON/OFFフラグ
    show_heatmap = scene.godeye_show_heatmap
    show_survival = scene.godeye_show_survival
    
    if not show_heatmap and not show_survival:
        return
    
    # キャッシュからデータを取得
    points = _curve_cache["points"]
    distances = _curve_cache["distances"]
    total_dist = _curve_cache["total_dist"]
    
    if not points:
        return
        
    # エネミーオブジェクトを抽出
    enemies = [obj for obj in scene.objects if obj.get("spawn") == "ENEMY"]
    
    # シェーダーの初期化
    try:
        shader = gpu.shader.from_builtin('3D_FLAT_COLOR')
    except ValueError:
        shader = gpu.shader.from_builtin('POLYLINE_FLAT_COLOR')
        
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE') # 最前面に描画
    
    try:
        gpu.state.line_width_set(4.0)
    except Exception:
        pass

    # ----------------------------------------------------
    # 1. レールのヒートマップ描画
    # ----------------------------------------------------
    if show_heatmap:
        density_colors = []
        for i, p in enumerate(points):
            d_val = distances[i]
            count = 0
            for enemy in enemies:
                e_dist = enemy.get("distance", 0.0)
                if abs(e_dist - d_val) <= 10.0:  # 前後10m範囲
                    count += 1
                    
            if count == 0:
                color = (0.1, 0.4, 0.9, 0.6)  # 青: 安全
            elif count == 1:
                color = (0.9, 0.8, 0.1, 0.7)  # 黄: 小競り合い
            else:
                color = (0.9, 0.1, 0.1, 0.8)  # 赤: 激戦区
                
            density_colors.append(color)

        # 各セグメントを描画
        for i in range(len(points) - 1):
            p0 = points[i]
            p1 = points[i+1]
            c0 = density_colors[i]
            c1 = density_colors[i+1]
            
            batch = batch_for_shader(
                shader,
                'LINE_STRIP',
                {"pos": [p0, p1], "color": [c0, c1]}
            )
            shader.bind()
            batch.draw(shader)

    # ----------------------------------------------------
    # 2. 各エネミーの生存ライン（想定ルート）の描画
    # ----------------------------------------------------
    if show_survival:
        survival_length = 20.0
        line_color = (0.2, 0.9, 0.2, 0.5)  # 薄緑色
        
        for enemy in enemies:
            e_dist = enemy.get("distance", 0.0)
            e_loc = enemy.location
            
            p_start_rail = distance_to_co(e_dist, points, distances)
            offset = e_loc - p_start_rail  # レールからのオフセット
            
            line_pts = []
            d_step = 1.0
            d_curr = e_dist
            d_max = min(total_dist, e_dist + survival_length)
            
            while d_curr <= d_max:
                rail_co = distance_to_co(d_curr, points, distances)
                line_pts.append(rail_co + offset)
                d_curr += d_step
                
            if len(line_pts) >= 2:
                batch_line = batch_for_shader(
                    shader,
                    'LINE_STRIP',
                    {"pos": line_pts, "color": [line_color] * len(line_pts)}
                )
                shader.bind()
                batch_line.draw(shader)

    # ----------------------------------------------------
    # 3. プレイヤー視野（FOV）の描画
    # ----------------------------------------------------
    show_fov = scene.godeye_show_fov
    if show_fov:
        players = [obj for obj in scene.objects if obj.get("spawn") == "PLAYER"]
        fov_angle = 60.0
        fov_range = 15.0
        fov_color = (0.0, 0.8, 0.8, 0.6)
        
        for player in players:
            p_loc = player.location
            forward = (player.matrix_world.to_3x3() @ mathutils.Vector((0, -1, 0))).normalized()
            up = (player.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1))).normalized()
            
            fov_pts = [p_loc]
            half_angle = int(fov_angle / 2)
            for angle in range(-half_angle, half_angle + 1, 5):
                rot_mat = mathutils.Matrix.Rotation(math.radians(angle), 4, up)
                dir_vec = (rot_mat @ forward).normalized()
                fov_pts.append(p_loc + dir_vec * fov_range)
            fov_pts.append(p_loc)
            
            if len(fov_pts) >= 2:
                batch_fov = batch_for_shader(
                    shader,
                    'LINE_STRIP',
                    {"pos": fov_pts, "color": [fov_color] * len(fov_pts)}
                )
                shader.bind()
                batch_fov.draw(shader)

    gpu.state.depth_test_set('LESS_EQUAL')


def update_simulation(scene):
    """テスト走行シミュレータの更新処理"""
    rail_obj = scene.godeye_rail_curve
    if not rail_obj:
        return
        
    global _curve_cache, _prev_locations, _prev_distances
    points = _curve_cache["points"]
    distances = _curve_cache["distances"]
    
    if not points:
        # キャッシュが空なら構築を試みる
        points, distances, _ = get_curve_geometry(rail_obj)
        if not points:
            return
            
    current_dist = scene.godeye_test_run_dist
    
    # 1. プレイヤーをレール上に配置し、接線方向に回転
    players = [obj for obj in scene.objects if obj.get("spawn") == "PLAYER"]
    if players:
        p_co = distance_to_co(current_dist, points, distances)
        
        # 接線
        p_co_next = distance_to_co(current_dist + 0.1, points, distances)
        tangent = (p_co_next - p_co).normalized()
        
        # -Y方向を接線に向ける回転を計算
        rot_diff = mathutils.Vector((0, -1, 0)).rotation_difference(tangent)
        rot_euler = rot_diff.to_euler()
        
        for player in players:
            player.location = p_co
            player.rotation_euler = rot_euler
            player["distance"] = current_dist
            
            # ハンドラ側の誤同期を防ぐためキャッシュを直接更新しておく
            _prev_locations[player.name] = tuple(p_co)
            _prev_distances[player.name] = current_dist
            
    # 2. 敵の出現/非表示制御
    enemies = [obj for obj in scene.objects if obj.get("spawn") == "ENEMY"]
    for enemy in enemies:
        enemy_dist = enemy.get("distance", 0.0)
        if enemy_dist <= current_dist:
            enemy.hide_viewport = False
        else:
            enemy.hide_viewport = True
            
    # 再描画
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def register_handlers():
    """ハンドラの登録"""
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_heatmap_callback, (), 'WINDOW', 'POST_VIEW'
        )
    if godeye_depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(godeye_depsgraph_update_handler)


def unregister_handlers():
    """ハンドラの解除"""
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
    if godeye_depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(godeye_depsgraph_update_handler)
