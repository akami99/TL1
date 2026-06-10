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

            # 2. spawn属性がなく、file_name属性がある場合（モデル読み込み）
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

            # 3. それ以外（MESHや一般的なメッシュ等）
            if new_obj is None:
                if obj_type == "MESH":
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.ops.mesh.primitive_cube_add(size=1.0)
                    new_obj = context.active_object
                    new_obj.name = obj_name
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

        self.report({'INFO'}, "シーン情報をImportしました")
        return {'FINISHED'}
