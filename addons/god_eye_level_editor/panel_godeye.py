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
        row_rail = box_setup.row(align=True)
        row_rail.prop(scene, "godeye_rail_curve", text="")
        row_rail.operator("myaddon.myaddon_ot_create_rail", text="作成", icon='ADD')

        rail_obj = scene.godeye_rail_curve
        if not rail_obj:
            box_setup.label(text="基準レールを設定してください。", icon='ERROR')
            return

        # キャッシュから安全に総延長距離を取得
        from .draw_heatmap import get_curve_cache
        cache = get_curve_cache()
        total_dist = cache["total_dist"] if cache["name"] == rail_obj.name else 0.0
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
            else:
                box_editor.operator("myaddon.myaddon_ot_add_distance", text="出現位置を追加", icon='ADD')
                
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
        box_vis.prop(scene, "godeye_show_fov", text="プレイヤー視野（FOV）を表示")

        # --- ④ テスト走行シミュレータ (Simulation) ---
        box_sim = layout.box()
        box_sim.label(text="④ テスト走行シミュレータ (Simulation)", icon='PLAY')
        rail_obj = scene.godeye_rail_curve
        if rail_obj:
            if "godeye_test_run_dist" not in scene:
                scene["godeye_test_run_dist"] = 0.0
            try:
                ui_api = scene.id_properties_ui("godeye_test_run_dist")
                ui_api.update(min=0.0, max=scene.godeye_test_run_max_dist, description="シミュレータ上の走行位置（m）")
            except Exception:
                pass
            box_sim.prop(scene, '["godeye_test_run_dist"]', text="走行位置 (m)", slider=True)
        else:
            box_sim.label(text="（基準レールを設定してください）")

        # --- ⑤ データ出力 (Export) ---
        box_export = layout.box()
        box_export.label(text="⑤ データ出力 (Export)", icon='EXPORT')
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


class MYADDON_OT_create_rail(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_create_rail"
    bl_label = "基準レールの作成"
    bl_description = "ベジェ曲線を生成し、太さを適用して基準レールに設定します"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.curve.primitive_bezier_curve_add(enter_editmode=False, align='WORLD', location=(0, 0, 0))
        rail = context.active_object
        rail.name = "EventRail"
        rail.data.name = "EventRailCurve"
        rail.data.dimensions = '3D'
        rail.data.bevel_depth = 0.2

        context.scene.godeye_rail_curve = rail

        from .draw_heatmap import trigger_cache_update
        trigger_cache_update(rail)

        return {"FINISHED"}


class MYADDON_OT_add_distance(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_distance"
    bl_label = "出現位置プロパティを追加"
    bl_description = "オブジェクトに出現位置プロパティを追加します"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.active_object:
            context.active_object["distance"] = 0.0
        return {"FINISHED"}


class MYADDON_OT_settings_dialog(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_settings_dialog"
    bl_label = "神サマ目線 設定"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 視覚効果
        box_vis = layout.box()
        box_vis.label(text="視覚効果表示 (Visualization)", icon='RESTRICT_VIEW_OFF')
        box_vis.prop(scene, "godeye_show_heatmap", text="ヒートマップを表示")
        box_vis.prop(scene, "godeye_show_survival", text="生存ラインを表示")
        box_vis.prop(scene, "godeye_show_fov", text="プレイヤー視野（FOV）を表示")

        # 交戦パラメータ
        box_param = layout.box()
        box_param.label(text="交戦・視野パラメータ (Parameters)", icon='PREFERENCES')
        box_param.prop(scene, "godeye_fov_angle", text="視野角（度）")
        box_param.prop(scene, "godeye_fov_range", text="視野射程（m）")
        box_param.prop(scene, "godeye_survival_length", text="生存ライン長さ（m）")

        # 自動保存
        box_save = layout.box()
        box_save.label(text="自動保存（ホットリロード）", icon='FILE')
        box_save.prop(scene, "godeye_enable_autosave", text="自動エクスポート有効化")
        box_save.prop(scene, "godeye_autosave_delay", text="自動保存遅延（秒）")

        # シミュレータ設定
        box_sim = layout.box()
        box_sim.label(text="シミュレータ設定", icon='PLAY')
        box_sim.prop(scene, "godeye_test_run_max_dist", text="テスト走行最大距離 (m)")

    def execute(self, context):
        # 設定が変更された際に再描画を促す
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)


class MYADDON_OT_help_dialog(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_help_dialog"
    bl_label = "神サマ目線 使い方ヘルプ"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        layout = self.layout

        box_step = layout.box()
        box_step.label(text="【基本操作手順】", icon='HELP')
        col = box_step.column(align=True)
        col.label(text="1. ① レール設定の「作成」で、進行経路（EventRail）を作成します。")
        col.label(text="2. ② イベント編集の「プレイヤー追加」「エネミー追加」でスポーンを配置します。")
        col.label(text="3. 配置したスポーンを選択し、3D移動またはNパネルの「出現位置(m)」で位置を調整します。")
        col.label(text="4. オブジェクトごとにカスタムプロパティ（area, disabled, コライダー等）を設定します。")
        col.label(text="5. ④ テスト走行シミュレータのスライダーを動かし、出現順や視野をプレビューします。")
        col.label(text="6. ⑤ データ出力の「エクスポート」で保存します。")
        col.label(text="   ※保存後は自動的にホットリロード（自動保存）が有効になります。")

        box_vis = layout.box()
        box_vis.label(text="【視覚効果（ヒートマップ）】", icon='RESTRICT_VIEW_OFF')
        col_vis = box_vis.column(align=True)
        col_vis.label(text="・ヒートマップ: 敵の密度を色で表示 (青: 安全, 黄: 敵1, 赤: 激戦区)")
        col_vis.label(text="・生存ライン: 敵の出現点から進行方向への想定交戦ルート (緑色の線)")
        col_vis.label(text="・プレイヤー視野 (FOV): プレイヤーの視界範囲を扇型で可視化")

        box_spec = layout.box()
        box_spec.label(text="【仕様】", icon='INFO')
        col_spec = box_spec.column(align=True)
        col_spec.label(text="・エネミーの3D座標と出現位置（distance）は連動しません。自由な場所に配置できます。")
        col_spec.label(text="・エネミーの位置・回転は、そのままワールド座標としてJSONに出力されます。")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=550)
