import bpy
import math
import os
import json
import mathutils
from bpy_extras.io_utils import ImportHelper

class MYADDON_OT_import_scene(bpy.types.Operator, ImportHelper):
    bl_idname = "myaddon.myaddon_ot_import_scene"
    bl_label = "シーン読み込み"
    bl_description = "シーン情報をImportして復元します"
    
    filename_ext = ".json"
    
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        filepath = self.filepath
        if not os.path.exists(filepath):
            self.report({'ERROR'}, f"File not found: {filepath}")
            return {'CANCELLED'}

        print("シーン情報読み込み開始... %r" % filepath)
        
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load JSON: {str(e)}")
            return {'CANCELLED'}

        if data.get("name") != "scene":
            self.report({'ERROR'}, "Invalid scene file format.")
            return {'CANCELLED'}

        # --- 事前準備: JSON内のspawn情報をスキャンし、安定したコンテキストの状態でプロトタイプを先んじてロードしておく ---
        from .spawn import import_symbol_model
        def scan_and_load_prototypes(objects_list):
            for obj in objects_list:
                if "spawn" in obj:
                    spawn_val = obj["spawn"]
                    spawn_type = "Player" if spawn_val == "PLAYER" else "Enemy"
                    import_symbol_model(spawn_type)
                if "children" in obj:
                    scan_and_load_prototypes(obj["children"])
        
        scan_and_load_prototypes(data.get("objects", []))

        # シーン内の一般オブジェクトをクリア (Prototypeオブジェクトは保護)
        for obj in list(context.scene.objects):
            if obj.name.startswith("Prototype"):
                continue
            bpy.data.objects.remove(obj, do_unlink=True)

        # アクティブコレクションをマスターコレクションにリセットして安定化
        context.view_layer.active_layer_collection = context.view_layer.layer_collection

        addon_dir = os.path.dirname(__file__)

        # 再帰的にオブジェクトを生成するヘルパー関数
        def create_object_recursive(obj_data, parent_obj=None):
            obj_name = obj_data.get("name", "Object")
            
            # 古いJSONの互換性対策: プロトタイプオブジェクトの直接生成はスキップする
            if obj_name.startswith("Prototype"):
                return

            obj_type = obj_data.get("type", "EMPTY")
            transform = obj_data.get("transform", {})
            
            trans = transform.get("translation", (0.0, 0.0, 0.0))
            rot = transform.get("rotation", (0.0, 0.0, 0.0))
            scale = transform.get("scaling", (1.0, 1.0, 1.0))
            
            new_obj = None

            # 1. spawn属性がある場合は出現ポイントシンボルとして作成
            if "spawn" in obj_data:
                spawn_val = obj_data["spawn"]
                spawn_type = "Player" if spawn_val == "PLAYER" else "Enemy"
                
                # spawn.pyのSpawnNamesを利用 (プロトタイプは事前ロードされているため必ず存在するはず)
                from .spawn import SpawnNames
                proto_name = SpawnNames.names[spawn_type][SpawnNames.PROTOTYPE]
                
                proto_obj = bpy.data.objects.get(proto_name)
                if proto_obj is not None:
                    # プロトタイプメッシュを共有して作成
                    new_obj = bpy.data.objects.new(name=obj_name, object_data=proto_obj.data)
                    context.collection.objects.link(new_obj)
                else:
                    print(f"Prototype for {spawn_type} not found, fallback to empty.")

            # 2. look_target属性がある場合（注視ターゲットEmpty作成）
            elif "look_target" in obj_data:
                new_obj = bpy.data.objects.new(name=obj_name, object_data=None)
                new_obj.empty_display_type = 'SPHERE'
                new_obj.empty_display_size = 0.6
                context.collection.objects.link(new_obj)

            # 3. file_name属性がある場合（モデル読み込み）
            elif "file_name" in obj_data and obj_data["file_name"]:
                file_rel_path = obj_data["file_name"]
                
                # パス判定
                model_path = os.path.join(addon_dir, file_rel_path)
                if not os.path.exists(model_path):
                    model_path = os.path.join(os.path.dirname(filepath), file_rel_path)
                
                if os.path.exists(model_path):
                    old_objs = set(bpy.data.objects)
                    try:
                        # 既存選択を解除
                        bpy.ops.object.select_all(action='DESELECT')
                        try:
                            bpy.ops.wm.obj_import(filepath=model_path)
                        except AttributeError:
                            bpy.ops.import_scene.obj(filepath=model_path)
                        
                        new_imported_objs = set(bpy.data.objects) - old_objs
                        if new_imported_objs:
                            new_obj = list(new_imported_objs)[0]
                            new_obj.name = obj_name
                        else:
                            print(f"Failed to import mesh from {model_path}")
                    except Exception as e:
                        print(f"Error importing model {model_path}: {e}")
                
                # モデルが見つからない、または読み込めなかった場合はCubeで代替
                if new_obj is None:
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.ops.mesh.primitive_cube_add(size=1.0)
                    new_obj = context.active_object
                    new_obj.name = obj_name

            # 3. それ以外（MESH、CURVE、一般的なオブジェクト等）
            if new_obj is None:
                if obj_type == "MESH":
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.ops.mesh.primitive_cube_add(size=1.0)
                    new_obj = context.active_object
                    new_obj.name = obj_name
                elif obj_type == "CURVE":
                    # 新規カーブデータブロックの作成とオブジェクト化
                    curve_data = bpy.data.curves.new(name=obj_name, type='CURVE')
                    new_obj = bpy.data.objects.new(name=obj_name, object_data=curve_data)
                    context.collection.objects.link(new_obj)
                    
                    # カーブ幾何データの復元
                    if "curve" in obj_data:
                        c_data = obj_data["curve"]
                        curve_data.dimensions = c_data.get("dimensions", '3D')
                        curve_data.bevel_depth = c_data.get("bevel_depth", 0.2)
                        
                        for spline_data in c_data.get("splines", []):
                            s_type = spline_data.get("type", 'BEZIER')
                            spline = curve_data.splines.new(type=s_type)
                            spline.use_cyclic_u = spline_data.get("use_cyclic_u", False)
                            
                            if s_type == 'BEZIER':
                                bp_list = spline_data.get("bezier_points", [])
                                # spline作成時にすでにデフォルトで1点あるので、追加分を確保
                                spline.bezier_points.add(len(bp_list) - 1)
                                
                                for idx, pt in enumerate(bp_list):
                                    bp = spline.bezier_points[idx]
                                    bp.co = pt["co"]
                                    bp.handle_left = pt["handle_left"]
                                    bp.handle_right = pt["handle_right"]
                                    bp.handle_left_type = pt.get("handle_left_type", 'FREE')
                                    bp.handle_right_type = pt.get("handle_right_type", 'FREE')
                            else:
                                p_list = spline_data.get("points", [])
                                spline.points.add(len(p_list) - 1)
                                
                                for idx, co_w in enumerate(p_list):
                                    p = spline.points[idx]
                                    p.co = co_w
                else:
                    # 空のオブジェクト
                    new_obj = bpy.data.objects.new(name=obj_name, object_data=None)
                    context.collection.objects.link(new_obj)

            # 親の設定 (トランスフォーム設定前に親にする)
            if parent_obj:
                new_obj.parent = parent_obj

            # トランスフォームの適用 (親との相対関係を反映)
            new_obj.location = (trans[0], trans[1], trans[2])
            new_obj.rotation_euler = (math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2]))
            new_obj.scale = (scale[0], scale[1], scale[2])

            # カスタムプロパティの復元
            if "disabled" in obj_data:
                new_obj["disabled"] = obj_data["disabled"]
                
            if "spawn" in obj_data:
                new_obj["spawn"] = obj_data["spawn"]
                
            if "file_name" in obj_data:
                new_obj["file_name"] = obj_data["file_name"]

            if "distance" in obj_data:
                new_obj["distance"] = obj_data["distance"]

            if "area" in obj_data:
                new_obj["area"] = True
                if "end_distance" in obj_data:
                    new_obj["end_distance"] = obj_data["end_distance"]
                if "time_limit" in obj_data:
                    new_obj["time_limit"] = obj_data["time_limit"]

            if "stop_point" in obj_data:
                new_obj["stop_point"] = True
                if "time_limit" in obj_data:
                    new_obj["time_limit"] = obj_data["time_limit"]

            if "look_target" in obj_data:
                new_obj["look_target"] = True
                new_obj["duration_distance"] = obj_data.get("duration_distance", 0.0)
                new_obj["blend_distance"] = obj_data.get("blend_distance", 3.0)

            if "collider" in obj_data:
                coll_data = obj_data["collider"]
                new_obj["collider"] = coll_data.get("type", "BOX")
                new_obj["collider_center"] = mathutils.Vector(coll_data.get("center", [0.0, 0.0, 0.0]))
                new_obj["collider_size"] = mathutils.Vector(coll_data.get("size", [1.0, 1.0, 1.0]))

            # 子要素の再帰処理
            if "children" in obj_data:
                for child_data in obj_data["children"]:
                    create_object_recursive(child_data, parent_obj=new_obj)

        # 全てのオブジェクトを再帰的に生成
        for obj_data in data.get("objects", []):
            create_object_recursive(obj_data)

        # もしobjects内にareaオブジェクトが存在せず、トップレベルareasにデータがある場合の復元
        from .draw_heatmap import distance_to_co, get_curve_cache
        cache = get_curve_cache()
        points = cache.get("points", [])
        distances = cache.get("distances", [])

        has_area_obj = any(obj.get("area") for obj in context.scene.objects)
        if not has_area_obj and "areas" in data:
            for a_data in data["areas"]:
                a_name = a_data.get("name", "Area_Zone")
                a_dist = a_data.get("distance", a_data.get("start_distance", 0.0))
                a_end_dist = a_data.get("end_distance", a_dist + 30.0)
                a_time = a_data.get("time_limit", 60.0)

                area_obj = bpy.data.objects.new(name=a_name, object_data=None)
                area_obj.empty_display_type = 'SINGLE_ARROW'
                area_obj.empty_display_size = 1.0
                context.collection.objects.link(area_obj)
                area_obj.location = distance_to_co(a_dist, points, distances) if points else (0, 0, 0)
                area_obj["area"] = True
                area_obj["distance"] = a_dist
                area_obj["end_distance"] = a_end_dist
                area_obj["time_limit"] = a_time

        has_stop_obj = any(obj.get("stop_point") for obj in context.scene.objects)
        if not has_stop_obj and "stop_points" in data:
            for s_data in data["stop_points"]:
                s_name = s_data.get("name", "StopPoint")
                s_dist = s_data.get("distance", 0.0)
                s_time = s_data.get("time_limit", 0.0)

                stop_obj = bpy.data.objects.new(name=s_name, object_data=None)
                stop_obj.empty_display_type = 'CUBE'
                stop_obj.empty_display_size = 1.0
                context.collection.objects.link(stop_obj)
                stop_obj.location = distance_to_co(s_dist, points, distances) if points else (0, 0, 0)
                stop_obj["stop_point"] = True
                stop_obj["distance"] = s_dist
                stop_obj["time_limit"] = s_time

        has_look_obj = any(obj.get("look_target") for obj in context.scene.objects)
        if not has_look_obj and "look_targets" in data:
            for l_data in data["look_targets"]:
                l_name = l_data.get("name", "LookTarget")
                l_dist = l_data.get("distance", 0.0)
                l_duration = l_data.get("duration_distance", 0.0)
                l_blend = l_data.get("blend_distance", 3.0)
                l_pos = l_data.get("position", [0.0, 0.0, 0.0])

                look_obj = bpy.data.objects.new(name=l_name, object_data=None)
                look_obj.empty_display_type = 'SPHERE'
                look_obj.empty_display_size = 0.6
                context.collection.objects.link(look_obj)
                look_obj.location = (l_pos[0], l_pos[1], l_pos[2])
                look_obj["look_target"] = True
                look_obj["distance"] = l_dist
                look_obj["duration_distance"] = l_duration
                look_obj["blend_distance"] = l_blend

        # インポート完了後にキャッシュを強制再構築し、バウンディングボックスの評価を更新
        if context.scene.godeye_rail_curve:
            from .draw_heatmap import update_curve_cache
            update_curve_cache(context.scene.godeye_rail_curve)

        # テスト走行シミュレータの初期化
        if context.scene.godeye_rail_curve:
            rail = context.scene.godeye_rail_curve
            rail["godeye_test_run_dist"] = 0.0
            from .draw_heatmap import get_curve_geometry
            _, _, total_dist = get_curve_geometry(rail)
            try:
                rail.id_properties_ensure()
                ui_api = rail.id_properties_ui("godeye_test_run_dist")
                ui_api.update(min=0.0, max=total_dist)
                
                # 再生終了フレームをレールの長さに合わせて自動更新 (1m=10f)
                context.scene.frame_end = int(total_dist * 10) + 1
            except Exception:
                pass

        # インポート完了時のキーフレーム同期
        from .draw_heatmap import sync_distance_to_keyframe, sync_area_distance_to_keyframe
        for obj in context.scene.objects:
            if "spawn" in obj or obj.get("stop_point") or obj.get("look_target"):
                sync_distance_to_keyframe(obj)
            elif obj.get("area"):
                sync_area_distance_to_keyframe(obj)

        self.report({'INFO'}, "[God Eye] Scene imported")
        return {'FINISHED'}
