import bpy
import importlib

# --- サブモジュールのインポート ---
# from . import は常に実行する（初回・リロード共通）
from . import metadata
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

# --- リロード ---
# 2回目以降の読み込み（F8 や Reload Scripts）時にサブモジュールを強制再読み込み
# "metadata" がすでに locals() にある = リロードされた = 2回目以降
if "metadata" in locals():
    importlib.reload(metadata)
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
    print("レベルエディタ: サブモジュールをリロードしました。")
else:
    print("レベルエディタ: サブモジュールを初回インポートしました。")

# --- bl_infoの登録 ---
# Blenderがアドオンを認識できるように、metadataからbl_infoをここに持ってくる
bl_info = metadata.bl_info

# Blenderに登録するクラスリスト
# ※ DrawCollider は bpy.types.* を継承しない純粋な Python クラスのため
#    register_class() には渡さず、draw_handler として手動登録する
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
)

#アドオン有効化時コールバック
def register():
    # Blenderにクラスを登録
    for cls in classes:
        bpy.utils.register_class(cls)

    # メニューに項目を追加
    bpy.types.TOPBAR_MT_editor_menus.append(menu_my_menu.TOPBAR_MT_my_menu.submenu)
    # 3Dビューに描画関数を追加
    draw_collider.DrawCollider.handle = bpy.types.SpaceView3D.draw_handler_add(draw_collider.DrawCollider.draw_collider, (), "WINDOW", "POST_VIEW")
    print("レベルエディタが有効化されました。")

#アドオン無効化時コールバック
def unregister():
    # メニューから項目を削除
    bpy.types.TOPBAR_MT_editor_menus.remove(menu_my_menu.TOPBAR_MT_my_menu.submenu)
    # 3Dビューから描画関数を削除
    bpy.types.SpaceView3D.draw_handler_remove(draw_collider.DrawCollider.handle, "WINDOW")

    # Blenderからクラスを削除
    for cls in classes:
        bpy.utils.unregister_class(cls)
    print("レベルエディタが無効化されました。")

# テスト実行用コード
if __name__ == "__main__":
    register()


