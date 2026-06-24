import bpy
import importlib

from . import op_stretch_vertex
from . import op_create_ico_sphere
from . import op_export_scene
from . import op_import_scene
from . import menu_my_menu
from . import op_add_filename
from . import panel_file_name
from . import op_add_collider
from . import panel_collider
from . import draw_collider
from . import draw_heatmap
from . import disabled
from . import spawn
from . import panel_godeye

# update exporter to support new custom properties
if "op_stretch_vertex" in locals():
    importlib.reload(op_stretch_vertex)
    importlib.reload(op_create_ico_sphere)
    importlib.reload(op_export_scene)
    importlib.reload(op_import_scene)
    importlib.reload(op_add_filename)
    importlib.reload(op_add_collider)
    importlib.reload(panel_file_name)
    importlib.reload(panel_collider)
    importlib.reload(menu_my_menu)
    importlib.reload(draw_collider)
    importlib.reload(draw_heatmap)
    importlib.reload(disabled)
    importlib.reload(spawn)
    importlib.reload(panel_godeye)
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
    op_import_scene.MYADDON_OT_import_scene,
    menu_my_menu.TOPBAR_MT_my_menu,
    op_add_filename.MYADDON_OT_add_filename,
    panel_file_name.OBJECT_PT_file_name,
    op_add_collider.MYADDON_OT_add_collider,
    panel_collider.OBJECT_PT_collider,
    disabled.MYADDON_OT_add_disabled,
    disabled.OBJECT_PT_disabled,
    spawn.MYADDON_OT_spawn_import_symbol,
    spawn.MYADDON_OT_spawn_create_symbol,
    spawn.MYADDON_OT_spawn_create_player_symbol,
    spawn.MYADDON_OT_spawn_create_enemy_symbol,
    spawn.OBJECT_PT_spawn,
    panel_godeye.OBJECT_PT_godeye_main,
    panel_godeye.MYADDON_OT_add_area,
    panel_godeye.MYADDON_OT_create_rail,
    panel_godeye.MYADDON_OT_add_distance,
    panel_godeye.MYADDON_OT_settings_dialog,
    panel_godeye.MYADDON_OT_help_dialog,
)


# 最大距離設定変更時のコールバック
def update_godeye_test_run_max_dist(self, context):
    try:
        if "godeye_test_run_dist" not in self:
            self["godeye_test_run_dist"] = 0.0
        ui_api = self.id_properties_ui("godeye_test_run_dist")
        ui_api.update(min=0.0, max=self.godeye_test_run_max_dist)
    except Exception as e:
        print(f"Failed to update test_run_dist UI max: {e}")


def register():
    # set menu description with author name from bl_info
    author_name = bl_info.get("author", "Ren Akamine")
    menu_my_menu.TOPBAR_MT_my_menu.bl_description = "拡張メニュー by " + author_name

    # 基準レール用プロパティの登録 (カーブオブジェクトのみ許可)
    bpy.types.Scene.godeye_rail_curve = bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="基準レール",
        poll=lambda self, obj: obj.type == 'CURVE'
    )
    
    # 走行位置最大距離（手動設定可能プロパティ）の登録
    bpy.types.Scene.godeye_test_run_max_dist = bpy.props.FloatProperty(
        name="テスト走行最大距離 (m)",
        default=100.0,
        min=0.0,
        update=update_godeye_test_run_max_dist,
        description="シミュレータ上で走行可能な最大距離（手動変更可能）"
    )
    

    
    # 視覚効果のON/OFFプロパティの登録
    bpy.types.Scene.godeye_show_heatmap = bpy.props.BoolProperty(
        name="ヒートマップ表示",
        default=True
    )
    bpy.types.Scene.godeye_show_survival = bpy.props.BoolProperty(
        name="生存ライン表示",
        default=True
    )
    bpy.types.Scene.godeye_show_fov = bpy.props.BoolProperty(
        name="視野（FOV）表示",
        default=True
    )

    bpy.types.Scene.godeye_enable_autosave = bpy.props.BoolProperty(
        name="自動エクスポート有効化",
        default=True
    )
    bpy.types.Scene.godeye_autosave_delay = bpy.props.FloatProperty(
        name="自動保存遅延（秒）",
        default=0.5,
        min=0.1,
        max=5.0
    )
    bpy.types.Scene.godeye_fov_angle = bpy.props.FloatProperty(
        name="視野角（度）",
        default=60.0,
        min=10.0,
        max=180.0
    )
    bpy.types.Scene.godeye_fov_range = bpy.props.FloatProperty(
        name="視野射程（m）",
        default=15.0,
        min=1.0,
        max=100.0
    )
    bpy.types.Scene.godeye_survival_length = bpy.props.FloatProperty(
        name="生存ライン長さ（m）",
        default=20.0,
        min=1.0,
        max=100.0
    )

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_editor_menus.append(menu_my_menu.TOPBAR_MT_my_menu.submenu)
    
    # コライダーの枠線描画ハンドラ
    draw_collider.DrawCollider.handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_collider.DrawCollider.draw_collider,
        (),
        "WINDOW",
        "POST_VIEW",
    )
    
    # ヒートマップ描画 & 双方向同期ハンドラの登録
    draw_heatmap.register_handlers()

    print("レベルエディタが有効化されました")


def unregister():
    # ヒートマップ描画 & 双方向同期ハンドラの解除
    draw_heatmap.unregister_handlers()

    bpy.types.TOPBAR_MT_editor_menus.remove(menu_my_menu.TOPBAR_MT_my_menu.submenu)
    bpy.types.SpaceView3D.draw_handler_remove(draw_collider.DrawCollider.handle, "WINDOW")

    for cls in classes:
        bpy.utils.unregister_class(cls)
        
    # プロパティの削除
    del bpy.types.Scene.godeye_rail_curve
    del bpy.types.Scene.godeye_test_run_max_dist

    del bpy.types.Scene.godeye_show_heatmap
    del bpy.types.Scene.godeye_show_survival
    del bpy.types.Scene.godeye_show_fov
    del bpy.types.Scene.godeye_enable_autosave
    del bpy.types.Scene.godeye_autosave_delay
    del bpy.types.Scene.godeye_fov_angle
    del bpy.types.Scene.godeye_fov_range
    del bpy.types.Scene.godeye_survival_length
    
    print("レベルエディタが無効化されました")


if __name__ == "__main__":
    register()
