import bpy
import importlib

from . import op_stretch_vertex
from . import op_create_ico_sphere
from . import op_export_scene
from . import op_import_scene
from . import op_new_scene
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
    importlib.reload(op_new_scene)
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
    op_new_scene.MYADDON_OT_new_scene,
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
    spawn.MYADDON_OT_spawn_create_group_symbol,
    spawn.OBJECT_PT_spawn,
    panel_godeye.OBJECT_PT_godeye_main,
    panel_godeye.MYADDON_OT_create_area,
    panel_godeye.MYADDON_OT_create_stop_point,
    panel_godeye.MYADDON_OT_create_look_target,
    panel_godeye.MYADDON_OT_enemy_create_path,
    panel_godeye.MYADDON_OT_delete_area,
    panel_godeye.MYADDON_OT_select_object,
    panel_godeye.MYADDON_OT_create_rail,
    panel_godeye.MYADDON_OT_add_distance,
    panel_godeye.MYADDON_OT_update_rail_info,
    panel_godeye.MYADDON_OT_setup_godeye_workspace,
    panel_godeye.MYADDON_OT_settings_dialog,
    panel_godeye.MYADDON_OT_help_dialog,
)


def update_godeye_rail_thick(self, context):
    rail = self.godeye_rail_curve
    if rail:
        if self.godeye_rail_thick:
            rail.data.bevel_depth = 0.2
            rail.display_type = 'WIRE'
        else:
            rail.data.bevel_depth = 0.0
            rail.display_type = 'TEXTURED'
    # 再描画
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def apply_player_locked_rotation(scene):
    players = [obj for obj in scene.objects if obj.get("spawn") == "PLAYER"]
    for player in players:
        player.rotation_euler = scene.godeye_locked_player_rotation_euler
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


# 視点固定化設定変更時のコールバック
def update_godeye_lock_player_rotation(self, context):
    if self.godeye_lock_player_rotation:
        apply_player_locked_rotation(self)


# 固定向き設定変更時のコールバック
def update_godeye_locked_player_rotation_euler(self, context):
    if self.godeye_lock_player_rotation:
        apply_player_locked_rotation(self)


def register():
    # クラスの登録を最初に行う（CollectionProperty で GodeyeAreaZone を参照するため）
    for cls in classes:
        bpy.utils.register_class(cls)

    # set menu description with author name from bl_info
    author_name = bl_info.get("author", "Ren Akamine")
    menu_my_menu.TOPBAR_MT_my_menu.bl_description = "拡張メニュー by " + author_name

    # 基準レール用プロパティの登録 (カーブオブジェクトのみ許可)
    bpy.types.Scene.godeye_rail_curve = bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="基準レール",
        poll=lambda self, obj: obj.type == 'CURVE'
    )
    
    bpy.types.Scene.godeye_rail_thick = bpy.props.BoolProperty(
        name="レールを太く表示する",
        default=False,
        update=update_godeye_rail_thick,
        description="基準レールを太く可視化します（重い場合はOFFにしてください）"
    )
    
    # 視点固定化の有効化プロパティ
    bpy.types.Scene.godeye_lock_player_rotation = bpy.props.BoolProperty(
        name="視点の向きを固定する",
        default=False,
        update=update_godeye_lock_player_rotation,
        description="テスト走行中、プレイヤーの視点の向きを固定する"
    )
    
    # 固定する向きのプロパティ (オイラー角)
    bpy.types.Scene.godeye_locked_player_rotation_euler = bpy.props.FloatVectorProperty(
        name="固定する向き",
        subtype='EULER',
        default=(0.0, 0.0, 0.0),
        update=update_godeye_locked_player_rotation_euler,
        description="プレイヤーの向きを固定する際の角度（初期値は-Y方向）"
    )
    
    # 視覚効果のON/OFFプロパティの登録
    bpy.types.Scene.godeye_show_heatmap = bpy.props.BoolProperty(
        name="レールヒートマップ表示",
        default=True
    )
    bpy.types.Scene.godeye_show_dopesheet_heatmap = bpy.props.BoolProperty(
        name="ドープシートヒートマップ表示",
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
    bpy.types.Scene.godeye_show_areas = bpy.props.BoolProperty(
        name="レール戦闘エリア表示",
        default=True
    )
    bpy.types.Scene.godeye_show_dopesheet_areas = bpy.props.BoolProperty(
        name="ドープシート戦闘エリア表示",
        default=True
    )
    bpy.types.Scene.godeye_show_look_targets = bpy.props.BoolProperty(
        name="注視ターゲット・視線表示",
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
    bpy.types.Scene.godeye_heatmap_search_range = bpy.props.FloatProperty(
        name="密集判定範囲 (±m)",
        default=10.0,
        min=1.0,
        max=50.0,
        description="敵の密集度を計算する前後方向の探索範囲（m）"
    )
    bpy.types.Scene.godeye_heatmap_threshold_low = bpy.props.IntProperty(
        name="中密度閾値 (体数)",
        default=1,
        min=1,
        max=50,
        description="この体数以上で中密度（黄色）になります（未満は青色/安全）"
    )
    bpy.types.Scene.godeye_heatmap_threshold_high = bpy.props.IntProperty(
        name="高密度閾値 (体数)",
        default=3,
        min=2,
        max=50,
        description="この体数以上で高密度（赤色/激戦区）になります"
    )

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
    del bpy.types.Scene.godeye_rail_thick

    del bpy.types.Scene.godeye_lock_player_rotation
    del bpy.types.Scene.godeye_locked_player_rotation_euler

    del bpy.types.Scene.godeye_show_heatmap
    del bpy.types.Scene.godeye_show_dopesheet_heatmap
    del bpy.types.Scene.godeye_show_survival
    del bpy.types.Scene.godeye_show_fov
    del bpy.types.Scene.godeye_show_areas
    del bpy.types.Scene.godeye_show_dopesheet_areas
    del bpy.types.Scene.godeye_show_look_targets
    del bpy.types.Scene.godeye_enable_autosave
    del bpy.types.Scene.godeye_autosave_delay
    del bpy.types.Scene.godeye_fov_angle
    del bpy.types.Scene.godeye_fov_range
    del bpy.types.Scene.godeye_survival_length
    del bpy.types.Scene.godeye_heatmap_search_range
    del bpy.types.Scene.godeye_heatmap_threshold_low
    del bpy.types.Scene.godeye_heatmap_threshold_high
    
    print("レベルエディタが無効化されました")


if __name__ == "__main__":
    register()
