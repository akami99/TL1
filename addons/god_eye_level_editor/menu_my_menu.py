import bpy

# トップバーの拡張メニュー
class TOPBAR_MT_my_menu(bpy.types.Menu):
    # Blenderがクラスを識別する為の固有の文字列
    bl_idname = "myaddon.topbar_mt_my_menu"
    # メニューのラベルとして表示される文字列
    bl_label = "MyMenu"
    # 著者表示用の文字列(__init__.pyで設定する)
    bl_description = "" 

    # サブメニューの描画
    def draw(self, context):
        # トップバーの「エディターメニュー」に項目（オペレータ）を追加
        self.layout.operator("myaddon.myaddon_ot_stretch_vertex", text="頂点を伸ばす")
        self.layout.operator("myaddon.myaddon_ot_create_object", text="ICO球生成")
        self.layout.separator()
        self.layout.operator("myaddon.myaddon_ot_new_scene", text="新規シーン作成", icon='FILE_NEW')
        self.layout.separator()
        self.layout.operator("myaddon.myaddon_ot_import_scene", text="シーン入力")
        self.layout.operator("myaddon.myaddon_ot_export_scene", text="シーン出力")
        self.layout.operator("myaddon.myaddon_ot_spawn_create_enemy_symbol", text="敵出現ポイントシンボルの作成")
        self.layout.operator("myaddon.myaddon_ot_spawn_create_group_symbol", text="集団敵出現ポイントシンボルの作成")
        self.layout.operator("myaddon.myaddon_ot_spawn_create_player_symbol", text="プレイヤー出現ポイントシンボルの作成")
        self.layout.separator()
        self.layout.operator("myaddon.myaddon_ot_settings_dialog", text="設定", icon='PREFERENCES')
        self.layout.operator("myaddon.myaddon_ot_help_dialog", text="使い方ヘルプ", icon='HELP')

    # 既存のメニューにサブメニューを追加
    def submenu(self, context):
        # ID指定でサブメニューを追加
        self.layout.menu(TOPBAR_MT_my_menu.bl_idname)
