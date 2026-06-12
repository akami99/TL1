import bpy

class OBJECT_PT_godeye_main(bpy.types.Panel):
    bl_label = "神サマ目線ツール"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "神サマ目線"  # Nパネルのタブ名

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- ① レール設定 (Setup) ---
        box_setup = layout.box()
        box_setup.label(text="① レール設定 (Setup)", icon='PARTICLE_PATH')
        box_setup.prop(scene, "godeye_rail_curve", text="")

        rail_obj = scene.godeye_rail_curve
        if not rail_obj:
            box_setup.warning(text="基準レールを設定してください。")
            return

        # カーブの総距離を計算
        from .draw_heatmap import get_curve_geometry
        _, _, total_dist = get_curve_geometry(rail_obj)
        box_setup.label(text=f"総延長距離: {total_dist:.2f} m")

        # --- ② イベント編集 (Event Editor) ---
        box_editor = layout.box()
        box_editor.label(text="② イベント編集 (Event Editor)", icon='EDITMODE_HLT')

        # 新規作成ボタン
        row_create = box_editor.row(align=True)
        row_create.operator("myaddon.myaddon_ot_spawn_create_player_symbol", text="プレイヤー追加", icon='OUTLINER_OB_LIGHT')
        row_create.operator("myaddon.myaddon_ot_spawn_create_enemy_symbol", text="エネミー追加", icon='OUTLINER_OB_MESH')
        box_editor.separator()

        active_obj = context.active_object
        if active_obj and "spawn" in active_obj:
            box_editor.label(text=f"選択中: {active_obj.name}", icon='OBJECT_DATA')
            
            # distanceプロパティの調整用スライダー
            if "distance" in active_obj:
                try:
                    ui_api = active_obj.id_properties_ui("distance")
                    ui_api.update(min=0.0, max=total_dist, description="始点からの進行距離（m）")
                except Exception as e:
                    print(f"Failed to update property UI limits: {e}")
                box_editor.prop(active_obj, '["distance"]', text="出現位置 (m)", slider=True)
                
            # areaプロパティ (エリア番号、タイムクライシス等のロック戦闘エリアをサポート)
            if "area" in active_obj:
                try:
                    ui_api_area = active_obj.id_properties_ui("area")
                    ui_api_area.update(min=1, max=100, step=1, description="足を止めて戦闘を行うエリア番号")
                except Exception as e:
                    print(f"Failed to update area UI: {e}")
                box_editor.prop(active_obj, '["area"]', text="エリア番号")
            else:
                box_editor.operator("myaddon.myaddon_ot_add_area", text="エリア番号を追加", icon='ADD')
            
            # 各種プロパティ
            box_editor.separator()
            box_editor.prop(active_obj, '["spawn"]', text="出現タイプ")
            if "file_name" in active_obj:
                box_editor.prop(active_obj, '["file_name"]', text="モデル")
            
            if "disabled" in active_obj:
                box_editor.prop(active_obj, '["disabled"]', text="無効フラグ")
            else:
                box_editor.operator("myaddon.myaddon_ot_add_disabled", text="無効フラグを追加", icon='ADD')

            # コライダー調整
            if "collider" in active_obj:
                box_editor.separator()
                box_editor.label(text="コライダー設定:")
                box_editor.prop(active_obj, '["collider"]', text="形状")
                box_editor.prop(active_obj, '["collider_center"]', text="中心オフセット")
                box_editor.prop(active_obj, '["collider_size"]', text="サイズ")
            else:
                box_editor.operator("myaddon.myaddon_ot_add_collider", text="コライダーを追加", icon='ADD')
        else:
            box_editor.label(text="（調整するスポーンを選択してください）", icon='INFO')

        # --- ③ 視覚効果 (Visualization) ---
        box_vis = layout.box()
        box_vis.label(text="③ 視覚効果 (Visualization)", icon='RESTRICT_VIEW_OFF')
        box_vis.prop(scene, "godeye_show_heatmap", text="ヒートマップを表示")
        box_vis.prop(scene, "godeye_show_survival", text="生存ラインを表示")

        # --- ④ データ出力 (Export) ---
        box_export = layout.box()
        box_export.label(text="④ データ出力 (Export)", icon='EXPORT')
        box_export.operator("myaddon.myaddon_ot_export_scene", text="エクスポート")


class MYADDON_OT_add_area(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_area"
    bl_label = "エリア番号を追加"
    bl_description = "オブジェクトにエリア番号プロパティを追加します"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.active_object:
            context.active_object["area"] = 1
        return {"FINISHED"}
