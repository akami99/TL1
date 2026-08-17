import bpy
import gpu
import math
import mathutils
from gpu_extras.batch import batch_for_shader
from bpy_extras import anim_utils

# グローバル変数保持用
_draw_handler = None
_dopesheet_draw_handler = None
_updating_godeye = False  # 同期無限ループ防止フラグ

# カーブ幾何データのキャッシュ
_curve_cache = {
    "name": "",
    "points": [],
    "distances": [],
    "total_dist": 0.0
}

# 前回位置・距離キャッシュ用
_prev_locations = {}
_prev_distances = {}
_prev_keyframe_frames = {}   # 各エネミーオブジェクトのキーフレームの前回フレーム位置キャッシュ
_prev_test_run_dist = None
_prev_rail_name = None
_prev_rail_mode = None
_prev_frame_current = None


def get_curve_points_via_mesh(curve_obj):
    """カーブオブジェクトをポリゴンメッシュに一時変換してサンプル点群をワールド座標で取得する"""
    if not curve_obj or curve_obj.type != 'CURVE':
        return []
    
    # らせん状のねじれを防ぐため、bevel_depthを一時的に0にしたコピーを作成して評価する
    temp_curve_data = curve_obj.data.copy()
    temp_curve_data.bevel_depth = 0.0
    
    temp_obj = bpy.data.objects.new(name="TempCurveForSampling", object_data=temp_curve_data)
    bpy.context.collection.objects.link(temp_obj)
    
    # デクスグラフに一時オブジェクトを反映させるためにビューレイヤーを更新
    try:
        bpy.context.view_layer.update()
    except Exception as e:
        print(f"[God Eye] View layer update failed during sampling: {e}")
    
    points = []
    temp_mesh = None
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = temp_obj.evaluated_get(depsgraph)
        temp_mesh = bpy.data.meshes.new_from_object(eval_obj)
        
        if temp_mesh:
            matrix = curve_obj.matrix_world
            points = [matrix @ vertex.co for vertex in temp_mesh.vertices]
    except Exception as e:
        print(f"[God Eye] Failed to convert curve to mesh: {e}")
    finally:
        # 一時オブジェクトとデータのクリーンアップを確実に実行
        if temp_mesh:
            try:
                bpy.data.meshes.remove(temp_mesh)
            except Exception:
                pass
        try:
            bpy.data.objects.remove(temp_obj, do_unlink=True)
        except Exception:
            pass
        try:
            bpy.data.curves.remove(temp_curve_data)
        except Exception:
            pass
        
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


def get_curve_cache():
    """メモリ上のカーブ幾何データキャッシュを安全に取得する"""
    global _curve_cache
    return _curve_cache


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
        
    try:
        points, distances, total_dist = get_curve_geometry(rail_obj)
        if not points:
            _curve_cache["name"] = rail_obj.name
            return
            
        _curve_cache = {
            "name": rail_obj.name,
            "points": points,
            "distances": distances,
            "total_dist": total_dist
        }
        print(f"[God Eye] Curve cache updated: {rail_obj.name} ({total_dist:.2f}m)")
        
        # 走行位置プロパティの上限値を安全に更新
        try:
            rail_obj.id_properties_ensure()
            ui_api = rail_obj.id_properties_ui("godeye_test_run_dist")
            ui_api.update(min=0.0, max=total_dist, description="Simulator position")
            
            # 再生終了フレームをレールの長さに合わせて自動更新 (タイマー経由で安全に実行)
            def safe_set_frame_end():
                try:
                    bpy.context.scene.frame_end = int(total_dist * 10) + 1
                except Exception:
                    pass
                return None
            bpy.app.timers.register(safe_set_frame_end)
        except Exception:
            pass
    except Exception as e:
        print(f"[God Eye] Error updating curve cache: {e}")
        _curve_cache["name"] = rail_obj.name


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
    """Auto-export JSON with debounce"""
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
        return None
        
    delay = scene.godeye_autosave_delay
    bpy.app.timers.register(autosave_callback, first_interval=delay)


def get_fcurve_compat(obj, data_path="location"):
    """Blender 4.4+ のスロット式アクションと、それ以前の双方に対応してF-Curveを取得する"""
    if not obj.animation_data or not obj.animation_data.action:
        return None
        
    action = obj.animation_data.action
    
    # --- Blender 4.4+ の新API (Slotted Actions) ---
    if hasattr(obj.animation_data, "action_slot") and obj.animation_data.action_slot:
        try:
            channelbag = anim_utils.action_get_channelbag_for_slot(action, obj.animation_data.action_slot)
            if channelbag:
                for fc in channelbag.fcurves:
                    if fc.data_path == data_path:
                        return fc
        except Exception:
            pass

    # --- Blender 4.3以前のレガシー互換処理 ---
    if hasattr(action, "fcurves"):
        for fc in action.fcurves:
            if fc.data_path == data_path:
                return fc
                
    return None


def force_disable_dopesheet_filter():
    """ドープシートの『選択物のみ表示』フィルターをスクリプトから自動でOFFにし、
    エネミーを選択していなくてもキーフレームが常に全員分見えている状態を作る。
    """
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'DOPESHEET_EDITOR':
                    for space in area.spaces:
                        if space.type == 'DOPESHEET_EDITOR':
                            # 「選択物のみ表示(Only Show Selected)」をOFFにする
                            space.show_only_selected = False
    except Exception:
        pass


def sync_distance_to_keyframe(obj):
    """【プロパティ -> キーフレーム】 
    distance(Nパネルや3D移動)が動いた時に、各エネミーオブジェクト自体のキーフレーム位置を更新する
    """
    if obj.get("spawn") == "PLAYER":
        if obj.animation_data:
            obj.animation_data.action = None
        return
        
    if "distance" not in obj:
        return
        
    dist = obj["distance"]
    target_frame = int(dist * 10) + 1
    
    # キーフレームを挿入してF-Curveを構築/更新
    if not obj.animation_data:
        obj.animation_data_create()
    if not obj.animation_data.action:
        obj.animation_data.action = bpy.data.actions.new(name=f"Timeline_{obj.name}")
        
    # Blender標準の挿入メソッドを使い、安全に全軸(X,Y,Z)のキーフレームを同一フレームに打つ
    obj.keyframe_insert(data_path="location", frame=target_frame)
    
    # 挿入後、すべてのlocationチャンネルのF-Curveを走査し、キーフレーム位置を完全にtarget_frameに合わせる
    action = obj.animation_data.action
    fcurves = []
    if hasattr(obj.animation_data, "action_slot") and obj.animation_data.action_slot:
        try:
            channelbag = anim_utils.action_get_channelbag_for_slot(action, obj.animation_data.action_slot)
            if channelbag:
                fcurves = [fc for fc in channelbag.fcurves if fc.data_path == "location"]
        except Exception:
            pass
    elif hasattr(action, "fcurves"):
        fcurves = [fc for fc in action.fcurves if fc.data_path == "location"]

    k_type = 'EXTREME' if obj.get("stop_point") else 'KEYFRAME'
    for fc in fcurves:
        for k in fc.keyframe_points:
            k.co = (target_frame, k.co[1])
            k.handle_left_type = 'FREE'
            k.handle_right_type = 'FREE'
            k.type = k_type
        fc.update()


def sync_keyframe_to_distance(obj):
    """【キーフレーム -> プロパティ】
    ドープシートでキーをドラッグした時に、各エネミーオブジェクト自体の distance プロパティを更新する
    """
    if obj.get("spawn") == "PLAYER":
        return False
        
    fcurve = get_fcurve_compat(obj, "location")
    if not fcurve or len(fcurve.keyframe_points) == 0:
        return False
        
    kp = fcurve.keyframe_points[0]
    frame = kp.co[0]
    
    curr_dist = obj.get("distance", 0.0)
    expected_frame = int(curr_dist * 10) + 1
    
    # ドープシート上での微細な移動も検知 (しきい値判定で自己ゲート)
    if abs(frame - expected_frame) > 0.05:
        new_dist = (frame - 1) / 10.0
        if new_dist < 0.0:
            new_dist = 0.0
        obj["distance"] = new_dist
        
        # 同一スロット内（同一ChannelBag内）の全ての location F-Curve のフレーム位置を統一
        if obj.animation_data and obj.animation_data.action:
            action = obj.animation_data.action
            fcurves = []
            if hasattr(obj.animation_data, "action_slot") and obj.animation_data.action_slot:
                try:
                    channelbag = anim_utils.action_get_channelbag_for_slot(action, obj.animation_data.action_slot)
                    if channelbag:
                        fcurves = [fc for fc in channelbag.fcurves if fc.data_path == "location"]
                except Exception:
                    pass
            elif hasattr(action, "fcurves"):
                fcurves = [fc for fc in action.fcurves if fc.data_path == "location"]

            k_type = 'EXTREME' if obj.get("stop_point") else 'KEYFRAME'
            for fc in fcurves:
                for k in fc.keyframe_points:
                    k.co = (frame, k.co[1])
                    k.type = k_type
                fc.update()
                
        return True
        
    return False


def sync_area_distance_to_keyframe(obj):
    """【エリア: プロパティ -> キーフレーム】
    エリアの distance, end_distance から開始・終了キーフレーム（2点）を設定する
    """
    if not obj.get("area"):
        return

    start_dist = obj.get("distance", 0.0)
    end_dist = obj.get("end_distance", start_dist + 30.0)
    f0 = int(start_dist * 10) + 1
    f1 = max(f0 + 1, int(end_dist * 10) + 1)

    if not obj.animation_data:
        obj.animation_data_create()
    if not obj.animation_data.action:
        obj.animation_data.action = bpy.data.actions.new(name=f"Timeline_{obj.name}")

    action = obj.animation_data.action

    # 2フレーム挿入
    obj.keyframe_insert(data_path="location", frame=f0)
    obj.keyframe_insert(data_path="location", frame=f1)

    fcurves = []
    if hasattr(obj.animation_data, "action_slot") and obj.animation_data.action_slot:
        try:
            channelbag = anim_utils.action_get_channelbag_for_slot(action, obj.animation_data.action_slot)
            if channelbag:
                fcurves = [fc for fc in channelbag.fcurves if fc.data_path == "location"]
        except Exception:
            pass
    elif hasattr(action, "fcurves"):
        fcurves = [fc for fc in action.fcurves if fc.data_path == "location"]

    for fc in fcurves:
        if len(fc.keyframe_points) >= 2:
            fc.keyframe_points[0].co = (f0, fc.keyframe_points[0].co[1])
            fc.keyframe_points[0].interpolation = 'CONSTANT'
            fc.keyframe_points[0].type = 'BREAKDOWN'
            fc.keyframe_points[1].co = (f1, fc.keyframe_points[1].co[1])
            fc.keyframe_points[1].interpolation = 'CONSTANT'
            fc.keyframe_points[1].type = 'BREAKDOWN'
            while len(fc.keyframe_points) > 2:
                fc.keyframe_points.remove(fc.keyframe_points[-1])
        fc.update()


def sync_area_keyframe_to_distance(obj):
    """【エリア: キーフレーム -> プロパティ】
    ドープシートでエリアの開始・終了キーをドラッグした時に、distance, end_distance を更新する
    """
    if not obj.get("area"):
        return False

    fcurve = get_fcurve_compat(obj, "location")
    if not fcurve or len(fcurve.keyframe_points) < 2:
        return False

    f0 = fcurve.keyframe_points[0].co[0]
    f1 = fcurve.keyframe_points[1].co[0]

    if f1 <= f0:
        f1 = f0 + 1

    changed = False
    new_dist = max(0.0, (f0 - 1) / 10.0)
    if abs(obj.get("distance", 0.0) - new_dist) > 0.05:
        obj["distance"] = new_dist
        changed = True

    new_end_dist = max(new_dist + 0.1, (f1 - 1) / 10.0)
    if abs(obj.get("end_distance", new_dist + 30.0) - new_end_dist) > 0.05:
        obj["end_distance"] = new_end_dist
        changed = True

    if fcurve and len(fcurve.keyframe_points) >= 2:
        fcurve.keyframe_points[0].type = 'BREAKDOWN'
        fcurve.keyframe_points[1].type = 'BREAKDOWN'

    return changed


def godeye_frame_change_handler(scene, depsgraph=None):
    """タイムラインの再生ヘッド移動・再生ボタンによるフレーム変化を検知する専用ハンドラ。
    depsgraph_update_postはIDの実変化が無いと発火しないため、frame_change側で確実に拾う。
    """
    global _updating_godeye, _prev_frame_current, _prev_test_run_dist, _curve_cache

    if _updating_godeye:
        return

    rail_obj = scene.godeye_rail_curve
    if not rail_obj:
        return

    curr_frame = scene.frame_current
    if _prev_frame_current is not None and curr_frame == _prev_frame_current:
        return
    _prev_frame_current = curr_frame

    # キャッシュが無ければ構築
    if not _curve_cache.get("points") or _curve_cache.get("name") != rail_obj.name:
        update_curve_cache(rail_obj)

    total_dist = _curve_cache.get("total_dist", 0.0)
    new_dist = (curr_frame - 1) / 10.0
    new_dist = max(0.0, min(total_dist, new_dist))

    update_simulation(scene, target_dist=new_dist)

    _updating_godeye = True
    try:
        rail_obj["godeye_test_run_dist"] = new_dist
        _prev_test_run_dist = new_dist
    except Exception:
        pass
    finally:
        _updating_godeye = False


def godeye_depsgraph_update_handler(scene, depsgraph):
    """同期およびキャッシュ管理ハンドラ"""
    global _updating_godeye, _prev_locations, _prev_distances, _curve_cache, _prev_test_run_dist, _prev_frame_current
    
    # 1. 基準レールが未設定の場合は、シーン内の最初のカーブオブジェクトを自動バインディング (最優先実行)
    if not scene.godeye_rail_curve:
        curves = [obj for obj in scene.objects if obj.type == 'CURVE']
        if curves:
            scene.godeye_rail_curve = curves[0]
            if "godeye_test_run_dist" not in curves[0]:
                curves[0]["godeye_test_run_dist"] = 0.0
            update_curve_cache(curves[0])
            
    curr_rail = scene.godeye_rail_curve
    if not curr_rail:
        return

    # タイムラインのフィルター状態を自動整備
    force_disable_dopesheet_filter()

    # キャッシュ確認
    if not _curve_cache.get("points") or _curve_cache.get("name") != curr_rail.name:
        update_curve_cache(curr_rail)

    points = _curve_cache["points"]
    distances = _curve_cache["distances"]

    spawn_objs = [obj for obj in scene.objects if ("spawn" in obj and obj.get("spawn") != "PLAYER") or obj.get("stop_point")]
    area_objs = [obj for obj in scene.objects if obj.get("area")]

    # --- パターンA: キーフレーム位置と distance プロパティ、どちらが変化したかを個別に判定 ---
    timeline_changed_any = False
    if not _updating_godeye:
        # スポーンオブジェクト（敵）および停止ポイントの同期 (1点キーフレーム)
        for obj in spawn_objs:
            fcurve = get_fcurve_compat(obj, "location")
            if not fcurve or len(fcurve.keyframe_points) == 0:
                continue

            curr_frame = fcurve.keyframe_points[0].co[0]
            curr_dist = obj.get("distance", 0.0)
            expected_frame = int(curr_dist * 10) + 1

            if abs(curr_frame - expected_frame) <= 0.05:
                _prev_keyframe_frames[obj.name] = curr_frame
                _prev_distances[obj.name] = curr_dist
                continue

            prev_frame = _prev_keyframe_frames.get(obj.name)
            prev_dist = _prev_distances.get(obj.name)

            frame_moved = prev_frame is not None and abs(curr_frame - prev_frame) > 0.05
            dist_moved = prev_dist is not None and not math.isclose(curr_dist, prev_dist, abs_tol=1e-4)

            if dist_moved and not frame_moved:
                sync_distance_to_keyframe(obj)
                _prev_keyframe_frames[obj.name] = int(curr_dist * 10) + 1
                _prev_distances[obj.name] = curr_dist
                timeline_changed_any = True
            else:
                if sync_keyframe_to_distance(obj):
                    _prev_keyframe_frames[obj.name] = fcurve.keyframe_points[0].co[0]
                    _prev_distances[obj.name] = obj["distance"]
                    timeline_changed_any = True

        # エリアオブジェクトの同期 (2点キーフレーム)
        for obj in area_objs:
            fcurve = get_fcurve_compat(obj, "location")
            if not fcurve or len(fcurve.keyframe_points) < 2:
                sync_area_distance_to_keyframe(obj)
                continue

            f0 = fcurve.keyframe_points[0].co[0]
            f1 = fcurve.keyframe_points[1].co[0]
            curr_dist = obj.get("distance", 0.0)
            end_dist = obj.get("end_distance", curr_dist + 30.0)
            expected_f0 = int(curr_dist * 10) + 1
            expected_f1 = max(expected_f0 + 1, int(end_dist * 10) + 1)

            if abs(f0 - expected_f0) <= 0.05 and abs(f1 - expected_f1) <= 0.05:
                _prev_keyframe_frames[obj.name] = (f0, f1)
                _prev_distances[obj.name] = curr_dist
                continue

            prev_key = _prev_keyframe_frames.get(obj.name)
            prev_dist = _prev_distances.get(obj.name)

            frame_moved = prev_key is not None and (abs(f0 - prev_key[0]) > 0.05 or abs(f1 - prev_key[1]) > 0.05)
            dist_moved = prev_dist is not None and not math.isclose(curr_dist, prev_dist, abs_tol=1e-4)

            if dist_moved and not frame_moved:
                sync_area_distance_to_keyframe(obj)
                _prev_keyframe_frames[obj.name] = (expected_f0, expected_f1)
                _prev_distances[obj.name] = curr_dist
                timeline_changed_any = True
            else:
                if sync_area_keyframe_to_distance(obj):
                    _prev_keyframe_frames[obj.name] = (fcurve.keyframe_points[0].co[0], fcurve.keyframe_points[1].co[0])
                    _prev_distances[obj.name] = obj["distance"]
                    timeline_changed_any = True

        if timeline_changed_any:
            # 画面を再描画
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            if scene.godeye_enable_autosave:
                trigger_auto_export(scene)
            return  # キー由来の変更時はプロパティ側からの逆同期を行わない

    # --- パターンB: 3D移動やNパネルプロパティの変更検知 (パターンAが何も検出しなかった時のみ) ---
    if not _updating_godeye:
        _updating_godeye = True
        try:
            active_objs = [obj for obj in bpy.context.selected_objects if "spawn" in obj or obj.get("area") or obj.get("stop_point")]
            for obj in active_objs:
                curr_dist = obj.get("distance", 0.0)
                prev_dist = _prev_distances.get(obj.name)
                
                # PLAYER: 3D位置とプロパティの双方向
                if obj.get("spawn") == "PLAYER":
                    curr_loc = tuple(obj.location)
                    prev_loc = _prev_locations.get(obj.name)
                    
                    if prev_loc is not None and curr_loc != prev_loc:
                        new_dist = get_closest_distance_on_curve(obj.location, points, distances)
                        obj["distance"] = new_dist
                        _prev_distances[obj.name] = new_dist
                        _prev_locations[obj.name] = tuple(obj.location)
                        
                    elif prev_dist is not None and not math.isclose(curr_dist, prev_dist, abs_tol=1e-4):
                        old_rail_co = distance_to_co(prev_dist, points, distances)
                        offset = obj.location - old_rail_co
                        new_rail_co = distance_to_co(curr_dist, points, distances)
                        
                        obj.location = new_rail_co + offset
                        _prev_locations[obj.name] = tuple(obj.location)
                        _prev_distances[obj.name] = curr_dist
                    else:
                        _prev_locations[obj.name] = curr_loc
                        _prev_distances[obj.name] = curr_dist

                # AREA / STOP POINT: 3Dドラッグ移動時はレール上にスナップ
                elif obj.get("area"):
                    curr_loc = tuple(obj.location)
                    prev_loc = _prev_locations.get(obj.name)
                    if prev_loc is not None and curr_loc != prev_loc:
                        new_dist = get_closest_distance_on_curve(obj.location, points, distances)
                        obj["distance"] = new_dist
                        sync_area_distance_to_keyframe(obj)
                        _prev_distances[obj.name] = new_dist
                        _prev_locations[obj.name] = tuple(obj.location)
                    elif prev_dist is not None and not math.isclose(curr_dist, prev_dist, abs_tol=1e-4):
                        new_rail_co = distance_to_co(curr_dist, points, distances)
                        obj.location = new_rail_co
                        sync_area_distance_to_keyframe(obj)
                        _prev_locations[obj.name] = tuple(obj.location)
                        _prev_distances[obj.name] = curr_dist
                    else:
                        _prev_locations[obj.name] = curr_loc
                        _prev_distances[obj.name] = curr_dist

                elif obj.get("stop_point"):
                    curr_loc = tuple(obj.location)
                    prev_loc = _prev_locations.get(obj.name)
                    if prev_loc is not None and curr_loc != prev_loc:
                        new_dist = get_closest_distance_on_curve(obj.location, points, distances)
                        obj["distance"] = new_dist
                        sync_distance_to_keyframe(obj)
                        _prev_distances[obj.name] = new_dist
                        _prev_locations[obj.name] = tuple(obj.location)
                    elif prev_dist is not None and not math.isclose(curr_dist, prev_dist, abs_tol=1e-4):
                        new_rail_co = distance_to_co(curr_dist, points, distances)
                        obj.location = new_rail_co
                        sync_distance_to_keyframe(obj)
                        _prev_locations[obj.name] = tuple(obj.location)
                        _prev_distances[obj.name] = curr_dist
                    else:
                        _prev_locations[obj.name] = curr_loc
                        _prev_distances[obj.name] = curr_dist
        except Exception as e:
            print(f"[God Eye] Properties sync failed: {e}")
        finally:
            _updating_godeye = False

    # 3. 走行距離の変更をタイムライン(フレーム)へ同期 (Nパネル等からの同期)
    curr_sim_dist = curr_rail.get("godeye_test_run_dist", 0.0)
    if _prev_test_run_dist is None or not math.isclose(curr_sim_dist, _prev_test_run_dist, abs_tol=1e-4):
        _prev_test_run_dist = curr_sim_dist
        target_frame = int(curr_sim_dist * 10) + 1
        if scene.frame_current != target_frame:
            scene.frame_current = target_frame
            _prev_frame_current = target_frame
        update_simulation(scene)


def draw_heatmap_callback():
    """3Dビューポートへのヒートマップおよび生存ラインの描画処理 (キャッシュを参照し安全に描画)"""
    global _curve_cache
    scene = bpy.context.scene
    
    # 描画表示のON/OFFフラグ
    show_heatmap = scene.godeye_show_heatmap
    show_survival = scene.godeye_show_survival
    show_fov = scene.godeye_show_fov
    show_areas = scene.godeye_show_areas
    
    if not show_heatmap and not show_survival and not show_fov and not show_areas:
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
        shader = gpu.shader.from_builtin('FLAT_COLOR')
    except ValueError:
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
    # 1. レールのヒートマップ描画 (一括バッチ)
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

        # 各セグメントを一括追加
        pos_coords = []
        color_coords = []
        for i in range(len(points) - 1):
            pos_coords.append(points[i])
            pos_coords.append(points[i+1])
            color_coords.append(density_colors[i])
            color_coords.append(density_colors[i+1])
            
        if pos_coords:
            batch = batch_for_shader(
                shader,
                'LINES',
                {"pos": pos_coords, "color": color_coords}
            )
            shader.bind()
            batch.draw(shader)

    # ----------------------------------------------------
    # 2. 各エネミーの生存ライン（想定ルート）の描画 (一括バッチ)
    # ----------------------------------------------------
    if show_survival:
        survival_length = scene.godeye_survival_length
        line_color = (0.2, 0.9, 0.2, 0.5)  # 薄緑色
        survival_pos = []
        survival_colors = []
        
        for enemy in enemies:
            e_dist = enemy.get("distance", 0.0)
            e_loc = enemy.location
            
            p_start_rail = distance_to_co(e_dist, points, distances)
            offset = e_loc - p_start_rail  # レールからのオフセット
            
            d_step = 1.0
            d_curr = e_dist
            d_max = min(total_dist, e_dist + survival_length)
            
            prev_pt = None
            while d_curr <= d_max:
                rail_co = distance_to_co(d_curr, points, distances)
                pt = rail_co + offset
                if prev_pt is not None:
                    survival_pos.append(prev_pt)
                    survival_pos.append(pt)
                    survival_colors.append(line_color)
                    survival_colors.append(line_color)
                prev_pt = pt
                if d_curr == d_max:
                    break
                d_curr = min(d_max, d_curr + d_step)
                
        if survival_pos:
            batch_line = batch_for_shader(
                shader,
                'LINES',
                {"pos": survival_pos, "color": survival_colors}
            )
            shader.bind()
            batch_line.draw(shader)

    # ----------------------------------------------------
    # 3. プレイヤー視野（FOV）の描画 (一括バッチ)
    # ----------------------------------------------------
    if show_fov:
        players = [obj for obj in scene.objects if obj.get("spawn") == "PLAYER"]
        fov_angle = scene.godeye_fov_angle
        fov_range = scene.godeye_fov_range
        fov_color = (0.0, 0.8, 0.8, 0.6)
        fov_pos = []
        fov_colors = []
        
        for player in players:
            p_loc = player.location
            forward = (player.matrix_world.to_3x3() @ mathutils.Vector((0, -1, 0))).normalized()
            up = (player.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1))).normalized()
            
            pts = [p_loc]
            half_angle = int(fov_angle / 2)
            for angle in range(-half_angle, half_angle + 1, 5):
                rot_mat = mathutils.Matrix.Rotation(math.radians(angle), 4, up)
                dir_vec = (rot_mat @ forward).normalized()
                fov_pts = p_loc + dir_vec * fov_range
                pts.append(fov_pts)
            pts.append(p_loc)
            
            for j in range(len(pts) - 1):
                fov_pos.append(pts[j])
                fov_pos.append(pts[j+1])
                fov_colors.append(fov_color)
                fov_colors.append(fov_color)
            
        if fov_pos:
            batch_fov = batch_for_shader(
                shader,
                'LINES',
                {"pos": fov_pos, "color": fov_colors}
            )
            shader.bind()
            batch_fov.draw(shader)

    # ----------------------------------------------------
    # 4. 戦闘エリアおよび停止ポイントのレール上への描画 (一括バッチ)
    # ----------------------------------------------------
    if scene.godeye_show_areas:
        offset = mathutils.Vector((0.0, 0.0, 0.3)) # 少しZ方向に浮かせる
        area_objs = [obj for obj in scene.objects if obj.get("area")]
        stop_objs = [obj for obj in scene.objects if obj.get("stop_point")]
        
        # 4-1. エリア（交戦区間）のライン描画
        area_color = (0.1, 0.7, 0.9, 0.8)  # シアンブルー
        area_pos = []
        area_line_colors = []
        for a_obj in area_objs:
            start_d = a_obj.get("distance", 0.0)
            end_d = a_obj.get("end_distance", start_d + 30.0)
            for i in range(len(points) - 1):
                d0 = distances[i]
                d1 = distances[i+1]
                if max(d0, start_d) < min(d1, end_d):
                    p0 = points[i] + offset
                    p1 = points[i+1] + offset
                    area_pos.append(p0)
                    area_pos.append(p1)
                    area_line_colors.append(area_color)
                    area_line_colors.append(area_color)
        if area_pos:
            batch_area = batch_for_shader(shader, 'LINES', {"pos": area_pos, "color": area_line_colors})
            shader.bind()
            batch_area.draw(shader)

        # 4-2. 停止ポイントのゲート描画
        gate_color = (0.9, 0.2, 0.2, 0.9)  # 赤
        gate_pos = []
        gate_cols = []
        w = 1.0
        h = 2.0
        for s_obj in stop_objs:
            s_dist = s_obj.get("distance", 0.0)
            p_center = distance_to_co(s_dist, points, distances) + offset
            g_p1 = p_center + mathutils.Vector((-w, 0, 0))
            g_p2 = p_center + mathutils.Vector((w, 0, 0))
            g_p3 = p_center + mathutils.Vector((w, 0, h))
            g_p4 = p_center + mathutils.Vector((-w, 0, h))
            
            pts = [g_p1, g_p2, g_p2, g_p3, g_p3, g_p4, g_p4, g_p1, g_p1, g_p3, g_p2, g_p4]
            gate_pos.extend(pts)
            gate_cols.extend([gate_color] * len(pts))

        if gate_pos:
            batch_gate = batch_for_shader(shader, 'LINES', {"pos": gate_pos, "color": gate_cols})
            shader.bind()
            batch_gate.draw(shader)

    gpu.state.depth_test_set('LESS_EQUAL')

def draw_dopesheet_heatmap_callback():
    """ドープシート/タイムラインの背景に、距離ベースの密集度ヒートマップやエリア帯を面で描画する。"""
    global _curve_cache
    scene = bpy.context.scene

    show_dopesheet_heatmap = scene.godeye_show_dopesheet_heatmap
    show_areas = getattr(scene, "godeye_show_dopesheet_areas", scene.godeye_show_areas)

    if not show_dopesheet_heatmap and not show_areas:
        return

    context = bpy.context
    space = context.space_data
    region = context.region
    if space is None or region is None or region.type != 'WINDOW':
        return

    # ドープシート/アクションエディタ/タイムラインいずれのモードでも表示する
    if hasattr(space, "mode") and space.mode not in ('DOPESHEET', 'ACTION', 'TIMELINE'):
        return

    total_dist = _curve_cache.get("total_dist", 0.0)
    if total_dist <= 0.0:
        return

    view2d = region.view2d
    max_frame = int(total_dist * 10) + 1
    y0 = 0
    y1 = region.height

    # 1. 密集度ヒートマップの描画
    if show_dopesheet_heatmap:
        enemies = [obj for obj in scene.objects if obj.get("spawn") == "ENEMY"]
        step = 5  # 0.5m刻みでサンプリング (負荷と精度のバランス)
        verts = []
        colors = []
        prev_x = None
        prev_color = None

        frame = 1
        while frame <= max_frame + step:
            f = min(frame, max_frame)
            d_val = (f - 1) / 10.0

            count = 0
            for enemy in enemies:
                e_dist = enemy.get("distance", 0.0)
                if abs(e_dist - d_val) <= 10.0:
                    count += 1

            if count == 0:
                color = (0.1, 0.4, 0.9, 0.12)
            elif count == 1:
                color = (0.9, 0.8, 0.1, 0.18)
            else:
                color = (0.9, 0.1, 0.1, 0.25)

            x, _ = view2d.view_to_region(f, 0, clip=False)

            if prev_x is not None:
                verts.extend([
                    (prev_x, y0), (x, y0), (x, y1),
                    (prev_x, y0), (x, y1), (prev_x, y1),
                ])
                colors.extend([prev_color] * 6)

            prev_x = x
            prev_color = color

            if f == max_frame:
                break
            frame += step

        if verts:
            try:
                shader = gpu.shader.from_builtin('FLAT_COLOR')
            except ValueError:
                shader = gpu.shader.from_builtin('2D_FLAT_COLOR')

            gpu.state.blend_set('ALPHA')
            batch = batch_for_shader(shader, 'TRIS', {"pos": verts, "color": colors})
            shader.bind()
            batch.draw(shader)
            gpu.state.blend_set('NONE')

    # 2. 戦闘エリアおよび停止ポイントのマーカー・ライン描画 (ドープシート)
    if show_areas:
        area_objs = [obj for obj in scene.objects if obj.get("area")]
        stop_objs = [obj for obj in scene.objects if obj.get("stop_point")]
        
        line_pos = []
        line_colors = []
        tris_pos = []
        tris_colors = []

        # フレーム番号（ルーラー）とキーフレーム行の間に配置
        y_bar = y1 - 34.0
        pin_size = 5.0
        tick_h = 5.0

        def add_down_pin(cx, cy, size, col):
            """下向き三角ピン（▼）を描画"""
            p_top_left = (cx - size, cy + size)
            p_top_right = (cx + size, cy + size)
            p_bottom = (cx, cy)
            tris_pos.extend([p_top_left, p_top_right, p_bottom])
            tris_colors.extend([col] * 3)

        # 2-1. 交戦エリア (シアン色の区間バーとピン▼)
        area_col = (0.1, 0.85, 1.0, 0.95)
        for a_obj in area_objs:
            start_d = a_obj.get("distance", 0.0)
            end_d = a_obj.get("end_distance", start_d + 30.0)
            f_start = int(start_d * 10) + 1
            f_end = max(f_start + 1, int(end_d * 10) + 1)

            x0, _ = view2d.view_to_region(f_start, 0, clip=False)
            x1, _ = view2d.view_to_region(f_end, 0, clip=False)

            # 区間バー (水平2重線)
            for dy in (0, 1):
                line_pos.extend([
                    (x0, y_bar + dy), (x1, y_bar + dy)
                ])
                line_colors.extend([area_col, area_col])

            # 開始・終了ティック
            line_pos.extend([
                (x0, y_bar - tick_h), (x0, y_bar + tick_h),
                (x1, y_bar - tick_h), (x1, y_bar + tick_h)
            ])
            line_colors.extend([area_col] * 4)

            # 開始・終了の下向き三角ピン（▼）
            add_down_pin(x0, y_bar - 1.0, pin_size, area_col)
            add_down_pin(x1, y_bar - 1.0, pin_size, area_col)

        # 2-2. 停止ポイント (赤色の下向き三角ピン▼と縦ストップライン)
        stop_col = (1.0, 0.25, 0.25, 0.95)
        stop_line_col = (1.0, 0.25, 0.25, 0.35)
        for s_obj in stop_objs:
            s_dist = s_obj.get("distance", 0.0)
            f_stop = int(s_dist * 10) + 1
            xs, _ = view2d.view_to_region(f_stop, 0, clip=False)

            # 薄い縦ストップライン
            line_pos.extend([
                (xs, y0), (xs, y1)
            ])
            line_colors.extend([stop_line_col, stop_line_col])

            # 停止ポイントの下向き三角ピン（▼）
            add_down_pin(xs, y_bar - 1.0, pin_size + 1.0, stop_col)

        # 描画実行
        try:
            shader = gpu.shader.from_builtin('FLAT_COLOR')
        except ValueError:
            shader = gpu.shader.from_builtin('2D_FLAT_COLOR')

        gpu.state.blend_set('ALPHA')

        if line_pos:
            batch_lines = batch_for_shader(shader, 'LINES', {"pos": line_pos, "color": line_colors})
            shader.bind()
            batch_lines.draw(shader)

        if tris_pos:
            batch_tris = batch_for_shader(shader, 'TRIS', {"pos": tris_pos, "color": tris_colors})
            shader.bind()
            batch_tris.draw(shader)

        gpu.state.blend_set('NONE')

def update_simulation(scene, target_dist=None):
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
            
    current_dist = target_dist if target_dist is not None else rail_obj.get("godeye_test_run_dist", 0.0)
    
    # 1. プレイヤーをレール上に配置し、回転を設定
    players = [obj for obj in scene.objects if obj.get("spawn") == "PLAYER"]
    if players:
        p_co = distance_to_co(current_dist, points, distances)
        
        if scene.godeye_lock_player_rotation:
            rot_euler = scene.godeye_locked_player_rotation_euler
        else:
            # 接線
            p_co_next = distance_to_co(current_dist + 0.1, points, distances)
            tangent = (p_co_next - p_co).normalized()
            
            # -Y方向を接線に向ける回転を計算
            rot_diff = mathutils.Vector((0, -1, 0)).rotation_difference(tangent)
            rot_euler = rot_diff.to_euler()
        
        for player in players:
            # プレイヤーのアニメーションロックを完全に解除
            if player.animation_data:
                player.animation_data.action = None
                
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
            
    # 安全な画面再描画のトリガー (コンテキストエラーの完全回避)
    def safe_redraw():
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception:
            pass
        return None
    bpy.app.timers.register(safe_redraw)


def register_handlers():
    """ハンドラの登録"""
    global _draw_handler, _dopesheet_draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_heatmap_callback, (), 'WINDOW', 'POST_VIEW'
        )
    if _dopesheet_draw_handler is None:
        _dopesheet_draw_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
            draw_dopesheet_heatmap_callback, (), 'WINDOW', 'POST_PIXEL'
        )
    if godeye_depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(godeye_depsgraph_update_handler)
    if godeye_frame_change_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(godeye_frame_change_handler)


def unregister_handlers():
    """ハンドラの解除"""
    global _draw_handler, _dopesheet_draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
    if _dopesheet_draw_handler is not None:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_dopesheet_draw_handler, 'WINDOW')
        _dopesheet_draw_handler = None
    if godeye_depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(godeye_depsgraph_update_handler)
    if godeye_frame_change_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(godeye_frame_change_handler)
