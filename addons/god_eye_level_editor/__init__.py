import bpy
import importlib

from . import op_stretch_vertex
from . import op_create_ico_sphere
from . import op_export_scene
from . import menu_my_menu
from . import op_add_filename
from . import panel_file_name
from . import op_add_collider
from . import panel_collider
from . import draw_collider
from . import disabled
from . import player_spawn

# update exporter to support new custom properties
if "op_stretch_vertex" in locals():
    importlib.reload(op_stretch_vertex)
    importlib.reload(op_create_ico_sphere)
    importlib.reload(op_export_scene)
    importlib.reload(op_add_filename)
    importlib.reload(op_add_collider)
    importlib.reload(panel_file_name)
    importlib.reload(panel_collider)
    importlib.reload(menu_my_menu)
    importlib.reload(draw_collider)
    importlib.reload(disabled)
    importlib.reload(player_spawn)
    print("レベルエディタ: サブモジュールをリロードしました")
else:
    print("レベルエディタ: サブモジュールを初回インポートしました")

# addon infomation
bl_info = {
    "name": "神サマ目線",
    "author": "Ren Akamine",
    "version": (1, 0, 0),
    "blender": (4, 4, 0),
    "location": "",
    "description": "A Blender add-on for rail shooters to visualize and edit enemy spawns and event pacing based on player distance directly in the viewport.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Object"
}

# classes to register
classes = (
    op_stretch_vertex.MYADDON_OT_stretch_vertex,
    op_create_ico_sphere.MYADDON_OT_create_ico_sphere,
    op_export_scene.MYADDON_OT_export_scene,
    menu_my_menu.TOPBAR_MT_my_menu,
    op_add_filename.MYADDON_OT_add_filename,
    panel_file_name.OBJECT_PT_file_name,
    op_add_collider.MYADDON_OT_add_collider,
    panel_collider.OBJECT_PT_collider,
    disabled.MYADDON_OT_add_disabled,
    disabled.OBJECT_PT_disabled,
    player_spawn.MYADDON_OT_add_player_spawn,
    player_spawn.OBJECT_PT_player_spawn,
)


def register():
    # set menu description with author name from bl_info
    author_name = bl_info.get("author", "Ren Akamine")
    menu_my_menu.TOPBAR_MT_my_menu.bl_description = "拡張メニュー by " + author_name

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_editor_menus.append(menu_my_menu.TOPBAR_MT_my_menu.submenu)
    draw_collider.DrawCollider.handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_collider.DrawCollider.draw_collider,
        (),
        "WINDOW",
        "POST_VIEW",
    )
    print("レベルエディタが有効化されました")


def unregister():
    bpy.types.TOPBAR_MT_editor_menus.remove(menu_my_menu.TOPBAR_MT_my_menu.submenu)
    bpy.types.SpaceView3D.draw_handler_remove(draw_collider.DrawCollider.handle, "WINDOW")

    for cls in classes:
        bpy.utils.unregister_class(cls)
    print("レベルエディタが無効化されました")


if __name__ == "__main__":
    register()
