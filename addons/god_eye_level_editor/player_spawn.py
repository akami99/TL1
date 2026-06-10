import bpy
import math
import os

from . import op_export_scene


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


class MYADDON_OT_add_player_spawn(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_player_spawn"
    bl_label = "出現ポイントシンボルの作成"
    bl_description = "Add player spawn point symbol"
    bl_options = {"REGISTER", "UNDO"}

    create_new: bpy.props.BoolProperty(
        name="Create New Symbol",
        description="Create a new symbol object from player.obj instead of modifying selected object",
        default=True,
    )

    def execute(self, context):
        if not self.create_new:
            if context.object is None:
                return {"CANCELLED"}
            context.object["spawn"] = "PLAYER"
            print("'spawn' カスタムプロパティを追加しました")
            return {"FINISHED"}

        addon_dir = os.path.dirname(__file__)
        obj_path = os.path.join(addon_dir, "player", "player.obj")

        if not os.path.exists(obj_path):
            self.report({"ERROR"}, f"Player model not found: {obj_path}")
            return {"CANCELLED"}

        mesh_name = "player"
        player_mesh = bpy.data.meshes.get(mesh_name)

        if player_mesh is None:
            old_objs = set(bpy.data.objects)
            try:
                bpy.ops.wm.obj_import(filepath=obj_path)
            except AttributeError:
                bpy.ops.import_scene.obj(filepath=obj_path)

            new_objs = set(bpy.data.objects) - old_objs
            if new_objs:
                new_obj = list(new_objs)[0]
                player_mesh = new_obj.data
                player_mesh.name = mesh_name
            else:
                self.report({"ERROR"}, "Failed to import player model.")
                return {"CANCELLED"}
        else:
            new_obj = bpy.data.objects.new(name="player", object_data=player_mesh)
            context.collection.objects.link(new_obj)

        bpy.ops.object.select_all(action="DESELECT")
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        new_obj["spawn"] = "PLAYER"
        new_obj.location = context.scene.cursor.location
        new_obj.rotation_euler = (math.radians(90.0), 0.0, math.radians(180.0))

        print("出現ポイントシンボルを作成しました")
        return {"FINISHED"}


class OBJECT_PT_player_spawn(bpy.types.Panel):
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
        else:
            op = layout.operator("myaddon.myaddon_ot_add_player_spawn", text="Add Spawn")
            op.create_new = False


