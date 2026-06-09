import bpy

# -------------------------------------------------------
# オペレータ  無効オプション追加
# -------------------------------------------------------
class MYADDON_OT_add_disabled(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_disabled"
    bl_label = "無効オプション追加"
    bl_description = "オブジェクトに『無効』カスタムプロパティを追加します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 選択オブジェクトに 'disabled' カスタムプロパティを追加 (初期値 False)
        context.object["disabled"] = False
        print("'disabled' カスタムプロパティを追加しました")
        return {'FINISHED'}


# -------------------------------------------------------
# パネル  無効オプション
# -------------------------------------------------------
class OBJECT_PT_disabled(bpy.types.Panel):
    bl_idname = "OBJECT_PT_disabled"
    bl_label = "無効オプション"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    def draw(self, context):
        layout = self.layout
        obj = context.object

        # 'disabled' カスタムプロパティがあれば表示、なければ追加ボタンを表示
        if "disabled" in obj:
            # bool 型なのでチェックボックスとして表示される
            layout.prop(obj, '["disabled"]', text="無効 (Disabled)")
        else:
            layout.operator("myaddon.myaddon_ot_add_disabled")
