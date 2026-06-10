#pragma once

#include <string>
#include <vector>
#include "MathTypes.h"
#include <json.hpp>

struct LevelData {
	struct ObjectData {
		std::string type;
		std::string name;
		std::string fileName;
		Vector3 translation;
		Vector3 rotation;
		Vector3 scaling;
		std::vector<ObjectData> children;
	};

	struct PlayerSpawnData {
		Vector3 translation;
		Vector3 rotation;
	};

	struct EnemySpawnData {
		std::string fileName;
		Vector3 translation;
		Vector3 rotation;
	};

	std::vector<ObjectData> objects;
	std::vector<PlayerSpawnData> players;
	std::vector<EnemySpawnData> enemies;
};

class LevelLoader {
public:
	static const std::string kDefaultBaseDirectory;
	static const std::string kExtension;

	static LevelData* LoadFile(const std::string& fileName);

private:
	static void ParseObject(LevelData::ObjectData& objectData, const nlohmann::json& jsonObject);
};
