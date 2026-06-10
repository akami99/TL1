#pragma once

#include "BaseScene.h"
#include <memory>
#include <vector>
#include "LevelLoader.h"
#include "Object3d.h"

class SampleGameScene : public BaseScene {
public:
	void Initialize() override;
	void Update() override;
	void Draw() override;
	void Finalize() override;

private:
	void CreateObjects(const std::vector<LevelData::ObjectData>& data);
	void CreatePlayerSpawns(const std::vector<LevelData::PlayerSpawnData>& data);
	void CreateEnemySpawns(const std::vector<LevelData::EnemySpawnData>& data);

private:
	std::unique_ptr<LevelData> levelData_;
	std::vector<std::unique_ptr<Object3d>> objects_;
	std::vector<std::unique_ptr<Object3d>> playerSpawnObjects_;
};
