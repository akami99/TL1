#include "LevelLoader.h"
#include <fstream>
#include <cassert>

// ディレクトリ定数の初期化
const std::string LevelLoader::kDefaultBaseDirectory = "Resources/levels/";
const std::string LevelLoader::kExtension = ".json";

LevelData* LevelLoader::LoadFile(const std::string& fileName) {
	// フルパスの構築
	const std::string fullPath = kDefaultBaseDirectory + fileName + kExtension;

	// ファイルを開く
	std::ifstream file;
	file.open(fullPath);
	if (file.fail()) {
		assert(0 && "Failed to open level file.");
		return nullptr;
	}

	// JSONデータをパース
	nlohmann::json deserialized;
	file >> deserialized;

	// シーンデータかチェック
	assert(deserialized.is_object());
	assert(deserialized.contains("name"));
	assert(deserialized["name"].get<std::string>() == "scene");

	// レベルデータコンテナを生成
	LevelData* levelData = new LevelData();

	// 全オブジェクトを走査
	for (const auto& object : deserialized["objects"]) {
		assert(object.contains("type"));

		// 無効フラグのチェック
		if (object.contains("disabled")) {
			bool disabled = object["disabled"].get<bool>();
			if (disabled) {
				// 配置しない（スキップ）
				continue;
			}
		}

		levelData->objects.emplace_back(LevelData::ObjectData{});
		ParseObject(levelData->objects.back(), object);
	}

	return levelData;
}

void LevelLoader::ParseObject(LevelData::ObjectData& objectData, const nlohmann::json& jsonObject) {
	// 基本情報のパース
	objectData.type = jsonObject["type"].get<std::string>();
	objectData.name = jsonObject["name"].get<std::string>();

	// MESHタイプ等のファイル名
	if (jsonObject.contains("file_name")) {
		objectData.fileName = jsonObject["file_name"].get<std::string>();
	}

	// トランスフォームの取得
	const auto& transform = jsonObject["transform"];

	// --- 座標系の変換 (Blender -> Engine) ---
	// Blender: 右手系, Z-Up
	// Engine:  左手系, Y-Up (DirectX標準)
	
	// Translation (X -> X, Z -> Y, Y -> Z)
	objectData.translation.x = (float)transform["translation"][0];
	objectData.translation.y = (float)transform["translation"][2];
	objectData.translation.z = (float)transform["translation"][1];

	// Rotation (度数法からラジアンへ変換し、符号を反転)
	float toRad = 3.1415926535f / 180.0f;
	objectData.rotation.x = -(float)transform["rotation"][0] * toRad;
	objectData.rotation.y = -(float)transform["rotation"][2] * toRad;
	objectData.rotation.z = -(float)transform["rotation"][1] * toRad;

	// Scaling (軸を入れ替え)
	objectData.scaling.x = (float)transform["scaling"][0];
	objectData.scaling.y = (float)transform["scaling"][2];
	objectData.scaling.z = (float)transform["scaling"][1];

	// --- 子要素の再帰パース ---
	if (jsonObject.contains("children")) {
		for (const auto& child : jsonObject["children"]) {
			objectData.children.emplace_back(LevelData::ObjectData{});
			ParseObject(objectData.children.back(), child);
		}
	}
}
