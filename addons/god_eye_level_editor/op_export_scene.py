import bpy
import math
import bpy_extras
import json
import mathutils

# オペレータ シーン出力
class MYADDON_OT_export_scene(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    bl_idname = "myaddon.myaddon_ot_export_scene"
    bl_label = "シーン出力"
    bl_description = "シーン情報をExportします"
    # 出力するファイルの拡張子
    filename_ext = ".json"

    def write_and_print(self, file, str):
        print(str)

        file.write(str)
        file.write('\n')

    def parse_scene_recursive(self, file, object, level):
        """シーン解析用再帰関数"""

        # 深さ分インデントする (タブを挿入)
        indent = ''
        for i in range(level):
            indent += "\t"

        # オブジェクト名書き込み
        self.write_and_print(file, indent + object.type)
        trans, rot, scale = object.matrix_local.decompose()
        # 回転を Quaternion から Euler (3軸での回転角) に変換
        rot = rot.to_euler()
        # ラジアンから度数法に変換
        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)

        # トランスフォーム情報を表示
        self.write_and_print(file, indent + "T %f %f %f" % (trans.x, trans.y, trans.z) )
        self.write_and_print(file, indent + "R %f %f %f" % (rot.x, rot.y, rot.z) )
        self.write_and_print(file, indent + "S %f %f %f" % (scale.x, scale.y, scale.z) )
        # カスタムプロパティ'file_name'
        if "file_name" in object:
            self.write_and_print(file, indent + "N %s" % object["file_name"])

        # カスタムプロパティ'spawn'
        if "spawn" in object:
            self.write_and_print(file, indent + "SPAWN %s" % object["spawn"])

        # カスタムプロパティ'distance'
        if "distance" in object:
            self.write_and_print(file, indent + "D %f" % object["distance"])

        # カスタムプロパティ'area'
        if "area" in object:
            self.write_and_print(file, indent + "A %d" % object["area"])

        # カスタムプロパティ'collider'
        if "collider" in object:
            self.write_and_print(file, indent + "C %s" % object["collider"])
            temp_str = indent + "CC %f %f %f"
            temp_str %= (object["collider_center"][0], object["collider_center"][1], object["collider_center"][2])
            self.write_and_print(file, temp_str)
            temp_str = indent + "CS %f %f %f"
            temp_str %= (object["collider_size"][0], object["collider_size"][1], object["collider_size"][2])
            self.write_and_print(file, temp_str)

        self.write_and_print(file, indent + 'END')
        self.write_and_print(file, indent + '')

        # 子ノードへ進む(深さが1上がる)
        for child in object.children:
            self.parse_scene_recursive(file, child, level + 1)

    def export(self):
        """ファイルに出力"""

        print("シーン情報出力開始... %r" % self.filepath)

        # ファイルをテキスト形式で書き出し用にオープン
        # スコープを抜けると自動的にクローズされる
        with open(self.filepath, "wt") as file:

            # ファイルに文字列を書き込む
            file.write("SCENE\n")

            # シーン内の全オブジェクトについて
            for object in bpy.context.scene.objects:

                # 親オブジェクトがあるものはスキップ (代わりに親から呼び出すから)
                if (object.parent):
                    continue

                # プロトタイプオブジェクトはスキップ
                if object.name.startswith("Prototype"):
                    continue

                # シーン直下のオブジェクトをルートノード(深さ0)とし、再帰関数で走査
                self.parse_scene_recursive(file, object, 0)

    def parse_scene_recursive_json(self, data_parent, object, level):
        """シーン解析用再帰関数 (JSON版)"""

        # シーンのオブジェクト1個分のjsonオブジェクト生成
        json_object = dict()
        # オブジェクト種類
        json_object["type"] = object.type
        # オブジェクト名
        json_object["name"] = object.name

        # オブジェクトのローカルトランスフォームから
        # 平行移動、回転、スケールを抽出
        trans, rot, scale = object.matrix_local.decompose()

        # 回転を Quaternion から Euler (3軸での回転角) に変換
        rot = rot.to_euler()
        # ラジアンから度数法に変換
        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)
        # トランスフォーム情報をディクショナリに登録
        transform = dict()
        transform["translation"] = (trans.x, trans.y, trans.z)
        transform["rotation"] = (rot.x, rot.y, rot.z)
        transform["scaling"] = (scale.x, scale.y, scale.z)
        # まとめて1個分のjsonオブジェクトに登録
        json_object["transform"] = transform

        # カスタムプロパティ'無効オプション'
        if "disabled" in object:
            json_object["disabled"] = object["disabled"]

        # カスタムプロパティ'file_name'
        if "file_name" in object:
            json_object["file_name"] = object["file_name"]

        # カスタムプロパティ'spawn'
        if "spawn" in object:
            json_object["spawn"] = object["spawn"]

        # カスタムプロパティ'distance'
        if "distance" in object:
            json_object["distance"] = object["distance"]

        # カスタムプロパティ'area'
        if "area" in object:
            json_object["area"] = object["area"]
            if "end_distance" in object:
                json_object["end_distance"] = object["end_distance"]
            if "time_limit" in object:
                json_object["time_limit"] = object["time_limit"]

        # カスタムプロパティ'stop_point'
        if "stop_point" in object:
            json_object["stop_point"] = object["stop_point"]
            if "time_limit" in object:
                json_object["time_limit"] = object["time_limit"]

        # カスタムプロパティ'look_target'
        if "look_target" in object:
            json_object["look_target"] = object["look_target"]
            if "duration_distance" in object:
                json_object["duration_distance"] = object["duration_distance"]
            if "blend_distance" in object:
                json_object["blend_distance"] = object["blend_distance"]

        # カーブデータのエクスポート
        if object.type == 'CURVE':
            curve_data = object.data
            json_object["curve"] = dict()
            json_object["curve"]["dimensions"] = curve_data.dimensions
            json_object["curve"]["bevel_depth"] = curve_data.bevel_depth
            json_object["curve"]["splines"] = list()
            
            for spline in curve_data.splines:
                spline_data = dict()
                spline_data["type"] = spline.type
                spline_data["use_cyclic_u"] = spline.use_cyclic_u
                
                if spline.type == 'BEZIER':
                    points_list = []
                    for bp in spline.bezier_points:
                        pt = dict()
                        pt["co"] = (bp.co.x, bp.co.y, bp.co.z)
                        pt["handle_left"] = (bp.handle_left.x, bp.handle_left.y, bp.handle_left.z)
                        pt["handle_right"] = (bp.handle_right.x, bp.handle_right.y, bp.handle_right.z)
                        pt["handle_left_type"] = bp.handle_left_type
                        pt["handle_right_type"] = bp.handle_right_type
                        points_list.append(pt)
                    spline_data["bezier_points"] = points_list
                else:
                    points_list = []
                    for p in spline.points:
                        points_list.append((p.co.x, p.co.y, p.co.z, p.co.w))
                    spline_data["points"] = points_list
                    
                json_object["curve"]["splines"].append(spline_data)

        # カスタムプロパティ'collider'
        if "collider" in object:
            collider = dict()
            collider["type"] = object["collider"]
            collider["center"] = object["collider_center"].to_list()
            collider["size"] = object["collider_size"].to_list()
            json_object["collider"] = collider

        # 1個分のjsonオブジェクトを親オブジェクトに登録
        data_parent.append(json_object)

        # 直接の子供リストを走査
        if len(object.children) > 0:
            # 子ノードリストを作成
            json_object["children"] = list()
            # 子ノードへ進む(深さが1上がる)
            for child in object.children:
                self.parse_scene_recursive_json(json_object["children"], child, level + 1)

    def export_json(self):
        """JSON形式でファイルに出力"""

        # 保存する情報をまとめるdict
        json_object_root = dict()
        
        # ノード名
        json_object_root["name"] = "scene"
        # オブジェクトリストを作成
        json_object_root["objects"] = list()

        # シーン内の全オブジェクトについて
        for object in bpy.context.scene.objects:
            # 親オブジェクトがあるものはスキップ (代わりに親から呼び出すから)
            if (object.parent):
                continue
            
            # プロトタイプオブジェクトはスキップ
            if object.name.startswith("Prototype"):
                continue
            
            # シーン直下のオブジェクトをルートノード(深さ0)とし、再帰関数で走査
            self.parse_scene_recursive_json(json_object_root["objects"], object, 0)

        # エリア情報（交戦区間）を出力
        json_object_root["areas"] = [
            {
                "name": obj.name,
                "start_distance": obj.get("distance", 0.0),
                "end_distance": obj.get("end_distance", obj.get("distance", 0.0) + 30.0),
                "time_limit": obj.get("time_limit", 60.0),
            }
            for obj in bpy.context.scene.objects if obj.get("area")
        ]

        # 停止ポイントを出力
        json_object_root["stop_points"] = [
            {
                "name": obj.name,
                "distance": obj.get("distance", 0.0),
                "time_limit": obj.get("time_limit", 0.0),
            }
            for obj in bpy.context.scene.objects if obj.get("stop_point")
        ]

        # 注視ターゲットを出力
        json_object_root["look_targets"] = [
            {
                "name": obj.name,
                "distance": obj.get("distance", 0.0),
                "duration_distance": obj.get("duration_distance", 0.0),
                "blend_distance": obj.get("blend_distance", 3.0),
                "position": [obj.location.x, obj.location.y, obj.location.z],
            }
            for obj in bpy.context.scene.objects if obj.get("look_target")
        ]

        # オブジェクトをJSON文字列にエンコード (改行・インデント付き)
        json_text = json.dumps(json_object_root, ensure_ascii=False, cls=json.JSONEncoder, indent=4)
        # コンソールに表示してみる
        print(json_text)

        # ファイルをテキスト形式で書き出し用にオープン
        # スコープを抜けると自動的にクローズされる
        with open(self.filepath, "wt", encoding="utf-8") as file:
            # ファイルに文字列を書き込む
            file.write(json_text)

    def execute(self, context):
        print("シーン情報をExportします")

        # ファイルに出力
        self.export_json()

        # 直前のエクスポート先を保存してホットリロードに備える
        context.scene["godeye_last_export_path"] = self.filepath

        self.report({'INFO'}, "シーン情報をExportしました")

        return {'FINISHED'}
