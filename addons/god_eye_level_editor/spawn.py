import bpy
import math
import os

from . import op_export_scene


class SpawnNames:
    PROTOTYPE = 0  # プロトタイプのオブジェクト名
    INSTANCE = 1   # 量産時のオブジェクト名
    FILENAME = 2   # リソースファイル名
    SPAWN_TYPE = 3 # エクスポートされる spawn プロパティの値
    INITIAL_ROT = 4 # 初期回転 (度数法)

    names = {}
    names["Enemy"] = ("PrototypeEnemySpawn", "EnemySpawn", "enemy/enemy.obj", "ENEMY", (0.0, 0.0, 0.0))
    names["Player"] = ("PrototypePlayerSpawn", "PlayerSpawn", "player/player.obj", "PLAYER", (0.0, 0.0, 0.0))


# _patch_exporter was removed and integrated directly into op_export_scene.py


# 汎用シンボルモデルインポート関数 (コンテキスト依存を避けるため直接呼び出せるように定義)
def import_symbol_model(spawn_type):
    if spawn_type not in SpawnNames.names:
        return False

    proto_name = SpawnNames.names[spawn_type][SpawnNames.PROTOTYPE]
    file_rel_path = SpawnNames.names[spawn_type][SpawnNames.FILENAME]

    # 重複ロード防止
    if bpy.data.objects.get(proto_name) is not None:
        return True

    addon_dir = os.path.dirname(__file__)
    obj_path = os.path.join(addon_dir, file_rel_path)

    if not os.path.exists(obj_path):
        print(f"Model not found: {obj_path}")
        return False

    old_objs = set(bpy.data.objects)
    try:
        try:
            bpy.ops.wm.obj_import(filepath=obj_path)
        except AttributeError:
            bpy.ops.import_scene.obj(filepath=obj_path)
    except Exception as e:
        print(f"Failed to import model: {e}")
        return False

    new_objs = set(bpy.data.objects) - old_objs
    if new_objs:
        new_obj = list(new_objs)[0]
        new_obj.name = proto_name
        # メッシュ名も固定
        new_obj.data.name = proto_name
        
        # プロトタイプオブジェクトはビューとレンダリングで非表示にする
        new_obj.hide_viewport = True
        new_obj.hide_render = True
        return True
    else:
        print("Failed to import model (no objects created).")
        return False


# 汎用シンボルインポートオペレータ
class MYADDON_OT_spawn_import_symbol(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_spawn_import_symbol"
    bl_label = "スポーンポイントシンボル読み込み"
    bl_description = "スポーンポイントのシンボルモデルを読み込みます"

    type: bpy.props.StringProperty(name="Type", default="Player")

    def execute(self, context):
        t = self.type
        if import_symbol_model(t):
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Failed to import symbol model for {t}")
            return {"CANCELLED"}


# 汎用シンボル作成オペレータ
class MYADDON_OT_spawn_create_symbol(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_spawn_create_symbol"
    bl_label = "出現ポイントシンボルの作成"
    bl_description = "出現ポイントのシンボルを作成します"
    bl_options = {"REGISTER", "UNDO"}

    type: bpy.props.StringProperty(name="Type", default="Player")

    def execute(self, context):
        t = self.type
        if t not in SpawnNames.names:
            return {"CANCELLED"}

        proto_name = SpawnNames.names[t][SpawnNames.PROTOTYPE]
        inst_name = SpawnNames.names[t][SpawnNames.INSTANCE]
        spawn_val = SpawnNames.names[t][SpawnNames.SPAWN_TYPE]
        file_rel_path = SpawnNames.names[t][SpawnNames.FILENAME]
        init_rot = SpawnNames.names[t][SpawnNames.INITIAL_ROT]

        proto_obj = bpy.data.objects.get(proto_name)

        if proto_obj is None:
            # プロトタイプがなければインポート
            bpy.ops.myaddon.myaddon_ot_spawn_import_symbol(type=t)
            proto_obj = bpy.data.objects.get(proto_name)
            if proto_obj is None:
                self.report({"ERROR"}, f"Failed to get prototype for {t}")
                return {"CANCELLED"}

        # メッシュデータを共有して新規インスタンスを作成
        new_obj = bpy.data.objects.new(name=inst_name, object_data=proto_obj.data)
        context.collection.objects.link(new_obj)

        # 選択状態にしてアクティブ化
        bpy.ops.object.select_all(action="DESELECT")
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        # 各種プロパティ設定
        new_obj["spawn"] = spawn_val
        new_obj["file_name"] = file_rel_path
        new_obj["area"] = 1
        new_obj["distance"] = 0.0
        
        # 位置と回転の設定
        new_obj.location = context.scene.cursor.location
        new_obj.rotation_euler = (math.radians(init_rot[0]), math.radians(init_rot[1]), math.radians(init_rot[2]))

        print(f"出現ポイントシンボル ({t}) を作成しました")
        return {"FINISHED"}


# プレイヤー専用シンボル作成オペレータ
class MYADDON_OT_spawn_create_player_symbol(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_spawn_create_player_symbol"
    bl_label = "プレイヤー出現ポイントシンボルの作成"
    bl_description = "プレイヤー出現ポイントのシンボルを作成します"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.myaddon.myaddon_ot_spawn_create_symbol('EXEC_DEFAULT', type="Player")
        return {"FINISHED"}


# 敵専用シンボル作成オペレータ
class MYADDON_OT_spawn_create_enemy_symbol(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_spawn_create_enemy_symbol"
    bl_label = "敵出現ポイントシンボルの作成"
    bl_description = "敵出現ポイントのシンボルを作成します"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.myaddon.myaddon_ot_spawn_create_symbol('EXEC_DEFAULT', type="Enemy")
        return {"FINISHED"}


# プロパティパネル
class OBJECT_PT_spawn(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_label = "Spawn"

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if obj is None:
            return

        if "spawn" in obj:
            layout.prop(obj, '["spawn"]', text="Spawn")
            if "file_name" in obj:
                layout.prop(obj, '["file_name"]', text="File Name")
        else:
            layout.operator("myaddon.myaddon_ot_spawn_create_player_symbol", text="Add Player Spawn")
            layout.operator("myaddon.myaddon_ot_spawn_create_enemy_symbol", text="Add Enemy Spawn")
