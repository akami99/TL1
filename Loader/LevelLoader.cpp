#include "LevelLoader.h"
#include <fstream>
#include <cassert>

const std::string LevelLoader::kDefaultBaseDirectory = "Resources/levels/";
const std::string LevelLoader::kExtension = ".json";

LevelData* LevelLoader::LoadFile(const std::string& fileName) {
	const std::string fullPath = kDefaultBaseDirectory + fileName + kExtension;

	std::ifstream file;
	file.open(fullPath);
	if (file.fail()) {
		assert(0 && "Failed to open level file.");
		return nullptr;
	}

	nlohmann::json deserialized;
	file >> deserialized;

	assert(deserialized.is_object());
	assert(deserialized.contains("name"));
	assert(deserialized["name"].get<std::string>() == "scene");

	LevelData* levelData = new LevelData();

	for (const auto& object : deserialized["objects"]) {
		assert(object.contains("type"));

		if (object.contains("disabled")) {
			bool disabled = object["disabled"].get<bool>();
			if (disabled) {
				continue;
			}
		}

		if (object.contains("spawn")) {
			const std::string spawnType = object["spawn"].get<std::string>();
			if (spawnType == "PLAYER") {
				levelData->players.emplace_back(LevelData::PlayerSpawnData{});
				LevelData::ObjectData temp{};
				ParseObject(temp, object);
				levelData->players.back().translation = temp.translation;
				levelData->players.back().rotation = temp.rotation;
				continue;
			}
		}

		levelData->objects.emplace_back(LevelData::ObjectData{});
		ParseObject(levelData->objects.back(), object);
	}

	return levelData;
}

void LevelLoader::ParseObject(LevelData::ObjectData& objectData, const nlohmann::json& jsonObject) {
	objectData.type = jsonObject["type"].get<std::string>();
	objectData.name = jsonObject["name"].get<std::string>();

	if (jsonObject.contains("file_name")) {
		objectData.fileName = jsonObject["file_name"].get<std::string>();
	}

	const auto& transform = jsonObject["transform"];

	objectData.translation.x = (float)transform["translation"][0];
	objectData.translation.y = (float)transform["translation"][2];
	objectData.translation.z = -(float)transform["translation"][1];

	float toRad = 3.1415926535f / 180.0f;
	objectData.rotation.x = (float)transform["rotation"][0] * toRad;
	objectData.rotation.y = -(float)transform["rotation"][2] * toRad;
	objectData.rotation.z = -(float)transform["rotation"][1] * toRad;

	objectData.scaling.x = (float)transform["scaling"][0];
	objectData.scaling.y = (float)transform["scaling"][2];
	objectData.scaling.z = (float)transform["scaling"][1];

	if (jsonObject.contains("children")) {
		for (const auto& child : jsonObject["children"]) {
			objectData.children.emplace_back(LevelData::ObjectData{});
			ParseObject(objectData.children.back(), child);
		}
	}
}
