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


def _patch_exporter():
    cls = op_export_scene.MYADDON_OT_export_scene
    if getattr(cls, "_player_spawn_patch_installed", False):
        return

    def parse_scene_recursive(self, file, object, level):
        indent = ""
        for _ in range(level):
            indent += "\t"

        self.write_and_print(file, indent + object.type)

        trans, rot, scale = object.matrix_local.decompose()
        rot = rot.to_euler()

        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)

        self.write_and_print(file, indent + "T %f %f %f" % (trans.x, trans.y, trans.z))
        self.write_and_print(file, indent + "R %f %f %f" % (rot.x, rot.y, rot.z))
        self.write_and_print(file, indent + "S %f %f %f" % (scale.x, scale.y, scale.z))

        if "spawn" in object:
            self.write_and_print(file, indent + "SPAWN %s" % object["spawn"])

        if "file_name" in object:
            self.write_and_print(file, indent + "N %s" % object["file_name"])

        if "collider" in object:
            self.write_and_print(file, indent + "C %s" % object["collider"])
            temp_str = indent + "CC %f %f %f"
            temp_str %= (
                object["collider_center"][0],
                object["collider_center"][1],
                object["collider_center"][2],
            )
            self.write_and_print(file, temp_str)
            temp_str = indent + "CS %f %f %f"
            temp_str %= (
                object["collider_size"][0],
                object["collider_size"][1],
                object["collider_size"][2],
            )
            self.write_and_print(file, temp_str)

        self.write_and_print(file, indent + "END")
        self.write_and_print(file, indent)

        for child in object.children:
            self.parse_scene_recursive(file, child, level + 1)

    def parse_scene_recursive_json(self, data_parent, object, level):
        json_object = dict()

        json_object["type"] = object.type
        json_object["name"] = object.name

        trans, rot, scale = object.matrix_local.decompose()
        rot = rot.to_euler()

        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)

        transform = dict()
        transform["translation"] = (trans.x, trans.y, trans.z)
        transform["rotation"] = (rot.x, rot.y, rot.z)
        transform["scaling"] = (scale.x, scale.y, scale.z)
        json_object["transform"] = transform

        if "disabled" in object:
            json_object["disabled"] = object["disabled"]

        if "spawn" in object:
            json_object["spawn"] = object["spawn"]

        if "file_name" in object:
            json_object["file_name"] = object["file_name"]

        if "collider" in object:
            collider = dict()
            collider["type"] = object["collider"]
            collider["center"] = object["collider_center"].to_list()
            collider["size"] = object["collider_size"].to_list()
            json_object["collider"] = collider

        data_parent.append(json_object)

        if len(object.children) > 0:
            json_object["children"] = list()
            for child in object.children:
                self.parse_scene_recursive_json(json_object["children"], child, level + 1)

    cls.parse_scene_recursive = parse_scene_recursive
    cls.parse_scene_recursive_json = parse_scene_recursive_json
    cls._player_spawn_patch_installed = True


_patch_exporter()


# 汎用シンボルインポートオペレータ
class MYADDON_OT_spawn_import_symbol(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_spawn_import_symbol"
    bl_label = "スポーンポイントシンボル読み込み"
    bl_description = "スポーンポイントのシンボルモデルを読み込みます"

    type: bpy.props.StringProperty(name="Type", default="Player")

    def execute(self, context):
        t = self.type
        if t not in SpawnNames.names:
            return {"CANCELLED"}

        proto_name = SpawnNames.names[t][SpawnNames.PROTOTYPE]
        file_rel_path = SpawnNames.names[t][SpawnNames.FILENAME]

        # 重複ロード防止
        if bpy.data.objects.get(proto_name) is not None:
            return {"CANCELLED"}

        addon_dir = os.path.dirname(__file__)
        obj_path = os.path.join(addon_dir, file_rel_path)

        if not os.path.exists(obj_path):
            self.report({"ERROR"}, f"Model not found: {obj_path}")
            return {"CANCELLED"}

        old_objs = set(bpy.data.objects)
        try:
            bpy.ops.wm.obj_import(filepath=obj_path)
        except AttributeError:
            bpy.ops.import_scene.obj(filepath=obj_path)

        new_objs = set(bpy.data.objects) - old_objs
        if new_objs:
            new_obj = list(new_objs)[0]
            new_obj.name = proto_name
            # メッシュ名も固定
            new_obj.data.name = proto_name
            
            # プロトタイプオブジェクトはビューとレンダリングで非表示にする
            new_obj.hide_viewport = True
            new_obj.hide_render = True
        else:
            self.report({"ERROR"}, "Failed to import model.")
            return {"CANCELLED"}

        return {"FINISHED"}


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
