import bpy
import os
import json
from bpy_extras.io_utils import ExportHelper

class MYADDON_OT_new_scene(bpy.types.Operator, ExportHelper):
    bl_idname = "myaddon.myaddon_ot_new_scene"
    bl_label = "新規シーン作成"
    bl_description = "現在のシーンをクリアし、新規保存先ファイルを指定してまっさらなシーンを作成します"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        filepath = self.filepath
        if not filepath:
            self.report({'WARNING'}, "保存先ファイルが指定されていません")
            return {'CANCELLED'}

        print("新規シーン作成処理を開始します... 保存先: %r" % filepath)
        
        scene = context.scene

        # 1. ホットリロード自動保存を一時的に完全に停止（フラグでガード）
        from . import draw_heatmap
        
        # モジュールの _updating_godeye フラグを True にして、depsgraph_handler を抑止する
        draw_heatmap._updating_godeye = True
        
        try:
            # 2. 新しい保存先パスを設定（以前のパスをクリア）
            scene["godeye_last_export_path"] = filepath
            
            # 3. シーン内の一般オブジェクトをクリア (Prototypeオブジェクトは保護)
            for obj in list(scene.objects):
                if obj.name.startswith("Prototype"):
                    continue
                bpy.data.objects.remove(obj, do_unlink=True)
                
            # 4. シーン内プロパティのリセット
            scene.godeye_rail_curve = None
            scene["godeye_test_run_dist"] = 0.0
            scene.godeye_test_run_max_dist = 100.0  # 初期値
            
            # 5. キャッシュのリセット
            from .draw_heatmap import update_curve_cache
            update_curve_cache(None)
            
            # 6. まっさらなシーンの初期JSONデータを新規ファイルに保存
            init_data = {
                "name": "scene",
                "objects": []
            }
            
            # ディレクトリの作成
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(init_data, file, indent=4, ensure_ascii=False)
                
            print(f"[God Eye] New scene initialized at {filepath}")
            self.report({'INFO'}, "新規シーンを作成しました")
            
        except Exception as e:
            self.report({'ERROR'}, f"新規シーンの作成に失敗しました: {e}")
            return {'CANCELLED'}
        finally:
            # ガードフラグを戻す
            draw_heatmap._updating_godeye = False
            
        return {'FINISHED'}
