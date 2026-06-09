import bpy
import math

from . import op_export_scene


def _is_player_spawn_object(obj):
    return "player_spawn" in obj and bool(obj["player_spawn"])


def _patch_exporter():
    cls = op_export_scene.MYADDON_OT_export_scene
    if getattr(cls, "_player_spawn_patch_installed", False):
        return

    def parse_scene_recursive(self, file, object, level):
        indent = ""
        for _ in range(level):
            indent += "\t"

        obj_type = "PlayerSpawn" if _is_player_spawn_object(object) else object.type
        self.write_and_print(file, indent + obj_type)

        trans, rot, scale = object.matrix_local.decompose()
        rot = rot.to_euler()

        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)

        self.write_and_print(file, indent + "T %f %f %f" % (trans.x, trans.y, trans.z))
        self.write_and_print(file, indent + "R %f %f %f" % (rot.x, rot.y, rot.z))
        self.write_and_print(file, indent + "S %f %f %f" % (scale.x, scale.y, scale.z))

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

        # PlayerSpawn を持つオブジェクトは type を差し替える
        json_object["type"] = "PlayerSpawn" if _is_player_spawn_object(object) else object.type
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


class MYADDON_OT_add_player_spawn(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_player_spawn"
    bl_label = "Add Player Spawn"
    bl_description = "Add player spawn custom property"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.object is None:
            return {"CANCELLED"}

        context.object["player_spawn"] = True
        print("'player_spawn' カスタムプロパティを追加しました")
        return {"FINISHED"}


class OBJECT_PT_player_spawn(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_label = "Player Spawn"

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if obj is None:
            return

        if "player_spawn" in obj:
            layout.prop(obj, '["player_spawn"]', text="Player Spawn")
        else:
            layout.operator("myaddon.myaddon_ot_add_player_spawn")
