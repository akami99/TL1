import bpy

# ブレンダーに登録するアドオン情報
bl_info = {
    "name": "レベルエディタ",
    "author": "Ren Akamine",
    "version": (1, 0),
    "blender": (3, 3, 1),
    "location": "",
    "description": "レベルエディタ",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Object"
}

#アドオン有効化時コールバック
def register():
    print("レベルエディタが有効化されました。")

#アドオン無効化時コールバック
def unregister():
    print("レベルエディタが無効化されました。")

# テスト実行用コード
if __name__ == "__main__":
    register()